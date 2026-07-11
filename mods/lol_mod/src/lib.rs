use game_view::MatchUIRunner;
use mod_api::*;

const PICK_SLOT_LIMIT: usize = 5;
const SPLASH_NODES: [(&str, &str); 5] = [
    ("lol_shen", "lol_splash_shen"),
    ("archer", "lol_splash_lucian"),
    ("barrier_magician", "lol_splash_orianna"),
    ("berserker", "lol_splash_briar"),
    ("boomerang_hunter", "lol_splash_sivir"),
];

struct LolModExtension;

impl ModExtension for LolModExtension {
    fn post_update(&self, _scene: &mut Scene, ui: &mut GameUI, _assets: &mut Assets, _dt: f32) {
        // MatchUIRunner owns the authoritative pick order. Clone it before
        // mutating child nodes so no runner borrow overlaps the UI tree borrow.
        let picks = ui
            .root
            .runner_as_mut::<MatchUIRunner>()
            .map(|runner| (runner.team1_pick.clone(), runner.team2_pick.clone()));

        let Some((blue_picks, red_picks)) = picks else {
            sync_encyclopedia_portraits(&mut ui.root);
            return;
        };

        sync_side(&mut ui.root, "blue", &blue_picks);
        sync_side(&mut ui.root, "red", &red_picks);
    }
}

fn sync_encyclopedia_portraits(root: &mut Node) {
    for (champion_id, portrait_node) in [
        ("lol_shen", "lol_fullbody_shen"),
        ("archer", "lol_fullbody_lucian"),
        ("barrier_magician", "lol_fullbody_orianna"),
        ("berserker", "lol_fullbody_briar"),
        ("boomerang_hunter", "lol_fullbody_sivir"),
    ] {
        let prefix = format!("data.champions.contents.{champion_id}");
        if root.query_mut(&prefix).is_none() {
            continue;
        }

        set_visible(root, &format!("{prefix}.icon"), false);
        set_visible(root, &format!("{prefix}.{portrait_node}"), true);
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
    }
}

fn init(_ctx: &GameCtx) -> ModRegistration {
    let mut registration = ModRegistration::new("lol_mod");
    registration.set_extension(LolModExtension);
    registration
}

declare_mod!(init);
