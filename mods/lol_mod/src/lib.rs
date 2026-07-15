use std::cell::RefCell;
use std::collections::{HashMap, HashSet};
use std::ffi::c_void;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::Path;
use std::rc::Rc;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Mutex, OnceLock};
use std::time::{SystemTime, UNIX_EPOCH};

use engine_core::render_state::RenderCommand;
use game_view::{ClientDatabase, MatchUIRunner};
use mod_api::MatchType;
use mod_api::*;

const MOD_ID: &str = "lol_mod";
// Teamfight Manager 2 updated its runtime to base 0.5.1 on 2026-07-15, while
// the bundled SDK still identifies itself as base 0.5.0.  The client/server
// extension traits expose internal game_view/game_core structures whose ABI
// is not covered by the stable Mod API version.  Calling those old extension
// vtables during 0.5.1 Ban/Pick caused the host renderer to unwrap a missing
// value and terminate.  Keep combat-native Mod API hooks enabled, but require
// an explicit developer opt-in before registering the stale internal ABI.
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
const URGOT_COMPACT_PORTRAIT_TEXTURE: &str = "asset/lol_mod/ui/champion_portrait/demon_compact";
const URGOT_SCOREBOARD_PORTRAIT_TEXTURE: &str =
    "asset/lol_mod/ui/champion_portrait/demon_scoreboard";
const URGOT_BP_GRID_PORTRAIT_TEXTURE: &str = "asset/lol_mod/ui/champion_portrait/demon_grid";
const YONE_ACTOR_SHEET_TEXTURES: [&str; 2] = [
    "asset/base/aseprite_resources/champions/dual_blader#sheet",
    "asset/lol_mod/aseprite_resources/champions/yone#sheet",
];
const YONE_COMPACT_PORTRAIT_TEXTURE: &str =
    "asset/lol_mod/ui/champion_portrait/dual_blader_compact";
const YONE_BP_GRID_PORTRAIT_TEXTURE: &str = "asset/lol_mod/ui/champion_portrait/dual_blader_grid";
const SPLASH_SPECS: [(&str, &str); 9] = [
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
    ("demon", "asset/lol_mod/BanPickIllust/demon"),
    ("dual_blader", "asset/lol_mod/BanPickIllust/dual_blader"),
];
const SHEN_COMPACT_PORTRAIT_TEXTURE: &str = "asset/lol_mod/ui/champion_portrait/lol_shen_compact";
const SHEN_SCOREBOARD_PORTRAIT_TEXTURE: &str =
    "asset/lol_mod/ui/champion_portrait/lol_shen_scoreboard";
const SHEN_BP_GRID_PORTRAIT_TEXTURE: &str = "asset/lol_mod/ui/champion_portrait/lol_shen_grid";
const LUCIAN_COMPACT_PORTRAIT_TEXTURE: &str = "asset/lol_mod/ui/champion_portrait/archer_compact";
const LUCIAN_SCOREBOARD_PORTRAIT_TEXTURE: &str =
    "asset/lol_mod/ui/champion_portrait/archer_scoreboard";
const LUCIAN_BP_GRID_PORTRAIT_TEXTURE: &str = "asset/lol_mod/ui/champion_portrait/archer_grid";
const SIVIR_COMPACT_PORTRAIT_TEXTURE: &str =
    "asset/lol_mod/ui/champion_portrait/boomerang_hunter_compact";
const SIVIR_SCOREBOARD_PORTRAIT_TEXTURE: &str =
    "asset/lol_mod/ui/champion_portrait/boomerang_hunter_scoreboard";
const SIVIR_BP_GRID_PORTRAIT_TEXTURE: &str =
    "asset/lol_mod/ui/champion_portrait/boomerang_hunter_grid";
const ORIANNA_COMPACT_PORTRAIT_TEXTURE: &str =
    "asset/lol_mod/ui/champion_portrait/barrier_magician_compact";
const ORIANNA_SCOREBOARD_PORTRAIT_TEXTURE: &str =
    "asset/lol_mod/ui/champion_portrait/barrier_magician_scoreboard";
const ORIANNA_BP_GRID_PORTRAIT_TEXTURE: &str =
    "asset/lol_mod/ui/champion_portrait/barrier_magician_grid";
const BRIAR_COMPACT_PORTRAIT_TEXTURE: &str = "asset/lol_mod/ui/champion_portrait/berserker_compact";
const BRIAR_SCOREBOARD_PORTRAIT_TEXTURE: &str =
    "asset/lol_mod/ui/champion_portrait/berserker_scoreboard";
const BRIAR_BP_GRID_PORTRAIT_TEXTURE: &str = "asset/lol_mod/ui/champion_portrait/berserker_grid";

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
        rewrite_shen_lucian_portrait_render_commands(state);
        rewrite_orianna_briar_portrait_render_commands(state);
        rewrite_sivir_urgot_portrait_render_commands(state);
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

fn legacy_portrait_assets(texture: &str) -> Option<(&'static str, &'static str, &'static str)> {
    match texture {
        "asset/base/aseprite_resources/champions/lol_shen#sheet"
        | "asset/lol_mod/aseprite_resources/champions/lol_shen#sheet"
        | "asset/lol_mod/aseprite_resources/champions/shen#sheet" => Some((
            SHEN_COMPACT_PORTRAIT_TEXTURE,
            SHEN_SCOREBOARD_PORTRAIT_TEXTURE,
            SHEN_BP_GRID_PORTRAIT_TEXTURE,
        )),
        "asset/base/aseprite_resources/champions/archer#sheet"
        | "asset/lol_mod/aseprite_resources/champions/archer#sheet"
        | "asset/lol_mod/aseprite_resources/champions/lucian#sheet" => Some((
            LUCIAN_COMPACT_PORTRAIT_TEXTURE,
            LUCIAN_SCOREBOARD_PORTRAIT_TEXTURE,
            LUCIAN_BP_GRID_PORTRAIT_TEXTURE,
        )),
        "asset/base/aseprite_resources/champions/boomerang_hunter#sheet"
        | "asset/base/aseprite_resources/champions/sivir#sheet"
        | "asset/lol_mod/aseprite_resources/champions/boomerang_hunter#sheet"
        | "asset/lol_mod/aseprite_resources/champions/sivir#sheet" => Some((
            SIVIR_COMPACT_PORTRAIT_TEXTURE,
            SIVIR_SCOREBOARD_PORTRAIT_TEXTURE,
            SIVIR_BP_GRID_PORTRAIT_TEXTURE,
        )),
        "asset/base/aseprite_resources/champions/barrier_magician#sheet"
        | "asset/lol_mod/aseprite_resources/champions/barrier_magician#sheet"
        | "asset/lol_mod/aseprite_resources/champions/orianna#sheet" => Some((
            ORIANNA_COMPACT_PORTRAIT_TEXTURE,
            ORIANNA_SCOREBOARD_PORTRAIT_TEXTURE,
            ORIANNA_BP_GRID_PORTRAIT_TEXTURE,
        )),
        "asset/base/aseprite_resources/champions/berserker#sheet"
        | "asset/lol_mod/aseprite_resources/champions/berserker#sheet"
        | "asset/lol_mod/aseprite_resources/champions/briar#sheet" => Some((
            BRIAR_COMPACT_PORTRAIT_TEXTURE,
            BRIAR_SCOREBOARD_PORTRAIT_TEXTURE,
            BRIAR_BP_GRID_PORTRAIT_TEXTURE,
        )),
        "asset/base/aseprite_resources/champions/demon#sheet"
        | "asset/lol_mod/aseprite_resources/champions/demon#sheet"
        | "asset/lol_mod/aseprite_resources/champions/urgot#sheet" => Some((
            URGOT_COMPACT_PORTRAIT_TEXTURE,
            URGOT_SCOREBOARD_PORTRAIT_TEXTURE,
            URGOT_BP_GRID_PORTRAIT_TEXTURE,
        )),
        _ => None,
    }
}

fn rewrite_shen_lucian_portrait_render_commands(state: &mut RenderState) {
    rewrite_legacy_portrait_render_commands(state, |texture| {
        texture.contains("/lol_shen#sheet")
            || texture.contains("/shen#sheet")
            || texture.contains("/archer#sheet")
            || texture.contains("/lucian#sheet")
    });
}

fn rewrite_orianna_briar_portrait_render_commands(state: &mut RenderState) {
    rewrite_legacy_portrait_render_commands(state, |texture| {
        texture.contains("/barrier_magician#sheet")
            || texture.contains("/orianna#sheet")
            || texture.contains("/berserker#sheet")
            || texture.contains("/briar#sheet")
    });
}

fn rewrite_sivir_urgot_portrait_render_commands(state: &mut RenderState) {
    rewrite_legacy_portrait_render_commands(state, |texture| {
        texture.contains("/boomerang_hunter#sheet")
            || texture.contains("/sivir#sheet")
            || texture.contains("/demon#sheet")
            || texture.contains("/urgot#sheet")
    });
}

fn rewrite_legacy_portrait_render_commands(
    state: &mut RenderState,
    accepts_texture: impl Fn(&str) -> bool,
) {
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
            if !accepts_texture(texture) {
                continue;
            }
            let Some((compact, scoreboard, grid)) = legacy_portrait_assets(texture) else {
                continue;
            };

            // Report/scoreboard rows and the larger side-list use independent
            // source-direct face crops. Battle actors are Sprite commands and
            // therefore cannot enter this UI-only NinePatch route.
            let is_scoreboard_square = (14.0..=38.0).contains(w);
            let is_scoreboard_square =
                is_scoreboard_square && (14.0..=38.0).contains(h) && (*w - *h).abs() <= 2.0;
            let is_compact_square = (39.0..=52.0).contains(w);
            let is_compact_square =
                is_compact_square && (39.0..=52.0).contains(h) && (*w - *h).abs() <= 2.0;
            // Most legacy actors arrive as a fixed 128px square. Urgot's new
            // 80x64 actor atlas can also arrive as a 160x128 rectangle; both
            // are center-preserving routes to the dedicated 90x122 grid art.
            let is_urgot = texture.contains("/demon#sheet") || texture.contains("/urgot#sheet");
            let is_bp_grid = (124.0..=132.0).contains(w)
                && (124.0..=132.0).contains(h)
                && (*w - *h).abs() <= 2.0;
            let is_bp_grid = if is_urgot {
                (124.0..=164.0).contains(w) && (120.0..=132.0).contains(h)
            } else {
                is_bp_grid
            };
            let replacement = if is_scoreboard_square {
                scoreboard
            } else if is_compact_square {
                compact
            } else if is_bp_grid {
                let center_x = *x + *w * 0.5;
                let center_y = *y + *h * 0.5;
                *w = 90.0;
                *h = 122.0;
                *x = center_x - *w * 0.5;
                *y = center_y - *h * 0.5;
                grid
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

fn is_yone_compact_portrait_geometry(width: f32, height: f32) -> bool {
    if !(14.0..=52.0).contains(&width) || !(14.0..=64.0).contains(&height) {
        return false;
    }
    let short_side = width.min(height);
    let long_side = width.max(height);
    short_side >= 14.0 && long_side / short_side <= 1.50
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
            if !is_yone_actor_sheet_texture(texture.as_str()) {
                continue;
            }

            // Scoreboard and battle-side-list commands preserve the native
            // actor frame's slight portrait aspect ratio (for example 18x26
            // and 30x38), so a square-only test silently left the tiny full
            // body actor in place. Route both compact geometries to the
            // dedicated head/shoulder crop and square the destination around
            // its original centre to avoid stretching the face.
            let is_compact = is_yone_compact_portrait_geometry(*w, *h);
            let is_bp_grid = is_yone_bp_grid_geometry(*w, *h);
            let replacement = if is_compact {
                let center_x = *x + *w * 0.5;
                let center_y = *y + *h * 0.5;
                let side = (*w).max(*h).min(52.0);
                *w = side;
                *h = side;
                *x = center_x - side * 0.5;
                *y = center_y - side * 0.5;
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
        ("demon", "lol_fullbody_urgot"),
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
            "version=0.11.1;root={};queried_blue={queried_blue};queried_red={queried_red};queried_delegate={queried_delegate};tree_blue={tree_blue};tree_red={tree_red};matched_passes={matched_passes};passes={}",
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
        "urgot" | "demon" => Some("demon"),
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
        let attack = Input::Attack { target };
        if ctx.is_valid_input(&attack) {
            PlayerInputDecision::Replace(attack)
        } else if let Some(retreat) = ctx.get_run_away_without_skill_input() {
            PlayerInputDecision::Replace(retreat)
        } else {
            PlayerInputDecision::Replace(attack)
        }
    }
}

const URGOT_PASSIVE_COOLDOWN_TICKS: usize = 120;
const URGOT_PASSIVE_FLAT_DAMAGE: usize = 20;
const URGOT_PASSIVE_ATTACK_RATIO_PERCENT: usize = 30;
const URGOT_PASSIVE_TARGET_MAX_HP_PERCENT: usize = 2;
const URGOT_R_EXECUTE_THRESHOLD_PERCENT: usize = 25;

#[derive(Debug)]
struct UrgotPassiveCooldown {
    caster: EntityHandle,
    ready_tick: usize,
}

static URGOT_PASSIVE_COOLDOWNS: OnceLock<Mutex<Vec<UrgotPassiveCooldown>>> = OnceLock::new();

fn urgot_passive_cooldowns() -> &'static Mutex<Vec<UrgotPassiveCooldown>> {
    URGOT_PASSIVE_COOLDOWNS.get_or_init(|| Mutex::new(Vec::new()))
}

#[derive(Clone, Copy, Debug, Default)]
struct UrgotPassiveNativeEffect;

impl ModEffectType for UrgotPassiveNativeEffect {
    fn apply(&self, ctx: &mut GameCtx, _rng_seed: u64, caster_id: usize, input: InputTarget) {
        let InputTarget::Target { target_id } = input else {
            return;
        };
        // This native callback runs after the data-driven Attack in the same
        // projectile payload. Reacquire both entities here: that Attack may
        // already have killed or removed either participant through combat
        // resolution, retaliation, or another engine-owned effect.
        let Some((caster_handle, caster_attack, caster_alive)) = ctx
            .get_entity(caster_id)
            .map(|caster| (caster.handle(), caster.stat().attack, caster.is_alive()))
        else {
            return;
        };
        if !caster_alive {
            return;
        }
        let Some((target_max_hp, target_alive)) = ctx
            .get_entity(target_id)
            .map(|target| (target.hp().max, target.is_alive()))
        else {
            return;
        };
        if !target_alive || target_max_hp == 0 {
            return;
        }

        let now = ctx.tick();
        let Ok(mut cooldowns) = urgot_passive_cooldowns().lock() else {
            return;
        };
        if let Some(cooldown) = cooldowns
            .iter_mut()
            .find(|cooldown| cooldown.caster == caster_handle)
        {
            if now < cooldown.ready_tick {
                return;
            }
            cooldown.ready_tick = now.saturating_add(URGOT_PASSIVE_COOLDOWN_TICKS);
        } else {
            cooldowns.push(UrgotPassiveCooldown {
                caster: caster_handle,
                ready_tick: now.saturating_add(URGOT_PASSIVE_COOLDOWN_TICKS),
            });
        }
        drop(cooldowns);

        let damage = URGOT_PASSIVE_FLAT_DAMAGE
            .saturating_add(caster_attack.saturating_mul(URGOT_PASSIVE_ATTACK_RATIO_PERCENT) / 100)
            .saturating_add(
                target_max_hp.saturating_mul(URGOT_PASSIVE_TARGET_MAX_HP_PERCENT) / 100,
            );
        ctx.deal_damage(caster_id, target_id, damage, 0, AttackType::Skill);
    }
}

#[derive(Clone, Copy, Debug, Default)]
struct UrgotRCheckNativeEffect;

impl ModEffectType for UrgotRCheckNativeEffect {
    fn apply(&self, ctx: &mut GameCtx, _rng_seed: u64, caster_id: usize, input: InputTarget) {
        let InputTarget::Target { target_id } = input else {
            return;
        };
        let Some((target_hp, target_alive)) = ctx
            .get_entity(target_id)
            .map(|target| (target.hp(), target.is_alive()))
        else {
            return;
        };
        if !target_alive || target_hp.max == 0 {
            return;
        }
        let execute_limit = target_hp
            .max
            .saturating_mul(URGOT_R_EXECUTE_THRESHOLD_PERCENT)
            / 100;
        if target_hp.current > execute_limit {
            return;
        }
        if !ctx
            .get_entity(caster_id)
            .is_some_and(|caster| caster.is_alive())
        {
            return;
        }

        // The reel and pull are data-driven behind this short-lived marker.
        // Targets above the execute threshold keep the chain slow but are
        // never grabbed, matching Fear Beyond Death's recast condition.
        let mut ready = BuffState::default();
        ready.name = "lol_urgot_r_execute_ready"
            .try_into()
            .expect("Urgot R ready marker fits BuffState name capacity");
        ready.duration = BuffType::Time { tick: 2 };
        ctx.add_buff(caster_id, ready);
    }
}

#[derive(Clone, Copy, Debug, Default)]
struct UrgotRExecuteNativeEffect;

impl ModEffectType for UrgotRExecuteNativeEffect {
    fn apply(&self, ctx: &mut GameCtx, _rng_seed: u64, caster_id: usize, input: InputTarget) {
        let InputTarget::Target { target_id } = input else {
            return;
        };
        let Some((target_hp, target_shield, target_alive)) = ctx
            .get_entity(target_id)
            .map(|target| (target.hp(), target.shield(), target.is_alive()))
        else {
            return;
        };
        if !target_alive || target_hp.max == 0 {
            return;
        }
        if !ctx
            .get_entity(caster_id)
            .is_some_and(|caster| caster.is_alive())
        {
            return;
        }

        // Deal enough physical damage to cross current HP and shield, then
        // query the entity again. Undying/invulnerability therefore prevents
        // the success marker and, in turn, prevents the execute VFX, splash
        // damage and fear branch in demon.data_champion.
        let lethal_damage = target_hp
            .current
            .saturating_add(target_shield)
            .saturating_add(target_hp.max);
        ctx.deal_damage(caster_id, target_id, lethal_damage, 0, AttackType::Skill);
        let executed = ctx
            .get_entity(target_id)
            .is_some_and(|target| !target.is_alive());
        if !executed {
            return;
        }
        if !ctx
            .get_entity(caster_id)
            .is_some_and(|caster| caster.is_alive())
        {
            return;
        }

        let mut success = BuffState::default();
        success.name = "lol_urgot_r_execute_success"
            .try_into()
            .expect("Urgot R success marker fits BuffState name capacity");
        success.duration = BuffType::Time { tick: 2 };
        ctx.add_buff(caster_id, success);
    }
}

const YONE_SOUL_UNBOUND_WINDOW_TICKS: usize = 240;
const YONE_SOUL_UNBOUND_RETURN_TICKS: usize = 60;
const YONE_SOUL_UNBOUND_STALE_GRACE_TICKS: usize = 600;
const YONE_SOUL_UNBOUND_REPEAT_PERCENT: usize = 25;
const YONE_SOUL_UNBOUND_SERVICE_ID: &str = "yone_soul_unbound_context";

static NEXT_YONE_CONTEXT_TOKEN: AtomicUsize = AtomicUsize::new(1);
static YONE_CONTEXT_SERVICE_VTABLE_SENTINEL: u8 = 0;

fn yone_context_token(ctx: &GameCtx) -> Option<usize> {
    if let Some(service) = ctx.query_service(MOD_ID, YONE_SOUL_UNBOUND_SERVICE_ID, ">=1.0.0") {
        let token = service.data as usize;
        return (token != 0).then_some(token);
    }

    let token = NEXT_YONE_CONTEXT_TOKEN.fetch_add(1, Ordering::Relaxed);
    if token == 0 {
        return None;
    }
    let service = ModService::from_raw(
        token as *mut c_void,
        (&YONE_CONTEXT_SERVICE_VTABLE_SENTINEL as *const u8).cast::<c_void>(),
    );
    if ctx.register_service(
        YONE_SOUL_UNBOUND_SERVICE_ID,
        ModServiceVersion::new(1, 0, 0),
        service,
    ) {
        return Some(token);
    }

    ctx.query_service(MOD_ID, YONE_SOUL_UNBOUND_SERVICE_ID, ">=1.0.0")
        .and_then(|registered| {
            let registered_token = registered.data as usize;
            (registered_token != 0).then_some(registered_token)
        })
}

#[derive(Debug)]
struct YoneSoulUnboundDamageMark {
    target_id: usize,
    target: EntityHandle,
    hp_and_shield_before_damage: Option<usize>,
    recorded_damage: usize,
}

#[derive(Debug)]
struct YoneSoulUnboundState {
    context_token: usize,
    caster: EntityHandle,
    player_id: usize,
    team: usize,
    position: Position,
    anchor: EntityPos,
    started_tick: usize,
    expiry_tick: usize,
    return_started_tick: Option<usize>,
    damage_marks: Vec<YoneSoulUnboundDamageMark>,
}

#[derive(Debug, Default)]
struct YoneSoulUnboundRegistry {
    last_tick_by_context: HashMap<usize, usize>,
    states: Vec<YoneSoulUnboundState>,
}

impl YoneSoulUnboundRegistry {
    fn prepare_for_tick(&mut self, context_token: usize, now: usize) {
        // Hidden/management simulations can interleave callbacks from several
        // matches whose ticks move independently.  Reset only the current
        // GameCtx service bucket; never clear another match's E ledger.
        if self
            .last_tick_by_context
            .get(&context_token)
            .is_some_and(|last_tick| now < *last_tick)
        {
            self.states
                .retain(|state| state.context_token != context_token);
        }
        self.last_tick_by_context.insert(context_token, now);

        // Collect stale state only inside this context bucket.  A lower tick
        // from another simulation must not delete the foreground ledger.
        self.states.retain(|state| {
            state.context_token != context_token
                || (state.started_tick <= now
                    && now
                        <= state
                            .expiry_tick
                            .saturating_add(YONE_SOUL_UNBOUND_STALE_GRACE_TICKS))
        });
    }

    fn forget_context_if_idle(&mut self, context_token: usize) {
        if !self
            .states
            .iter()
            .any(|state| state.context_token == context_token)
        {
            self.last_tick_by_context.remove(&context_token);
        }
    }
}

static YONE_SOUL_UNBOUND_STATE: OnceLock<Mutex<YoneSoulUnboundRegistry>> = OnceLock::new();

fn yone_soul_unbound_state() -> &'static Mutex<YoneSoulUnboundRegistry> {
    YONE_SOUL_UNBOUND_STATE.get_or_init(|| Mutex::new(YoneSoulUnboundRegistry::default()))
}

#[derive(Clone, Copy, Debug, Default)]
struct YoneSoulUnboundStartNativeEffect;

impl ModEffectType for YoneSoulUnboundStartNativeEffect {
    fn apply(&self, ctx: &mut GameCtx, _rng_seed: u64, caster_id: usize, _input: InputTarget) {
        let Some(context_token) = yone_context_token(ctx) else {
            return;
        };
        let Some((caster, caster_alive, anchor)) = ctx
            .get_entity(caster_id)
            .map(|entity| (entity.handle(), entity.is_alive(), entity.pos()))
        else {
            return;
        };
        if !caster_alive {
            return;
        }
        let Some((player_id, team, position, player_caster)) =
            xayah_player_for_caster(ctx, caster_id)
        else {
            return;
        };
        if player_caster != caster {
            return;
        }

        let now = ctx.tick();
        let Ok(mut registry) = yone_soul_unbound_state().lock() else {
            return;
        };
        registry.prepare_for_tick(context_token, now);
        // Recasting/re-entering E replaces the old window for this exact
        // entity in this match instead of counting damage twice.
        registry
            .states
            .retain(|state| state.context_token != context_token || state.caster != caster);
        registry.states.push(YoneSoulUnboundState {
            context_token,
            caster,
            player_id,
            team,
            position,
            anchor,
            started_tick: now,
            expiry_tick: now.saturating_add(YONE_SOUL_UNBOUND_WINDOW_TICKS),
            return_started_tick: None,
            damage_marks: Vec::new(),
        });
    }
}

#[derive(Clone, Copy, Debug, Default)]
struct YoneSoulUnboundBeginReturnNativeEffect;

impl ModEffectType for YoneSoulUnboundBeginReturnNativeEffect {
    fn apply(&self, ctx: &mut GameCtx, _rng_seed: u64, caster_id: usize, _input: InputTarget) {
        let Some(context_token) = yone_context_token(ctx) else {
            return;
        };
        let Some(caster) = ctx.get_entity(caster_id).map(|entity| entity.handle()) else {
            return;
        };
        let now = ctx.tick();
        let Ok(mut registry) = yone_soul_unbound_state().lock() else {
            return;
        };
        registry.prepare_for_tick(context_token, now);
        let Some(state) = registry.states.iter_mut().find(|state| {
            state.context_token == context_token
                && state.caster == caster
                && state.started_tick <= now
        }) else {
            return;
        };
        state.return_started_tick = Some(now);
    }
}

#[derive(Clone, Debug, Default)]
struct YoneSoulUnboundReturnInputAi;

impl ModPlayerInputAi for YoneSoulUnboundReturnInputAi {
    fn clone_box(&self) -> Box<dyn ModPlayerInputAi> {
        Box::new(self.clone())
    }

    fn id(&self) -> &str {
        "lol_yone_e_return_input_ai"
    }

    fn think(
        &mut self,
        ctx: &mut PlayerAiContext<'_, '_, '_>,
        _base_input: Option<Input>,
    ) -> PlayerInputDecision {
        if !matches!(ctx.champion_name(), "dual_blader" | "Yone" | "永恩") {
            return PlayerInputDecision::Pass;
        }

        let now = ctx.tick();
        let player_id = ctx.player_id();
        let team = ctx.team();
        let position = ctx.position();
        let anchor = yone_soul_unbound_state().lock().ok().and_then(|registry| {
            registry
                .states
                .iter()
                .filter(|state| {
                    state.player_id == player_id && state.team == team && state.position == position
                })
                .filter_map(|state| {
                    state.return_started_tick.and_then(|return_tick| {
                        (return_tick <= now
                            && now < return_tick.saturating_add(YONE_SOUL_UNBOUND_RETURN_TICKS))
                        .then_some((
                            return_tick,
                            state.context_token,
                            state.anchor.x,
                            state.anchor.y,
                        ))
                    })
                })
                .max_by_key(|(return_tick, context_token, _, _)| (*return_tick, *context_token))
                .map(|(_, _, x, y)| (x, y))
        });
        let Some((x, y)) = anchor else {
            return PlayerInputDecision::Pass;
        };

        PlayerInputDecision::Replace(Input::Move { x, y })
    }
}

#[derive(Clone, Copy, Debug, Default)]
struct YoneSoulUnboundDamagePreNativeEffect;

impl ModEffectType for YoneSoulUnboundDamagePreNativeEffect {
    fn apply(&self, ctx: &mut GameCtx, _rng_seed: u64, caster_id: usize, input: InputTarget) {
        let Some(context_token) = yone_context_token(ctx) else {
            return;
        };
        let InputTarget::Target { target_id } = input else {
            return;
        };
        let Some((caster, caster_alive)) = ctx
            .get_entity(caster_id)
            .map(|entity| (entity.handle(), entity.is_alive()))
        else {
            return;
        };
        if !caster_alive {
            return;
        }
        let Some((target, target_alive, hp_and_shield)) = ctx.get_entity(target_id).map(|entity| {
            (
                entity.handle(),
                entity.is_alive(),
                entity.hp().current.saturating_add(entity.shield()),
            )
        }) else {
            return;
        };
        if !target_alive {
            return;
        }

        let now = ctx.tick();
        let Ok(mut registry) = yone_soul_unbound_state().lock() else {
            return;
        };
        registry.prepare_for_tick(context_token, now);
        let Some(state) = registry.states.iter_mut().find(|state| {
            state.context_token == context_token
                && state.caster == caster
                && state.started_tick <= now
                && now < state.expiry_tick
        }) else {
            return;
        };
        let mark = if let Some(mark) = state
            .damage_marks
            .iter_mut()
            .find(|mark| mark.target_id == target_id && mark.target == target)
        {
            mark
        } else {
            state.damage_marks.push(YoneSoulUnboundDamageMark {
                target_id,
                target,
                hp_and_shield_before_damage: None,
                recorded_damage: 0,
            });
            state
                .damage_marks
                .last_mut()
                .expect("Yone E damage mark was just inserted")
        };
        mark.hp_and_shield_before_damage = Some(hp_and_shield);
    }
}

#[derive(Clone, Copy, Debug, Default)]
struct YoneSoulUnboundDamagePostNativeEffect;

impl ModEffectType for YoneSoulUnboundDamagePostNativeEffect {
    fn apply(&self, ctx: &mut GameCtx, _rng_seed: u64, caster_id: usize, input: InputTarget) {
        let Some(context_token) = yone_context_token(ctx) else {
            return;
        };
        let InputTarget::Target { target_id } = input else {
            return;
        };
        let Some(caster) = ctx.get_entity(caster_id).map(|entity| entity.handle()) else {
            return;
        };
        let Some((target, hp_and_shield_after_damage)) = ctx.get_entity(target_id).map(|entity| {
            (
                entity.handle(),
                entity.hp().current.saturating_add(entity.shield()),
            )
        }) else {
            return;
        };

        let now = ctx.tick();
        let Ok(mut registry) = yone_soul_unbound_state().lock() else {
            return;
        };
        registry.prepare_for_tick(context_token, now);
        let Some(state) = registry.states.iter_mut().find(|state| {
            state.context_token == context_token
                && state.caster == caster
                && state.started_tick <= now
                && now < state.expiry_tick
        }) else {
            return;
        };
        let Some(mark) = state
            .damage_marks
            .iter_mut()
            .find(|mark| mark.target_id == target_id && mark.target == target)
        else {
            return;
        };
        let Some(hp_and_shield_before_damage) = mark.hp_and_shield_before_damage.take() else {
            return;
        };
        mark.recorded_damage = mark
            .recorded_damage
            .saturating_add(hp_and_shield_before_damage.saturating_sub(hp_and_shield_after_damage));
    }
}

#[derive(Clone, Copy, Debug, Default)]
struct YoneSoulUnboundSettleNativeEffect;

impl ModEffectType for YoneSoulUnboundSettleNativeEffect {
    fn apply(&self, ctx: &mut GameCtx, _rng_seed: u64, caster_id: usize, _input: InputTarget) {
        let Some(context_token) = yone_context_token(ctx) else {
            return;
        };
        let Some(caster) = ctx.get_entity(caster_id).map(|entity| entity.handle()) else {
            return;
        };
        let now = ctx.tick();

        // Remove and own the complete settlement payload while locked. Engine
        // queries and damage calls happen only after the mutex is released.
        let state = {
            let Ok(mut registry) = yone_soul_unbound_state().lock() else {
                return;
            };
            registry.prepare_for_tick(context_token, now);
            let Some(state_index) = registry.states.iter().position(|state| {
                state.context_token == context_token
                    && state.caster == caster
                    && state.started_tick <= now
            }) else {
                return;
            };
            let state = registry.states.remove(state_index);
            registry.forget_context_if_idle(context_token);
            state
        };

        let caster_is_same_and_alive = ctx
            .get_entity(caster_id)
            .is_some_and(|entity| entity.handle() == state.caster && entity.is_alive());
        if !caster_is_same_and_alive {
            return;
        }

        for mark in state.damage_marks {
            let target_is_same_and_alive = ctx
                .get_entity(mark.target_id)
                .is_some_and(|entity| entity.handle() == mark.target && entity.is_alive());
            if !target_is_same_and_alive {
                continue;
            }
            let repeated_damage = mark
                .recorded_damage
                .saturating_mul(YONE_SOUL_UNBOUND_REPEAT_PERCENT)
                / 100;
            if repeated_damage == 0 {
                continue;
            }
            ctx.deal_damage(
                caster_id,
                mark.target_id,
                repeated_damage,
                0,
                AttackType::Skill,
            );
        }
    }
}

const SHEN_SHADOW_DASH_TAUNT_TICKS: u64 = 90;

#[derive(Clone, Copy, Debug, Default)]
struct ShenShadowDashAiHintNativeEffect;

impl ModEffectType for ShenShadowDashAiHintNativeEffect {
    fn apply(&self, _ctx: &mut GameCtx, _rng_seed: u64, _caster_id: usize, _input: InputTarget) {}

    fn expected_cc_time(&self) -> Option<usize> {
        Some(SHEN_SHADOW_DASH_TAUNT_TICKS as usize)
    }
}

#[derive(Clone, Copy, Debug, Default)]
struct ShenShadowDashTauntNativeEffect;

impl ModEffectType for ShenShadowDashTauntNativeEffect {
    fn apply(&self, ctx: &mut GameCtx, _rng_seed: u64, caster_id: usize, input: InputTarget) {
        let InputTarget::Target { target_id } = input else {
            return;
        };
        if !ctx
            .get_entity(caster_id)
            .is_some_and(|caster| caster.is_alive())
            || !ctx
                .get_entity(target_id)
                .is_some_and(|target| target.is_alive())
        {
            return;
        }

        ctx.apply_cc(
            target_id,
            CCState::Taunt {
                tick: SHEN_SHADOW_DASH_TAUNT_TICKS,
                target: caster_id,
            },
        );
    }

    fn expected_cc_time(&self) -> Option<usize> {
        Some(SHEN_SHADOW_DASH_TAUNT_TICKS as usize)
    }
}

#[derive(Clone, Debug, Default)]
struct ShenShadowDashInputAi;

impl ModPlayerInputAi for ShenShadowDashInputAi {
    fn clone_box(&self) -> Box<dyn ModPlayerInputAi> {
        Box::new(self.clone())
    }

    fn id(&self) -> &str {
        "lol_shen_shadow_dash_input_ai"
    }

    fn think(
        &mut self,
        ctx: &mut PlayerAiContext<'_, '_, '_>,
        base_input: Option<Input>,
    ) -> PlayerInputDecision {
        if !matches!(ctx.champion_name(), "lol_shen" | "Shen" | "慎") {
            return PlayerInputDecision::Pass;
        }
        let target = match base_input {
            Some(Input::Skill { target }) | Some(Input::Attack { target }) => target,
            _ => return PlayerInputDecision::Pass,
        };
        let shadow_dash = Input::Skill2 { target };
        if ctx.is_valid_input(&shadow_dash) {
            PlayerInputDecision::Replace(shadow_dash)
        } else {
            PlayerInputDecision::Pass
        }
    }
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
    registration.add_player_input_ai(XayahFeatherInputGate);
    registration.add_native_effect("lol_urgot_passive_native", UrgotPassiveNativeEffect);
    registration.add_native_effect("lol_urgot_r_check_native", UrgotRCheckNativeEffect);
    registration.add_native_effect("lol_urgot_r_execute_native", UrgotRExecuteNativeEffect);
    registration.add_native_effect("lol_yone_e_start_native", YoneSoulUnboundStartNativeEffect);
    registration.add_native_effect(
        "lol_yone_e_begin_return_native",
        YoneSoulUnboundBeginReturnNativeEffect,
    );
    registration.add_player_input_ai(YoneSoulUnboundReturnInputAi);
    registration.add_native_effect(
        "lol_yone_e_damage_pre_native",
        YoneSoulUnboundDamagePreNativeEffect,
    );
    registration.add_native_effect(
        "lol_yone_e_damage_post_native",
        YoneSoulUnboundDamagePostNativeEffect,
    );
    registration.add_native_effect(
        "lol_yone_e_settle_native",
        YoneSoulUnboundSettleNativeEffect,
    );
    registration.add_native_effect(
        "lol_shen_shadow_dash_ai_hint_native",
        ShenShadowDashAiHintNativeEffect,
    );
    registration.add_native_effect(
        "lol_shen_shadow_dash_taunt_native",
        ShenShadowDashTauntNativeEffect,
    );
    registration.add_player_input_ai(ShenShadowDashInputAi);
    if std::env::var(LEGACY_BASE_050_INTERNAL_EXTENSIONS_ENV).is_ok_and(|value| value == "1") {
        registration.set_extension(LolModExtension);
        registration.set_server_extension(LolDragonServerExtension {
            announced: Mutex::new(HashSet::new()),
        });
    }
    registration
}

declare_mod!(init);
