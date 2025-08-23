# engine_init.py
# [Fix]
import hashlib
import os
import sys

from typing import Dict

ENGINE_VERSION = os.getenv("ENGINE_VERSION", "VV5Q")
ENGINE_PATH = os.getenv("ENGINE_PATH", "Virtueverse Engine V5 Quirked.txt")


_ENGINE_TEXT: str = ""
_ENGINE_BYTES: int = 0
_ENGINE_HASH: str = ""
_ENGINE_READY: bool = False
_ENGINE_ERROR: str | None = None

def _hash_text(txt: str) -> str:
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()

def load_engine(strict: bool = True) -> None:
    """Read the engine file once and cache version/size/hash. strict=True aborts boot on failure."""
    global _ENGINE_TEXT, _ENGINE_BYTES, _ENGINE_HASH, _ENGINE_READY, _ENGINE_ERROR
    try:
        with open(ENGINE_PATH, "r", encoding="utf-8") as f:
            _ENGINE_TEXT = f.read()
        _ENGINE_BYTES = len(_ENGINE_TEXT.encode("utf-8"))
        _ENGINE_HASH = _hash_text(_ENGINE_TEXT)
        _ENGINE_READY = True
        _ENGINE_ERROR = None
    except Exception as e:
        _ENGINE_TEXT = ""
        _ENGINE_BYTES = 0
        _ENGINE_HASH = ""
        _ENGINE_READY = False
        _ENGINE_ERROR = f"{type(e).__name__}: {e}"
        if strict:
            # Fail the process so you never “run improv” without the scroll
            sys.stderr.write(f"[engine_init] FATAL: could not load engine at {ENGINE_PATH}: {_ENGINE_ERROR}\n")
            sys.exit(1)

def get_engine_text() -> str:
    """Return the cached engine text (do NOT log or expose this)."""
    return _ENGINE_TEXT

def health_blob() -> Dict[str, object]:
    """Minimal health payload; never returns the engine body."""
    return {
        "engine_version": ENGINE_VERSION,
        "engine_bytes": _ENGINE_BYTES,
        "engine_hash": _ENGINE_HASH,
        "engine_ready": _ENGINE_READY,
        "engine_error": _ENGINE_ERROR,  # will be None on success
    }
