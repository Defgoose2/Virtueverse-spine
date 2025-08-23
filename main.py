# main.py
# VirtueVerse v5 — Step 4 Minimal Endpoint (Pydantic v2-ready)
# POST /vv/jobs with shared-secret auth, version check, schema validation,
# per-job handler stubs, uniform Bridge-Result response.

import os
import time
import uuid
from typing import Optional, Literal, List, Dict, Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
import uvicorn
from pathlib import Path
import re

from engine_init import load_engine, health_blob

# -----------------------------
# Config
# -----------------------------
ENGINE_VERSION = os.getenv("ENGINE_VERSION", "").strip()
SHARED_SECRET = os.getenv("VV_SHARED_SECRET", "")

# -----------------------------
# Engine Init (Step 1.4)
# -----------------------------
load_engine(strict=True)

# -----------------------------
# Schemas (Step 1 contract)
# -----------------------------
JobType = Literal["setup", "flashpoint_map", "scene", "subs", "audit", "continuity_check"]

class BridgeJobParams(BaseModel):
    strict_lang: Optional[bool] = True

    # Step 3/4 fields used by validators and handlers
    anchor_hint: Optional[str] = None
    goal: Optional[str] = None
    scene_ref: Optional[str] = None
    scene_text: Optional[str] = None
    answers: Optional[Dict[str, Any]] = None
    text: Optional[str] = None
    artifact_ref: Optional[str] = None
    history_refs: Optional[List[str]] = None
    summary_text: Optional[str] = None
    setup_ref: Optional[str] = None

    # Optional D15 quality-of-life fields (not used in minimal gate logic)
    retry: Optional[int] = 0
    user_input: Optional[str] = None

class BridgeJob(BaseModel):
    version: str
    auth_token: Optional[str] = None  # reserved for parity, not used for auth
    session_id: str
    job_id: str
    job_type: JobType
    params: BridgeJobParams = Field(default_factory=BridgeJobParams)

    @field_validator("version")
    @classmethod
    def must_match_engine_version(cls, v: str) -> str:
        if v != ENGINE_VERSION:
            raise ValueError(f"version mismatch: expected {ENGINE_VERSION}")
        return v

class BridgeError(BaseModel):
    code: Literal[
        "auth_error",
        "schema_error",
        "version_error",
        "engine_refusal",
        "rate_limited",
        "unknown",
        "input_unresolved",
        "format_error",   # Step 3 validators
    ]
    message: str

class BridgeArtifact(BaseModel):
    content: str

class BridgeResult(BaseModel):
    ok: bool
    job_id: str
    session_id: str
    artifact_type: Optional[str] = None
    artifact: Optional[BridgeArtifact] = None
    notes: List[str] = Field(default_factory=list)
    errors: List[BridgeError] = Field(default_factory=list)
    # Ops fields
    request_id: str
    latency_ms: int

# -----------------------------
# App
# -----------------------------
app = FastAPI(title="VirtueVerse v5 Step-4 Stub", version="0.0.3")

@app.get("/")
def root():
    return {"message": "VirtueVerse v5 Step-4 stub. See /docs and POST /vv/jobs."}

@app.get("/healthz")
def healthz():
    return {"ok": True, "version": ENGINE_VERSION}

def auth_check(header_secret: Optional[str]) -> None:
    """
    Shared-secret check. Accepts:
      - Authorization: Bearer <secret>
      - X-Shared-Secret: <secret>
    """
    header_secret = (header_secret or "").strip()
    want = (SHARED_SECRET or "").strip()
    if not want:
        raise HTTPException(status_code=500, detail="Server misconfigured: VV_SHARED_SECRET missing.")
    if not header_secret:
        raise HTTPException(status_code=401, detail="Missing Authorization header.")
    if header_secret != f"Bearer {want}" and header_secret != want:
        raise HTTPException(status_code=403, detail="Invalid shared secret.")

def make_result(
    job: "BridgeJob",
    *,
    ok: bool,
    t0: float,
    artifact_type: Optional[str] = None,
    content: Optional[str] = None,
    notes: Optional[List[str]] = None,
    errors: Optional[List[BridgeError]] = None,
) -> BridgeResult:
    return BridgeResult(
        ok=ok,
        job_id=job.job_id,
        session_id=job.session_id,
        artifact_type=artifact_type,
        artifact=BridgeArtifact(content=content) if content is not None else None,
        notes=notes or [],
        errors=errors or [],
        request_id=str(uuid.uuid4()),
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )

# --- Step 3.2: Prompt Pack Loader ---
PROMPT_DIR = Path(__file__).parent / "prompts"
PROMPTS = {
    "setup": PROMPT_DIR / "setup.txt",
    "flashpoint_map": PROMPT_DIR / "flashpoint_map.txt",
    "scene": PROMPT_DIR / "scene.txt",
    "subs": PROMPT_DIR / "subs.txt",
    "audit": PROMPT_DIR / "audit.txt",
    "continuity_check": PROMPT_DIR / "continuity_check.txt",
}

def get_prompt(job_type: str) -> Optional[str]:
    p = PROMPTS.get(job_type)
    if not p or not p.exists():
        return None
    return p.read_text(encoding="utf-8")
# --- end Step 3.2 ---

# --- Step 3.3: Minimal Format Guards ---
def check_scene_format(text: str) -> tuple[bool, str]:
    if "Breakdown:" not in text:
        return False, "Missing 'Breakdown:' section"
    first_line = next((ln for ln in text.splitlines() if ln.strip()), "")
    if "「" in first_line or "」" in first_line:
        return False, "First line must be English narration"
    if not re.search(r'「.+?」', text):
        return False, "No Japanese dialogue lines found"
    pairs = re.findall(r'^\-\s*「.+?」\s*->\s*".+?"\s*$', text, flags=re.M)
    if len(pairs) == 0:
        return False, "No JP→EN pairs in Breakdown"
    return True, "ok"

def check_subs_format(text: str) -> tuple[bool, str]:
    if not text.strip().startswith("Breakdown:"):
        return False, "Subs must start with 'Breakdown:'"
    pairs = re.findall(r'^\-\s*「.+?」\s*->\s*".+?"\s*$', text, flags=re.M)
    if len(pairs) == 0:
        return False, "No subtitle pairs found"
    return True, "ok"

def check_audit_format(text: str) -> tuple[bool, str]:
    need = ["Audit:", "Actions:"]
    missing = [k for k in need if k not in text]
    if missing:
        return False, "Missing sections: " + ", ".join(missing)
    return True, "ok"

def check_continuity_format(text: str) -> tuple[bool, str]:
    need = ["Continuity:", "Status:", "Evidence:"]
    missing = [k for k in need if k not in text]
    if missing:
        return False, "Missing fields: " + ", ".join(missing)
    return True, "ok"

def validate_artifact(job_type: str, text: str) -> tuple[bool, str]:
    if job_type == "scene":
        return check_scene_format(text)
    if job_type == "subs":
        return check_subs_format(text)
    if job_type == "audit":
        return check_audit_format(text)
    if job_type == "continuity_check":
        return check_continuity_format(text)
    return True, "ok"
# --- end Step 3.3 ---

# -----------------------------
# D15 invalid-input checks (minimal, stateless)
# -----------------------------
def validate_minimal_inputs(job: BridgeJob) -> Optional[BridgeError]:
    p = job.params or BridgeJobParams()

    if job.job_type == "setup":
        if p.answers is None:
            return BridgeError(
                code="input_unresolved",
                message="setup requires params.answers (dict with your 6 setup answers)",
            )

    elif job.job_type == "flashpoint_map":
        if not (p.setup_ref or p.answers):
            return BridgeError(
                code="input_unresolved",
                message="flashpoint_map requires params.setup_ref or params.answers",
            )

    elif job.job_type == "scene":
        if not (p.anchor_hint or p.goal or p.scene_ref):
            return BridgeError(
                code="input_unresolved",
                message="scene requires one of: params.anchor_hint | params.goal | params.scene_ref",
            )

    elif job.job_type == "subs":
        if not (p.scene_ref or p.scene_text):
            return BridgeError(
                code="input_unresolved",
                message="subs requires params.scene_ref or params.scene_text",
            )

    elif job.job_type == "audit":
        if not (p.artifact_ref or p.text):
            return BridgeError(
                code="input_unresolved",
                message="audit requires params.artifact_ref or params.text",
            )

    elif job.job_type == "continuity_check":
        if not (p.history_refs or p.summary_text):
            return BridgeError(
                code="input_unresolved",
                message="continuity_check requires params.history_refs or params.summary_text",
            )

    return None

# -----------------------------
# Per-job minimal handlers (no model calls in Step 4)
# -----------------------------
def handle_setup(job: BridgeJob) -> Dict[str, str]:
    return {"artifact_type": "setup_seed", "content": "setup: anchors seeded (stub)."}

def handle_flashpoint_map(job: BridgeJob) -> Dict[str, str]:
    return {"artifact_type": "flashpoint_map", "content": "flashpoint_map: anchors + foreshadow (stub)."}

def handle_scene(job: BridgeJob) -> Dict[str, str]:
    # Minimal v5-shaped scene: EN narration, JP lines in 「」, then Breakdown pairs.
    content = (
        "Cold air nips your fingers as the station chime fades. You spot her by the map, eyes on you.\n"
        "「様子を見るだけ。…どうする？」\n"
        "「落ち着いて。」\n"
        "\n"
        "Breakdown:\n"
        "- 「様子を見るだけ。…どうする？」 -> \"Just observing... so what do we do?\"\n"
        "- 「落ち着いて。」 -> \"Calm down.\""
    )
    return {"artifact_type": "scene_block", "content": content}

def handle_subs(job: BridgeJob) -> Dict[str, str]:
    content = (
        "Breakdown:\n"
        "- 「様子を見るだけ。…どうする？」 -> \"Just observing... so what do we do?\"\n"
        "- 「落ち着いて。」 -> \"Calm down.\""
    )
    return {"artifact_type": "subs_pairs", "content": content}

def handle_audit(job: BridgeJob) -> Dict[str, str]:
    content = (
        "Audit:\n"
        "- Language discipline: pass — EN narration, JP in quotes, breakdown at end\n"
        "- Flashpoint discipline: pass — one tension advanced\n"
        "- Tone & profanity: pass — neutral tone, no profanity\n"
        "- Meta leakage: pass — no out-of-world notes\n"
        "Actions:\n"
        "- Keep JP lines short and conversational next scene."
    )
    return {"artifact_type": "audit_report", "content": content}

def handle_continuity_check(job: BridgeJob) -> Dict[str, str]:
    content = (
        "Continuity:\n"
        "- Prior promise: \"Breakdown only at the end\"\n"
        "Status: kept\n"
        "Evidence: Scene placed all JP→EN pairs under 'Breakdown:'"
    )
    return {"artifact_type": "continuity_result", "content": content}

JOB_HANDLERS = {
    "setup": handle_setup,
    "flashpoint_map": handle_flashpoint_map,
    "scene": handle_scene,
    "subs": handle_subs,
    "audit": handle_audit,
    "continuity_check": handle_continuity_check,
}

# -----------------------------
# Route
# -----------------------------
@app.post("/vv/jobs")
async def vv_jobs(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_shared_secret: Optional[str] = Header(default=None),
):
    t0 = time.perf_counter()
    try:
        # auth
        auth_check(authorization or x_shared_secret)

        # parse and validate schema
        payload = await request.json()
        try:
            job = BridgeJob(**payload)
        except Exception as e:
            # Surface version mismatch distinctly
            if isinstance(e, ValueError) and "version mismatch:" in str(e):
                res = BridgeResult(
                    ok=False,
                    job_id=payload.get("job_id", "unknown"),
                    session_id=payload.get("session_id", "unknown"),
                    artifact_type=None,
                    artifact=None,
                    notes=[],
                    errors=[BridgeError(code="version_error", message=f"backend pinned to {ENGINE_VERSION}")],
                    request_id=str(uuid.uuid4()),
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                )
                return JSONResponse(status_code=400, content=res.model_dump())
            res = BridgeResult(
                ok=False,
                job_id=payload.get("job_id", "unknown"),
                session_id=payload.get("session_id", "unknown"),
                artifact_type=None,
                artifact=None,
                notes=[],
                errors=[BridgeError(code="schema_error", message=str(e))],
                request_id=str(uuid.uuid4()),
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )
            return JSONResponse(status_code=400, content=res.model_dump())

        # --- Step 4: D15 invalid-input gate ---
        d15 = validate_minimal_inputs(job)
        if d15:
            res = make_result(job, ok=False, errors=[d15], t0=t0)
            return JSONResponse(status_code=422, content=res.model_dump())

        # --- dispatch ---
        handler = JOB_HANDLERS.get(job.job_type)
        if not handler:
            res = make_result(
                job,
                ok=False,
                errors=[BridgeError(code="schema_error", message=f"Unknown job_type: {job.job_type}")],
                t0=t0,
            )
            return JSONResponse(status_code=400, content=res.model_dump())

        outcome = handler(job)

        # --- Step 3.4: Apply format guards to the artifact text ---
        artifact_text = outcome.get("content", "")
        okf, whyf = validate_artifact(job.job_type, artifact_text)
        if not okf:
            res = make_result(
                job,
                ok=False,
                errors=[BridgeError(code="format_error", message=whyf)],
                t0=t0,
            )
            return JSONResponse(status_code=422, content=res.model_dump())
        # --- end Step 3.4 ---

        # --- success ---
        res = make_result(
            job,
            ok=True,
            artifact_type=outcome.get("artifact_type"),
            content=artifact_text,
            t0=t0,
        )
        return JSONResponse(status_code=200, content=res.model_dump())

    except HTTPException as hx:
        # uniform error wrapper
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        res = BridgeResult(
            ok=False,
            job_id=payload.get("job_id", "unknown"),
            session_id=payload.get("session_id", "unknown"),
            artifact_type=None,
            artifact=None,
            notes=[],
            errors=[
                BridgeError(code="auth_error" if hx.status_code in (401, 403) else "unknown", message=hx.detail)
            ],
            request_id=str(uuid.uuid4()),
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
        return JSONResponse(status_code=hx.status_code, content=res.model_dump())
    except Exception as e:
        # last-resort unknown error
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        res = BridgeResult(
            ok=False,
            job_id=payload.get("job_id", "unknown"),
            session_id=payload.get("session_id", "unknown"),
            artifact_type=None,
            artifact=None,
            notes=[],
            errors=[BridgeError(code="unknown", message=str(e))],
            request_id=str(uuid.uuid4()),
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
        return JSONResponse(status_code=500, content=res.model_dump())

@app.get("/health")  # PATCH 3
def health():
    return health_blob()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    uvicorn.run("gal.server:app", host="0.0.0.0", port=port)