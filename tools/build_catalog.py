#!/usr/bin/env python3
"""Convert the vendor ``preset.xml`` into ``src/ge150/data/effects.json``.

Only functional data is kept (module, model names, parameter names and ranges).
``paraPos`` = number of the model whose parameter list is reused; it is resolved here.

Usage: build_catalog.py [preset.xml] [effects.json]
Defaults: reference/qrc/preset/preset/preset.xml -> src/ge150/data/effects.json
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_XML = ROOT / "reference/qrc/preset/preset/preset.xml"
DEFAULT_OUT = ROOT / "src/ge150/data/effects.json"
#: AMP 56..65 are commented out in the V1.3.8 XML but the editor can upload NR files
#: to wire slots 0x37..0x40 (plan.md §2.8). They reuse the parameters of AMP 01.
NR_SLOTS = range(56, 66)


def parse_param(elem: ET.Element) -> dict[str, Any]:
    name, kind, text = elem.get("name", ""), elem.get("type", "0"), (elem.text or "").strip()
    if kind == "1":
        return {"name": name, "kind": "enum", "options": text.split("_")}
    parts = text.split("_")
    if kind != "0" or len(parts) < 4:
        return {"name": name, "kind": "raw", "spec": text}
    unit = parts[4].strip() if len(parts) > 4 else ""
    return {
        "name": name,
        "kind": "number",
        "min": float(parts[0]) if "." in parts[0] else int(parts[0]),
        "max": float(parts[1]) if "." in parts[1] else int(parts[1]),
        "step": float(parts[2]) if "." in parts[2] else int(parts[2]),
        "decimals": int(parts[3]),
        "unit": unit,
    }


#: Parameter -> word index inside the module block, for the models that do not use the
#: default ``2 + k``. Transcribed from the vendor's FUN_0041d470 [V] (plan.md §2.7) and
#: consistent with 200 presets read from a real pedal.
#: MOD words: 2 RATE, 3 MIX/LEVEL, 4 TONE, 5 DEPTH, 6 DETUNE pitch, 7 PITCH SHIFT pitch.
WORD_MAP: dict[tuple[str, str], list[int]] = {
    ("EQ", "CUSTOM EQ"): [2, 8, 4, 9, 6, 10],  # GAIN1 FREQ1 GAIN2 FREQ2 GAIN3 FREQ3
    ("MOD", "PHASER"): [2, 3, 5],
    ("MOD", "STEP PHASER"): [2, 3, 5],
    ("MOD", "FAT PHASER"): [2, 3, 5],
    ("MOD", "VIBRATO"): [2, 5, 4],
    ("MOD", "PITCH SHIFT"): [7, 3, 4],
    ("MOD", "DETUNE"): [6, 3, 4],
    ("DELAY", "DYNAMIC"): [2, 3, 4, 5, 8],
}


def assign_words(module: str, params: list[dict[str, Any]],
                 model_name: str = "") -> list[dict[str, Any]]:
    """Copy ``params`` adding ``word`` (index inside the module block)."""
    words = WORD_MAP.get((module, model_name), [2 + k for k in range(len(params))])
    if len(words) != len(params):
        raise SystemExit(f"{module} {model_name}: word map does not match its parameters")
    return [dict(p, word=w) for p, w in zip(params, words, strict=True)]


def build(xml_path: Path) -> dict[str, Any]:
    root = ET.parse(xml_path).getroot()
    modules = []
    for index, chain in enumerate(root.findall("chain")):
        models: list[dict[str, Any]] = []
        own_params: dict[int, list[dict[str, Any]]] = {}
        for elem in chain:
            number_text, _, model_name = elem.get("name", "").partition(":")
            number = int(number_text)
            params = [parse_param(p) for p in elem.findall("para")]
            if params:
                own_params[number] = params
            models.append({
                "number": number,
                "name": model_name.strip(),
                "param_source": int(elem.get("paraPos", number)),
                "user_slot": elem.get("import") == "1",
                "params": params,
            })
        if chain.get("name") == "AMP" and models and models[-1]["number"] < NR_SLOTS.start:
            for n in NR_SLOTS:
                models.append({"number": n, "name": "EMPTY", "param_source": 1,
                               "user_slot": True, "hidden_in_vendor_ui": True, "params": []})
        for model in models:
            if not model["params"]:
                source = own_params.get(model["param_source"])
                if source is None:
                    raise SystemExit(f"{chain.get('name')} {model['number']}: no paraPos source")
                model["params"] = source
            model["params"] = assign_words(chain.get("name", ""), model["params"], model["name"])
        modules.append({"index": index, "name": chain.get("name"), "tag": chain[0].tag,
                        "models": models})
    return {
        "source": "Functional data derived from preset.xml of Mooer Studio for GE150 V1.3.8",
        "generator": "tools/build_catalog.py",
        "modules": modules,
    }


def dumps(catalog: dict[str, Any]) -> str:
    """Readable JSON with one model per line (keeps diffs small)."""
    head = {k: v for k, v in catalog.items() if k != "modules"}
    lines = ["{"] + [f" {json.dumps(k)}: {json.dumps(v)}," for k, v in head.items()]
    lines.append(' "modules": [')
    for i, module in enumerate(catalog["modules"]):
        meta = {k: v for k, v in module.items() if k != "models"}
        lines.append(f"  {json.dumps(meta)[:-1]}, \"models\": [")
        models = [f"   {json.dumps(m, ensure_ascii=False)}" for m in module["models"]]
        lines.append(",\n".join(models))
        lines.append("  ]}" + ("," if i < len(catalog["modules"]) - 1 else ""))
    lines += [" ]", "}"]
    return "\n".join(lines) + "\n"


def main() -> None:
    xml_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XML
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    catalog = build(xml_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = dumps(catalog)
    if json.loads(text) != catalog:
        raise SystemExit("internal error: compact JSON does not round-trip")
    out.write_text(text)
    for m in catalog["modules"]:
        print(f"{m['index']} {m['name']:8} {len(m['models']):3} models")


if __name__ == "__main__":
    main()
