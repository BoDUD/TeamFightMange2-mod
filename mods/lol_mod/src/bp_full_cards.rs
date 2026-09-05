//! Native-owned BP portraits. Never infer identity from dimensions or draft order.
//! All registered heroes have a three-region PNG; its middle is the native
//! preview and its outer regions are the blue/red 284x172 side cards.
use mod_api_stable::StableClient;
use std::sync::OnceLock;

const CATALOG: &str = include_str!("../ui/bp_full_cards/catalog.txt");
const BLUE_ICON: &str = "x: 0px; y: 0px; width: 284px; height: 172px; anchor_x: 0; anchor_y: 0; pivot_x: 0; pivot_y: 0; flip_x: false; rect: { x: 0; y: 0.03260869565; w: 0.27734375; h: 0.9347826087; }";
const RED_ICON: &str = "x: 0px; y: 0px; width: 284px; height: 172px; anchor_x: 0; anchor_y: 0; pivot_x: 0; pivot_y: 0; flip_x: false; rect: { x: 0.72265625; y: 0.03260869565; w: 0.27734375; h: 0.9347826087; }";
const FRAME: &str = "x: 8px; y: 1px; width: 284px; height: 172px; z: 100;";

fn installed_catalog_ready() -> bool {
    static READY: OnceLock<bool> = OnceLock::new();
    *READY.get_or_init(|| {
        let Ok(exe) = std::env::current_exe() else { return false; };
        let Some(root) = exe.parent() else { return false; };
        let directory = root.join("mods/lol_mod/banpick_illustrations");
        CATALOG.lines().all(|id| {
            use std::io::Read;
            let Ok(mut file) = std::fs::File::open(directory.join(format!("{id}.png"))) else {return false;};
            let mut header = [0u8; 24];
            file.read_exact(&mut header).is_ok()
                && &header[..8] == b"\x89PNG\r\n\x1a\n"
                && u32::from_be_bytes(header[16..20].try_into().unwrap()) == 1024
                && u32::from_be_bytes(header[20..24].try_into().unwrap()) == 184
        })
    })
}

/// Returns false without mutations if the package is incomplete or the active
/// roster is newer than the authored catalog. Caller can retain stock fallback.
pub fn sync(client: &mut StableClient<'_>, root: &str) -> bool {
    if !installed_catalog_ready() { return false; }
    let champions = client.champion_names();
    if champions.is_empty() || champions.iter().any(|id| !CATALOG.lines().any(|known| known == id)) {
        return false;
    }
    for side in ["blue", "red"] {
        let picks = format!("{root}.{side}_picks");
        for slot in client.ui_child_names(&picks).into_iter().take(12) {
            if !slot.starts_with("pick_slot_") {continue;}
            let done = format!("{picks}.{slot}.done");
            if client.ui_visible(&done) != Some(true) {continue;}
            let actor = format!("{done}.champion");
            let icon = format!("{actor}.icon");
            if client.ui_runner_name(&icon).as_deref() != Some("image") {continue;}
            // The source is set by the game on every native assignment refresh.
            // Only choose a region within that same texture, on BOTH stages.
            let _ = client.ui_set_properties(&icon, if side == "blue" {BLUE_ICON} else {RED_ICON});
            let _ = client.ui_set_properties(&actor, FRAME);
            let _ = client.ui_set_visible(&actor, true);
            let _ = client.ui_set_visible(&format!("{done}.lol_bp_illustrations"), false);
        }
    }
    true
}
