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
// Teamfight Manager 2 base 0.5.1 is newer than the bundled base 0.5.0 SDK.
// Client/server extensions expose internal game structures outside the stable
// Mod API ABI, so require an explicit developer opt-in before registering
// either extension through the stale interface.
const LEGACY_BASE_050_INTERNAL_EXTENSIONS_ENV: &str = "LOL_MOD_ALLOW_BASE_050_INTERNAL_EXTENSIONS";
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
// Live 0.9.1 telemetry proves that Dancer's completed side-card command is
// 81x141 (the 27x47 native idle rect at 3x), centered on exactly the same
// point as the standard 137x184 pick actor.  Its slide-in transition keeps an
// 81px width while height grows from about 125px to 141px.  The separate
// center champion grid remains 54x94; the left/right edge gate below is what
// prevents that grid art from ever being converted into a side-card splash.
const BP_DANCER_ACTOR_WIDTH: f32 = 81.0;
const BP_DANCER_ACTOR_HEIGHT: f32 = 141.0;
const BP_DANCER_TRANSITION_MIN_WIDTH: f32 = 80.0;
const BP_DANCER_TRANSITION_MAX_WIDTH: f32 = 82.0;
const BP_DANCER_TRANSITION_MIN_HEIGHT: f32 = 124.0;
const BP_DANCER_TRANSITION_MAX_HEIGHT: f32 = 142.0;
// Official 009 Dual Blader's native idle frame is 43x55 and the Ban/Pick
// surface renders it at 3x.  Keep its settled 129x165 actor centre distinct
// from both the 90x122 hero-grid portrait and the generic 137x184 contract.
const BP_DUAL_BLADER_ACTOR_WIDTH: f32 = 129.0;
const BP_DUAL_BLADER_ACTOR_HEIGHT: f32 = 165.0;
// Live 0.10.0 telemetry records Dual Blader's picked-side slide from
// 114.4x134.1 through 129x165.  These limits deliberately remain disjoint
// from the 84..96x108..130 centre-grid portrait contract below.
const BP_DUAL_BLADER_TRANSITION_MIN_WIDTH: f32 = 112.0;
const BP_DUAL_BLADER_TRANSITION_MAX_WIDTH: f32 = 132.0;
const BP_DUAL_BLADER_TRANSITION_MIN_HEIGHT: f32 = 132.0;
const BP_DUAL_BLADER_TRANSITION_MAX_HEIGHT: f32 = 168.0;
const KLED_ACTOR_SHEET_TEXTURES: [&str; 2] = [
    "asset/base/aseprite_resources/champions/cavalry_knight#sheet",
    "asset/lol_mod/aseprite_resources/champions/kled#sheet",
];
const KLED_COMPACT_PORTRAIT_TEXTURE: &str =
    "asset/lol_mod/ui/champion_portrait/cavalry_knight_compact";
const KLED_BP_GRID_PORTRAIT_TEXTURE: &str =
    "asset/lol_mod/ui/champion_portrait/cavalry_knight_grid";
const XAYAH_ACTOR_SHEET_TEXTURES: [&str; 2] = [
    "asset/base/aseprite_resources/champions/dancer#sheet",
    "asset/lol_mod/aseprite_resources/champions/xayah#sheet",
];
const XAYAH_COMPACT_PORTRAIT_TEXTURE: &str = "asset/lol_mod/ui/champion_portrait/dancer_compact";
const XAYAH_BP_GRID_PORTRAIT_TEXTURE: &str = "asset/lol_mod/ui/champion_portrait/dancer_grid";
const YONE_ACTOR_SHEET_TEXTURES: [&str; 2] = [
    "asset/base/aseprite_resources/champions/dual_blader#sheet",
    "asset/lol_mod/aseprite_resources/champions/yone#sheet",
];
const YONE_COMPACT_PORTRAIT_TEXTURE: &str =
    "asset/lol_mod/ui/champion_portrait/dual_blader_compact";
const YONE_SCOREBOARD_PORTRAIT_TEXTURE: &str =
    "asset/lol_mod/ui/champion_portrait/dual_blader_scoreboard";
const YONE_BP_GRID_PORTRAIT_TEXTURE: &str = "asset/lol_mod/ui/champion_portrait/dual_blader_grid";
const SPLASH_SPECS: [(&str, &str); 8] = [
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
    (
        "cavalry_knight",
        "asset/lol_mod/BanPickIllust/cavalry_knight",
    ),
    ("dancer", "asset/lol_mod/BanPickIllust/dancer"),
    ("dual_blader", "asset/lol_mod/BanPickIllust/dual_blader"),
];

// Elder is intentionally excluded: this feature selects one base elemental
// drake for the whole match.  The relative names are retained for telemetry;
// the renderer uses the direct mod sheet keys below so it does not depend on
// EntityView's neutral-monster asset routing.
const DRAGON_VIEW_NAMES: [&str; 5] = [
    "dragon_variants/infernal",
    "dragon_variants/ocean",
    "dragon_variants/mountain",
    "dragon_variants/cloud",
    "dragon_variants/hextech",
];
const DRAGON_SOURCE_SHEET_TEXTURES: [&str; 2] = [
    "asset/base/aseprite_resources/ingame/serpen#sheet",
    "asset/lol_mod/aseprite_resources/ingame/serpen#sheet",
];
const DRAGON_VARIANT_SHEET_TEXTURES: [&str; 5] = [
    "asset/lol_mod/aseprite_resources/ingame/dragon_variants/infernal#sheet",
    "asset/lol_mod/aseprite_resources/ingame/dragon_variants/ocean#sheet",
    "asset/lol_mod/aseprite_resources/ingame/dragon_variants/mountain#sheet",
    "asset/lol_mod/aseprite_resources/ingame/dragon_variants/cloud#sheet",
    "asset/lol_mod/aseprite_resources/ingame/dragon_variants/hextech#sheet",
];

// UI kill notifications are sourced from asset/base/text/ui rather than
// asset/base/text/object. The static merge below fixes Baron and provides an
// Infernal fallback; this table keeps every rendered dragon label in lockstep
// with the per-match seed-selected model.
const DRAGON_RENDER_NAMES: [[&str; 5]; 5] = [
    [
        "Infernal Drake",
        "Ocean Drake",
        "Mountain Drake",
        "Cloud Drake",
        "Hextech Drake",
    ],
    [
        "화염의 드래곤",
        "바다의 드래곤",
        "대지의 드래곤",
        "바람의 드래곤",
        "마법공학 드래곤",
    ],
    [
        "インファーナルドレイク",
        "オーシャンドレイク",
        "マウンテンドレイク",
        "クラウドドレイク",
        "ヘクステックドレイク",
    ],
    [
        "炼狱亚龙",
        "海洋亚龙",
        "山脉亚龙",
        "云端亚龙",
        "海克斯科技亚龙",
    ],
    [
        "赤燄飛龍",
        "癒水飛龍",
        "裂地飛龍",
        "疾風飛龍",
        "海克斯科技飛龍",
    ],
];
const DRAGON_RENDER_LEGACY_NAMES: [&str; 5] = ["Serpen", "세르펜", "セルペン", "双角巨蛇", "蛇彭"];
const BARON_RENDER_NAMES: [(&str, &str); 5] = [
    ("Morgard", "Baron Nashor"),
    ("모르가드", "내셔 남작"),
    ("モルガード", "バロンナッシャー"),
    ("莫尔加德", "纳什男爵"),
    ("莫加德", "巴龍納什"),
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
    active_selection: Option<DragonSelection>,
    last_rendered: Option<DragonSelection>,
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
        rewrite_dragon_render_commands(ui, state);
        rewrite_objective_render_text(ui, state);
        rewrite_bp_render_commands(ui, state);
        rewrite_kled_portrait_render_commands(state);
        rewrite_xayah_portrait_render_commands(state);
        rewrite_yone_portrait_render_commands(state);
    }
}

fn rewrite_kled_portrait_render_commands(state: &mut RenderState) {
    for commands in state.commands.values_mut() {
        for command in commands {
            let RenderCommand::NinePatch {
                texture,
                texture_rect,
                w,
                h,
                left,
                right,
                top,
                bottom,
                sample_nearest,
                ..
            } = command
            else {
                continue;
            };
            if !KLED_ACTOR_SHEET_TEXTURES.contains(&texture.as_str()) {
                continue;
            }

            // Compact report/scoreboard/HUD rows are square (telemetry shows
            // 18/26/34/46px).  A full Kled + Skaarl mount cannot retain a
            // readable face there, so route only these exact UI geometries
            // to the rider-focused portrait.  Native battle frames are
            // rectangular and therefore cannot enter this branch.
            let is_compact_square =
                (14.0..=52.0).contains(w) && (14.0..=52.0).contains(h) && (*w - *h).abs() <= 2.0;
            // Ban/pick grid telemetry identifies native 006 at 90x122, with
            // a small scale transition around 86x122.  Keep that full-body
            // surface distinct from the head-focused compact icon.
            let is_bp_grid = (84.0..=96.0).contains(w) && (108.0..=130.0).contains(h);
            let replacement = if is_compact_square {
                KLED_COMPACT_PORTRAIT_TEXTURE
            } else if is_bp_grid {
                KLED_BP_GRID_PORTRAIT_TEXTURE
            } else {
                continue;
            };

            *texture = replacement.to_owned();
            texture_rect.x = 0.0;
            texture_rect.y = 0.0;
            texture_rect.w = 1.0;
            texture_rect.h = 1.0;
            *left = 0.0;
            *right = 0.0;
            *top = 0.0;
            *bottom = 0.0;
            *sample_nearest = true;
        }
    }
}

fn rewrite_xayah_portrait_render_commands(state: &mut RenderState) {
    for commands in state.commands.values_mut() {
        for command in commands {
            let RenderCommand::NinePatch {
                texture,
                texture_rect,
                x,
                y,
                w,
                h,
                left,
                right,
                top,
                bottom,
                sample_nearest,
                ..
            } = command
            else {
                continue;
            };
            if !XAYAH_ACTOR_SHEET_TEXTURES.contains(&texture.as_str()) {
                continue;
            }

            // Square report, scoreboard, side-list, and HUD commands receive
            // the v3 two-eye face crop.  Battle actor commands are Sprite
            // commands and cannot enter this NinePatch-only UI route.
            let is_compact_square =
                (14.0..=52.0).contains(w) && (14.0..=52.0).contains(h) && (*w - *h).abs() <= 2.0;
            // Dancer's center hero-grid preview is the native 27x47 idle rect
            // rendered at 2x.  Keep this tight 54x94 geometry disjoint from
            // the telemetry-proven 81x125-141 picked-side transition; the
            // latter is removed by rewrite_bp_render_commands above.
            let is_bp_grid = (50.0..=58.0).contains(w) && (88.0..=100.0).contains(h);
            let replacement = if is_compact_square {
                XAYAH_COMPACT_PORTRAIT_TEXTURE
            } else if is_bp_grid {
                // The dedicated grid texture is 90x122, while native Dancer
                // draws its 27x47 idle rect at 2x (54x94). Preserve the
                // command center and expand to the real texture size;
                // stretching 90x122 back into 54x94 would squeeze Xayah on x
                // and recreate the tiny/deformed grid model.
                let center_x = *x + *w * 0.5;
                let center_y = *y + *h * 0.5;
                *w = 90.0;
                *h = 122.0;
                *x = center_x - *w * 0.5;
                *y = center_y - *h * 0.5;
                XAYAH_BP_GRID_PORTRAIT_TEXTURE
            } else {
                continue;
            };

            *texture = replacement.to_owned();
            texture_rect.x = 0.0;
            texture_rect.y = 0.0;
            texture_rect.w = 1.0;
            texture_rect.h = 1.0;
            *left = 0.0;
            *right = 0.0;
            *top = 0.0;
            *bottom = 0.0;
            *sample_nearest = true;
        }
    }
}

fn is_yone_actor_sheet_texture(texture: &str) -> bool {
    YONE_ACTOR_SHEET_TEXTURES.contains(&texture)
        || texture.contains("/aseprite_resources/champions/dual_blader")
        || texture.contains("/aseprite_resources/champions/yone")
}

fn is_yone_scoreboard_portrait_geometry(width: f32, height: f32) -> bool {
    if !(14.0..=38.0).contains(&width) || !(14.0..=40.0).contains(&height) {
        return false;
    }
    width >= 14.0 && height / width >= 1.15 && height / width <= 1.50
}

fn is_yone_compact_portrait_geometry(width: f32, height: f32) -> bool {
    (14.0..=52.0).contains(&width)
        && (14.0..=52.0).contains(&height)
        && (width - height).abs() <= 2.0
}

fn is_yone_bp_grid_geometry(width: f32, height: f32) -> bool {
    (84.0..=96.0).contains(&width) && (108.0..=130.0).contains(&height)
}

fn rewrite_yone_portrait_render_commands(state: &mut RenderState) {
    for commands in state.commands.values_mut() {
        for command in commands {
            let RenderCommand::NinePatch {
                texture,
                texture_rect,
                x: _,
                y: _,
                w,
                h,
                left,
                right,
                top,
                bottom,
                sample_nearest,
                ..
            } = command
            else {
                continue;
            };
            if !is_yone_actor_sheet_texture(texture.as_str()) {
                continue;
            }

            // Rectangular scoreboard rows and square compact portraits are
            // separate surfaces. Route each to its source-direct final-scale
            // crop while preserving the command's original x/y/w/h.
            let is_scoreboard = is_yone_scoreboard_portrait_geometry(*w, *h);
            let is_compact = is_yone_compact_portrait_geometry(*w, *h);
            let is_bp_grid = is_yone_bp_grid_geometry(*w, *h);
            let replacement = if is_scoreboard {
                YONE_SCOREBOARD_PORTRAIT_TEXTURE
            } else if is_compact {
                YONE_COMPACT_PORTRAIT_TEXTURE
            } else if is_bp_grid {
                YONE_BP_GRID_PORTRAIT_TEXTURE
            } else {
                continue;
            };

            *texture = replacement.to_owned();
            texture_rect.x = 0.0;
            texture_rect.y = 0.0;
            texture_rect.w = 1.0;
            texture_rect.h = 1.0;
            *left = 0.0;
            *right = 0.0;
            *top = 0.0;
            *bottom = 0.0;
            *sample_nearest = true;
        }
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
            state.active_selection = None;
            state.last_rendered = None;
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

        let database = database.borrow();
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
        let mut state = state.borrow_mut();
        if let Some(selection) = selection {
            if state.active_selection != Some(selection) {
                state.active_selection = Some(selection);
                state.last_rendered = None;
            }
            state.fallback_logged = false;
        } else if !state.fallback_logged {
            write_dragon_fallback_telemetry(if replay_mode {
                "replay seed unavailable; retained default serpen"
            } else {
                "server seed event unavailable; retained default serpen"
            });
            state.active_selection = None;
            state.last_rendered = None;
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

fn current_dragon_variant_index() -> usize {
    current_dragon_selection()
        .map(|selection| dragon_variant_index(selection.seed))
        .unwrap_or(0)
}

fn current_dragon_selection() -> Option<DragonSelection> {
    CLIENT_DRAGON_STATE.with(|state| state.borrow().active_selection)
}

fn rewrite_dragon_render_commands(ui: &GameUI, state: &mut RenderState) {
    // EntityView::view_name is applied too late for the already-produced
    // Sprite command and is overwritten again by the next server refresh.
    // Rewrite the final command instead, inside the same MatchUIRunner gate as
    // the objective-name pass, so model and text use one seed in one frame.
    if !ui_tree_has_match_runner(&ui.root) {
        return;
    }

    let selection = current_dragon_selection();
    let selected_dragon = selection
        .map(|selection| dragon_variant_index(selection.seed))
        .unwrap_or(0);
    let replacement = DRAGON_VARIANT_SHEET_TEXTURES[selected_dragon];
    let mut rewrite_count = 0usize;
    let mut first_source = None;

    for commands in state.commands.values_mut() {
        for command in commands {
            let RenderCommand::Sprite { texture, .. } = command else {
                continue;
            };
            let Some(source) = DRAGON_SOURCE_SHEET_TEXTURES
                .iter()
                .copied()
                .find(|source| texture.as_str() == *source)
            else {
                continue;
            };
            first_source.get_or_insert(source);
            texture.clear();
            texture.push_str(replacement);
            rewrite_count += 1;
        }
    }

    let Some(selection) = selection.filter(|_| rewrite_count > 0) else {
        return;
    };
    CLIENT_DRAGON_STATE.with(|dragon_state| {
        let mut dragon_state = dragon_state.borrow_mut();
        if dragon_state.last_rendered == Some(selection) {
            return;
        }
        let detail = format!(
            "old={} new={} rewrite_count={}",
            first_source.unwrap_or(DRAGON_SOURCE_SHEET_TEXTURES[0]),
            replacement,
            rewrite_count
        );
        write_dragon_telemetry("render_apply", selection, &detail);
        dragon_state.last_rendered = Some(selection);
    });
}

fn rewrite_objective_render_text(ui: &GameUI, state: &mut RenderState) {
    // active_selection intentionally survives through the match result view, but
    // must never recolor encyclopedia/management text with a previous match's
    // element. Limit the dynamic pass to a live/replay MatchUIRunner tree.
    if !ui_tree_has_match_runner(&ui.root) {
        return;
    }
    let selected_dragon = current_dragon_variant_index();
    for commands in state.commands.values_mut() {
        for command in commands {
            let RenderCommand::Text { text, .. } = command else {
                continue;
            };

            let mut rewritten = text.clone();
            for (legacy, replacement) in BARON_RENDER_NAMES {
                if rewritten.contains(legacy) {
                    rewritten = rewritten.replace(legacy, replacement);
                }
            }
            for (locale_index, names) in DRAGON_RENDER_NAMES.iter().enumerate() {
                let replacement = names[selected_dragon];
                let legacy = DRAGON_RENDER_LEGACY_NAMES[locale_index];
                if rewritten.contains(legacy) {
                    rewritten = rewritten.replace(legacy, replacement);
                }
                for name in names {
                    if *name != replacement && rewritten.contains(name) {
                        rewritten = rewritten.replace(name, replacement);
                    }
                }
            }
            if *text != rewritten {
                *text = rewritten;
            }
        }
    }
}

fn ui_tree_has_match_runner(root: &Node) -> bool {
    root.runner_as::<MatchUIRunner>().is_some() || root.child.iter().any(ui_tree_has_match_runner)
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
        ("cavalry_knight", "lol_fullbody_kled"),
        ("dancer", "lol_fullbody_xayah"),
        ("dual_blader", "lol_fullbody_yone"),
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
            "version=0.10.6;root={};queried_blue={queried_blue};queried_red={queried_red};queried_delegate={queried_delegate};tree_blue={tree_blue};tree_red={tree_red};matched_passes={matched_passes};passes={}",
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
                let side = bp_side_from_geometry(champion_id, *x, *y, *w, *h, map_width)?;
                let slot = bp_slot_from_geometry(*y, *h)?;
                Some((side, slot))
            };
            let Some((side, slot_index)) = pass_identity.or_else(geometry_identity) else {
                // Keep telemetry capacity for real side-card failures. The
                // old route recorded every scrolling 128x128 grid preview
                // and every 18x18 footer icon, exhausting all 80 rows before
                // a user could complete a pick.
                if bp_geometry_is_actor_sized_near_pick_edge(*x, *w, *h, map_width) {
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
                }
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

            let score = bp_actor_candidate_score(
                champion_id,
                side,
                slot_index,
                map_width,
                original_geometry,
            );
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
    champion_id: &str,
    side: BpRenderSide,
    slot_index: usize,
    map_width: f32,
    geometry: (f32, f32, f32, f32),
) -> f32 {
    let contract = bp_actor_contract(champion_id);
    let native_center_x = match side {
        BpRenderSide::Blue => BP_NATIVE_ACTOR_BLUE_X + BP_NATIVE_ACTOR_WIDTH * 0.5,
        BpRenderSide::Red => map_width - BP_NATIVE_ACTOR_RED_INSET + BP_NATIVE_ACTOR_WIDTH * 0.5,
    };
    let native_center_y =
        BP_NATIVE_ACTOR_TOP + BP_NATIVE_ACTOR_HEIGHT * 0.5 + BP_CARD_STEP_Y * slot_index as f32;
    let expected_x = native_center_x - contract.width * 0.5;
    let expected_y = native_center_y - contract.height * 0.5;
    (geometry.0 - expected_x).abs()
        + (geometry.1 - expected_y).abs()
        + (geometry.2 - contract.width).abs()
        + (geometry.3 - contract.height).abs()
}

#[derive(Clone, Copy)]
struct BpActorContract {
    width: f32,
    height: f32,
    min_width: f32,
    max_width: f32,
    min_height: f32,
    max_height: f32,
}

fn bp_actor_contract(champion_id: &str) -> BpActorContract {
    if champion_id == "dancer" {
        return BpActorContract {
            width: BP_DANCER_ACTOR_WIDTH,
            height: BP_DANCER_ACTOR_HEIGHT,
            min_width: BP_DANCER_TRANSITION_MIN_WIDTH,
            max_width: BP_DANCER_TRANSITION_MAX_WIDTH,
            min_height: BP_DANCER_TRANSITION_MIN_HEIGHT,
            max_height: BP_DANCER_TRANSITION_MAX_HEIGHT,
        };
    }
    if champion_id == "dual_blader" {
        return BpActorContract {
            width: BP_DUAL_BLADER_ACTOR_WIDTH,
            height: BP_DUAL_BLADER_ACTOR_HEIGHT,
            min_width: BP_DUAL_BLADER_TRANSITION_MIN_WIDTH,
            max_width: BP_DUAL_BLADER_TRANSITION_MAX_WIDTH,
            min_height: BP_DUAL_BLADER_TRANSITION_MIN_HEIGHT,
            max_height: BP_DUAL_BLADER_TRANSITION_MAX_HEIGHT,
        };
    }
    BpActorContract {
        width: BP_NATIVE_ACTOR_WIDTH,
        height: BP_NATIVE_ACTOR_HEIGHT,
        min_width: BP_TRANSITION_ACTOR_MIN_WIDTH,
        max_width: BP_TRANSITION_ACTOR_MAX_WIDTH,
        min_height: BP_TRANSITION_ACTOR_MIN_HEIGHT,
        max_height: BP_TRANSITION_ACTOR_MAX_HEIGHT,
    }
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
    champion_id: &str,
    x: f32,
    y: f32,
    width: f32,
    height: f32,
    map_width: f32,
) -> Option<BpRenderSide> {
    let contract = bp_actor_contract(champion_id);
    if !(40.0..=960.0).contains(&y)
        || !(contract.min_width..=contract.max_width).contains(&width)
        || !(contract.min_height..=contract.max_height).contains(&height)
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

fn bp_geometry_is_actor_sized_near_pick_edge(
    x: f32,
    width: f32,
    height: f32,
    map_width: f32,
) -> bool {
    let right_edge_start = (map_width - BP_RED_TRANSITION_EDGE_BAND).max(335.0);
    let near_side =
        (0.0..=335.0).contains(&x) || (right_edge_start..=(map_width + 180.0)).contains(&x);
    near_side && width >= 40.0 && height >= 70.0
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
        "kled" | "cavalry_knight" => Some("cavalry_knight"),
        "xayah" | "dancer" => Some("dancer"),
        "yone" | "dual_blader" => Some("dual_blader"),
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

const XAYAH_FEATHER_STATE_TTL_TICKS: usize = 600;
const XAYAH_AI_MIN_RECALL_FEATHERS: u8 = 2;

#[derive(Debug)]
struct XayahFeatherUnitState {
    unit: EntityHandle,
    player_id: usize,
    team: usize,
    position: Position,
    count: u8,
    updated_tick: usize,
    expiry_tick: usize,
}

static XAYAH_AI_FEATHER_STATE: OnceLock<Mutex<Vec<XayahFeatherUnitState>>> = OnceLock::new();

fn xayah_ai_feather_state() -> &'static Mutex<Vec<XayahFeatherUnitState>> {
    XAYAH_AI_FEATHER_STATE.get_or_init(|| Mutex::new(Vec::new()))
}

fn xayah_player_for_caster(
    ctx: &GameCtx,
    caster_id: usize,
) -> Option<(usize, usize, Position, EntityHandle)> {
    let caster_handle = ctx.get_entity(caster_id)?.handle();
    (0..ctx.player_count()).find_map(|player_id| {
        let Some(player) = ctx.player_at(player_id) else {
            return None;
        };
        let Some(champion) = player.champion() else {
            return None;
        };
        (champion.handle() == caster_handle)
            .then(|| (player_id, player.team(), player.position(), caster_handle))
    })
}

#[derive(Clone, Copy, Debug)]
enum XayahFeatherStateChange {
    Add(u8),
    Set(u8),
    Clear,
}

#[derive(Clone, Copy, Debug)]
struct XayahFeatherAiStateEffect {
    change: XayahFeatherStateChange,
}

impl ModEffectType for XayahFeatherAiStateEffect {
    fn apply(&self, ctx: &mut GameCtx, _rng_seed: u64, caster_id: usize, _input: InputTarget) {
        let Some((player_id, team, position, unit)) = xayah_player_for_caster(ctx, caster_id)
        else {
            return;
        };
        let now = ctx.tick();
        let Ok(mut states) = xayah_ai_feather_state().lock() else {
            return;
        };
        states.retain(|state| state.expiry_tick > now || state.unit == unit);

        if matches!(self.change, XayahFeatherStateChange::Clear) {
            states.retain(|state| state.unit != unit);
            return;
        }

        let state_index = states.iter().position(|state| state.unit == unit);
        let state = if let Some(index) = state_index {
            &mut states[index]
        } else {
            states.push(XayahFeatherUnitState {
                unit,
                player_id,
                team,
                position,
                count: 0,
                updated_tick: now,
                expiry_tick: now,
            });
            states.last_mut().expect("Xayah state was just inserted")
        };
        if state.expiry_tick <= now {
            state.count = 0;
        }
        state.player_id = player_id;
        state.team = team;
        state.position = position;
        state.count = match self.change {
            XayahFeatherStateChange::Add(amount) => state.count.saturating_add(amount).min(5),
            XayahFeatherStateChange::Set(amount) => amount.min(5),
            XayahFeatherStateChange::Clear => 0,
        };
        state.updated_tick = now;
        state.expiry_tick = now.saturating_add(XAYAH_FEATHER_STATE_TTL_TICKS);
    }
}

#[derive(Clone, Debug, Default)]
struct XayahFeatherInputGate;

impl ModPlayerInputAi for XayahFeatherInputGate {
    fn clone_box(&self) -> Box<dyn ModPlayerInputAi> {
        Box::new(self.clone())
    }

    fn id(&self) -> &str {
        "lol_xayah_feather_input_gate"
    }

    fn think(
        &mut self,
        ctx: &mut PlayerAiContext<'_, '_, '_>,
        base_input: Option<Input>,
    ) -> PlayerInputDecision {
        if !matches!(
            ctx.champion_name(),
            "dancer" | "Xayah" | "霞" | "剎雅" | "ザヤ" | "자야"
        ) {
            return PlayerInputDecision::Pass;
        }
        let Some(Input::Skill2 { target }) = base_input else {
            return PlayerInputDecision::Pass;
        };

        let player_id = ctx.player_id();
        let team = ctx.team();
        let position = ctx.position();
        let now = ctx.tick();
        let feather_count = xayah_ai_feather_state()
            .lock()
            .map(|mut states| {
                states.retain(|state| state.expiry_tick > now);
                states
                    .iter()
                    .filter(|state| {
                        state.player_id == player_id
                            && state.team == team
                            && state.position == position
                            && state.updated_tick <= now
                    })
                    .max_by_key(|state| state.updated_tick)
                    .map(|state| state.count)
                    .unwrap_or(0)
            })
            .unwrap_or(0);
        if feather_count >= XAYAH_AI_MIN_RECALL_FEATHERS {
            return PlayerInputDecision::Pass;
        }

        // DataActionDef has no buff-based cast predicate in Mod API 0.8.
        // Replace an empty Bladecaller decision before it reaches the action,
        // so its cooldown, cast animation, SFX and effect tree are not spent.
        // Do not call PlayerAiContext fallback helpers here: the 0.5.0 SDK
        // helper can cross into a missing 0.5.1 hidden-simulation score state
        // and abort the host while BP is transitioning into the match.
        let attack = Input::Attack { target };
        PlayerInputDecision::Replace(attack)
    }
}

const YONE_W_RANGE: i128 = 42_000;
const YONE_W_COS_SQ_SCALE: i128 = 1_000_000;
// cos(40 degrees)^2: Spirit Cleave is an 80-degree forward cone.
const YONE_W_COS_SQ_HALF_ANGLE: i128 = 586_824;
const YONE_W_FLAT_DAMAGE: usize = 35;
const YONE_W_ATTACK_RATIO_PERCENT: usize = 45;
const YONE_W_TARGET_MAX_HP_PERCENT: usize = 6;
const YONE_W_MAX_ENEMY_CHAMPIONS: usize = 5;

#[derive(Clone, Copy, Debug, Default)]
struct YoneSpiritCleaveConeNativeEffect;

impl ModEffectType for YoneSpiritCleaveConeNativeEffect {
    fn apply(&self, ctx: &mut GameCtx, _rng_seed: u64, caster_id: usize, input: InputTarget) {
        let Some((caster_pos, caster_team, caster_attack, true)) = ctx
            .get_entity(caster_id)
            .map(|caster| {
                (
                    caster.pos(),
                    caster.team(),
                    caster.stat().attack,
                    caster.is_alive(),
                )
            })
        else {
            return;
        };
        let (dir_x, dir_y) = match input {
            InputTarget::Dir { dir_x, dir_y } => (i128::from(dir_x), i128::from(dir_y)),
            InputTarget::Pos { x, y } => (
                i128::from(x) - i128::from(caster_pos.x),
                i128::from(y) - i128::from(caster_pos.y),
            ),
            InputTarget::Target { target_id } => {
                let Some(target_pos) = ctx.get_entity(target_id).map(|target| target.pos()) else {
                    return;
                };
                (
                    i128::from(target_pos.x) - i128::from(caster_pos.x),
                    i128::from(target_pos.y) - i128::from(caster_pos.y),
                )
            }
            InputTarget::None => return,
        };
        if dir_x == 0 && dir_y == 0 {
            return;
        }

        let dir_sq = dir_x * dir_x + dir_y * dir_y;
        let mut hits: Vec<(usize, usize)> = Vec::new();
        let mut champion_hits = 0usize;
        for index in 0..ctx.entity_count() {
            let Some(target) = ctx.entity_at(index) else {
                continue;
            };
            let target_id = target.id();
            if target_id == caster_id
                || target.team() == caster_team
                || !target.is_alive()
                || !target.is_targetable()
                || target.is_tower()
            {
                continue;
            }

            let target_pos = target.pos();
            let dx = i128::from(target_pos.x) - i128::from(caster_pos.x);
            let dy = i128::from(target_pos.y) - i128::from(caster_pos.y);
            let distance_sq = dx * dx + dy * dy;
            let hit_range = YONE_W_RANGE + target.radius() as i128;
            if distance_sq > hit_range * hit_range {
                continue;
            }

            let dot = dx * dir_x + dy * dir_y;
            if dot <= 0
                || dot * dot * YONE_W_COS_SQ_SCALE
                    < distance_sq * dir_sq * YONE_W_COS_SQ_HALF_ANGLE
            {
                continue;
            }

            let damage = YONE_W_FLAT_DAMAGE
                .saturating_add(
                    caster_attack.saturating_mul(YONE_W_ATTACK_RATIO_PERCENT) / 100,
                )
                .saturating_add(
                    target
                        .hp()
                        .max
                        .saturating_mul(YONE_W_TARGET_MAX_HP_PERCENT)
                        / 100,
                );
            champion_hits += usize::from(target.is_champion());
            hits.push((target_id, damage));
        }
        if hits.is_empty() {
            return;
        }

        // Scan first and mutate second so every target is resolved from one
        // immutable cone snapshot. No process-global ledger means hidden and
        // foreground GameCtx instances cannot share or steal W state.
        for (target_id, damage) in hits {
            ctx.deal_damage(caster_id, target_id, damage, 0, AttackType::Skill);
        }
        if !ctx
            .get_entity(caster_id)
            .is_some_and(|caster| caster.is_alive())
        {
            return;
        }

        let shield_tier = champion_hits.min(YONE_W_MAX_ENEMY_CHAMPIONS);
        let marker_name = format!("lol_yone_w_shield_tier_{shield_tier}");
        let Ok(name) = marker_name.as_str().try_into() else {
            return;
        };
        let mut marker = BuffState::default();
        marker.name = name;
        marker.duration = BuffType::Time { tick: 3 };
        ctx.add_buff(caster_id, marker);
    }
}

// Saved seasons embed their champion definitions. Keep retired native names
// resolvable so a pre-W save can enter Ban/Pick on the current runtime without
// restoring any of the deleted E or legacy Shen behavior.
#[derive(Clone, Copy, Debug, Default)]
struct LegacySavedNativeCompatibilityEffect;

impl ModEffectType for LegacySavedNativeCompatibilityEffect {
    fn apply(&self, _ctx: &mut GameCtx, _rng_seed: u64, _caster_id: usize, _input: InputTarget) {}
}

fn init(_ctx: &GameCtx) -> ModRegistration {
    let mut registration = ModRegistration::new(MOD_ID);
    registration.add_native_effect(
        "lol_xayah_ai_feather_add_1",
        XayahFeatherAiStateEffect {
            change: XayahFeatherStateChange::Add(1),
        },
    );
    registration.add_native_effect(
        "lol_xayah_ai_feather_add_2",
        XayahFeatherAiStateEffect {
            change: XayahFeatherStateChange::Add(2),
        },
    );
    registration.add_native_effect(
        "lol_xayah_ai_feather_set_5",
        XayahFeatherAiStateEffect {
            change: XayahFeatherStateChange::Set(5),
        },
    );
    registration.add_native_effect(
        "lol_xayah_ai_feather_clear",
        XayahFeatherAiStateEffect {
            change: XayahFeatherStateChange::Clear,
        },
    );
    registration.add_native_effect(
        "lol_yone_w_cone_native",
        YoneSpiritCleaveConeNativeEffect,
    );
    // 0.10.4 saves embed the retired three-stage rectangular W tree. Keep its
    // native names resolvable for load/BP compatibility, but current saves use
    // the stateless cone callback above and never enter these aliases.
    registration.add_native_effect(
        "lol_yone_w_begin_native",
        LegacySavedNativeCompatibilityEffect,
    );
    registration.add_native_effect(
        "lol_yone_w_collect_hit_native",
        LegacySavedNativeCompatibilityEffect,
    );
    registration.add_native_effect(
        "lol_yone_w_settle_native",
        LegacySavedNativeCompatibilityEffect,
    );
    registration.add_native_effect(
        "lol_yone_e_start_native",
        LegacySavedNativeCompatibilityEffect,
    );
    registration.add_native_effect(
        "lol_yone_e_begin_return_native",
        LegacySavedNativeCompatibilityEffect,
    );
    registration.add_native_effect(
        "lol_yone_e_damage_pre_native",
        LegacySavedNativeCompatibilityEffect,
    );
    registration.add_native_effect(
        "lol_yone_e_damage_post_native",
        LegacySavedNativeCompatibilityEffect,
    );
    registration.add_native_effect(
        "lol_yone_e_settle_native",
        LegacySavedNativeCompatibilityEffect,
    );
    registration.add_native_effect(
        "lol_shen_shadow_dash_ai_hint_native",
        LegacySavedNativeCompatibilityEffect,
    );
    registration.add_native_effect(
        "lol_shen_shadow_dash_taunt_native",
        LegacySavedNativeCompatibilityEffect,
    );
    registration.add_player_input_ai(XayahFeatherInputGate);
    if std::env::var(LEGACY_BASE_050_INTERNAL_EXTENSIONS_ENV).is_ok_and(|value| value == "1") {
        registration.set_extension(LolModExtension);
        registration.set_server_extension(LolDragonServerExtension {
            announced: Mutex::new(HashSet::new()),
        });
    }
    registration
}

declare_mod!(init);
