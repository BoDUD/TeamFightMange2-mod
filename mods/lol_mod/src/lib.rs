use std::cell::RefCell;
use std::collections::HashSet;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::Path;
use std::rc::Rc;
use std::sync::{Mutex, OnceLock};
use std::time::{SystemTime, UNIX_EPOCH};

use engine_core::render_state::RenderCommand;
use game_view::{ClientDatabase, MatchUIRunner};
use mod_api::MatchType;
use mod_api::*;

const MOD_ID: &str = "lol_mod";
const DRAGON_SEED_EVENT: &str = "dragon_variant_seed";
const DRAGON_EVENT_VERSION: &str = "v1";
const DRAGON_TELEMETRY_ENV: &str = "LOL_QA_DRAGON_VARIANT_TELEMETRY";
const DRAGON_TELEMETRY_PATH: &str = "ModData/lol_mod/quality_dragon_variant_runtime_telemetry.tsv";
const BP_TELEMETRY_PATH: &str = "ModData/lol_mod/quality_bp_runtime_telemetry.tsv";
const BP_TELEMETRY_ROW_LIMIT: usize = 80;
const PICK_SLOT_LIMIT: usize = 5;
const SPLASH_SPECS: [(&str, &str); 5] = [
    ("lol_shen", "asset/lol_mod/BanPickIllust/lol_shen"),
    ("archer", "asset/lol_mod/BanPickIllust/archer"),
    (
        "barrier_magician",
        "asset/lol_mod/BanPickIllust/barrier_magician",
    ),
    ("berserker", "asset/lol_mod/BanPickIllust/berserker"),
    (
        "boomerang_hunter",
        "asset/lol_mod/BanPickIllust/boomerang_hunter",
    ),
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
static BP_TELEMETRY_LOCK: Mutex<()> = Mutex::new(());
static BP_TELEMETRY_SEEN: OnceLock<Mutex<HashSet<String>>> = OnceLock::new();

struct LolModExtension;

impl ModExtension for LolModExtension {
    fn post_update(&self, _scene: &mut Scene, ui: &mut GameUI, _assets: &mut Assets, _dt: f32) {
        if let Some(database) = match_ui_database(ui) {
            remember_database(database);
        } else {
            sync_encyclopedia_portraits(&mut ui.root);
        }

        sync_deterministic_dragon();
    }

    fn post_render(&self, _scene: &Scene, ui: &GameUI, _assets: &Assets, state: &mut RenderState) {
        rewrite_bp_render_commands(ui, state);
    }
}

fn match_ui_database(ui: &mut GameUI) -> Option<Rc<RefCell<ClientDatabase>>> {
    if let Some(database) = ui
        .query_mut("main")
        .and_then(|main| main.runner_as_mut::<MatchUIRunner>())
        .map(|runner| runner.database.clone())
    {
        return Some(database);
    }
    match_ui_database_from_node(&mut ui.root)
}

fn match_ui_database_from_node(root: &mut Node) -> Option<Rc<RefCell<ClientDatabase>>> {
    if let Some(runner) = root.runner_as_mut::<MatchUIRunner>() {
        return Some(runner.database.clone());
    }
    for child in &mut root.child {
        if let Some(database) = match_ui_database_from_node(child) {
            return Some(database);
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

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum BpRenderSide {
    Blue,
    Red,
}

impl BpRenderSide {
    fn as_str(self) -> &'static str {
        match self {
            Self::Blue => "blue",
            Self::Red => "red",
        }
    }
}

fn rewrite_bp_render_commands(ui: &GameUI, state: &mut RenderState) {
    // The reference mod uses `main.header.bp_settings` as its BP-page marker.
    // Our minimal layout intentionally has no settings button, so the native
    // blue/red pick containers are the equivalent scene guard.
    let bp_ui_found = ui.query("main.blue_picks").is_some() || ui.query("main.red_picks").is_some();
    let command_count: usize = state.commands.values().map(Vec::len).sum();
    write_bp_render_telemetry_once(
        "scan",
        "",
        None,
        "",
        "",
        &format!(
            "bp_ui_found={bp_ui_found};passes={};commands={command_count}",
            state.commands.len()
        ),
    );
    if !bp_ui_found {
        return;
    }

    for (pass, commands) in &mut state.commands {
        let map_width = state
            .map_size
            .get(pass)
            .map(|(width, _)| *width)
            .unwrap_or(1920.0);
        for command in commands {
            let RenderCommand::NinePatch {
                texture,
                texture_rect,
                x,
                y,
                w,
                h,
                z,
                rot,
                left,
                right,
                top,
                bottom,
                pivot_x,
                pivot_y,
                skew_x,
                sample_nearest,
                flip_x,
                flip_y,
                ..
            } = command
            else {
                continue;
            };

            let Some(champion_id) = splash_id_from_source(texture) else {
                continue;
            };
            let Some(side) = bp_side_from_geometry(*x, *y, *h, map_width) else {
                write_bp_render_telemetry_once(
                    "candidate_skip",
                    "",
                    None,
                    texture,
                    "",
                    &format!(
                        "champion={champion_id};pass={pass};map_width={map_width:.1};geometry={x:.1},{y:.1},{w:.1},{h:.1}"
                    ),
                );
                continue;
            };
            let Some(slot_index) = bp_slot_from_geometry(*y, *h) else {
                continue;
            };
            let Some(asset) = splash_asset(champion_id) else {
                continue;
            };

            let original_texture = texture.clone();
            let original_geometry = (*x, *y, *w, *h);
            *texture = asset.to_owned();
            texture_rect.x = 0.0;
            texture_rect.y = 0.0;
            texture_rect.w = 1420.0;
            texture_rect.h = 860.0;
            *x = match side {
                BpRenderSide::Blue => original_geometry.0 - 145.0,
                BpRenderSide::Red => original_geometry.0 - 6.0,
            };
            // BVP's own 50px-header layout maps native icon y=50 to overlay
            // y=61. Our game keeps the stock 97px header, so preserve the same
            // +11px card-relative offset instead of incorrectly forcing y=61.
            *y = original_geometry.1 + 11.0;
            *w = 284.0;
            *h = 172.0;
            *z = 200;
            *rot = 0.0;
            *left = 0.0;
            *right = 0.0;
            *top = 0.0;
            *bottom = 0.0;
            *pivot_x = 0.0;
            *pivot_y = 0.0;
            *skew_x = 0.0;
            *sample_nearest = false;
            *flip_x = side == BpRenderSide::Red;
            *flip_y = false;

            write_bp_render_telemetry_once(
                "rewrite",
                side.as_str(),
                Some(slot_index),
                &original_texture,
                asset,
                &format!(
                    "champion={champion_id};pass={pass};map_width={map_width:.1};from={:.1},{:.1},{:.1},{:.1};to={:.1},{:.1},284,172;flip_x={}",
                    original_geometry.0,
                    original_geometry.1,
                    original_geometry.2,
                    original_geometry.3,
                    *x,
                    *y,
                    *flip_x,
                ),
            );
        }
    }
}

fn bp_side_from_geometry(x: f32, y: f32, height: f32, map_width: f32) -> Option<BpRenderSide> {
    if !(40.0..=960.0).contains(&y) || !(100.0..=250.0).contains(&height) {
        return None;
    }
    // BVP's absolute 1585..2100 red range assumes a 1920-wide render map.
    // The game can render BP at narrower widths (for example 1618px), so keep
    // the same 335px edge band relative to the active render pass instead.
    let right_edge_start = (map_width - 335.0).max(335.0);
    if (0.0..=335.0).contains(&x) {
        Some(BpRenderSide::Blue)
    } else if (right_edge_start..=(map_width + 180.0)).contains(&x) {
        Some(BpRenderSide::Red)
    } else {
        None
    }
}

fn bp_slot_from_geometry(y: f32, height: f32) -> Option<usize> {
    let raw = ((y + height * 0.5 - 60.0) / 188.0).floor();
    if raw < 0.0 {
        return None;
    }
    let slot = raw as usize;
    (slot < PICK_SLOT_LIMIT).then_some(slot)
}

fn splash_asset(champion_id: &str) -> Option<&'static str> {
    SPLASH_SPECS
        .iter()
        .find(|(candidate, _)| *candidate == champion_id)
        .map(|(_, asset)| *asset)
}

fn splash_id_from_source(source: &str) -> Option<&'static str> {
    // Mirror Ban/Pick View Plus exactly: find the first `/champions/` marker,
    // keep the entire suffix, and only strip a terminal `#sheet`. The aliases
    // below bridge our visual atlas names to the stable champion data ids.
    let marker = "/champions/";
    let marker_end = source.find(marker)? + marker.len();
    let key = source[marker_end..]
        .strip_suffix("#sheet")
        .unwrap_or(&source[marker_end..]);
    match key {
        "shen" | "lol_shen" => Some("lol_shen"),
        "lucian" | "archer" => Some("archer"),
        "orianna" | "barrier_magician" => Some("barrier_magician"),
        "briar" | "berserker" => Some("berserker"),
        "sivir" | "boomerang_hunter" => Some("boomerang_hunter"),
        _ => None,
    }
}

fn write_bp_render_telemetry_once(
    event: &str,
    side: &str,
    slot_index: Option<usize>,
    source: &str,
    target: &str,
    detail: &str,
) {
    let signature = format!("{event}\t{side}\t{slot_index:?}\t{source}\t{target}\t{detail}");
    let seen = BP_TELEMETRY_SEEN.get_or_init(|| Mutex::new(HashSet::new()));
    let Ok(mut seen) = seen.lock() else {
        return;
    };
    if seen.len() >= BP_TELEMETRY_ROW_LIMIT || !seen.insert(signature) {
        return;
    }
    drop(seen);

    let Ok(_guard) = BP_TELEMETRY_LOCK.lock() else {
        return;
    };
    let path = Path::new(BP_TELEMETRY_PATH);
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let new_file = !path.exists();
    let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) else {
        return;
    };
    if new_file {
        let _ = writeln!(file, "unix_ms\tevent\tside\tslot\tsource\ttarget\tdetail");
    }
    let _ = writeln!(
        file,
        "{}\t{}\t{}\t{}\t{}\t{}\t{}",
        unix_millis(),
        sanitize_telemetry(event),
        sanitize_telemetry(side),
        slot_index.map_or_else(String::new, |slot| slot.to_string()),
        sanitize_telemetry(source),
        sanitize_telemetry(target),
        sanitize_telemetry(detail),
    );
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
