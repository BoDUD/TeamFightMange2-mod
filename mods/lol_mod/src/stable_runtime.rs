//! Stable-ABI runtime for Teamfight Manager 2 0.5.7 and later.
//!
//! `src/lib.rs` is retained as the classic Mod API 0.8 migration reference,
//! but Cargo deliberately builds only this file. Only the frozen `*V1` value
//! types and size-guarded stable host tables cross the DLL boundary.

use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Mutex, OnceLock};

use mod_api_stable::{
    declare_stable_mod, AttackTypeV1, BuffV1, CcKindV1, CcV1, InputKindV1, InputTargetKindV1,
    InputTargetV1, InputV1, LaneV1, LogLevel, StableAiContext, StableAiInit, StableEffectType,
    StableHost, StableMod, StablePlayerAi, StableSim,
};

const MOD_ID: &str = "lol_mod";

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

const SHEN_SHADOW_DASH_TAUNT_TICKS: u64 = 90;

#[derive(Clone, Copy, Debug, Default)]
struct ShenShadowDashAiHintNativeEffect;

impl StableEffectType for ShenShadowDashAiHintNativeEffect {
    fn apply(
        &self,
        _sim: &mut StableSim<'_>,
        _rng_seed: u64,
        _caster_id: usize,
        _input: InputTargetV1,
    ) {
    }

    fn expected_cc_time(&self) -> Option<usize> {
        Some(SHEN_SHADOW_DASH_TAUNT_TICKS as usize)
    }
}

#[derive(Clone, Copy, Debug, Default)]
struct ShenShadowDashTauntNativeEffect;

impl StableEffectType for ShenShadowDashTauntNativeEffect {
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
        if !sim
            .get_entity(caster_id)
            .is_some_and(|caster| caster.is_alive())
            || !sim
                .get_entity(target_id)
                .is_some_and(|target| target.is_alive())
        {
            return;
        }

        let cc = CcV1 {
            kind: CcKindV1::Taunt.code(),
            tick: SHEN_SHADOW_DASH_TAUNT_TICKS,
            target: caster_id,
            ..CcV1::default()
        };
        sim.apply_cc(target_id, &cc);
    }

    fn expected_cc_time(&self) -> Option<usize> {
        Some(SHEN_SHADOW_DASH_TAUNT_TICKS as usize)
    }
}

fn is_shen_name(name: &str) -> bool {
    matches!(name, "lol_shen" | "Shen" | "慎")
}

#[derive(Clone, Debug, Default)]
struct ShenShadowDashInputAi;

impl StablePlayerAi for ShenShadowDashInputAi {
    fn clone_box(&self) -> Box<dyn StablePlayerAi> {
        Box::new(self.clone())
    }

    fn id(&self) -> String {
        "lol_shen_shadow_dash_input_ai".to_string()
    }

    fn matches(&self, init: &StableAiInit) -> bool {
        is_shen_name(&init.champion_name)
    }

    fn think(
        &mut self,
        ctx: &mut StableAiContext<'_>,
        base_input: Option<InputV1>,
    ) -> Option<InputV1> {
        if !ctx.champion_name().as_deref().is_some_and(is_shen_name) {
            return None;
        }
        let base_input = base_input?;
        if !matches!(
            InputKindV1::from_code(base_input.kind),
            Some(InputKindV1::Skill | InputKindV1::Attack)
        ) {
            return None;
        }
        let shadow_dash = InputV1::action(InputKindV1::Skill2, base_input.target);
        ctx.is_valid_input(&shadow_dash).then_some(shadow_dash)
    }
}

const YONE_W_RANGE: i128 = 42_000;
const YONE_W_COS_SQ_SCALE: i128 = 1_000_000;
const YONE_W_COS_SQ_HALF_ANGLE: i128 = 586_824;
const YONE_W_FLAT_DAMAGE: usize = 35;
const YONE_W_ATTACK_RATIO_PERCENT: usize = 45;
const YONE_W_TARGET_MAX_HP_PERCENT: usize = 6;
const YONE_W_MAX_ENEMY_CHAMPIONS: usize = 5;

#[derive(Clone, Copy, Debug, Default)]
struct YoneSpiritCleaveConeNativeEffect;

impl StableEffectType for YoneSpiritCleaveConeNativeEffect {
    fn apply(
        &self,
        sim: &mut StableSim<'_>,
        _rng_seed: u64,
        caster_id: usize,
        input: InputTargetV1,
    ) {
        let Some((caster_pos, caster_team, caster_attack, true)) =
            sim.get_entity(caster_id).map(|caster| {
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
        let (dir_x, dir_y) = match InputTargetKindV1::from_code(input.kind) {
            Some(InputTargetKindV1::Dir) => (i128::from(input.dir_x), i128::from(input.dir_y)),
            Some(InputTargetKindV1::Pos) => (
                i128::from(input.x) - i128::from(caster_pos.0),
                i128::from(input.y) - i128::from(caster_pos.1),
            ),
            Some(InputTargetKindV1::Target) => {
                let Some(target_pos) = sim.get_entity(input.target_id).map(|target| target.pos())
                else {
                    return;
                };
                (
                    i128::from(target_pos.0) - i128::from(caster_pos.0),
                    i128::from(target_pos.1) - i128::from(caster_pos.1),
                )
            }
            _ => return,
        };
        if dir_x == 0 && dir_y == 0 {
            return;
        }

        let dir_sq = dir_x * dir_x + dir_y * dir_y;
        let mut hits: Vec<(usize, usize)> = Vec::new();
        let mut champion_hits = 0usize;
        for index in 0..sim.entity_count() {
            let Some(target) = sim.entity_at(index) else {
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
            let dx = i128::from(target_pos.0) - i128::from(caster_pos.0);
            let dy = i128::from(target_pos.1) - i128::from(caster_pos.1);
            let distance_sq = dx * dx + dy * dy;
            let hit_range = YONE_W_RANGE + target.radius() as i128;
            if distance_sq > hit_range * hit_range {
                continue;
            }

            let dot = dx * dir_x + dy * dir_y;
            if dot <= 0
                || dot * dot * YONE_W_COS_SQ_SCALE < distance_sq * dir_sq * YONE_W_COS_SQ_HALF_ANGLE
            {
                continue;
            }

            let target_max_hp = target.hp().1;
            let damage = YONE_W_FLAT_DAMAGE
                .saturating_add(caster_attack.saturating_mul(YONE_W_ATTACK_RATIO_PERCENT) / 100)
                .saturating_add(target_max_hp.saturating_mul(YONE_W_TARGET_MAX_HP_PERCENT) / 100);
            champion_hits += usize::from(target.is_champion());
            hits.push((target_id, damage));
        }
        if hits.is_empty() {
            return;
        }

        for (target_id, damage) in hits {
            sim.deal_damage(caster_id, target_id, damage, 0, AttackTypeV1::Skill);
        }
        if !sim
            .get_entity(caster_id)
            .is_some_and(|caster| caster.is_alive())
        {
            return;
        }

        let shield_tier = champion_hits.min(YONE_W_MAX_ENEMY_CHAMPIONS);
        sim.add_buff(
            caster_id,
            &BuffV1::timed(&format!("lol_yone_w_shield_tier_{shield_tier}"), 3),
        );
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
            "lol_mod stable ABI loaded on game {}.{}.{} (host ABI {}; mod version {})",
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
    registration.add_native_effect("lol_yone_w_cone_native", YoneSpiritCleaveConeNativeEffect);
    for retired_name in [
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
    registration.add_player_input_ai(XayahFeatherInputGate);
    registration.add_native_effect("lol_urgot_passive_native", UrgotPassiveNativeEffect);
    registration.add_native_effect("lol_urgot_r_check_native", UrgotRCheckNativeEffect);
    registration.add_native_effect("lol_urgot_r_execute_native", UrgotRExecuteNativeEffect);
    registration.add_native_effect(
        "lol_shen_shadow_dash_ai_hint_native",
        ShenShadowDashAiHintNativeEffect,
    );
    registration.add_native_effect(
        "lol_shen_shadow_dash_taunt_native",
        ShenShadowDashTauntNativeEffect,
    );
    registration.add_player_input_ai(ShenShadowDashInputAi);
    registration
}

declare_stable_mod!(init);
