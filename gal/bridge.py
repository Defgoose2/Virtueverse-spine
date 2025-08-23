# gal/bridge.py
import os, json, uuid, urllib.request

BASE = os.getenv("VV_BASE", "https://virtueverse.onrender.com")
SECRET = os.getenv("VV_SHARED_SECRET")
VERSION = os.getenv("ENGINE_VERSION")
TIMEOUT = int(os.getenv("VV_TIMEOUT", "60"))

def _post(path, body):
    if not SECRET or not VERSION:
        raise RuntimeError("missing_secret_or_version")
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type":"application/json", "Authorization": f"Bearer {SECRET}"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60.) as r:
        return json.loads(r.read().decode("utf-8"))

def post_scene(input_text, anchor_hint=None, goal=None, session_id="s_persist"):
    job = {
        "version": VERSION,
        "session_id": session_id,
        "job_id": f"j_scene_{uuid.uuid4().hex[:8]}",
        "job_type": "scene",
        "params": {"strict_lang": True, "input": input_text}
    }
    if anchor_hint: job["params"]["anchor_hint"] = anchor_hint
    if goal: job["params"]["goal"] = goal

    resp = _post("/vv/jobs", job)
    if not resp.get("ok"):
        codes = ",".join(e.get("code","") for e in resp.get("errors", [])) or "unknown"
        raise RuntimeError(f"engine_error:{codes}")
    return (resp.get("artifact") or {}).get("content","")

if __name__ == "__main__":
    # smoke test prints artifact content only
    print(post_scene(
        "Quiet campus morning. I bump into her at the gate.",
        anchor_hint="first_meet"
    ))
