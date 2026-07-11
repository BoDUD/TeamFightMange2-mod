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
const BP_CARD_WIDTH: f32 = 284.0;
const BP_CARD_HEIGHT: f32 = 172.0;
const BP_CARD_EDGE_INSET: f32 = 15.0;
const BP_CARD_TOP: f32 = 98.0;
const BP_CARD_STEP_Y: f32 = 188.0;
const BP_NATIVE_ACTOR_WIDTH: f32 = 137.0;
const BP_NATIVE_ACTOR_HEIGHT: f32 = 184.0;
const BP_NATIVE_ACTOR_BLUE_X: f32 = 160.0;
const BP_NATIVE_ACTOR_RED_INSET: f32 = 294.0;
const BP_NATIVE_ACTOR_TOP: f32 = 87.0;
// The native pick-complete animation briefly scales the 137x184 actor down to
// roughly 125x147 and starts the red-side slide at x ~= 1579 on a 1920-wide
// pass.  Keep this transition band wider than the settled card band, while
// the actor-size gate below excludes 128x128 champion-grid thumbnails.
const BP_RED_TRANSITION_EDGE_BAND: f32 = 430.0;
const BP_TRANSITION_ACTOR_MIN_WIDTH: f32 = 120.0;
const BP_TRANSITION_ACTOR_MAX_WIDTH: f32 = 140.0;
const BP_TRANSITION_ACTOR_MIN_HEIGHT: f32 = 140.0;
const BP_TRANSITION_ACTOR_MAX_HEIGHT: f32 = 190.0;
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

    fn candidate_index(self, slot_index: usize) -> usize {
        let side_offset = match self {
            Self::Blue => 0,
            Self::Red => PICK_SLOT_LIMIT,
        };
        side_offset + slot_index
    }
}

struct BpOverlayCandidate {
    score: f32,
    side: BpRenderSide,
    slot_index: usize,
    champion_id: &'static str,
    asset: &'static str,
    original_texture: String,
    original_geometry: (f32, f32, f32, f32),
    overlay: RenderCommand,
    route: &'static str,
}

fn rewrite_bp_render_commands(ui: &GameUI, state: &mut RenderState) {
    // The native layout root is `main:match_ui`, so GameUI queries are relative
    // (`blue_picks`, not `main.blue_picks`). Ban/Pick View Plus also identifies
    // the concrete side and slot from RenderState pass keys. Prefer that exact
    // route, with relative UI + geometry only as a compatibility fallback.
    let queried_blue = ui.query("blue_picks").is_some();
    let queried_red = ui.query("red_picks").is_some();
    let queried_delegate =
        ui.query("header.delegate_btn").is_some() || ui.query("main.header.delegate_btn").is_some();
    let tree_blue = ui_tree_contains_id(&ui.root, "blue_picks");
    let tree_red = ui_tree_contains_id(&ui.root, "red_picks");
    let matched_passes = state
        .commands
        .keys()
        .filter(|pass| bp_identity_from_pass(pass).is_some())
        .count();
    let bp_ui_found = queried_blue
        || queried_red
        || queried_delegate
        || tree_blue
        || tree_red
        || matched_passes > 0;
    if !bp_ui_found {
        return;
    }
    write_bp_render_telemetry_once(
        "scan",
        "",
        None,
        "",
        "",
        &format!(
            "version=0.7.9;root={};queried_blue={queried_blue};queried_red={queried_red};queried_delegate={queried_delegate};tree_blue={tree_blue};tree_red={tree_red};matched_passes={matched_passes};passes={}",
            ui.root.id,
            state.commands.len(),
        ),
    );

    for (pass, commands) in &mut state.commands {
        let pass_identity = bp_identity_from_pass(pass);
        let map_width = state
            .map_size
            .get(pass)
            .map(|(width, _)| *width)
            .unwrap_or(1920.0);
        // BP actor commands animate their x/y/w/h while picks slide into a
        // card. Illustrations are card backgrounds, so they must stay locked
        // to the side + slot instead of inheriting that transition geometry.
        // Keep only the command closest to the native settled actor rectangle
        // when a transition emits more than one candidate for the same slot.
        let mut candidates: Vec<Option<BpOverlayCandidate>> =
            (0..PICK_SLOT_LIMIT * 2).map(|_| None).collect();
        let mut original_actor_indices = Vec::new();
        let mut original_actor_counts = [0usize; PICK_SLOT_LIMIT * 2];
        for (command_index, command) in commands.iter().enumerate() {
            let RenderCommand::NinePatch {
                texture,
                x,
                y,
                w,
                h,
                ..
            } = command
            else {
                continue;
            };

            let Some(champion_id) = splash_id_from_source(texture) else {
                if pass_identity.is_some() && texture.contains("/champions/") {
                    write_bp_render_telemetry_once(
                        "texture_skip",
                        "",
                        None,
                        texture,
                        "",
                        &format!("pass={pass};map_width={map_width:.1}"),
                    );
                }
                continue;
            };
            let geometry_identity = || {
                let side = bp_side_from_geometry(*x, *y, *w, *h, map_width)?;
                let slot = bp_slot_from_geometry(*y, *h)?;
                Some((side, slot))
            };
            let Some((side, slot_index)) = pass_identity.or_else(geometry_identity) else {
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
            let Some(asset) = splash_asset(champion_id) else {
                continue;
            };

            // The illustration replaces this picked-card actor; it is not a
            // translucent decoration behind it.  Retaining the native actor
            // lets the scaled slide-in pose protrude beyond the 284x172 art
            // for a few frames (most visibly on Lucian's red-side pick).
            original_actor_indices.push(command_index);
            original_actor_counts[side.candidate_index(slot_index)] += 1;

            let original_geometry = (*x, *y, *w, *h);
            let target_x = bp_overlay_x(side, map_width);
            let target_y = bp_overlay_y(slot_index);
            let mut overlay = (*command).clone();
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
            } = &mut overlay
            else {
                unreachable!("cloned NinePatch changed variant")
            };
            *texture = asset.to_owned();
            texture_rect.x = 0.0;
            texture_rect.y = 0.0;
            // NinePatch texture_rect is normalized UV space. The source PNG
            // is 1420x860, but Ban/Pick View Plus writes the full image as
            // (0,0,1,1); pixel dimensions here sample outside the texture.
            texture_rect.w = 1.0;
            texture_rect.h = 1.0;
            *x = target_x;
            *y = target_y;
            *w = BP_CARD_WIDTH;
            *h = BP_CARD_HEIGHT;
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

            let score = bp_actor_candidate_score(side, slot_index, map_width, original_geometry);
            let candidate_index = side.candidate_index(slot_index);
            let should_replace = candidates[candidate_index]
                .as_ref()
                .is_none_or(|candidate| score < candidate.score);
            if should_replace {
                candidates[candidate_index] = Some(BpOverlayCandidate {
                    score,
                    side,
                    slot_index,
                    champion_id,
                    asset,
                    original_texture: texture_source(command).unwrap_or_default().to_owned(),
                    original_geometry,
                    overlay,
                    route: if pass_identity.is_some() {
                        "pass"
                    } else {
                        "geometry"
                    },
                });
            }
        }

        // Remove every recognized actor command, including duplicate
        // transition commands for the same slot.  Iterating in reverse keeps
        // the recorded indices valid and leaves champion-grid/tooltip icons
        // untouched because those never pass the picked-card geometry gate.
        original_actor_indices.sort_unstable();
        original_actor_indices.dedup();
        for command_index in original_actor_indices.into_iter().rev() {
            commands.remove(command_index);
        }
        let mut overlays = Vec::new();
        for candidate in candidates.into_iter().flatten() {
            let target_x = bp_overlay_x(candidate.side, map_width);
            let target_y = bp_overlay_y(candidate.slot_index);
            let removed_actor_count =
                original_actor_counts[candidate.side.candidate_index(candidate.slot_index)];
            write_bp_render_telemetry_once(
                "overlay_append",
                candidate.side.as_str(),
                Some(candidate.slot_index),
                &candidate.original_texture,
                candidate.asset,
                &format!(
                    "champion={};route={};pass={pass};map_width={map_width:.1};score={:.1};from={:.1},{:.1},{:.1},{:.1};to={:.1},{:.1},284,172;flip_x={};original_actor_commands_removed={removed_actor_count}",
                    candidate.champion_id,
                    candidate.route,
                    candidate.score,
                    candidate.original_geometry.0,
                    candidate.original_geometry.1,
                    candidate.original_geometry.2,
                    candidate.original_geometry.3,
                    target_x,
                    target_y,
                    candidate.side == BpRenderSide::Red,
                ),
            );
            overlays.push(candidate.overlay);
        }
        commands.extend(overlays);
    }
}

fn texture_source(command: &RenderCommand) -> Option<&str> {
    let RenderCommand::NinePatch { texture, .. } = command else {
        return None;
    };
    Some(texture)
}

fn bp_overlay_x(side: BpRenderSide, map_width: f32) -> f32 {
    match side {
        BpRenderSide::Blue => BP_CARD_EDGE_INSET,
        // Ban/Pick View Plus defaults to a horizontally flipped red card.
        // NinePatch flips around pivot_x=0, so its command anchor is the
        // right edge (1905 at 1920px), not the left edge at 1620px.
        BpRenderSide::Red => map_width - BP_CARD_EDGE_INSET,
    }
}

fn bp_overlay_y(slot_index: usize) -> f32 {
    BP_CARD_TOP + BP_CARD_STEP_Y * slot_index as f32
}

fn bp_actor_candidate_score(
    side: BpRenderSide,
    slot_index: usize,
    map_width: f32,
    geometry: (f32, f32, f32, f32),
) -> f32 {
    let expected_x = match side {
        BpRenderSide::Blue => BP_NATIVE_ACTOR_BLUE_X,
        BpRenderSide::Red => map_width - BP_NATIVE_ACTOR_RED_INSET,
    };
    let expected_y = BP_NATIVE_ACTOR_TOP + BP_CARD_STEP_Y * slot_index as f32;
    (geometry.0 - expected_x).abs()
        + (geometry.1 - expected_y).abs()
        + (geometry.2 - BP_NATIVE_ACTOR_WIDTH).abs()
        + (geometry.3 - BP_NATIVE_ACTOR_HEIGHT).abs()
}

fn ui_tree_contains_id(root: &Node, target: &str) -> bool {
    root.id == target
        || root
            .child
            .iter()
            .any(|child| ui_tree_contains_id(child, target))
}

fn bp_identity_from_pass(pass: &str) -> Option<(BpRenderSide, usize)> {
    let side = if pass.contains("blue_picks") {
        BpRenderSide::Blue
    } else if pass.contains("red_picks") {
        BpRenderSide::Red
    } else {
        return None;
    };
    let marker = "pick_slot_";
    let digits: String = pass[pass.find(marker)? + marker.len()..]
        .chars()
        .take_while(char::is_ascii_digit)
        .collect();
    let slot = digits.parse::<usize>().ok()?;
    (slot < PICK_SLOT_LIMIT).then_some((side, slot))
}

fn bp_side_from_geometry(
    x: f32,
    y: f32,
    width: f32,
    height: f32,
    map_width: f32,
) -> Option<BpRenderSide> {
    if !(40.0..=960.0).contains(&y)
        || !(BP_TRANSITION_ACTOR_MIN_WIDTH..=BP_TRANSITION_ACTOR_MAX_WIDTH).contains(&width)
        || !(BP_TRANSITION_ACTOR_MIN_HEIGHT..=BP_TRANSITION_ACTOR_MAX_HEIGHT).contains(&height)
    {
        return None;
    }
    // The red-side actor starts its completion transition just outside the
    // settled 335px edge band.  The 120..140 by 140..190 actor-size contract
    // lets us include that slide without ever converting 128x128 list art.
    let right_edge_start = (map_width - BP_RED_TRANSITION_EDGE_BAND).max(335.0);
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
