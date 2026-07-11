use std::cell::RefCell;
use std::collections::HashSet;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::Path;
use std::rc::Rc;
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

use game_view::{ClientDatabase, MatchUIRunner};
use mod_api::MatchType;
use mod_api::*;

const MOD_ID: &str = "lol_mod";
const DRAGON_SEED_EVENT: &str = "dragon_variant_seed";
const DRAGON_EVENT_VERSION: &str = "v1";
const DRAGON_TELEMETRY_ENV: &str = "LOL_QA_DRAGON_VARIANT_TELEMETRY";
const DRAGON_TELEMETRY_PATH: &str =
    "ModData/lol_mod/quality_dragon_variant_runtime_telemetry.tsv";
const PICK_SLOT_LIMIT: usize = 5;
const SPLASH_NODES: [(&str, &str); 5] = [
    ("lol_shen", "lol_splash_shen"),
    ("archer", "lol_splash_lucian"),
    ("barrier_magician", "lol_splash_orianna"),
    ("berserker", "lol_splash_briar"),
    ("boomerang_hunter", "lol_splash_sivir"),
];

// EntityView::view_name is relative to
// asset/base/aseprite_resources/ingame/. Elder is intentionally excluded:
// this feature selects one base elemental drake for the whole match.
const DRAGON_VIEW_NAMES: [&str; 5] = [
    "dragon_variants/infernal",
    "dragon_variants/ocean",
    "dragon_variants/mountain",
    "dragon_variants/cloud",
    "dragon_variants/hextech",
];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum DragonSeedSource {
    LiveServerEvent,
    Replay,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct DragonSelection {
    running_id: usize,
    set: usize,
    seed: u64,
    source: DragonSeedSource,
}

#[derive(Default)]
struct ClientDragonState {
    database: Option<Rc<RefCell<ClientDatabase>>>,
    live_selection: Option<DragonSelection>,
    seen_payloads: HashSet<Vec<u8>>,
    last_applied: Option<DragonSelection>,
    fallback_logged: bool,
}

thread_local! {
    // ModExtension is Send + Sync, while ClientDatabase is an Rc. Keeping the
    // handle thread-local guarantees it never crosses threads; callbacks on a
    // different thread simply use the conservative default dragon.
    static CLIENT_DRAGON_STATE: RefCell<ClientDragonState> =
        RefCell::new(ClientDragonState::default());
}

static DRAGON_TELEMETRY_LOCK: Mutex<()> = Mutex::new(());

struct LolModExtension;

impl ModExtension for LolModExtension {
    fn post_update(&self, _scene: &mut Scene, ui: &mut GameUI, _assets: &mut Assets, _dt: f32) {
        // MatchUIRunner owns both the authoritative pick order and the public
        // ClientDatabase handle. Clone them before mutating the UI tree.
        let snapshot = match_ui_snapshot(&mut ui.root);

        if let Some(snapshot) = snapshot {
            remember_database(snapshot.database);
            sync_side(&mut ui.root, "blue", &snapshot.blue_picks);
            sync_side(&mut ui.root, "red", &snapshot.red_picks);
        } else {
            sync_encyclopedia_portraits(&mut ui.root);
        }

        sync_deterministic_dragon();
    }
}

struct MatchUiSnapshot {
    blue_picks: Vec<String>,
    red_picks: Vec<String>,
    database: Rc<RefCell<ClientDatabase>>,
}

fn snapshot_from_runner(runner: &mut MatchUIRunner) -> MatchUiSnapshot {
    MatchUiSnapshot {
        blue_picks: picks_by_roster_slot(&runner.team1_pick, &runner.team1_order),
        red_picks: picks_by_roster_slot(&runner.team2_pick, &runner.team2_order),
        database: runner.database.clone(),
    }
}

fn picks_by_roster_slot(picks: &[String], order: &[usize]) -> Vec<String> {
    // Picks are stored in draft order, while pick_slot_N is a roster slot.
    // team*_order records the roster slot assigned to each drafted champion.
    // Fall back to the original order for partial/legacy SDK fixtures.
    if picks.is_empty() || order.len() != picks.len() {
        return picks.to_vec();
    }

    let output_len = PICK_SLOT_LIMIT.max(picks.len());
    let mut output = vec![String::new(); output_len];
    let mut occupied = vec![false; output_len];
    for (draft_index, &slot_index) in order.iter().enumerate() {
        if slot_index >= output_len || occupied[slot_index] {
            return picks.to_vec();
        }
        output[slot_index] = picks[draft_index].clone();
        occupied[slot_index] = true;
    }
    output
}

fn match_ui_snapshot(root: &mut Node) -> Option<MatchUiSnapshot> {
    if let Some(runner) = root.runner_as_mut::<MatchUIRunner>() {
        return Some(snapshot_from_runner(runner));
    }

    // Match UI can be wrapped by one or more scene/overlay roots before it is
    // handed to a mod extension.  The wrapper depth also changes between the
    // normal draft, spectator draft, and post-swap refresh.  Search the real
    // Node tree instead of assuming either `root` or `root.main` owns the
    // runner.
    for child in &mut root.child {
        if let Some(snapshot) = match_ui_snapshot(child) {
            return Some(snapshot);
        }
    }
    None
}

fn remember_database(database: Rc<RefCell<ClientDatabase>>) {
    CLIENT_DRAGON_STATE.with(|state| {
        let mut state = state.borrow_mut();
        let changed = state
            .database
            .as_ref()
            .is_none_or(|current| !Rc::ptr_eq(current, &database));
        if changed {
            state.database = Some(database);
            state.live_selection = None;
            state.seen_payloads.clear();
            state.last_applied = None;
            state.fallback_logged = false;
        }
    });
}

fn sync_deterministic_dragon() {
    CLIENT_DRAGON_STATE.with(|state| {
        let database = {
            let state = state.borrow();
            state.database.clone()
        };
        let Some(database) = database else {
            return;
        };

        let mut database = database.borrow_mut();
        let events = database.mod_events(MOD_ID);

        {
            let mut state = state.borrow_mut();
            for event in events {
                if event.event != DRAGON_SEED_EVENT
                    || !state.seen_payloads.insert(event.payload.clone())
                {
                    continue;
                }
                if let Some(selection) = parse_dragon_seed_event(&event.payload) {
                    state.live_selection = Some(selection);
                    state.fallback_logged = false;
                    write_dragon_telemetry("client_event", selection, "authoritative server seed");
                }
            }
        }

        // Replays derive directly from serialized replay data. If replay data
        // is not available yet, never leak a prior live match's selection.
        let replay_mode = database.replay_view.is_some();
        let replay_selection = database.replay_view.as_ref().and_then(|current| {
            let running_id = match_type_id(current);
            database
                .match_replays
                .get(&running_id)
                .map(|replay| DragonSelection {
                    running_id,
                    set: 0,
                    seed: replay.seed,
                    source: DragonSeedSource::Replay,
                })
        });
        let selection = if replay_mode {
            replay_selection
        } else {
            state.borrow().live_selection
        };
        let view_name = selection
            .map(|selected| DRAGON_VIEW_NAMES[dragon_variant_index(selected.seed)])
            .unwrap_or("serpen");

        if let Some(game) = database.game_view.as_mut() {
            for entity in game.client.view.entity_view.values_mut() {
                if entity.name == "serpen" && entity.view_name != view_name {
                    entity.view_name.clear();
                    entity.view_name.push_str(view_name);
                }
            }
        }

        let mut state = state.borrow_mut();
        if let Some(selection) = selection {
            if state.last_applied != Some(selection) {
                let detail = format!(
                    "view_name={}",
                    DRAGON_VIEW_NAMES[dragon_variant_index(selection.seed)]
                );
                write_dragon_telemetry("entity_apply", selection, &detail);
                state.last_applied = Some(selection);
                state.fallback_logged = false;
            }
        } else if !state.fallback_logged {
            write_dragon_fallback_telemetry(if replay_mode {
                "replay seed unavailable; retained default serpen"
            } else {
                "server seed event unavailable; retained default serpen"
            });
            state.last_applied = None;
            state.fallback_logged = true;
        }
    });
}

fn parse_dragon_seed_event(payload: &[u8]) -> Option<DragonSelection> {
    let text = std::str::from_utf8(payload).ok()?;
    let mut fields = text.split(':');
    if fields.next()? != DRAGON_EVENT_VERSION {
        return None;
    }
    let selection = DragonSelection {
        running_id: fields.next()?.parse().ok()?,
        set: fields.next()?.parse().ok()?,
        seed: fields.next()?.parse().ok()?,
        source: DragonSeedSource::LiveServerEvent,
    };
    fields.next().is_none().then_some(selection)
}

fn match_type_id(value: &MatchType) -> usize {
    match value {
        MatchType::Tutorial { match_id }
        | MatchType::Normal { match_id }
        | MatchType::Practice { match_id }
        | MatchType::SoloRank { match_id } => *match_id,
    }
}

fn dragon_variant_index(seed: u64) -> usize {
    // SplitMix64 gives a stable, platform-independent result from the match
    // seed without process randomness or mutable global RNG state.
    let mut value = seed.wrapping_add(0x9e37_79b9_7f4a_7c15);
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    ((value ^ (value >> 31)) % DRAGON_VIEW_NAMES.len() as u64) as usize
}

struct LolDragonServerExtension {
    announced: Mutex<HashSet<(usize, usize, u64)>>,
}

impl ModServerExtension for LolDragonServerExtension {
    fn after_management_tick(&self, ctx: &mut ServerModContext) {
        let mut pending = Vec::new();
        if let Ok(mut announced) = self.announced.lock() {
            for (running_id, info) in &ctx.server_state.running_matches {
                let Some(snapshot) = info.running_game.as_ref() else {
                    continue;
                };
                let key = (*running_id, snapshot.set, snapshot.seed);
                if announced.insert(key) {
                    pending.push((
                        info.team1,
                        info.team2,
                        *running_id,
                        snapshot.set,
                        snapshot.seed,
                    ));
                }
            }
        }

        // Target the two participants separately so concurrent/hidden matches
        // cannot overwrite another match's visual selection.
        for (blue, red, running_id, set, seed) in pending {
            let payload = format!("{DRAGON_EVENT_VERSION}:{running_id}:{set}:{seed}");
            ctx.emit_event_to_team(blue, DRAGON_SEED_EVENT, payload.as_str());
            ctx.emit_event_to_team(red, DRAGON_SEED_EVENT, payload.as_str());
            let selection = DragonSelection {
                running_id,
                set,
                seed,
                source: DragonSeedSource::LiveServerEvent,
            };
            write_dragon_telemetry("server_select", selection, "sent to both teams");
        }
    }
}

fn dragon_telemetry_enabled() -> bool {
    std::env::var(DRAGON_TELEMETRY_ENV).is_ok_and(|value| value == "1")
}

fn write_dragon_telemetry(origin: &str, selection: DragonSelection, detail: &str) {
    if !dragon_telemetry_enabled() {
        return;
    }
    let index = dragon_variant_index(selection.seed);
    let source = match selection.source {
        DragonSeedSource::LiveServerEvent => "live",
        DragonSeedSource::Replay => "replay",
    };
    append_dragon_telemetry(&format!(
        "{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}:{}",
        unix_millis(),
        origin,
        selection.running_id,
        selection.set,
        selection.seed,
        index,
        DRAGON_VIEW_NAMES[index],
        source,
        sanitize_telemetry(detail)
    ));
}

fn write_dragon_fallback_telemetry(detail: &str) {
    if dragon_telemetry_enabled() {
        append_dragon_telemetry(&format!(
            "{}\tfallback\t0\t0\t0\t-1\tserpen\t{}",
            unix_millis(),
            sanitize_telemetry(detail)
        ));
    }
}

fn append_dragon_telemetry(row: &str) {
    let Ok(_guard) = DRAGON_TELEMETRY_LOCK.lock() else {
        return;
    };
    let path = Path::new(DRAGON_TELEMETRY_PATH);
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let new_file = !path.exists();
    let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) else {
        return;
    };
    if new_file {
        let _ = writeln!(
            file,
            "unix_ms\torigin\trunning_id\tset\tseed\tvariant_index\tview_name\tdetail"
        );
    }
    let _ = writeln!(file, "{row}");
}

fn sanitize_telemetry(value: &str) -> String {
    value.replace(['\t', '\r', '\n'], " ")
}

fn unix_millis() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |duration| duration.as_millis())
}

fn sync_encyclopedia_portraits(root: &mut Node) {
    for (champion_id, portrait_node) in [
        ("lol_shen", "lol_fullbody_shen"),
        ("archer", "lol_fullbody_lucian"),
        ("barrier_magician", "lol_fullbody_orianna"),
        ("berserker", "lol_fullbody_briar"),
        ("boomerang_hunter", "lol_fullbody_sivir"),
    ] {
        // The live encyclopedia is nested below
        // main.top.right.champion_info; keep the shorter path for SDK fixtures.
        for prefix in [
            format!("data.champions.contents.{champion_id}"),
            format!("top.right.champion_info.data.champions.contents.{champion_id}"),
        ] {
            set_visible(root, &format!("{prefix}.icon"), false);
            set_visible(root, &format!("{prefix}.{portrait_node}"), true);
        }
    }
}

fn sync_side(root: &mut Node, side: &str, picks: &[String]) {
    for slot_index in 0..PICK_SLOT_LIMIT {
        sync_slot(
            root,
            side,
            slot_index,
            picks.get(slot_index).map(String::as_str),
        );
    }
}

fn sync_slot(root: &mut Node, side: &str, slot_index: usize, champion: Option<&str>) {
    let supported = champion.filter(|selected| {
        SPLASH_NODES
            .iter()
            .any(|(champion_id, _)| champion_id == selected)
    });
    let prefix = format!("{side}_picks.pick_slot_{slot_index}.done");

    // Preserve the game's actor portrait for every champion we do not own.
    // Hide the entire actor container for supported champions so a runner that
    // refreshes the child icon cannot paint it back over the splash image.
    set_visible(
        root,
        &format!("{prefix}.champion"),
        supported.is_none(),
    );
    set_visible(
        root,
        &format!("{prefix}.champion.icon"),
        supported.is_none(),
    );

    for (champion_id, node_id) in SPLASH_NODES {
        set_visible(
            root,
            &format!("{prefix}.{node_id}"),
            supported == Some(champion_id),
        );
    }
}

fn set_visible(root: &mut Node, query: &str, visible: bool) {
    if let Some(node) = root.query_mut(query) {
        node.visible = visible;
        return;
    }

    // A GameUI root is not guaranteed to be the root declared by the loaded
    // .ui file.  Find the first path component (blue_picks, red_picks, data,
    // top, ...) at any depth, then let Node::query_mut traverse the stable
    // path below that component.  This survives the live scene wrappers and
    // BP overlay rebuilds without depending on a hard-coded `main` depth.
    if let Some(node) = query_anywhere_mut(root, query) {
        node.visible = visible;
    }
}

fn query_anywhere_mut<'a>(root: &'a mut Node, query: &str) -> Option<&'a mut Node> {
    let (anchor_id, relative_query) = query.split_once('.').unwrap_or((query, ""));
    find_path_anchor_mut(root, anchor_id, relative_query)
}

fn find_path_anchor_mut<'a>(
    root: &'a mut Node,
    anchor_id: &str,
    relative_query: &str,
) -> Option<&'a mut Node> {
    if root.id == anchor_id {
        if relative_query.is_empty() {
            return Some(root);
        }
        // There can be more than one cached/overlay container with the same
        // id.  Only accept an anchor that actually owns the requested path;
        // otherwise continue the DFS to the next matching container.
        if root.query(relative_query).is_some() {
            return root.query_mut(relative_query);
        }
    }
    for child in &mut root.child {
        if let Some(found) = find_path_anchor_mut(child, anchor_id, relative_query) {
            return Some(found);
        }
    }
    None
}

fn init(_ctx: &GameCtx) -> ModRegistration {
    let mut registration = ModRegistration::new(MOD_ID);
    registration.set_extension(LolModExtension);
    registration.set_server_extension(LolDragonServerExtension {
        announced: Mutex::new(HashSet::new()),
    });
    registration
}

declare_mod!(init);
