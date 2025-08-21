# spine.py
from schema import NarrativeTurn, EngineTurn, Scene, PC, PCONPC, PunSys, Flashpoint
import json, os, random
from typing import Any
from copy import deepcopy

class Spine:
    def __init__(self):
        self.state_file = "state.json"
        self.load_state()

    def load_state(self):
        if os.path.exists(self.state_file):
            with open(self.state_file, "r") as f:
                self.state = json.load(f)
        else:
            self.state = self.default_state()
            self.save_state()

    def save_state(self):
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def default_state(self) -> dict:
        return {
            "version": "v6",
            "scene": {
                "id": "S-001",
                "tone": "slow_burn",
                "location": "rooftop",
                "beat_idx": 0,
                "spi": 3
            },
            "pc": {
                "name": "Bullet",
                "stance": "active",
                "last_move": ""
            },
            "npcs": [
                {
                    "id": "CNPC-1",
                    "name": "Aiko",
                    "traits": ["witty", "protective"],
                    "quirks": ["tease", "soft_dom"],
                    "rv": 0.6,
                    "pv": 0.4,
                    "voice_style": "light, clipped"
                }
            ],
            "punsys": {
                "tier": 2,
                "wave": [0.2, 0.4, 0.55, 0.35],
                "gate": "open"
            },
            "flashpoint": {
                "armed": True,
                "type": "jealousy",
                "threshold": 0.7,
                "cooldown_left": 2
            }
        }

    def process_turn(self, turn: NarrativeTurn) -> EngineTurn:
        # Validate language and tier
        narration = turn.narration_en
        dialogue_lines = [d["line"] for d in turn.dialogue_jp]

        if any(self.contains_japanese(c) for c in narration):
            raise Exception("JP detected in narration")

        for line in dialogue_lines:
            if any(self.contains_english(c) for c in line):
                raise Exception("EN detected in dialogue")

        if turn.punsys_feedback["tier_suggestion"] > self.state["punsys"]["tier"]:
            raise Exception("Tier exceeded")

        # Update beat index and basic memory
        self.state["scene"]["beat_idx"] += 1
        self.state["pc"]["last_move"] = turn.pc_move_suggestions[0]["label"] if turn.pc_move_suggestions else ""
        npc = self.state["npcs"][0]
        npc["rv"] = min(1.0, npc["rv"] + 0.02)
        npc["pv"] = min(1.0, npc["pv"] + 0.03)

        # Flashpoint logic
        avg_pressure = (npc["rv"] + npc["pv"]) / 2
        fp = self.state["flashpoint"]

        if fp["cooldown_left"] > 0:
            fp["cooldown_left"] -= 1
        elif fp["armed"] and avg_pressure >= fp["threshold"]:
            fp["armed"] = False
            fp["cooldown_left"] = 5

        # PunSys modulation
        self.state["punsys"]["wave"] = [round(random.uniform(0.2, 0.7), 2) for _ in range(4)]

        self.save_state()

        return EngineTurn(
            version="v6",
            seed=1337,
            lang_mode="EN_narration_JP_dialogue",
            scene=Scene(**self.state["scene"]),
            pc=PC(**self.state["pc"]),
            npcs=[PCONPC(**npc)],
            punsys=PunSys(**self.state["punsys"]),
            flashpoint=Flashpoint(**fp),
            constraints={
                "max_tokens": 250,
                "no_meta": True,
                "jp_dialogue_only": True,
                "furigana_in_breakdown_only": True
            },
            asks={
                "render_narration": True,
                "suggest_pc_moves": 3,
                "return_observed_markers": ["trait", "quirk", "tone"]
            }
        )

    def contains_japanese(self, c: str) -> bool:
        return '\u3040' <= c <= '\u30ff' or '\u4e00' <= c <= '\u9faf'

    def contains_english(self, c: str) -> bool:
        return 'A' <= c <= 'Z' or 'a' <= c <= 'z'
