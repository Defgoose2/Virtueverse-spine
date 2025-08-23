# gal/server.py
from fastapi import FastAPI, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse# <-- this was missing
from pydantic import BaseModel
from gal.bridge import post_scene


app = FastAPI()
LAST_ANCHOR = "first_meet"  # always have a fallback

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/ui")


class PlayIn(BaseModel):
    text: str
    anchor: str | None = None

@app.post("/play")
def play(payload: PlayIn):
    global LAST_ANCHOR
    text = (payload.text or "").strip()
    if not text:
        return Response("[bridge error] missing_text",
                        status_code=status.HTTP_400_BAD_REQUEST,
                        media_type="text/plain; charset=utf-8")

    # Use provided anchor, else the last one, else first_meet
    anchor = (payload.anchor or "").strip() or LAST_ANCHOR
    LAST_ANCHOR = anchor  # remember for next call

    try:
        content = post_scene(text, anchor_hint=anchor, session_id="s_persist")
        return Response(content, media_type="text/plain; charset=utf-8")
    except Exception as e:
        return Response(f"[bridge error] {e}",
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        media_type="text/plain; charset=utf-8")


@app.get("/ui", response_class=HTMLResponse)
def ui():
    return """
<!doctype html>
<meta charset="utf-8">
<title>VirtueVerse v5 — GAL</title>
<style>
  body { font: 14px/1.4 system-ui, sans-serif; margin: 2rem; max-width: 800px }
  textarea, input { width: 100%; box-sizing: border-box; margin: .5rem 0 }
  button { padding: .6rem 1rem; cursor: pointer }
  pre { white-space: pre-wrap; background: #111; color: #eee; padding: 1rem; border-radius: 8px }
  small { color: #666 }
</style>
<h1>VirtueVerse v5 — One-window Play</h1>
<label>Anchor (optional; first call defaults to <code>first_meet</code>)</label>
<input id="anchor" placeholder="first_meet, rooftop, club_entry …">
<label>Say something to the engine</label>
<textarea id="text" rows="3" placeholder="Quiet campus morning. I bump into her at the gate."></textarea>
<button id="go">Play</button>
<small id="msg"></small>
<h3>Output</h3>
<pre id="out"></pre>
<script>
const $ = id => document.getElementById(id);
$("go").onclick = async () => {
  $("msg").textContent = "Thinking…";
  $("out").textContent = "";
  try {
    const body = { text: $("text").value };
    const a = $("anchor").value.trim();
    if (a) body.anchor = a;
    const r = await fetch("/play", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body)
    });
    const t = await r.text();   // artifact-only
    $("out").textContent = t;
    $("msg").textContent = r.ok ? "" : `[${r.status}]`;
  } catch {
    $("msg").textContent = "[network error]";
  }
};
</script>
"""
