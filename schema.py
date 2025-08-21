# schema.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class Scene(BaseModel):
    id: str
    tone: str
    location: str
    beat_idx: int
    spi: int

class PC(BaseModel):
    name: str
    stance: str
    last_move: str

class NPC(BaseModel):
    id: str
    name: str
    traits: List[str]
    quirks: List[str]
    rv: float
    pv: float
    voice_style: str

class PunSys(BaseModel):
    tier: int
    wave: List[float]
    gate: str

class Flashpoint(BaseModel):
    armed: bool
    type: str
    threshold: float
    cooldown_left: int

class Constraints(BaseModel):
    max_tokens: int
    no_meta: bool
    jp_dialogue_only: bool
    furigana_in_breakdown_only: bool

class Asks(BaseModel):
    render_narration: bool
    suggest_pc_moves: int
    return_observed_markers: List[str]

class EngineTurn(BaseModel):
    version: str
    seed: int
    lang_mode: str
    scene: Scene
    pc: PC
    npcs: List[NPC]
    punsys: PunSys
    flashpoint: Flashpoint
    constraints: Constraints
    asks: Asks

class DialogueLine(BaseModel):
    speaker: str
    line: str

class Marker(BaseModel):
    speaker: str
    trait: str
    quirk: str
    tone: str

class MoveSuggestion(BaseModel):
    id: str
    label: str

class Translation(BaseModel):
    jp: str
    kana: str
    en: str

class Breakdown(BaseModel):
    translations: List[Translation]
    vocab: List[str]

class FlashpointHint(BaseModel):
    prime_level: float
    ready_to_trigger: bool

class PunSysFeedback(BaseModel):
    pressure_hint: float
    tier_suggestion: int

class NarrativeTurn(BaseModel):
    scene_id: str
    beat_idx: int
    narration_en: str
    dialogue_jp: List[DialogueLine]
    markers: List[Marker]
    pc_move_suggestions: List[MoveSuggestion]
    punsys_feedback: PunSysFeedback
    flashpoint_hint: FlashpointHint
    post_scene_breakdown: Breakdown
