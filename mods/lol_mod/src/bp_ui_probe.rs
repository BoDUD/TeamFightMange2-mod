//! Read-only, opt-in developer build: inspect the real BP UI contract before
//! inventing a swap-identity resolver. No input, save, UI mutation or network.
use mod_api_stable::StableClient;
use std::sync::{Mutex, OnceLock};

#[derive(Default)]
struct Probe {
    micros: u64,
    last: String,
    serial: u32,
}
static STATE: OnceLock<Mutex<Probe>> = OnceLock::new();

fn walk(client: &StableClient<'_>, path: &str, depth: usize, lines: &mut Vec<String>) {
    if lines.len() >= 1800 || !client.ui_exists(path) { return; }
    // Athlete detail/proficiency trees drown out the champion identity nodes.
    if path.ends_with(".popup") || path.ends_with(".player_tooltip")
        || path.contains(".name_slot") { return; }
    let runner = client.ui_runner_name(path);
    // Athlete-name labels are irrelevant to champion identity and omitted.
    let text = if path.ends_with(".name") { None } else { client.ui_text(path) };
    lines.push(format!("{path}\trunner={runner:?}\tvisible={:?}\trect={:?}\tstate={:?}\ttext={text:?}",
        client.ui_visible(path), client.ui_node_rect(path),
        if path.ends_with(".name") { None } else { client.ui_state_json(path) }));
    if depth == 0 { return; }
    for child in client.ui_child_names(path).into_iter().take(256) {
        walk(client, &format!("{path}.{child}"), depth - 1, lines);
    }
}

pub fn observe(client: &StableClient<'_>, elapsed: u64) {
    let Ok(mut state) = STATE.get_or_init(|| Mutex::new(Probe::default())).lock() else { return; };
    state.micros = state.micros.saturating_add(elapsed);
    if state.micros < 1_000_000 || state.serial >= 200 { return; }
    state.micros = 0;
    for root in ["main", "top.main", "banpick.main"] {
        if !client.ui_exists(&format!("{root}.blue_picks")) { continue; }
        // Record selected cards, not animated timers/showcase popups which
        // previously exhausted the budget before the first hero was picked.
        if !(0..5).any(|slot| client.ui_visible(&format!("{root}.blue_picks.pick_slot_{slot}.done")) == Some(true)) { return; }
        let mut rows = Vec::new();
        walk(client, &format!("{root}.swap"), 0, &mut rows);
        for side in ["blue", "red"] {
            for slot in 0..5 {
                let path = format!("{root}.{side}_picks.pick_slot_{slot}");
                walk(client, &path, 1, &mut rows);
                walk(client, &format!("{path}.done"), 4, &mut rows);
            }
        }
        let body = rows.join("\n");
        if body == state.last { return; }
        // Exists only in explicitly compiled QA builds and stays OUTSIDE mods.
        let dir = std::path::Path::new("mod_backups/bp_native_selected_probe_20260905");
        if std::fs::create_dir_all(dir).is_err() { return; }
        let target = dir.join(format!("snapshot_{:02}.txt", state.serial));
        if std::fs::write(target, &body).is_ok() {
            state.last = body;
            state.serial += 1;
        }
        return;
    }
}
