#!/usr/bin/env python3
"""Generate src/ge150/data/gear.json: the real gear behind every model and how to draw it.

``gear`` entries describe one physical unit (shared by e.g. the CL and DS channels of an
amp): its name, the shape the GUI draws when there is no photo (``kind``) and its colours.
``models`` maps ``module tag -> model number -> gear id``. Edit the tables below and rerun.
Model origins come from the "Effects List" of the GE150 manual.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "src" / "ge150" / "data" / "gear.json"

# kind: wah | stomp | boss | round | bigbox | micro | eq | head | combo | cab | acoustic
# colours: body, text, knob (+ panel, grille for amps/cabs); speakers for combos/cabs.
G: dict[str, dict[str, object]] = {}


def gear(gid: str, name: str, kind: str, body: str, text: str = "#f2f2f2",
         knob: str = "#151515", query: str | None = None, **extra: object) -> None:
    G[gid] = {"name": name, "kind": kind, "body": body, "text": text, "knob": knob,
              "query": query if query is not None else name, **extra}


def amp(gid: str, name: str, kind: str, tolex: str, panel: str, grille: str,
        text: str = "#f2f2f2", knob: str = "#151515", speakers: str = "", query: str | None = None,
        **extra: object) -> None:
    gear(gid, name, kind, tolex, text, knob, query, panel=panel, grille=grille,
         speakers=speakers, **extra)


# --- FX / COMP ---------------------------------------------------------------
gear("crybaby", "Dunlop Cry Baby GCB95", "wah", "#161616", query="Dunlop Cry Baby wah")
gear("crybaby535", "Dunlop Cry Baby 535Q", "wah", "#161616", knob="#c8102e",
     query="Cry Baby 535Q wah")
gear("mooer_wah", "Mooer @Wah", "wah", "#2b2b2b", text="#ff8a00", query="")
gear("mooer_envelope", "Mooer Envelope", "micro", "#6a2c91", query="")
gear("mooer_redkid", "Mooer Red Kid Talkwah", "micro", "#c4161c", query="")
gear("mooer_touchwah", "Touch wah", "micro", "#e0661b", query="")
gear("mooer_yellowcomp", "Mooer Yellow Comp", "micro", "#f2c230", text="#1a1a1a", query="")
gear("mooer_bluecomp", "Mooer Blue Comp", "micro", "#3d8fd6", query="")
# --- DS / OD -----------------------------------------------------------------
gear("tubedriver", "B.K. Butler Tube Driver", "stomp", "#2a2a2a", text="#d9d9d9", knob="#d0d0d0",
     query="Tube Driver pedal Butler")
gear("ts808", "Ibanez TS808 Tube Screamer", "stomp", "#3c8c3c", text="#f4f1e1",
     query="Ibanez Tube Screamer TS808")
gear("mooer_pureboost", "Mooer Pure Boost", "micro", "#cfd3d6", text="#1a1a1a", query="")
gear("mooer_flexboost", "Mooer Flex Boost", "micro", "#9e1b1b", query="")
gear("directdrive", "Barber Direct Drive", "stomp", "#b3262b", query="Barber Direct Drive pedal")
gear("rat", "ProCo RAT", "stomp", "#141414", text="#f2f2f2", query="ProCo RAT pedal")
gear("fuzzface", "Dunlop Fuzz Face", "round", "#8e959b", text="#1a1a1a", knob="#151515",
     query="Fuzz Face pedal")
gear("bigmuff", "Electro-Harmonix Big Muff Pi", "bigbox", "#d5d7d9", text="#c41e1e",
     query="Big Muff Pi pedal")
gear("mt2", "BOSS MT-2 Metal Zone", "boss", "#2c2c2c", text="#ff7a1a",
     query="Boss MT-2 Metal Zone")
gear("metalmaster", "DigiTech Metal Master", "stomp", "#1b1b1b", text="#e2231a",
     query="DigiTech Metal Master pedal")
gear("ocd", "Fulltone OCD", "stomp", "#eeeae0", text="#1a1a1a", query="Fulltone OCD pedal")
gear("timmy", "Paul Cochrane Timmy", "stomp", "#c4c8cc", text="#1a1a1a",
     query="Paul Cochrane Timmy overdrive")
gear("fulldrive", "Fulltone Fulldrive 2", "stomp", "#2f4f7f", query="Fulltone Fulldrive 2")
gear("shredmaster", "Marshall ShredMaster", "stomp", "#151515", text="#d4af37",
     query="Marshall ShredMaster pedal")
gear("bbpre", "Xotic BB Preamp", "stomp", "#c8963e", text="#1a1a1a", query="Xotic BB Preamp")
gear("bbplus", "Xotic BB Plus", "stomp", "#a8742a", text="#1a1a1a", query="Xotic BB Plus")
gear("riot", "Suhr Riot", "stomp", "#1d1d1d", text="#e6c35c", query="Suhr Riot distortion")
gear("tightrock", "Amptweaker TightRock", "stomp", "#d9a520", text="#1a1a1a",
     query="Amptweaker TightRock")
gear("gt500", "Fulltone GT-500", "stomp", "#3b6ea5", query="Fulltone GT-500")
gear("klon", "Klon Centaur", "stomp", "#c9a227", text="#1a1a1a", query="Klon Centaur")
# --- AMP (head / combo) --------------------------------------------------------
BF = {"tolex": "#141414", "panel": "#1b1b1b", "grille": "#b9b9b4", "text": "#f0f0f0"}
amp("deluxe", "Fender '65 Deluxe Reverb", "combo", **BF, speakers="1x12",
    query="Fender Deluxe Reverb amplifier")
amp("twin", "Fender '65 Twin Reverb", "combo", **BF, speakers="2x12",
    query="Fender Twin Reverb amplifier")
amp("bassman", "Fender '59 Bassman", "combo", "#c8a46a", "#d9c39a", "#6e4b2a", text="#2b1d10",
    knob="#e8e0cc", speakers="4x10", query="Fender Bassman tweed amplifier")
amp("supersonic", "Fender Super-Sonic", "combo", "#141414", "#c9c9c9", "#2a2a2a",
    text="#1a1a1a", speakers="1x12", query="Fender Super-Sonic amplifier")
amp("bluesdeluxe", "Fender Blues Deluxe", "combo", "#c8a46a", "#3a2a1a", "#6e4b2a",
    knob="#e8e0cc", speakers="1x12", query="Fender Blues Deluxe amplifier")
MARSHALL = {"tolex": "#151515", "panel": "#c9a54a", "grille": "#1e1e1e", "text": "#1a1a1a"}
amp("jcm800", "Marshall JCM800", "head", **MARSHALL, query="Marshall JCM800")
amp("jcm900", "Marshall JCM900", "head", **MARSHALL, query="Marshall JCM900")
amp("plexi", "Marshall Plexi Super Lead 100", "head", **MARSHALL,
    query="Marshall Super Lead 1959 plexi")
ENGL = {"tolex": "#121212", "panel": "#1d2026", "grille": "#2a2d33", "text": "#8fc3ff",
        "knob": "#c9c9c9"}
amp("engl_e650", "ENGL E650 Ritchie Blackmore", "head", **ENGL, query="ENGL Blackmore amplifier")
amp("engl_e645", "ENGL Powerball E645", "head", **ENGL, query="ENGL Powerball amplifier")
amp("engl_blackmore", "ENGL E650 Blackmore Signature", "head", **ENGL,
    query="ENGL Ritchie Blackmore E650")
amp("mark3", "Mesa/Boogie Mark III", "combo", "#141414", "#161616", "#3b3324",
    text="#e8e8e8", knob="#151515", speakers="1x12", query="Mesa Boogie Mark III")
amp("mark5", "Mesa/Boogie Mark V", "head", "#141414", "#161616", "#2a2a2a",
    text="#e8e8e8", query="Mesa Boogie Mark V")
amp("rectifier", "Mesa/Boogie Triple Rectifier", "head", "#141414", "#b8bcc0", "#2a2a2a",
    text="#141414", diamond=True, query="Mesa Boogie Rectifier amplifier")
ORANGE = {"tolex": "#e8731f", "panel": "#efe6d2", "grille": "#d9cdb0", "text": "#1a1a1a"}
amp("rockerverb", "Orange Rockerverb", "head", **ORANGE, query="Orange Rockerverb")
amp("ad30", "Orange AD30", "head", **ORANGE, query="Orange AD30 amplifier")
amp("or50", "Orange OR50", "head", **ORANGE, query="Orange OR50")
amp("slo100", "Soldano SLO-100", "head", "#141414", "#d8dadc", "#262626", text="#1a1a1a",
    query="Soldano SLO-100")
amp("maz18", "Dr. Z Maz 18 Jr", "combo", "#2a2a2a", "#3a3a3a", "#a9a39a", speakers="1x12",
    query="Dr. Z Maz 18 amplifier")
amp("zwreck", "Dr. Z Z-Wreck", "combo", "#4a1f1f", "#2a2a2a", "#a9a39a", speakers="2x12",
    query="Dr. Z Z-Wreck")
amp("jetcity", "Jet City JCA100H", "head", "#141414", "#2a2a2a", "#3a3a3a", text="#e33",
    query="Jet City JCA100H")
amp("jc120", "Roland JC-120 Jazz Chorus", "combo", "#141414", "#c6c8ca", "#1e1e1e",
    text="#1a1a1a", speakers="2x12", query="Roland JC-120 Jazz Chorus")
amp("ac30", "Vox AC30", "combo", "#151515", "#7a4a2a", "#5e4630", text="#e7d3a8",
    knob="#2a2a2a", speakers="2x12", query="Vox AC30")
amp("hiwatt", "Hiwatt DR103", "head", "#151515", "#1a1a1a", "#262626", text="#f2f2f2",
    query="Hiwatt DR103")
amp("peavey5150", "Peavey 5150", "head", "#151515", "#2a2a2a", "#262626", text="#e6e6e6",
    knob="#d6d6d6", query="Peavey 5150 amplifier")
amp("falcon", "Tone King Falcon", "combo", "#e3d7bd", "#3d2b1f", "#7a5b3d", text="#e3d7bd",
    knob="#e8e0cc", speakers="1x12", query="Tone King Falcon amplifier")
amp("tworock", "Two-Rock Coral", "head", "#1b1b1b", "#c9a54a", "#2a2a2a", text="#1a1a1a",
    query="Two-Rock amplifier")
amp("cardiff", "Two-Rock Cardiff", "head", "#1b1b1b", "#b8bcc0", "#2a2a2a", text="#1a1a1a",
    query="Two-Rock Cardiff")
amp("evh5150", "EVH 5150 III", "head", "#141414", "#1c1c1c", "#262626", text="#d8d8d8",
    knob="#f2f2f2", stripes=True, query="EVH 5150 III amplifier")
amp("blackstar", "Blackstar HT Stage 100", "head", "#141414", "#1c1c1c", "#262626",
    text="#d4af37", query="Blackstar HT Stage 100")
amp("diezel", "Diezel Hagen", "head", "#141414", "#c6c8ca", "#262626", text="#1a1a1a",
    query="Diezel Hagen amplifier")
amp("koch", "Koch Powertone", "head", "#141414", "#2a2a2a", "#262626", text="#d4af37",
    query="Koch Powertone amplifier")
amp("acoustic", "Acoustic simulator", "acoustic", "#c48a4a", "#3a2412", "#1a1008",
    text="#f2e6d0", query="")
# --- CAB ---------------------------------------------------------------------------
BFG = {"tolex": "#141414", "panel": "#141414", "grille": "#b9b9b4"}
amp("c_deluxe", "Fender Deluxe Reverb 1x12", "cab", **BFG, speakers="1x12",
    query="Fender Deluxe Reverb amplifier")
amp("c_twin", "Fender Twin Reverb 2x12", "cab", **BFG, speakers="2x12",
    query="Fender Twin Reverb amplifier")
amp("c_bassman", "Fender Bassman 4x10", "cab", "#c8a46a", "#c8a46a", "#6e4b2a", speakers="4x10",
    query="Fender Bassman tweed amplifier")
amp("c_supersonic", "Fender Super-Sonic 1x12", "cab", "#141414", "#141414", "#2a2a2a",
    speakers="1x12", query="Fender Super-Sonic amplifier")
amp("c_blues", "Fender Blues Deluxe 1x12", "cab", "#c8a46a", "#c8a46a", "#6e4b2a",
    speakers="1x12", query="Fender Blues Deluxe amplifier")
amp("c_1960", "Marshall 1960A 4x12", "cab", "#151515", "#151515", "#2a2a2a", speakers="4x12",
    slant=True, query="Marshall 1960A cabinet")
amp("c_englpro", "ENGL Pro XXL 4x12", "cab", "#121212", "#121212", "#2a2d33", speakers="4x12",
    slant=True, query="ENGL 4x12 cabinet")
amp("c_englvint", "ENGL Vintage XXL 4x12", "cab", "#121212", "#121212", "#2a2d33",
    speakers="4x12", query="ENGL 4x12 cabinet")
amp("c_mark", "Mesa/Boogie Mark 1x12", "cab", "#141414", "#141414", "#3b3324", speakers="1x12",
    query="Mesa Boogie 1x12 cabinet")
amp("c_rect", "Mesa/Boogie Rectifier 4x12", "cab", "#141414", "#b8bcc0", "#2a2a2a",
    speakers="4x12", slant=True, diamond=True, query="Mesa Boogie Rectifier 4x12 cabinet")
amp("c_orange412", "Orange PPC412", "cab", "#e8731f", "#e8731f", "#d9cdb0", speakers="4x12",
    query="Orange PPC412 cabinet")
amp("c_orange212", "Orange PPC212", "cab", "#e8731f", "#e8731f", "#d9cdb0", speakers="2x12",
    query="Orange PPC212 cabinet")
amp("c_soldano", "Soldano SLO 4x12", "cab", "#141414", "#141414", "#262626", speakers="4x12",
    slant=True, query="Soldano 4x12 cabinet")
amp("c_maz", "Dr. Z Maz 1x12", "cab", "#2a2a2a", "#2a2a2a", "#a9a39a", speakers="1x12",
    query="Dr. Z 1x12 cabinet")
amp("c_zwreck", "Dr. Z Z-Wreck 2x12", "cab", "#4a1f1f", "#4a1f1f", "#a9a39a", speakers="2x12",
    query="Dr. Z Z-Wreck")
amp("c_jc120", "Roland JC-120 2x12", "cab", "#141414", "#141414", "#1e1e1e", speakers="2x12",
    query="Roland JC-120 Jazz Chorus")
amp("c_ac30", "Vox AC30 2x12", "cab", "#151515", "#151515", "#5e4630", speakers="2x12",
    query="Vox AC30")
amp("c_hiwatt", "Hiwatt AP 4x12", "cab", "#151515", "#151515", "#262626", speakers="4x12",
    query="Hiwatt 4x12 cabinet")
amp("c_peavey", "Peavey 5150 4x12", "cab", "#151515", "#151515", "#262626", speakers="4x12",
    slant=True, query="Peavey 5150 4x12 cabinet")
amp("c_falcon", "Tone King Falcon 1x10", "cab", "#e3d7bd", "#e3d7bd", "#7a5b3d",
    speakers="1x10", query="Tone King Falcon amplifier")
amp("c_tworock212", "Two-Rock 2x12", "cab", "#1b1b1b", "#1b1b1b", "#3a3a3a", speakers="2x12",
    query="Two-Rock 2x12 cabinet")
amp("c_tworock112", "Two-Rock 1x12", "cab", "#1b1b1b", "#1b1b1b", "#3a3a3a", speakers="1x12",
    query="Two-Rock 1x12 cabinet")
amp("c_evh", "EVH 5150 III 4x12", "cab", "#141414", "#141414", "#262626", speakers="4x12",
    slant=True, query="EVH 5150 III 4x12 cabinet")
amp("c_blackstar", "Blackstar HTV 4x12", "cab", "#141414", "#141414", "#262626",
    speakers="4x12", slant=True, query="Blackstar 4x12 cabinet")
amp("c_diezel", "Diezel 4x12", "cab", "#141414", "#141414", "#262626", speakers="4x12",
    query="Diezel 4x12 cabinet")
amp("c_acoustic", "1x12 acoustic cabinet", "cab", "#7a5233", "#7a5233", "#2a2018",
    speakers="1x12", query="")
amp("c_user", "User IR", "cab", "#232a33", "#232a33", "#3a4452", speakers="1x12", query="")
amp("user_nr", "User NR capture", "head", "#232a33", "#2c3540", "#3a4452", text="#7fd3ff",
    query="")
# --- NS / EQ / MOD / DELAY / REVERB (Mooer originals, drawn only) ----------------------
for gid, name, colour, text in (
    ("mooer_noisekiller", "Mooer Noise Killer", "#3b3f44", "#f2f2f2"),
    ("mooer_intel", "Intelligent noise reduction", "#22313f", "#9fe3ff"),
    ("mooer_gate", "Digital noise gate", "#2f2f2f", "#f2f2f2"),
):
    gear(gid, name, "micro", colour, text=text, query="")
gear("mooer_graphic_g", "Mooer Graphic G", "eq", "#c9ccd0", text="#1a1a1a", query="")
gear("mooer_graphic_b", "Mooer Graphic B", "eq", "#1f1f1f", query="")
gear("mooer_g6", "6-band graphic EQ", "eq", "#2e5d8c", query="")
gear("custom_eq", "Parametric EQ", "eq", "#3a3a3a", text="#9fe3ff", query="")
MOD_COLOURS = ("#e8731f", "#7d4cc2", "#d64545", "#2f8f83", "#cfd3d6", "#f2c230", "#c2185b",
               "#5c6bc0", "#43a047", "#26a69a", "#8d6e63", "#1e88e5", "#00897b", "#6d4c41",
               "#fb8c00", "#90a4ae", "#546e7a", "#ab47bc", "#9e9d24")
MOD_NAMES = ("Mooer Ninety Orange", "Step phaser", "Fat phaser", "Mooer E-Lady",
             "Mooer Jet Flanger", "Mooer Trelicopter", "Stutter", "Vibrato", "Pitch shifter",
             "Detune", "Rotary speaker", "Analog chorus", "Tri-chorus", "Ring modulator",
             "Q-filter", "High pass", "Low pass", "Slow gear", "Lo-fi")
for i, (name, colour) in enumerate(zip(MOD_NAMES, MOD_COLOURS, strict=True), 1):
    light = colour in ("#cfd3d6", "#f2c230", "#90a4ae")
    gear(f"mod{i}", name, "micro", colour, text="#1a1a1a" if light else "#f2f2f2", query="")
DELAYS = (("Digital delay", "#1e88e5"), ("Analog delay", "#6d8f3a"), ("Real echo", "#455a64"),
          ("Tape echo", "#8d6e63"), ("Modulated delay", "#7e57c2"), ("Reverse delay", "#c62828"),
          ("Ping-pong delay", "#00897b"), ("Dynamic delay", "#ef6c00"), ("Dual delay", "#37474f"))
for i, (name, colour) in enumerate(DELAYS, 1):
    gear(f"delay{i}", name, "micro", colour, query="")
REVERBS = (("Room", "#546e7a"), ("Hall", "#3949ab"), ("Church", "#6a1b9a"), ("Plate", "#b0bec5"),
           ("Spring", "#2e7d32"), ("Mod reverb", "#00838f"), ("Cave", "#4e342e"))
for i, (name, colour) in enumerate(REVERBS, 1):
    gear(f"reverb{i}", f"{name} reverb", "micro", colour,
         text="#1a1a1a" if colour == "#b0bec5" else "#f2f2f2", query="")


# Generic algorithms (no unit named in the manual): the GUI shows their name without
# "based on".
for gid, entry in G.items():
    name = str(entry["name"])
    if gid.startswith(("mod", "delay", "reverb", "mooer_", "custom_")) and not name.startswith(
            "Mooer"):
        entry["generic"] = True

# --- reference photos -------------------------------------------------------------------
# Effects the manual ties to a classic pedal without being based on a Mooer unit show a
# photo of that pedal as a *reference* ("foto de referencia"), never as "based on". Mooer
# originals use the photo of the Mooer pedal itself. Everything else keeps its drawing.
REFERENCES: dict[str, tuple[str, str]] = {
    "mod9": ("DigiTech Whammy", "DigiTech Whammy"),  # manual: "simulate classic whammy"
    "mod18": ("BOSS SG-1 Slow Gear", "Boss Slow Gear"),
}
for gid, (reference, query) in REFERENCES.items():
    G[gid]["reference"] = reference
    G[gid]["query"] = query

# Broader searches for real gear the first pass did not find.
RETRY = {
    "crybaby535": "Cry Baby wah pedal", "tubedriver": "Tube Driver overdrive",
    "directdrive": "Barber Direct Drive", "fulldrive": "Fulltone Fulldrive",
    "metalmaster": "DigiTech Metal Master", "ocd": "OCD overdrive pedal",
    "timmy": "Timmy overdrive", "shredmaster": "Marshall Shred Master",
    "bbplus": "Xotic BB", "riot": "Suhr Riot", "tightrock": "Amptweaker",
    "gt500": "Fulltone GT500", "bassman": "Fender Bassman",
    "supersonic": "Fender Super Sonic", "plexi": "Marshall Plexi",
    "engl_e645": "ENGL amplifier", "mark3": "Mesa Boogie Mark",
    "mark5": "Mesa Boogie Mark V", "ad30": "Orange amplifier", "or50": "Orange OR",
    "maz18": "Dr. Z amplifier", "zwreck": "Dr. Z Z Wreck", "jetcity": "Jet City amplifier",
    "falcon": "Tone King", "tworock": "Two Rock amplifier", "cardiff": "Two Rock amp",
    "evh5150": "EVH 5150", "blackstar": "Blackstar amplifier", "diezel": "Diezel amplifier",
    "koch": "Koch amplifier", "c_bassman": "Fender Bassman", "c_supersonic": "Fender Super Sonic",
    "c_englpro": "ENGL cabinet", "c_englvint": "ENGL cabinet", "c_soldano": "Soldano cabinet",
    "c_hiwatt": "Hiwatt cabinet", "c_peavey": "Peavey 5150 cabinet", "c_evh": "EVH cabinet",
    "c_blackstar": "Blackstar cabinet", "c_diezel": "Diezel cabinet",
    "c_tworock212": "Two Rock cabinet", "c_tworock112": "Two Rock cabinet",
    "c_maz": "Dr. Z cabinet", "c_zwreck": "Dr. Z cabinet", "c_falcon": "Tone King",
}
for gid, query in RETRY.items():
    G[gid]["query"] = query

# --- models -> gear -------------------------------------------------------------------
FX = ["crybaby", "crybaby535", "mooer_envelope", "mooer_redkid", "mooer_redkid", "mooer_touchwah",
      "mooer_yellowcomp", "mooer_bluecomp"]
DS = ["tubedriver", "ts808", "mooer_pureboost", "mooer_flexboost", "directdrive", "rat",
      "fuzzface", "bigmuff", "mt2", "metalmaster", "ocd", "timmy", "fulldrive", "shredmaster",
      "bbpre", "bbplus", "riot", "tightrock", "gt500", "klon"]
AMP = ["deluxe", "twin", "bassman", "supersonic", "bluesdeluxe", "bluesdeluxe", "jcm800", "jcm900",
       "plexi", "engl_e650", "engl_e650", "engl_e645", "engl_e645", "engl_blackmore",
       "engl_blackmore", "mark3", "mark3", "mark5", "mark5", "rectifier", "rectifier",
       "rockerverb", "rockerverb", "ad30", "or50", "slo100", "slo100", "maz18", "zwreck",
       "jetcity", "jetcity", "jc120", "ac30", "ac30", "hiwatt", "peavey5150", "peavey5150",
       "falcon", "falcon", "falcon", "tworock", "tworock", "cardiff", "evh5150", "evh5150",
       "blackstar", "blackstar", "diezel", "diezel", "diezel", "koch", "koch", "acoustic",
       "acoustic", "acoustic"] + ["user_nr"] * 10
CAB = ["c_deluxe", "c_twin", "c_bassman", "c_supersonic", "c_blues", "c_1960", "c_englpro",
       "c_englvint", "c_mark", "c_rect", "c_orange412", "c_orange212", "c_soldano", "c_maz",
       "c_zwreck", "c_jc120", "c_ac30", "c_hiwatt", "c_peavey", "c_falcon", "c_tworock212",
       "c_tworock112", "c_evh", "c_blackstar", "c_diezel", "c_acoustic"] + ["c_user"] * 10
TABLES = {
    "FX": FX, "DS": DS, "AMP": AMP, "CAB": CAB,
    "NS": ["mooer_noisekiller", "mooer_intel", "mooer_gate"],
    "EQ": ["mooer_graphic_g", "mooer_graphic_b", "mooer_g6", "custom_eq"],
    "MOD": [f"mod{i}" for i in range(1, 20)],
    "DELAY": [f"delay{i}" for i in range(1, 10)],
    "REVERB": [f"reverb{i}" for i in range(1, 8)],
}


def main() -> None:
    catalog = json.loads((OUT.parent / "effects.json").read_text())
    models: dict[str, dict[str, str]] = {}
    for module in catalog["modules"]:
        table = TABLES[module["tag"]]
        if len(table) != len(module["models"]):
            raise SystemExit(f"{module['tag']}: {len(table)} gear ids for "
                             f"{len(module['models'])} models")
        for gid in table:
            if gid not in G:
                raise SystemExit(f"unknown gear id {gid}")
        models[module["tag"]] = {str(m["number"]): gid
                                 for m, gid in zip(module["models"], table, strict=True)}
    lines = ['{', ' "source": "tools/build_gear.py (origins from the GE150 manual)",', ' "gear": {']
    items = [f'  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}' for k, v in G.items()]
    lines += [",\n".join(items), ' },', ' "models": {']
    rows = [f'  {json.dumps(k)}: {json.dumps(v)}' for k, v in models.items()]
    lines += [",\n".join(rows), ' }', '}']
    OUT.write_text("\n".join(lines) + "\n")
    print(f"{OUT}: {len(G)} gear, {sum(len(v) for v in models.values())} models")


if __name__ == "__main__":
    main()
