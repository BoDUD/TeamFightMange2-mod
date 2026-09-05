//! BP presentation only. Never infer a champion from the athlete-name label.
//! Kept host-independent so the actual resolver and fallback run in tests.

pub const HEROES: [&str; 9] = [
    "lol_shen", "archer", "barrier_magician", "berserker", "boomerang_hunter",
    "cavalry_knight", "dancer", "demon", "dual_blader",
];
pub const MAX_SLOTS: usize = 12;
const MAX_CARDS: usize = 256;

pub trait Ui {
    fn children(&self, path: &str) -> Vec<String>;
    fn visible(&self, path: &str) -> Option<bool>;
    fn text(&self, path: &str) -> Option<String>;
    fn image_size(&self, path: &str) -> Option<(f32, f32)>;
    fn show(&mut self, path: &str, visible: bool) -> bool;
}

fn decimal(text: &str) -> Option<usize> {
    if text.is_empty() || !text.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let value = text.parse::<usize>().ok()?;
    (value.to_string() == text).then_some(value)
}

fn pick_slot(child: &str) -> Option<usize> {
    decimal(child.strip_prefix("pick_slot_")?).filter(|&n| n < MAX_SLOTS)
}

fn picks(ui: &impl Ui, root: &str, side: &str) -> [Option<&'static str>; MAX_SLOTS] {
    let mut result = [None; MAX_SLOTS];
    let mut claims = [0u16; MAX_SLOTS];
    let other = if side == "blue" { "red" } else { "blue" };
    let contents = format!("{root}.champions.contents");
    let children = ui.children(&contents);
    if children.len() > MAX_CARDS {
        return result;
    }
    for id in children {
        let card = format!("{contents}.{id}");
        let marker = format!("{card}.{side}");
        // LOCAL marker visibility matters, not parent visibility: native
        // filtering/scrolling can hide a selected card without unpicking it.
        if ui.visible(&marker) != Some(true) {
            continue;
        }
        let Some(index) = ui.text(&format!("{marker}.text"))
            .as_deref().and_then(decimal).and_then(|n| n.checked_sub(1))
            .filter(|&n| n < MAX_SLOTS) else {
                return [None; MAX_SLOTS];
            };
        claims[index] += 1;
        result[index] = if claims[index] == 1
            && ui.visible(&format!("{card}.{other}")) == Some(false)
            && ui.visible(&format!("{card}.ban")) == Some(false)
        {
            HEROES.iter().copied().find(|&hero| hero == id)
        } else {
            None
        };
    }
    result
}

pub fn sync(ui: &mut impl Ui, root: &str) {
    // The stable host cannot expose the post-swap assignment permutation.
    // Pick badges represent draft order, not athlete/lane order. Restore
    // the stock actor during swap instead of displaying a guessed hero.
    let drafting = ui.visible(&format!("{root}.swap")) == Some(false);
    for side in ["blue", "red"] {
        let ids = if drafting { picks(ui, root, side) } else { [None; MAX_SLOTS] };
        let container = format!("{root}.{side}_picks");
        for child in ui.children(&container).into_iter().take(MAX_SLOTS) {
            let done = format!("{container}.{child}.done");
            let group = format!("{done}.lol_bp_illustrations");
            let actor = format!("{done}.champion");
            let was_ours = ui.visible(&group) == Some(true);
            let selected = pick_slot(&child).and_then(|index| ids[index])
                .filter(|_| ui.visible(&done) == Some(true));
            let mut ready = false;
            let mut all_set = true;
            for hero in HEROES {
                let image = format!("{group}.{hero}");
                let wanted = selected == Some(hero);
                let changed = ui.show(&image, wanted);
                all_set &= changed;
                if wanted && changed {
                    // Hidden nodes may need one layout pass after enabling.
                    // Keep the original actor until the fixed-size image is
                    // initialized; never hide it after a failed UI mutation.
                    ready = ui.image_size(&image).is_some_and(|(w, h)| {
                        (w - 284.0).abs() < 0.5 && (h - 172.0).abs() < 0.5
                    });
                }
            }
            let group_shown = ui.show(&group, selected.is_some() && all_set);
            if ready && all_set && group_shown {
                ui.show(&actor, false);
            } else if was_ours || selected.is_some() {
                ui.show(&actor, true);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    #[derive(Default)]
    struct Fake {
        kids: HashMap<String, Vec<String>>,
        visibility: HashMap<String, bool>,
        labels: HashMap<String, String>,
        sizes: HashMap<String, (f32, f32)>,
        fail: Option<String>,
    }
    impl Ui for Fake {
        fn children(&self, p: &str) -> Vec<String> { self.kids.get(p).cloned().unwrap_or_default() }
        fn visible(&self, p: &str) -> Option<bool> { self.visibility.get(p).copied() }
        fn text(&self, p: &str) -> Option<String> {
            assert!(!p.ends_with(".name"), "athlete name must never identify a champion");
            self.labels.get(p).cloned()
        }
        fn image_size(&self, p: &str) -> Option<(f32, f32)> { self.sizes.get(p).copied() }
        fn show(&mut self, p: &str, v: bool) -> bool {
            if self.fail.as_deref() == Some(p) { return false; }
            if let Some(value) = self.visibility.get_mut(p) { *value = v; true } else { false }
        }
    }
    fn card(ui: &mut Fake, hero: &str, side: &str, number: &str) {
        ui.kids.entry("main.champions.contents".into()).or_default().push(hero.into());
        let p = format!("main.champions.contents.{hero}");
        ui.visibility.insert(p.clone(), false); // filtered parent, selected marker still valid
        for s in ["blue", "red", "ban"] { ui.visibility.insert(format!("{p}.{s}"), s == side); }
        ui.labels.insert(format!("{p}.{side}.text"), number.into());
    }
    fn fixture(hero: &str, side: &str) -> (Fake, String) {
        let mut ui = Fake::default();
        ui.visibility.insert("main.swap".into(), false);
        card(&mut ui, hero, side, "1");
        // Child order is deliberately not the numeric slot order.
        ui.kids.insert(format!("main.{side}_picks"), vec!["pick_slot_3".into(), "pick_slot_0".into()]);
        let done = format!("main.{side}_picks.pick_slot_0.done");
        ui.visibility.insert(done.clone(), true);
        ui.visibility.insert(format!("{done}.champion"), true);
        ui.visibility.insert(format!("{done}.lol_bp_illustrations"), false);
        for id in HEROES {
            let p = format!("{done}.lol_bp_illustrations.{id}");
            ui.visibility.insert(p.clone(), false);
            ui.sizes.insert(p, (284., 172.));
        }
        (ui, done)
    }
    fn actor(ui: &Fake, done: &str) -> bool { ui.visible(&format!("{done}.champion")).unwrap() }

    #[test]
    fn all_nine_both_sides_filtered_and_reordered() {
        for hero in HEROES { for side in ["blue", "red"] {
            let (mut ui, done) = fixture(hero, side);
            sync(&mut ui, "main");
            assert!(!actor(&ui, &done), "{hero} {side}");
            for id in HEROES {
                assert_eq!(ui.visible(&format!("{done}.lol_bp_illustrations.{id}")), Some(id == hero));
            }
        }}
    }
    #[test]
    fn unknown_hero_and_duplicate_claims_do_not_hide_actor() {
        for hero in ["fighter", "Yone", "Oner", "Faker"] {
            let (mut ui, done) = fixture(hero, "blue");
            sync(&mut ui, "main"); assert!(actor(&ui, &done));
        }
        for hero in ["archer", "fighter"] {
            let (mut ui, done) = fixture("dual_blader", "blue");
            card(&mut ui, hero, "blue", "1");
            sync(&mut ui, "main"); assert!(actor(&ui, &done));
        }
    }
    #[test]
    fn malformed_missing_or_ambiguous_markers_are_not_matches() {
        for number in ["", "0", "13", "-1", "01", "1.0", " 1", "+1", "99999999999999999999999"] {
            let (mut ui, done) = fixture("dual_blader", "blue");
            ui.labels.insert("main.champions.contents.dual_blader.blue.text".into(), number.into());
            sync(&mut ui, "main"); assert!(actor(&ui, &done), "{number}");
        }
        for marker in ["red", "ban"] {
            let (mut ui, done) = fixture("dual_blader", "blue");
            ui.visibility.insert(format!("main.champions.contents.dual_blader.{marker}"), true);
            sync(&mut ui, "main"); assert!(actor(&ui, &done));
        }
    }
    #[test]
    fn unpick_swap_and_new_draft_clear_old_art() {
        for hidden in ["main.swap", "main.champions.contents.dual_blader.blue"] {
            let (mut ui, done) = fixture("dual_blader", "blue");
            sync(&mut ui, "main"); assert!(!actor(&ui, &done));
            ui.visibility.insert(hidden.into(), hidden == "main.swap");
            sync(&mut ui, "main"); assert!(actor(&ui, &done));
            assert_eq!(ui.visible(&format!("{done}.lol_bp_illustrations")), Some(false));
        }
        let (mut ui, done) = fixture("dual_blader", "blue");
        sync(&mut ui, "main");
        ui.kids.remove("main.champions.contents");
        sync(&mut ui, "main"); assert!(actor(&ui, &done));
    }
    #[test]
    fn zero_rect_or_failed_setter_keeps_original_until_ready() {
        let (mut ui, done) = fixture("dual_blader", "red");
        let image = format!("{done}.lol_bp_illustrations.dual_blader");
        ui.sizes.insert(image.clone(), (0., 0.));
        sync(&mut ui, "main"); assert!(actor(&ui, &done));
        ui.sizes.insert(image.clone(), (284., 172.));
        sync(&mut ui, "main"); assert!(!actor(&ui, &done));
        ui.fail = Some(image);
        sync(&mut ui, "main"); assert!(actor(&ui, &done));
    }
    #[test]
    fn slot_ids_are_strict_and_one_based_markers_use_zero_based_slots() {
        for name in ["pick_slot_-1", "pick_slot_12", "pick_slot_01", "pick_slot_", "header"] { assert_eq!(pick_slot(name), None); }
        assert_eq!(pick_slot("pick_slot_0"), Some(0));
        let (mut ui, _) = fixture("dancer", "red");
        ui.labels.insert("main.champions.contents.dancer.red.text".into(), "12".into());
        assert_eq!(picks(&ui, "main", "red")[11], Some("dancer"));
    }
}
