from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "mods" / "lol_mod"


def load_validator():
    path = MOD / "tools" / "validate_lol_mod.py"
    spec = importlib.util.spec_from_file_location("validate_lol_mod", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_static_validator_passes() -> None:
    validator = load_validator()
    validator.ERRORS.clear()
    assert validator.main() == 0


def test_data_champion_is_additive_and_localized() -> None:
    champion = json.loads((MOD / "champion" / "lol_shen.data_champion").read_text(encoding="utf-8"))
    mod_info = json.loads((MOD / "mod.mod_info").read_text(encoding="utf-8"))
    text = json.loads((MOD / "text" / "champion.i18n").read_text(encoding="utf-8"))
    assert champion["id"] == "lol_shen"
    assert mod_info["mod_id"] == "lol_mod"
    assert text["zh-hans"]["description"]["lol_shen"]["name"] == "慎"
    assert text["zh-hant"]["description"]["lol_shen"]["name"] == "慎"


def test_generated_sources_and_official_audio_are_auditable() -> None:
    imagegen = json.loads((MOD / "qa" / "shen_imagegen_sources.json").read_text(encoding="utf-8"))
    audio = json.loads((MOD / "qa" / "shen_official_audio_sources.json").read_text(encoding="utf-8"))
    assert len(imagegen["sources"]) == 8
    assert {entry["role"] for entry in imagegen["sources"]} == {
        "actor_model",
        "run_cycle",
        "q_icon",
        "w_icon",
        "r_icon",
        "q_vfx",
        "w_vfx",
        "r_vfx",
    }
    assert len(audio["outputs"]) == 7
    assert all(entry["volume"] >= 0.85 for entry in audio["outputs"])
