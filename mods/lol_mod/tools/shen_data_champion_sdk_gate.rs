extern crate game_core;
extern crate serde_json;

use game_core::DataChampionInfo;
use std::env;
use std::fs;
use std::process;

fn main() {
    let path = env::args().nth(1).unwrap_or_else(|| {
        eprintln!("usage: shen_data_champion_sdk_gate <champion.data_champion>");
        process::exit(2);
    });
    let raw = fs::read_to_string(&path).unwrap_or_else(|error| {
        eprintln!("cannot read {path}: {error}");
        process::exit(3);
    });
    let _: DataChampionInfo = serde_json::from_str(&raw).unwrap_or_else(|error| {
        eprintln!("official SDK DataChampionInfo rejected {path}: {error}");
        process::exit(4);
    });
    println!("SDK DataChampionInfo accepted {path}");
}
