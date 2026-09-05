//! Stable-ABI runtime for Teamfight Manager 2 0.5.8 and later.
//!
//! `src/lib.rs` is retained as the classic Mod API 0.8 migration reference,
//! but Cargo deliberately builds only this file. Only the frozen `*V1` value
//! types and size-guarded stable host tables cross the DLL boundary.

use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Mutex, OnceLock};

use mod_api_stable::{
    declare_stable_mod, AttackTypeV1, BuffV1, InputKindV1, InputTargetKindV1, InputTargetV1,
    InputV1, LaneV1, LogLevel, StableAiContext, StableAiInit, StableClient, StableEffectType,
    StableExtension, StableHost, StableMatchHook, StableMod, StablePlayerAi, StableSim,
};

const MOD_ID: &str = "lol_mod";

const MOBA_MIN_TOWER_COUNT: usize = 6;
const MOBA_EXPECTED_PLAYER_COUNT: usize = 10;
const MOBA_EXPECTED_LANE_MASK: u8 = 0b1_1111;

#[derive(Clone, Copy, Debug, Default)]
struct CorruptMobaMatchGuard;

fn invalid_moba_structure(sim: &StableSim<'_>) -> Option<String> {
    let player_count = sim.player_count();
    let champion_count = sim.champion_count();
    if player_count != MOBA_EXPECTED_PLAYER_COUNT {
        return Some(format!("expected 10 players, found {player_count}"));
    }
    if champion_count != MOBA_EXPECTED_PLAYER_COUNT {
        return Some(format!("expected 10 champions, found {champion_count}"));
    }

    let mut team_counts = [0usize; 2];
    let mut lane_masks = [0u8; 2];
    let mut champion_ids = Vec::with_capacity(MOBA_EXPECTED_PLAYER_COUNT);
    for index in 0..player_count {
        let Some(player) = sim.player_at(index) else {
            return Some(format!("player_at({index}) is missing"));
        };
        let player_id = player.id();
        let team = player.team();
        if team > 1 {
            return Some(format!("player {player_id} has invalid team {team}"));
        }
        let Some(lane) = player.lane() else {
            return Some(format!("player {player_id} has no lane"));
        };
        let lane_bit = 1u8 << lane.code();
        if lane_masks[team] & lane_bit != 0 {
            return Some(format!(
                "team {team} assigns lane {} more than once",
                lane.code()
            ));
        }
        lane_masks[team] |= lane_bit;
        team_counts[team] += 1;

        let Some(champion) = player.champion() else {
            return Some(format!("player {player_id} has no champion entity"));
        };
        let champion_id = champion.id();
        if !champion.is_champion() {
            return Some(format!(
                "player {player_id} entity {champion_id} is not a champion"
            ));
        }
        if champion.team() != team {
            return Some(format!(
                "player {player_id} team {team} owns champion {champion_id} on team {}",
                champion.team()
            ));
        }
        if champion_ids.contains(&champion_id) {
            return Some(format!("champion entity {champion_id} is assigned twice"));
        }
        champion_ids.push(champion_id);
    }

    for team in 0..2 {
        if team_counts[team] != 5 {
            return Some(format!(
                "team {team} expected 5 players, found {}",
                team_counts[team]
            ));
        }
        if lane_masks[team] != MOBA_EXPECTED_LANE_MASK {
            return Some(format!(
                "team {team} lane mask is {:05b}, expected 11111",
                lane_masks[team]
            ));
        }
    }
    None
}

impl StableMatchHook for CorruptMobaMatchGuard {
    fn on_match_start(&self, sim: &mut StableSim<'_>) {
        let tower_count = sim.tower_count();

        // Other modes can legitimately be 1v1 or omit lanes. Only inspect a
        // map that has the regular MOBA tower topology and roughly a 5v5
        // population. This keeps valid live matches and custom modes intact.
        let looks_like_moba = tower_count >= MOBA_MIN_TOWER_COUNT;
        if !looks_like_moba {
            return;
        }

        if invalid_moba_structure(sim).is_some() {
            let seed = sim.seed();
            // A broken generated match would otherwise enter the base 0.5.8
            // plan_legacy AI and panic on its first unwrap. Resolve only that
            // structurally invalid match, deterministically, before tick one.
            sim.force_end(seed & 1 == 0);
        }
    }
}

const BP_RUNTIME_SCAN_INTERVAL_MICROS: u64 = 250_000;
const BP_RUNTIME_ROOT_PATHS: [&str; 3] = ["main", "top.main", "banpick.main"];
const BP_RUNTIME_MAX_PICK_SLOTS: usize = 12;
const BP_RUNTIME_MAX_CHAMPION_CARDS: usize = 256;

#[derive(Debug, Default)]
struct QualityBpExtension {
    elapsed_micros: AtomicU64,
}

fn join_ui_path(parent: &str, child: &str) -> String {
    if parent.is_empty() {
        child.to_string()
    } else {
        format!("{parent}.{child}")
    }
}

fn bp_champion_id_from_name(name: &str) -> Option<&'static str> {
    match name.trim() {
        "lol_shen" | "Shen" | "慎" | "シェン" | "쉔" => Some("lol_shen"),
        "archer" | "Lucian" | "卢锡安" | "路西恩" | "ルシアン" | "루시안" => {
            Some("archer")
        }
        "barrier_magician" | "Orianna" | "奥利安娜" | "奧利安娜" | "オリアナ" | "오리아나" => {
            Some("barrier_magician")
        }
        "berserker" | "Briar" | "贝蕾亚" | "貝蕾亞" | "ブライアー" | "브라이어" => {
            Some("berserker")
        }
        "boomerang_hunter" | "Sivir" | "希维尔" | "希維爾" | "シヴィア" | "시비르" => {
            Some("boomerang_hunter")
        }
        "cavalry_knight" | "Kled" | "克烈" | "クレッド" | "클레드" => {
            Some("cavalry_knight")
        }
        "dancer" | "Xayah" | "霞" | "剎雅" | "ザヤ" | "자야" => Some("dancer"),
        "demon" | "Urgot" | "厄加特" | "アーゴット" | "우르곳" => Some("demon"),
        "dual_blader" | "Yone" | "永恩" | "犽凝" | "ヨネ" | "요네" => Some("dual_blader"),
        _ => None,
    }
}

fn ensure_ui_child(client: &mut StableClient<'_>, parent: &str, child: &str, source: &str) -> bool {
    if !client.ui_exists(parent) {
        return false;
    }
    let child_path = join_ui_path(parent, child);
    client.ui_exists(&child_path) || client.ui_spawn_source(parent, source)
}

fn decorate_bp_shell(client: &mut StableClient<'_>, root: &str) {
    let background = join_ui_path(root, "background");
    ensure_ui_child(
        client,
        &background,
        "lol_bp_runtime_background",
        r#"lol_bp_runtime_background:image { ignore_event: true; width: 100%; height: 100%; z: -20; source: "asset/lol_mod/ui/banpick/lol_bp_background"; }"#,
    );

    let header = join_ui_path(root, "header");
    ensure_ui_child(
        client,
        &header,
        "lol_bp_runtime_header_chrome",
        r#"lol_bp_runtime_header_chrome:image { ignore_event: true; width: 100%; height: 100%; z: -10; source: "asset/lol_mod/ui/banpick/lol_bp_header_chrome"; }"#,
    );

    let bottom = join_ui_path(root, "bottom");
    ensure_ui_child(
        client,
        &bottom,
        "lol_bp_runtime_bottom_chrome",
        r#"lol_bp_runtime_bottom_chrome:image { ignore_event: true; width: 100%; height: 100%; z: -10; source: "asset/lol_mod/ui/banpick/lol_bp_bottom_chrome"; }"#,
    );

    ensure_ui_child(
        client,
        root,
        "lol_bp_runtime_filter_toolbar",
        r#"lol_bp_runtime_filter_toolbar:image { ignore_event: true; x: 305px; y: 55px; width: 1310px; height: 50px; z: -10; source: "asset/lol_mod/ui/banpick/lol_bp_filter_toolbar"; }"#,
    );

    let champion_grid = join_ui_path(root, "champions_bg");
    ensure_ui_child(
        client,
        &champion_grid,
        "lol_bp_runtime_champion_grid_frame",
        r#"lol_bp_runtime_champion_grid_frame:image { ignore_event: true; width: 100%; height: 100%; z: 80; source: "asset/lol_mod/ui/banpick/lol_bp_champion_grid_frame"; }"#,
    );

    let timer_icon = join_ui_path(root, "timer_area.timer_icon");
    ensure_ui_child(
        client,
        &timer_icon,
        "lol_bp_runtime_timer_icon",
        r#"lol_bp_runtime_timer_icon:image { ignore_event: true; width: 20px; height: 20px; z: 80; source: "asset/lol_mod/ui/banpick/lol_bp_timer_icon"; }"#,
    );
    let timer_bar = join_ui_path(root, "timer_area.timer_bar_bg");
    ensure_ui_child(
        client,
        &timer_bar,
        "lol_bp_runtime_timer_plate",
        r#"lol_bp_runtime_timer_plate:image { ignore_event: true; width: 220px; height: 20px; z: -5; source: "asset/lol_mod/ui/banpick/lol_bp_timer_plate"; }"#,
    );

    let stat = join_ui_path(root, "champion_info.stat");
    ensure_ui_child(
        client,
        &stat,
        "lol_bp_runtime_stat_frame",
        r#"lol_bp_runtime_stat_frame:image { ignore_event: true; width: 100%; height: 100%; z: 80; source: "asset/lol_mod/ui/banpick/lol_bp_stat_frame"; }"#,
    );
    for skill in ["skill1", "skill2", "ult"] {
        let skill_path = join_ui_path(root, &format!("champion_info.{skill}"));
        ensure_ui_child(
            client,
            &skill_path,
            "lol_bp_runtime_skill_frame",
            r#"lol_bp_runtime_skill_frame:image { ignore_event: true; x: -10px; y: -10px; width: 100%; height: 200px; z: 80; source: "asset/lol_mod/ui/banpick/lol_bp_skill_frame"; }"#,
        );
    }
}

fn decorate_bp_champion_cards(client: &mut StableClient<'_>, root: &str) {
    let contents = join_ui_path(root, "champions.contents");
    for child in client
        .ui_child_names(&contents)
        .into_iter()
        .take(BP_RUNTIME_MAX_CHAMPION_CARDS)
    {
        let card = join_ui_path(&contents, &child);
        ensure_ui_child(
            client,
            &card,
            "lol_bp_runtime_champion_card_frame",
            r#"lol_bp_runtime_champion_card_frame:image { ignore_event: true; width: 100%; height: 100%; z: 90; source: "asset/lol_mod/ui/banpick/lol_bp_champion_card_frame"; }"#,
        );
    }
}

fn sync_bp_pick_container(client: &mut StableClient<'_>, root: &str, side: &str) {
    let container = join_ui_path(root, &format!("{side}_picks"));
    for child in client
        .ui_child_names(&container)
        .into_iter()
        .take(BP_RUNTIME_MAX_PICK_SLOTS)
    {
        let slot = join_ui_path(&container, &child);
        ensure_ui_child(
            client,
            &slot,
            "lol_bp_runtime_side_pick_frame",
            r#"lol_bp_runtime_side_pick_frame:image { ignore_event: true; width: 100%; height: 100%; z: 90; source: "asset/lol_mod/ui/banpick/lol_bp_side_pick_frame"; }"#,
        );

        let done = join_ui_path(&slot, "done");
        if !client.ui_exists(&done) {
            continue;
        }
        ensure_ui_child(
            client,
            &done,
            "lol_bp_runtime_illustration",
            r#"lol_bp_runtime_illustration:image { ignore_event: true; x: 8px; y: 1px; width: 284px; height: 172px; visible: false; sample_linear: true; z: -20; }"#,
        );
        let tint_source = if side == "red" {
            r#"lol_bp_runtime_illustration_tint:color { ignore_event: true; x: 145px; width: 147px; height: 174px; visible: false; color: #07080ba8; z: -10; }"#
        } else {
            r#"lol_bp_runtime_illustration_tint:color { ignore_event: true; width: 158px; height: 174px; visible: false; color: #07080ba8; z: -10; }"#
        };
        ensure_ui_child(
            client,
            &done,
            "lol_bp_runtime_illustration_tint",
            tint_source,
        );

        let name = client.ui_text(&join_ui_path(&done, "name"));
        let illustration = join_ui_path(&done, "lol_bp_runtime_illustration");
        let tint = join_ui_path(&done, "lol_bp_runtime_illustration_tint");
        let champion = join_ui_path(&done, "champion");
        if let Some(champion_id) = name.as_deref().and_then(bp_champion_id_from_name) {
            let source = format!(
                "source: \"asset/lol_mod/ui/banpick/champion_illustration/{champion_id}_{side}\"; sample_linear: true;"
            );
            client.ui_set_properties(&illustration, &source);
            client.ui_set_visible(&illustration, true);
            client.ui_set_visible(&tint, true);
            client.ui_set_visible(&champion, false);
        } else if client.ui_visible(&illustration) == Some(true) {
            client.ui_set_visible(&illustration, false);
            client.ui_set_visible(&tint, false);
            client.ui_set_visible(&champion, true);
        }
    }
}

fn sync_bp_runtime_ui(client: &mut StableClient<'_>) {
    for root in BP_RUNTIME_ROOT_PATHS {
        let blue_picks = join_ui_path(root, "blue_picks");
        let red_picks = join_ui_path(root, "red_picks");
        if !client.ui_exists(&blue_picks) || !client.ui_exists(&red_picks) {
            continue;
        }
        decorate_bp_shell(client, root);
        decorate_bp_champion_cards(client, root);
        sync_bp_pick_container(client, root, "blue");
        sync_bp_pick_container(client, root, "red");
    }
}

// ChampionInfoUIRunner owns the texture AND its UV rectangle. The public
// champion-icon API helper uses the FACE camera, so it must not be called
// here. Only scale the already-resolved image layout, preserving its source,
// UVs, clipping, visibility, and parent scroll transform.
//
// Stock 0.5.8: set_champion_icon_center(85, 93, 2). Yone's fitted node is
// 85x93, Xayah's is 54x93. A uniform 0.75 layout factor gives 1.5x pixels:
// 57 / 58.5 px full-body heights. The source cameras are independently
// checked by qa_encyclopedia_geometry.py. Do not multiply the current rect:
// this runs every frame, including after search/filter rebuilds.
fn fit_encyclopedia_native_layout(client: &mut StableClient<'_>) {
    if client.client_main_tab().as_deref() != Some("GameInfo") {
        return;
    }
    for container in [
        "main.top.right.champion_info.data.champions.contents",
        "body.main.top.right.champion_info.data.champions.contents",
        "body.top.right.champion_info.data.champions.contents",
        "top.right.champion_info.data.champions.contents",
        "body.main.right.champion_info.data.champions.contents",
        "main.right.champion_info.data.champions.contents",
    ] {
        if !client.ui_exists(container) {
            continue;
        }
        for (champion, width) in [("dual_blader", 63.75_f32), ("dancer", 40.5_f32)] {
            let icon = join_ui_path(&join_ui_path(container, champion), "icon");
            if client.ui_runner_name(&icon).as_deref() != Some("image") {
                continue;
            }
            let _ = client.ui_set_properties(
                &icon,
                &format!("width: {width}px; height: 69.75px; y: 76px;"),
            );
        }
        break;
    }
}

impl StableExtension for QualityBpExtension {
    fn post_update(&self, client: &mut StableClient<'_>, dt_micros: u64) {
        fit_encyclopedia_native_layout(client);
        let previous = self.elapsed_micros.fetch_add(dt_micros, Ordering::Relaxed);
        if previous.saturating_add(dt_micros) < BP_RUNTIME_SCAN_INTERVAL_MICROS {
            return;
        }
        self.elapsed_micros.store(0, Ordering::Relaxed);

        sync_bp_runtime_ui(client);
    }
}

const XAYAH_FEATHER_STATE_TTL_TICKS: usize = 600;
const XAYAH_FEATHER_MAX_STATES: usize = 128;
const XAYAH_AI_MIN_RECALL_FEATHERS: u8 = 2;

#[derive(Debug)]
struct XayahFeatherUnitState {
    simulation_seed: u64,
    unit_id: usize,
    player_id: usize,
    team: usize,
    lane: Option<LaneV1>,
    count: u8,
    updated_tick: usize,
    expiry_tick: usize,
}

static XAYAH_AI_FEATHER_STATE: OnceLock<Mutex<Vec<XayahFeatherUnitState>>> = OnceLock::new();

fn xayah_ai_feather_state() -> &'static Mutex<Vec<XayahFeatherUnitState>> {
    XAYAH_AI_FEATHER_STATE.get_or_init(|| Mutex::new(Vec::new()))
}

fn xayah_player_for_caster(
    sim: &StableSim<'_>,
    caster_id: usize,
) -> Option<(usize, usize, Option<LaneV1>, usize)> {
    for index in 0..sim.player_count() {
        let Some(player) = sim.player_at(index) else {
            continue;
        };
        let Some(champion) = player.champion() else {
            continue;
        };
        if champion.id() == caster_id {
            return Some((player.id(), player.team(), player.lane(), champion.id()));
        }
    }
    None
}

fn is_xayah_name(name: &str) -> bool {
    matches!(name, "dancer" | "Xayah" | "霞" | "剎雅" | "ザヤ" | "자야")
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

impl StableEffectType for XayahFeatherAiStateEffect {
    fn apply(
        &self,
        sim: &mut StableSim<'_>,
        _rng_seed: u64,
        caster_id: usize,
        _input: InputTargetV1,
    ) {
        let Some((player_id, team, lane, unit_id)) = xayah_player_for_caster(sim, caster_id) else {
            return;
        };
        let simulation_seed = sim.seed();
        let now = sim.tick();
        let Ok(mut states) = xayah_ai_feather_state().lock() else {
            return;
        };
        states.retain(|state| {
            state.simulation_seed != simulation_seed
                || state.expiry_tick > now
                || state.unit_id == unit_id
        });

        if matches!(self.change, XayahFeatherStateChange::Clear) {
            states.retain(|state| {
                state.simulation_seed != simulation_seed || state.unit_id != unit_id
            });
            return;
        }

        let state_index = states
            .iter()
            .position(|state| state.simulation_seed == simulation_seed && state.unit_id == unit_id);
        let state = if let Some(index) = state_index {
            &mut states[index]
        } else {
            if states.len() >= XAYAH_FEATHER_MAX_STATES {
                if let Some((oldest, _)) = states
                    .iter()
                    .enumerate()
                    .min_by_key(|(_, state)| state.updated_tick)
                {
                    states.remove(oldest);
                }
            }
            states.push(XayahFeatherUnitState {
                simulation_seed,
                unit_id,
                player_id,
                team,
                lane,
                count: 0,
                updated_tick: now,
                expiry_tick: now,
            });
            let Some(state) = states.last_mut() else {
                return;
            };
            state
        };
        if state.expiry_tick <= now {
            state.count = 0;
        }
        state.player_id = player_id;
        state.team = team;
        state.lane = lane;
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

impl StablePlayerAi for XayahFeatherInputGate {
    fn clone_box(&self) -> Box<dyn StablePlayerAi> {
        Box::new(self.clone())
    }

    fn id(&self) -> String {
        "lol_xayah_feather_input_gate".to_string()
    }

    fn matches(&self, init: &StableAiInit) -> bool {
        is_xayah_name(&init.champion_name)
    }

    fn think(
        &mut self,
        ctx: &mut StableAiContext<'_>,
        base_input: Option<InputV1>,
    ) -> Option<InputV1> {
        if !ctx.champion_name().as_deref().is_some_and(is_xayah_name) {
            return None;
        }
        let base_input = base_input?;
        if base_input.kind != InputKindV1::Skill2.code() {
            return None;
        }

        let simulation_seed = ctx.sim().map(|sim| sim.seed()).unwrap_or(0);
        let player_id = ctx.player_id();
        let team = ctx.team();
        let lane = ctx.lane();
        let now = ctx.tick();
        let feather_count = xayah_ai_feather_state()
            .lock()
            .map(|mut states| {
                states.retain(|state| {
                    state.simulation_seed != simulation_seed || state.expiry_tick > now
                });
                states
                    .iter()
                    .filter(|state| {
                        state.simulation_seed == simulation_seed
                            && state.player_id == player_id
                            && state.team == team
                            && state.lane == lane
                            && state.updated_tick <= now
                    })
                    .max_by_key(|state| state.updated_tick)
                    .map(|state| state.count)
                    .unwrap_or(0)
            })
            .unwrap_or(0);
        if feather_count >= XAYAH_AI_MIN_RECALL_FEATHERS {
            return None;
        }

        Some(InputV1::action(InputKindV1::Attack, base_input.target))
    }
}

const URGOT_PASSIVE_COOLDOWN_TICKS: usize = 120;
const URGOT_PASSIVE_STATE_TTL_TICKS: usize = 3600;
const URGOT_PASSIVE_MAX_STATES: usize = 128;
const URGOT_PASSIVE_FLAT_DAMAGE: usize = 20;
const URGOT_PASSIVE_ATTACK_RATIO_PERCENT: usize = 30;
const URGOT_PASSIVE_TARGET_MAX_HP_PERCENT: usize = 2;
const URGOT_R_EXECUTE_THRESHOLD_PERCENT: usize = 25;

#[derive(Debug)]
struct UrgotPassiveCooldown {
    simulation_seed: u64,
    caster_id: usize,
    ready_tick: usize,
    last_seen_tick: usize,
    last_access_serial: u64,
}

static URGOT_PASSIVE_COOLDOWNS: OnceLock<Mutex<Vec<UrgotPassiveCooldown>>> = OnceLock::new();
static URGOT_PASSIVE_ACCESS_SERIAL: AtomicU64 = AtomicU64::new(1);

fn next_urgot_passive_access_serial() -> u64 {
    URGOT_PASSIVE_ACCESS_SERIAL.fetch_add(1, Ordering::Relaxed)
}

fn urgot_passive_cooldowns() -> &'static Mutex<Vec<UrgotPassiveCooldown>> {
    URGOT_PASSIVE_COOLDOWNS.get_or_init(|| Mutex::new(Vec::new()))
}

#[derive(Clone, Copy, Debug, Default)]
struct UrgotPassiveNativeEffect;

impl StableEffectType for UrgotPassiveNativeEffect {
    fn apply(
        &self,
        sim: &mut StableSim<'_>,
        _rng_seed: u64,
        caster_id: usize,
        input: InputTargetV1,
    ) {
        if input.kind != InputTargetKindV1::Target.code() {
            return;
        }
        let target_id = input.target_id;
        let Some((caster_attack, true)) = sim
            .get_entity(caster_id)
            .map(|caster| (caster.stat().attack, caster.is_alive()))
        else {
            return;
        };
        let Some(((_, target_max_hp), true)) = sim
            .get_entity(target_id)
            .map(|target| (target.hp(), target.is_alive()))
        else {
            return;
        };
        if target_max_hp == 0 {
            return;
        }

        let simulation_seed = sim.seed();
        let now = sim.tick();
        let Ok(mut cooldowns) = urgot_passive_cooldowns().lock() else {
            return;
        };
        cooldowns.retain(|cooldown| {
            cooldown.simulation_seed != simulation_seed
                || now < cooldown.last_seen_tick
                || now.saturating_sub(cooldown.last_seen_tick) <= URGOT_PASSIVE_STATE_TTL_TICKS
        });
        let access_serial = next_urgot_passive_access_serial();
        if let Some(cooldown) = cooldowns.iter_mut().find(|cooldown| {
            cooldown.simulation_seed == simulation_seed && cooldown.caster_id == caster_id
        }) {
            let timeline_restarted = now < cooldown.last_seen_tick;
            cooldown.last_seen_tick = now;
            cooldown.last_access_serial = access_serial;
            if !timeline_restarted && now < cooldown.ready_tick {
                return;
            }
            cooldown.ready_tick = now.saturating_add(URGOT_PASSIVE_COOLDOWN_TICKS);
        } else {
            if cooldowns.len() >= URGOT_PASSIVE_MAX_STATES {
                if let Some((oldest_index, _)) = cooldowns
                    .iter()
                    .enumerate()
                    .min_by_key(|(_, cooldown)| cooldown.last_access_serial)
                {
                    cooldowns.remove(oldest_index);
                }
            }
            cooldowns.push(UrgotPassiveCooldown {
                simulation_seed,
                caster_id,
                ready_tick: now.saturating_add(URGOT_PASSIVE_COOLDOWN_TICKS),
                last_seen_tick: now,
                last_access_serial: access_serial,
            });
        }
        drop(cooldowns);

        let damage = URGOT_PASSIVE_FLAT_DAMAGE
            .saturating_add(caster_attack.saturating_mul(URGOT_PASSIVE_ATTACK_RATIO_PERCENT) / 100)
            .saturating_add(
                target_max_hp.saturating_mul(URGOT_PASSIVE_TARGET_MAX_HP_PERCENT) / 100,
            );
        sim.deal_damage(caster_id, target_id, damage, 0, AttackTypeV1::Skill);
    }
}

#[derive(Clone, Copy, Debug, Default)]
struct UrgotRCheckNativeEffect;

impl StableEffectType for UrgotRCheckNativeEffect {
    fn apply(
        &self,
        sim: &mut StableSim<'_>,
        _rng_seed: u64,
        caster_id: usize,
        input: InputTargetV1,
    ) {
        if input.kind != InputTargetKindV1::Target.code() {
            return;
        }
        let target_id = input.target_id;
        let Some(((target_hp, target_max_hp), true)) = sim
            .get_entity(target_id)
            .map(|target| (target.hp(), target.is_alive()))
        else {
            return;
        };
        if target_max_hp == 0 {
            return;
        }
        let execute_limit = target_max_hp.saturating_mul(URGOT_R_EXECUTE_THRESHOLD_PERCENT) / 100;
        if target_hp > execute_limit
            || !sim
                .get_entity(caster_id)
                .is_some_and(|caster| caster.is_alive())
        {
            return;
        }

        sim.add_buff(caster_id, &BuffV1::timed("lol_urgot_r_execute_ready", 2));
    }
}

#[derive(Clone, Copy, Debug, Default)]
struct UrgotRExecuteNativeEffect;

impl StableEffectType for UrgotRExecuteNativeEffect {
    fn apply(
        &self,
        sim: &mut StableSim<'_>,
        _rng_seed: u64,
        caster_id: usize,
        input: InputTargetV1,
    ) {
        if input.kind != InputTargetKindV1::Target.code() {
            return;
        }
        let target_id = input.target_id;
        let Some(((target_hp, target_max_hp), target_shield, true)) = sim
            .get_entity(target_id)
            .map(|target| (target.hp(), target.shield(), target.is_alive()))
        else {
            return;
        };
        if target_max_hp == 0
            || !sim
                .get_entity(caster_id)
                .is_some_and(|caster| caster.is_alive())
        {
            return;
        }

        let lethal_damage = target_hp
            .saturating_add(target_shield)
            .saturating_add(target_max_hp);
        sim.deal_damage(caster_id, target_id, lethal_damage, 0, AttackTypeV1::Skill);
        if sim
            .get_entity(target_id)
            .is_some_and(|target| target.is_alive())
            || !sim
                .get_entity(caster_id)
                .is_some_and(|caster| caster.is_alive())
        {
            return;
        }

        sim.add_buff(caster_id, &BuffV1::timed("lol_urgot_r_execute_success", 2));
    }
}

#[derive(Clone, Copy, Debug, Default)]
struct LegacySavedNativeCompatibilityEffect;

impl StableEffectType for LegacySavedNativeCompatibilityEffect {
    fn apply(
        &self,
        _sim: &mut StableSim<'_>,
        _rng_seed: u64,
        _caster_id: usize,
        _input: InputTargetV1,
    ) {
    }
}

fn init(host: &StableHost) -> StableMod {
    let version = host.game_version();
    host.log(
        LogLevel::Info,
        &format!(
            "lol_mod stable ABI loaded on game {}.{}.{} (host ABI {}; mod version {}; corrupt 5v5 pre-tick guard active)",
            version.major,
            version.minor,
            version.patch,
            host.abi_level(),
            env!("CARGO_PKG_VERSION"),
        ),
    );

    let mut registration = StableMod::new(MOD_ID);
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
    for retired_name in [
        "lol_yone_w_cone_native",
        "lol_yone_w_begin_native",
        "lol_yone_w_collect_hit_native",
        "lol_yone_w_settle_native",
        "lol_yone_e_start_native",
        "lol_yone_e_begin_return_native",
        "lol_yone_e_damage_pre_native",
        "lol_yone_e_damage_post_native",
        "lol_yone_e_settle_native",
    ] {
        registration.add_native_effect(retired_name, LegacySavedNativeCompatibilityEffect);
    }
    // Pre-0.12.6 saves/custom databases can still embed the retired Shadow
    // Dash data tree even though the active lol_shen data now exposes Q/W/R.
    // Keep only the two referenced native names loadable.  Binding them to
    // the same empty compatibility effect deliberately does not restore the
    // old input rewrite, dash hint, damage, or taunt implementation.
    registration.add_native_effect(
        "lol_shen_shadow_dash_ai_hint_native",
        LegacySavedNativeCompatibilityEffect,
    );
    registration.add_native_effect(
        "lol_shen_shadow_dash_taunt_native",
        LegacySavedNativeCompatibilityEffect,
    );
    registration.add_player_input_ai(XayahFeatherInputGate);
    registration.add_native_effect("lol_urgot_passive_native", UrgotPassiveNativeEffect);
    registration.add_native_effect("lol_urgot_r_check_native", UrgotRCheckNativeEffect);
    registration.add_native_effect("lol_urgot_r_execute_native", UrgotRExecuteNativeEffect);
    registration.set_match_hook(CorruptMobaMatchGuard);
    registration.set_extension(QualityBpExtension::default());
    registration
}

declare_stable_mod!(init, requires = mod_api_stable::ABI_LEVEL);
