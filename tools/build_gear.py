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
gear("mooer_wah", "Mooer @Wah", "micro", "#6fb6ea", text="#1a1a1a", query="")
gear("mooer_envelope", "Mooer Envelope", "micro", "#6a2c91", query="")
gear("mooer_redkid", "Mooer Red Kid Talkwah", "wah", "#c47d62", text="#8f4f3b")
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
amp("c_user", "IR de usuario", "cab", "#232a33", "#232a33", "#3a4452", speakers="1x12", query="")
amp("user_nr", "Captura NR de usuario", "head", "#232a33", "#2c3540", "#3a4452", text="#7fd3ff",
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

G["c_user"]["generic"] = True  # user slots: the caption shows the loaded file name
G["user_nr"]["generic"] = True

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


# How the drawing looks when there is no photo (see ui/amp_art.py and ui/gear_art.py):
# the brand logo, grille material, knobs and the name printed on pedals, after the real units.
ENGL_LOGO = {"logo_text": "ENGL", "logo": "block", "logo_colour": "chrome"}
ORANGE_LOGO = {"logo_text": "ORANGE", "logo": "rounded", "logo_colour": "#141414",
               "grille_style": "basket"}
TWO_ROCK = {"logo_text": "Two-Rock", "logo": "script", "logo_colour": "chrome",
            "logo_pos": "topright", "grille_style": "basket", "grille": "#1c1c1c"}
FENDER_SCRIPT = {"logo_text": "Fender", "logo": "script", "logo_colour": "chrome",
                 "logo_pos": "topleft"}
MARSHALL_SCRIPT = {"logo_text": "Marshall", "logo": "script", "logo_colour": "#f4f4f4",
                   "grille_style": "basket", "grille": "#1c1c1c", "piping": "#efe9dc"}
DR_Z = {"logo_text": "Z", "logo": "z", "logo_colour": "gold", "logo_pos": "top",
        "grille_style": "wicker", "grille": "#b2ab9e"}
DR_Z_WRECK = {"logo": "z", "logo_colour": "#f2f2f2", "logo_pos": "top", "grille_style": "basket",
              "grille": "#1c1c1c", "body": "#151515"}
STYLE: dict[str, dict[str, object]] = {
    # heads
    "blackstar": {"logo_text": "Blackstar", "logo": "block", "logo_colour": "chrome",
                  "grille_style": "basket", "grille": "#1a1a1a", "panel": "#1c1c1c",
                  "knob_style": "chrome"},
    "cardiff": {**TWO_ROCK, "panel": "#1c1c1c", "knob_style": "skirt"},
    "tworock": {**TWO_ROCK, "panel": "#1c1c1c", "knob_style": "skirt"},
    "diezel": {"logo_text": "DIEZEL", "logo": "block", "logo_colour": "chrome",
               "grille_style": "mesh", "grille": "#1d1d1d", "panel": "#c8cacc",
               "knob_style": "chrome"},
    "engl_e645": {**ENGL_LOGO, "grille_style": "mesh", "grille": "#1b1d21", "panel": "#22252b",
                  "knob_style": "chrome", "corners": "chrome"},
    "engl_e650": {**ENGL_LOGO, "grille_style": "bars", "grille": "#1b1d21", "panel": "#cdb886",
                  "corners": "chrome"},
    "engl_blackmore": {**ENGL_LOGO, "grille_style": "bars", "grille": "#1b1d21",
                       "panel": "#cdb886", "corners": "chrome"},
    "evh5150": {"logo_text": "EVH", "logo": "oval", "grille_style": "basket", "grille": "#111111",
                "panel": "#e4e5e6", "knob": "#151515"},
    "jcm800": {**MARSHALL_SCRIPT, "knob_style": "gold"},
    "jetcity": {"logo_text": "JET CITY", "logo": "block", "logo_colour": "chrome",
                "grille_style": "basket", "panel": "#161616", "knob_style": "chrome"},
    "koch": {"logo_text": "Koch", "logo": "script", "logo_colour": "gold", "grille_style": "basket",
             "panel": "#1b1b1b", "knob_style": "gold"},
    "mark5": {"logo_text": "MESA/BOOGIE", "logo": "badge", "logo_pos": "bottomleft",
              "grille_style": "basket", "grille": "#161616", "panel_side": "top",
              "eq_sliders": 5},
    "or50": {**ORANGE_LOGO},
    "rockerverb": {**ORANGE_LOGO},
    "slo100": {"logo_text": "soldano", "logo": "lower", "logo_colour": "chrome",
               "grille_style": "mesh", "grille": "#202020", "knob_style": "chrome"},
    # combos
    "twin": {"logo_text": "Fender", "logo": "script", "logo_colour": "chrome",
             "logo_pos": "topleft", "grille_style": "sparkle", "knob_style": "skirt"},
    "jc120": {"logo_text": "Roland", "logo": "badge", "logo_pos": "topleft",
              "grille_style": "basket", "grille": "#161616", "corners": "chrome"},
    "maz18": {**DR_Z, "panel": "#1a1a1a", "knob_style": "chrome"},
    "zwreck": {**DR_Z_WRECK, "panel": "#1a1a1a", "knob_style": "chrome"},
    "mark3": {"logo_text": "MESA/BOOGIE", "logo": "badge", "logo_pos": "topleft",
              "grille_style": "basket", "grille": "#181818", "eq_sliders": 5},
    "falcon": {"logo": "script", "logo_colour": "gold", "logo_pos": "bottomright",
               "grille_style": "sparkle", "grille": "#c9c9c4", "body": "#5b3a29",
               "panel": "#e9e1cc", "panel_side": "right", "knob_style": "chrome",
               "piping": "#e9e1cc"},
    # cabinets
    "c_blackstar": {"logo_text": "Blackstar", "logo": "block", "logo_colour": "chrome",
                    "logo_pos": "topleft", "grille_style": "basket"},
    "c_diezel": {"logo_text": "DIEZEL", "logo": "block", "logo_colour": "chrome",
                 "grille_style": "basket"},
    "c_englpro": {**ENGL_LOGO, "grille_style": "mesh", "corners": "chrome"},
    "c_englvint": {**ENGL_LOGO, "grille_style": "basket", "piping": "#e9e9e9"},
    "c_evh": {"logo_text": "EVH", "logo": "oval", "grille_style": "basket"},
    "c_falcon": {"logo": "script", "logo_colour": "gold", "logo_pos": "bottomright",
                 "grille_style": "sparkle", "grille": "#c9c9c4", "body": "#5b3a29",
                 "piping": "#e9e1cc"},
    "c_hiwatt": {"logo_text": "HIWATT", "logo": "badge", "logo_pos": "top",
                 "grille_style": "basket", "grille": "#8a8a8a"},
    "c_jc120": {"logo_text": "Roland", "logo": "badge", "logo_pos": "topleft",
                "grille_style": "basket", "corners": "chrome"},
    "c_maz": {**DR_Z},
    "c_zwreck": {**DR_Z_WRECK},
    "c_peavey": {"logo_text": "PEAVEY", "logo": "block", "logo_colour": "chrome",
                 "logo_pos": "topleft", "grille_style": "basket"},
    "c_rect": {"logo_text": "MESA", "logo": "badge", "grille_style": "basket", "diamond": False},
    "c_soldano": {"logo_text": "soldano", "logo": "lower", "logo_colour": "chrome",
                  "grille_style": "basket"},
    "c_twin": {"logo_text": "Fender", "logo": "script", "logo_colour": "chrome",
               "logo_pos": "topleft", "grille_style": "sparkle"},
    "c_tworock112": {**TWO_ROCK},
    "c_tworock212": {**TWO_ROCK},
    # wahs and stompboxes: the name printed on them
    "crybaby": {"logo_text": "cry baby"},
    "crybaby535": {"logo_text": "cry baby"},
    "mooer_wah": {"big_knob": "#f2f2f2"},
    "bbplus": {"logo_text": "BB PLUS"},
    "bbpre": {"logo_text": "BB PREAMP", "body": "#b8693a"},
    "directdrive": {"logo_text": "DIRECT DRIVE", "body": "#1d2f5e", "accent": "#c0262d",
                    "knob_style": "chrome"},
    "fulldrive": {"logo_text": "FULLDRIVE 2", "knob_style": "chrome", "body": "#1f74d8"},
    "gt500": {"logo_text": "GT-500", "knob_style": "chrome", "body": "#c9cdd1"},
    "ocd": {"logo_text": "OCD", "body": "#efebdf"},
    "riot": {"logo_text": "RIOT", "body": "#1b1b1d"},
    "shredmaster": {"logo_text": "ShredMaster", "shape": "slope"},
    "tightrock": {"logo_text": "TIGHTROCK", "body": "#cf1f2a"},
    "timmy": {"logo_text": "TIMMY", "body": "#1e78d0"},
    "tubedriver": {"logo_text": "TUBE DRIVER", "knob_style": "chrome", "body": "#e4dfcc"},
    # Mooer micro pedals
    "mod1": {"logo_text": "Ninety Orange", "big_knob": "#f2f2f2"},
    "mod4": {"body": "#ece6dc", "panel": "#141414", "text": "#1a1a1a", "big_knob": "#efe6cf"},
    "mod5": {"body": "#ededed", "text": "#1a1a1a", "big_knob": "#efe6cf"},
    "mod6": {"body": "#151515", "text": "#f2f2f2", "big_knob": "#efe6cf"},
    "mooer_bluecomp": {"body": "#4f9fe0", "big_knob": "#f2f2f2"},
    "mooer_envelope": {"body": "#e6e4c2", "text": "#1a1a1a"},
    "mooer_flexboost": {"body": "#f2df1a", "text": "#1a1a1a"},
    "mooer_noisekiller": {"body": "#eeeeee", "text": "#1a1a1a"},
    "mooer_pureboost": {"body": "#f2e6e0", "text": "#1a1a1a"},
    "mooer_redkid": {},
    "mooer_yellowcomp": {"logo_text": "Yellow Comp"},
    "mooer_graphic_g": {"logo_text": "Graphic G", "body": "#6b9fd4", "text": "#f2f2f2"},
    "mooer_graphic_b": {"body": "#f0f0f0", "text": "#1a1a1a"},
    # units that used to have a photo
    "ac30": {"logo_text": "VOX", "logo": "block", "logo_colour": "#e9dcc0", "logo_pos": "topleft",
             "grille": "#6b2f24", "diamond": True, "piping": "gold"},
    "bassman": {**FENDER_SCRIPT, "grille_style": "wicker", "knob_style": "chicken"},
    "bluesdeluxe": {**FENDER_SCRIPT, "grille_style": "wicker", "knob_style": "chicken"},
    "deluxe": {**FENDER_SCRIPT, "grille_style": "sparkle", "knob_style": "skirt"},
    "supersonic": {**FENDER_SCRIPT, "body": "#e7dcc3", "panel": "#e7dcc3", "grille": "#5a3e2b",
                   "grille_style": "wicker", "knob_style": "chicken"},
    "ad30": {**ORANGE_LOGO},
    "hiwatt": {"logo_text": "HIWATT", "logo": "badge", "grille_style": "basket",
               "grille": "#1c1c1c", "panel": "#3f4246"},
    "jcm900": {**MARSHALL_SCRIPT, "knob_style": "gold"},
    "plexi": {**MARSHALL_SCRIPT, "knob_style": "gold"},
    "peavey5150": {"logo_text": "5150", "logo": "block", "logo_colour": "chrome",
                   "grille_style": "basket", "knob_style": "chrome"},
    "rectifier": {"logo_text": "MESA/BOOGIE", "logo": "badge", "grille_style": "basket"},
    "c_1960": {**MARSHALL_SCRIPT, "logo_pos": "top"},
    "c_ac30": {"logo_text": "VOX", "logo": "block", "logo_colour": "#e9dcc0", "logo_pos": "topleft",
               "grille": "#6b2f24", "diamond": True, "piping": "gold"},
    "c_bassman": {**FENDER_SCRIPT, "grille_style": "wicker"},
    "c_blues": {**FENDER_SCRIPT, "grille_style": "wicker"},
    "c_deluxe": {**FENDER_SCRIPT, "grille_style": "sparkle"},
    "c_supersonic": {**FENDER_SCRIPT, "body": "#e7dcc3", "grille": "#5a3e2b",
                     "grille_style": "wicker"},
    "c_mark": {"logo_text": "MESA", "logo": "badge", "logo_pos": "topleft",
               "grille_style": "basket", "grille": "#1d1d1d"},
    "c_orange212": {**ORANGE_LOGO},
    "c_orange412": {**ORANGE_LOGO},
    "bigmuff": {"logo_text": "Big Muff π"},
    "mt2": {"logo_text": "Metal Zone"},
    "fuzzface": {"logo_text": "Fuzz Face"},
    "klon": {"logo_text": "CENTAUR", "body": "#c8913f"},
    "metalmaster": {"logo_text": "METAL MASTER"},
    "rat": {"logo_text": "RAT"},
    "ts808": {"logo_text": "TUBE SCREAMER", "body": "#4fb38a"},
}

# Pedals laid out like the original unit (ui/art_spec.py): knobs, parts, switches and texts
# in fractions of the drawing. "$MODEL" is the GE150 model name: no brand is drawn.
ART: dict[str, dict[str, object]] = {
    "mooer_redkid": {
        "aspect": 0.6, "radius": 0.1,
        "parts": [
            {"rect": [0.0, 0.0, 1.0, 1.0], "fill": "copper", "radius": 0.1, "brushed": True},
            {"rect": [0.17, 0.07, 0.66, 0.34], "fill": "#c98a70", "stroke": "#8f4f3b",
             "width": 0.01, "radius": 0.06, "shade": True},
            {"rect": [0.25, 0.115, 0.5, 0.25], "fill": "#161616", "stroke": "#2b2b2b",
             "width": 0.008, "radius": 0.05},
            {"rect": [0.17, 0.59, 0.66, 0.34], "fill": "#c98a70", "stroke": "#8f4f3b",
             "width": 0.01, "radius": 0.06, "shade": True},
            {"rect": [0.25, 0.635, 0.5, 0.25], "fill": "#161616", "stroke": "#2b2b2b",
             "width": 0.008, "radius": 0.05},
            {"polyline": [[0.08, 0.44], [0.08, 0.05], [0.92, 0.05], [0.92, 0.44]],
             "stroke": "steel", "width": 0.06},
            {"polyline": [[0.08, 0.56], [0.08, 0.95], [0.92, 0.95], [0.92, 0.56]],
             "stroke": "steel", "width": 0.06},
        ],
        "texts": [{"box": [0.24, 0.455, 0.52, 0.08], "colour": "#8f4f3b"}],
    },
    "ts808": {
        "aspect": 0.6, "jacks": 0.5,
        "parts": [
            {"line": [0.04, 0.46, 0.96, 0.46], "stroke": "#2f7a5c", "width": 0.012},
            {"rect": [0.06, 0.49, 0.88, 0.48], "fill": "#58bd93", "radius": 0.04, "shade": True,
             "stroke": "#2f7a5c", "width": 0.01},
            {"rect": [0.1, 0.52, 0.8, 0.42], "stroke": "#f1ecd6", "width": 0.008,
             "radius": 0.02},
        ],
        "knobs": [
            {"param": "GAIN", "label": "OVERDRIVE", "at": [0.29, 0.15], "r": 0.115,
             "label_colour": "#f1ecd6"},
            {"param": "VOLUME", "label": "LEVEL", "at": [0.71, 0.15], "r": 0.115,
             "label_colour": "#f1ecd6"},
            {"param": "TONE", "label": "TONE", "at": [0.5, 0.32], "r": 0.1,
             "label_colour": "#f1ecd6", "label_at": "above"},
        ],
        "leds": [{"at": [0.5, 0.05], "r": 0.022}],
        "texts": [
            {"box": [0.14, 0.55, 0.72, 0.1], "colour": "#f1ecd6", "stretch": 0.72},
            {"text": "OVERDRIVE", "box": [0.3, 0.655, 0.4, 0.035], "colour": "#f1ecd6",
             "style": "light"},
        ],
        "switches": [{"type": "rect", "at": [0.5, 0.82], "size": [0.32, 0.14]}],
    },
    "rat": {
        "aspect": 0.62, "jacks": 0.45,
        "parts": [
            {"rect": [0.0, 0.0, 1.0, 0.36], "fill": "#262626", "radius": 0.06},
            {"line": [0.02, 0.36, 0.98, 0.36], "stroke": "#0a0a0a", "width": 0.012},
            {"rect": [0.12, 0.42, 0.76, 0.15], "stroke": "#f2f2f2", "width": 0.012,
             "radius": 0.025},
        ],
        "knobs": [
            {"param": "GAIN", "label": "DISTORTION", "at": [0.2, 0.2], "r": 0.1,
             "style": "knurled", "label_at": "above"},
            {"param": "TONE", "label": "FILTER", "at": [0.5, 0.2], "r": 0.1,
             "style": "knurled", "label_at": "above"},
            {"param": "VOLUME", "label": "VOLUME", "at": [0.8, 0.2], "r": 0.1,
             "style": "knurled", "label_at": "above"},
        ],
        "leds": [{"at": [0.88, 0.64], "r": 0.02}],
        "texts": [{"box": [0.16, 0.44, 0.68, 0.11], "colour": "#f2f2f2"}],
        "switches": [{"type": "round", "at": [0.5, 0.82], "r": 0.075}],
    },
    "bigmuff": {
        "aspect": 0.8,
        "parts": [
            {"rect": [0.04, 0.04, 0.92, 0.92], "stroke": "#151515", "width": 0.012,
             "radius": 0.02},
            {"line": [0.04, 0.3, 0.96, 0.3], "stroke": "#151515", "width": 0.008},
        ],
        "knobs": [
            {"param": "VOLUME", "label": "VOLUME", "at": [0.2, 0.16], "r": 0.075,
             "label_colour": "#151515", "label_at": "above"},
            {"param": "TONE", "label": "TONE", "at": [0.5, 0.16], "r": 0.075,
             "label_colour": "#151515", "label_at": "above"},
            {"param": "GAIN", "label": "SUSTAIN", "at": [0.8, 0.16], "r": 0.075,
             "label_colour": "#151515", "label_at": "above"},
        ],
        "texts": [
            {"box": [0.1, 0.33, 0.8, 0.17], "colour": "#c41e1e", "outline": "#151515"},
            {"text": "π", "box": [0.4, 0.5, 0.2, 0.16], "colour": "#c41e1e",
             "outline": "#151515", "upper": False},
        ],
        "leds": [{"at": [0.76, 0.66], "r": 0.018}],
        "switches": [{"type": "round", "at": [0.5, 0.81], "r": 0.075}],
    },
    "fuzzface": {
        "aspect": 1.0, "shape": "round",
        "parts": [
            {"poly": [[0.43, 0.42], [0.57, 0.42], [0.7, 0.78], [0.3, 0.78]], "fill": "#161616"},
            {"rect": [0.3, 0.8, 0.4, 0.06], "fill": "#d9d9d9", "stroke": "#151515",
             "width": 0.006, "radius": 0.01},
        ],
        "knobs": [
            {"param": "VOLUME", "label": "VOLUME", "at": [0.22, 0.33], "r": 0.075,
             "label_colour": "#202020"},
            {"param": "GAIN", "label": "FUZZ", "at": [0.78, 0.33], "r": 0.075,
             "label_colour": "#202020"},
        ],
        "texts": [{"box": [0.27, 0.17, 0.46, 0.1], "colour": "#3a3d40", "style": "serif"}],
        "switches": [{"type": "round", "at": [0.5, 0.64], "r": 0.06}],
    },
    "klon": {
        "aspect": 1.25, "jacks": 0.45, "radius": 0.04,
        "parts": [
            {"line": [0.04, 0.06, 0.96, 0.06], "stroke": "#e8b968", "width": 0.006},
        ],
        "knobs": [
            {"param": "GAIN", "label": "GAIN", "at": [0.2, 0.3], "r": 0.11,
             "label_colour": "#4a2c10"},
            {"param": "TONE", "label": "TREBLE", "at": [0.5, 0.3], "r": 0.11,
             "label_colour": "#4a2c10"},
            {"param": "VOLUME", "label": "OUTPUT", "at": [0.8, 0.3], "r": 0.11,
             "label_colour": "#4a2c10"},
        ],
        "leds": [{"at": [0.07, 0.3], "r": 0.015}],
        "texts": [{"box": [0.7, 0.74, 0.24, 0.07], "colour": "#4a2c10", "style": "serif"}],
        "switches": [{"type": "round", "at": [0.58, 0.77], "r": 0.04}],
    },
    "mt2": {
        "aspect": 0.58, "jacks": 0.42, "radius": 0.05,
        "parts": [
            {"rect": [0.04, 0.03, 0.92, 0.31], "fill": "#0e0e0e", "radius": 0.03},
            {"rect": [0.06, 0.49, 0.88, 0.48], "fill": "#3a3a3a", "radius": 0.03,
             "shade": True},
            {"line": [0.12, 0.57, 0.88, 0.57], "stroke": "#2a2a2a", "width": 0.006},
            {"line": [0.12, 0.62, 0.88, 0.62], "stroke": "#2a2a2a", "width": 0.006},
            {"line": [0.12, 0.67, 0.88, 0.67], "stroke": "#2a2a2a", "width": 0.006},
            {"rect": [0.3, 0.84, 0.4, 0.07], "fill": "#2e2e2e", "stroke": "#555555",
             "width": 0.006, "radius": 0.01},
        ],
        "knobs": [
            {"param": "VOLUME", "label": "LEVEL", "at": [0.15, 0.17], "r": 0.075,
             "label_at": "above"},
            {"param": "TONE", "label": "HIGH/LOW", "at": [0.38, 0.19], "r": 0.075,
             "label_at": "above"},
            {"param": "MID", "label": "MIDDLE", "at": [0.62, 0.19], "r": 0.075,
             "label_at": "above"},
            {"param": "GAIN", "label": "DIST", "at": [0.85, 0.17], "r": 0.075,
             "label_at": "above"},
        ],
        "leds": [{"at": [0.5, 0.06], "r": 0.02}],
        "texts": [
            {"text": "◄ OUTPUT", "box": [0.08, 0.36, 0.32, 0.04], "colour": "#ff7a1a"},
            {"text": "INPUT ◄", "box": [0.6, 0.36, 0.32, 0.04], "colour": "#ff7a1a"},
            {"box": [0.18, 0.415, 0.64, 0.065], "colour": "#ff7a1a", "style": "italic"},
        ],
    },
    "metalmaster": {
        "aspect": 0.62, "jacks": 0.33,
        "parts": [
            {"rect": [0.04, 0.03, 0.92, 0.28], "fill": "#101010", "radius": 0.04},
            {"rect": [0.75, 0.06, 0.18, 0.22], "fill": "#f2f2f2", "radius": 0.02},
            {"rect": [0.06, 0.38, 0.88, 0.14], "fill": "#f2f2f2", "stroke": "#111111",
             "width": 0.008, "radius": 0.015},
        ],
        "knobs": [
            {"param": "VOLUME", "label": "LEVEL", "at": [0.15, 0.15], "r": 0.07,
             "style": "silver"},
            {"param": "BASS", "label": "LOW", "at": [0.37, 0.15], "r": 0.07, "style": "silver"},
            {"param": "TONE", "label": "HI", "at": [0.59, 0.15], "r": 0.07, "style": "silver"},
            {"param": "GAIN", "label": "MORPH", "at": [0.84, 0.15], "r": 0.07,
             "style": "silver", "label_colour": "#111111"},
        ],
        "leds": [{"at": [0.5, 0.345], "r": 0.018}],
        "texts": [
            {"box": [0.1, 0.39, 0.8, 0.075], "colour": "#111111"},
            {"text": "HEAVY METAL DISTORTION", "box": [0.14, 0.47, 0.72, 0.035],
             "colour": "#111111"},
        ],
        "switches": [{"type": "treadle", "at": [0.5, 0.77], "size": [0.84, 0.4]}],
    },
    "directdrive": {
        "aspect": 0.6, "jacks": 0.62,
        "parts": [
            {"poly": [[0.0, 0.5], [1.0, 0.37], [1.0, 0.62], [0.0, 0.75]], "fill": "#c0262d"},
            {"ellipse": [0.5, 0.86, 0.15, 0.15], "stroke": "#8fa6d8", "width": 0.01},
        ],
        "knobs": [
            {"param": "VOLUME", "label": "VOLUME", "at": [0.2, 0.13], "r": 0.085,
             "style": "chrome"},
            {"param": "TONE", "label": "TONE", "at": [0.5, 0.13], "r": 0.085,
             "style": "chrome"},
            {"param": "GAIN", "label": "DRIVE", "at": [0.8, 0.13], "r": 0.085,
             "style": "chrome"},
        ],
        "leds": [{"at": [0.5, 0.035], "r": 0.02}],
        "texts": [{"box": [0.08, 0.38, 0.84, 0.24], "colour": "#e9f0fb", "style": "italic",
                   "outline": "#14224a"}],
        "switches": [{"type": "round", "at": [0.5, 0.86], "r": 0.07}],
    },
    "shredmaster": {
        "aspect": 0.86, "jacks": 0.5,
        "parts": [
            {"rect": [0.0, 0.0, 1.0, 0.3], "fill": "#262626", "radius": 0.05},
            {"line": [0.04, 0.29, 0.25, 0.29], "stroke": "#d4af37", "width": 0.008},
            {"line": [0.75, 0.29, 0.96, 0.29], "stroke": "#d4af37", "width": 0.008},
        ],
        "knobs": [
            {"param": "GAIN", "label": "GAIN", "at": [0.14, 0.11], "r": 0.06,
             "style": "knurled"},
            {"param": "BASS", "label": "BASS", "at": [0.32, 0.11], "r": 0.06,
             "style": "knurled"},
            {"param": "TONE", "label": "CONTOUR", "at": [0.5, 0.11], "r": 0.06,
             "style": "knurled"},
            {"param": "TREBLE", "label": "TREBLE", "at": [0.68, 0.11], "r": 0.06,
             "style": "knurled"},
            {"param": "VOLUME", "label": "VOLUME", "at": [0.86, 0.11], "r": 0.06,
             "style": "knurled"},
        ],
        "texts": [{"box": [0.26, 0.245, 0.48, 0.09], "colour": "#d4af37", "style": "italic",
                   "outline": "#000000"}],
        "leds": [{"at": [0.5, 0.42], "r": 0.012}],
        "switches": [{"type": "round", "at": [0.5, 0.55], "r": 0.05}],
    },
    "ocd": {
        "aspect": 0.6, "jacks": 0.6,
        "knobs": [
            {"param": "VOLUME", "label": "VOLUME", "at": [0.26, 0.16], "r": 0.11,
             "style": "cream", "label_colour": "#1a1a1a"},
            {"param": "GAIN", "label": "DRIVE", "at": [0.74, 0.16], "r": 0.11, "style": "cream",
             "label_colour": "#1a1a1a"},
            {"param": "TONE", "label": "TONE", "at": [0.5, 0.33], "r": 0.1, "style": "cream",
             "label_colour": "#1a1a1a"},
        ],
        "toggles": [{"at": [0.5, 0.08], "r": 0.025}],
        "texts": [{"box": [0.1, 0.48, 0.8, 0.15], "colour": "#161616", "style": "italic"}],
        "leds": [{"at": [0.5, 0.7], "r": 0.02}],
        "switches": [{"type": "round", "at": [0.5, 0.84], "r": 0.075}],
    },
    "timmy": {
        "aspect": 0.55, "jacks": 0.5,
        "knobs": [
            {"param": "VOLUME", "label": "VOLUME", "at": [0.26, 0.12], "r": 0.1},
            {"param": "GAIN", "label": "GAIN", "at": [0.74, 0.12], "r": 0.1},
            {"param": "BASS", "label": "BASS", "at": [0.26, 0.32], "r": 0.08},
            {"param": "TONE", "label": "TREBLE", "at": [0.74, 0.32], "r": 0.08},
        ],
        "toggles": [{"at": [0.5, 0.22], "r": 0.025}],
        "texts": [{"box": [0.15, 0.48, 0.7, 0.14], "colour": "#f2f2f2", "style": "script",
                   "upper": False}],
        "leds": [{"at": [0.5, 0.67], "r": 0.02}],
        "switches": [{"type": "round", "at": [0.5, 0.84], "r": 0.09}],
    },
    "tubedriver": {
        "aspect": 0.72, "radius": 0.05,
        "parts": [
            {"rect": [0.0, 0.9, 1.0, 0.1], "fill": "#151515", "radius": 0.03},
            {"line": [0.06, 0.15, 0.94, 0.15], "stroke": "#1a1a1a", "width": 0.006},
            {"line": [0.06, 0.52, 0.94, 0.52], "stroke": "#1a1a1a", "width": 0.008},
            {"line": [0.06, 0.7, 0.94, 0.7], "stroke": "#1a1a1a", "width": 0.008},
            {"line": [0.36, 0.475, 0.64, 0.475], "stroke": "#1a1a1a", "width": 0.006},
        ],
        "knobs": [
            {"param": "VOLUME", "label": "OUT LEVEL", "at": [0.16, 0.36], "r": 0.065,
             "style": "yellow", "label_colour": "#1a1a1a"},
            {"param": "TREBLE", "label": "HI", "at": [0.39, 0.36], "r": 0.065, "style": "yellow",
             "label_colour": "#1a1a1a"},
            {"param": "TONE", "label": "LO", "at": [0.61, 0.36], "r": 0.065, "style": "yellow",
             "label_colour": "#1a1a1a"},
            {"param": "GAIN", "label": "TUBE DRIVE", "at": [0.84, 0.36], "r": 0.065,
             "style": "yellow", "label_colour": "#1a1a1a"},
        ],
        "leds": [{"at": [0.3, 0.24], "r": 0.016, "colour": "green"},
                 {"at": [0.7, 0.24], "r": 0.016}],
        "texts": [
            {"text": "OUT ▲          ▼ IN", "box": [0.2, 0.07, 0.6, 0.05], "colour": "#1a1a1a"},
            {"text": "POWER", "box": [0.2, 0.17, 0.2, 0.035], "colour": "#1a1a1a"},
            {"text": "DRIVE", "box": [0.6, 0.17, 0.2, 0.035], "colour": "#1a1a1a"},
            {"box": [0.12, 0.54, 0.76, 0.14], "colour": "#111111", "stretch": 0.85},
            {"text": "REAL TUBE OVERDRIVE", "box": [0.15, 0.72, 0.7, 0.04],
             "colour": "#1a1a1a"},
        ],
        "switches": [{"type": "round", "at": [0.5, 0.82], "r": 0.045}],
    },
    "fulldrive": {
        "aspect": 1.05, "jacks": 0.4,
        "knobs": [
            {"param": "VOLUME", "label": "VOLUME", "at": [0.14, 0.2], "r": 0.075},
            {"param": "TONE", "label": "TONE", "at": [0.37, 0.2], "r": 0.075},
            {"param": "GAIN", "label": "OVERDRIVE", "at": [0.63, 0.2], "r": 0.075},
            {"param": "BOOST", "label": "BOOST", "at": [0.86, 0.2], "r": 0.075},
        ],
        "toggles": [{"at": [0.5, 0.12], "r": 0.022}],
        "texts": [{"box": [0.14, 0.46, 0.72, 0.15], "colour": "#f2f2f2", "style": "italic",
                   "outline": "#0d3f7a"}],
        "leds": [{"at": [0.2, 0.68], "r": 0.016, "colour": "green"},
                 {"at": [0.8, 0.68], "r": 0.016}],
        "switches": [{"type": "round", "at": [0.2, 0.83], "r": 0.06},
                     {"type": "round", "at": [0.8, 0.83], "r": 0.06}],
    },
    "gt500": {
        "aspect": 1.25, "jacks": 0.4, "radius": 0.04,
        "parts": [
            {"rect": [0.04, 0.05, 0.43, 0.46], "stroke": "#151515", "width": 0.008,
             "radius": 0.03},
            {"rect": [0.53, 0.05, 0.43, 0.46], "stroke": "#151515", "width": 0.008,
             "radius": 0.03},
            {"rect": [0.3, 0.66, 0.4, 0.17], "stroke": "#151515", "width": 0.01,
             "radius": 0.02},
        ],
        "knobs": [
            {"param": "VOLUME", "label": "Volume", "at": [0.14, 0.18], "r": 0.065,
             "label_colour": "#151515"},
            {"param": "BOOST", "label": "Drive", "at": [0.37, 0.18], "r": 0.065,
             "label_colour": "#151515"},
            {"param": "BASS", "label": "Bass", "at": [0.14, 0.38], "r": 0.04,
             "label_colour": "#151515"},
            {"param": "TREBLE", "label": "Highs", "at": [0.37, 0.38], "r": 0.04,
             "label_colour": "#151515"},
            {"param": "VOLUME", "label": "Volume", "at": [0.63, 0.18], "r": 0.065,
             "label_colour": "#151515"},
            {"param": "GAIN", "label": "Distortion", "at": [0.86, 0.18], "r": 0.065,
             "label_colour": "#151515"},
            {"param": "BASS", "label": "Bass", "at": [0.61, 0.38], "r": 0.04,
             "label_colour": "#151515"},
            {"param": "MID", "label": "Mids", "at": [0.745, 0.38], "r": 0.04,
             "label_colour": "#151515"},
            {"param": "TONE", "label": "Highs", "at": [0.88, 0.38], "r": 0.04,
             "label_colour": "#151515"},
        ],
        "toggles": [{"at": [0.5, 0.12], "r": 0.02}],
        "leds": [{"at": [0.5, 0.3], "r": 0.016}],
        "texts": [{"box": [0.33, 0.68, 0.34, 0.13], "colour": "#151515"}],
        "switches": [{"type": "round", "at": [0.12, 0.82], "r": 0.05},
                     {"type": "round", "at": [0.88, 0.82], "r": 0.05}],
    },
    "riot": {
        "aspect": 0.56, "jacks": 0.5,
        "parts": [
            {"poly": [[0.06, 0.6], [0.14, 0.57], [0.14, 0.63]], "fill": "#a36cc9"},
            {"poly": [[0.86, 0.6], [0.94, 0.57], [0.94, 0.63]], "fill": "#a36cc9"},
        ],
        "knobs": [
            {"param": "GAIN", "label": "Dist", "at": [0.24, 0.17], "r": 0.12, "style": "chicken",
             "label_colour": "#a36cc9", "label_at": "above"},
            {"param": "VOLUME", "label": "Level", "at": [0.76, 0.17], "r": 0.12,
             "style": "chicken", "label_colour": "#a36cc9", "label_at": "above"},
            {"param": "TONE", "label": "Tone", "at": [0.5, 0.38], "r": 0.12, "style": "chicken",
             "label_colour": "#a36cc9", "label_at": "above"},
        ],
        "toggles": [{"at": [0.5, 0.09], "r": 0.022}],
        "leds": [{"at": [0.5, 0.56], "r": 0.022, "colour": "white"}],
        "texts": [{"box": [0.2, 0.83, 0.6, 0.12], "colour": "#a36cc9", "style": "script",
                   "upper": False}],
        "switches": [{"type": "round", "at": [0.5, 0.7], "r": 0.1}],
    },
    "bbpre": {
        "aspect": 0.6, "jacks": 0.55, "radius": 0.05,
        "parts": [{"rect": [0.05, 0.03, 0.9, 0.94], "stroke": "#f0c9a6", "width": 0.008,
                   "radius": 0.04}],
        "knobs": [
            {"param": "VOLUME", "label": "Volume", "at": [0.27, 0.15], "r": 0.105,
             "label_colour": "#f6e0c8"},
            {"param": "GAIN", "label": "Gain", "at": [0.73, 0.15], "r": 0.105,
             "label_colour": "#f6e0c8"},
            {"param": "TREBLE", "label": "Treble", "at": [0.27, 0.36], "r": 0.09,
             "label_colour": "#f6e0c8"},
            {"param": "TONE", "label": "Bass", "at": [0.73, 0.36], "r": 0.09,
             "label_colour": "#f6e0c8"},
        ],
        "texts": [{"box": [0.18, 0.52, 0.64, 0.11], "colour": "#f6e0c8", "style": "italic",
                   "outline": "#5a2a10"}],
        "leds": [{"at": [0.5, 0.68], "r": 0.02}],
        "switches": [{"type": "round", "at": [0.5, 0.83], "r": 0.075}],
    },
    "bbplus": {
        "aspect": 1.0, "jacks": 0.45,
        "knobs": [
            {"param": "VOLUME", "label": "VOL", "at": [0.15, 0.14], "r": 0.065,
             "label_colour": "#2b1b08"},
            {"param": "GAIN", "label": "GAIN", "at": [0.35, 0.14], "r": 0.065,
             "label_colour": "#2b1b08"},
            {"param": "TONE", "label": "TONE", "at": [0.25, 0.33], "r": 0.055,
             "label_colour": "#2b1b08"},
            {"param": "VOLUME", "label": "VOL", "at": [0.65, 0.14], "r": 0.065,
             "label_colour": "#2b1b08"},
            {"param": "GAIN", "label": "GAIN", "at": [0.85, 0.14], "r": 0.065,
             "label_colour": "#2b1b08"},
            {"param": "TONE", "label": "TONE", "at": [0.75, 0.33], "r": 0.055,
             "label_colour": "#2b1b08"},
        ],
        "texts": [{"box": [0.25, 0.47, 0.5, 0.1], "colour": "#2b1b08"}],
        "leds": [{"at": [0.25, 0.63], "r": 0.018}, {"at": [0.75, 0.63], "r": 0.018}],
        "switches": [{"type": "round", "at": [0.25, 0.81], "r": 0.07},
                     {"type": "round", "at": [0.75, 0.81], "r": 0.07}],
    },
    "tightrock": {
        "aspect": 0.96, "jacks": 0.62,
        "parts": [
            {"rect": [0.18, -0.02, 0.64, 0.13], "stroke": "chrome", "width": 0.03,
             "radius": 0.05},
            {"rect": [0.08, 0.83, 0.84, 0.12], "fill": "#f2f2f2", "stroke": "#111111",
             "width": 0.01, "radius": 0.03},
        ],
        "knobs": [
            {"param": "VOLUME", "label": "Volume", "at": [0.14, 0.17], "r": 0.075},
            {"param": "TONE", "label": "Tone", "at": [0.38, 0.17], "r": 0.075},
            {"param": "GAIN", "label": "Gain", "at": [0.62, 0.17], "r": 0.075},
            {"param": "TIGHT", "label": "Tight", "at": [0.86, 0.17], "r": 0.075},
        ],
        "toggles": [{"at": [0.26, 0.31], "r": 0.018}, {"at": [0.5, 0.31], "r": 0.018},
                    {"at": [0.74, 0.31], "r": 0.018}],
        "leds": [{"at": [0.5, 0.69], "r": 0.016}],
        "texts": [{"box": [0.12, 0.845, 0.76, 0.09], "colour": "#c4161c"}],
        "switches": [{"type": "round", "at": [0.5, 0.76], "r": 0.045}],
    },
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
    for gid, look in STYLE.items():
        G[gid].update(look)
    for gid, recipe in ART.items():
        G[gid]["art"] = recipe
    for entry in G.values():  # no brand or product name is drawn: the model name goes there
        entry.pop("logo_text", None)
    items = [f'  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}' for k, v in G.items()]
    lines += [",\n".join(items), ' },', ' "models": {']
    rows = [f'  {json.dumps(k)}: {json.dumps(v)}' for k, v in models.items()]
    lines += [",\n".join(rows), ' }', '}']
    OUT.write_text("\n".join(lines) + "\n")
    print(f"{OUT}: {len(G)} gear, {sum(len(v) for v in models.values())} models")


if __name__ == "__main__":
    main()
