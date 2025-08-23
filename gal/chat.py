# gal/chat.py
from gal.bridge import post_scene

DEFAULT_ANCHOR = "first_meet"
booted = False
current_anchor = None  # optional override

def run_once(text: str):
    global booted, current_anchor
    anchor = current_anchor or (DEFAULT_ANCHOR if not booted else None)
    out = post_scene(text, anchor_hint=anchor, session_id="s_persist")
    booted = True
    return out

if __name__ == "__main__":
    print("VirtueVerse v5 — one-window play. Empty line to quit.")
    print("(optional) set anchor: /anchor first_meet | rooftop | club_entry ...")
    while True:
        try:
            user = input("> ").strip()
            if not user:
                break
            if user.lower().startswith("/anchor"):
                # simple inline control for anchors
                parts = user.split(maxsplit=1)
                current_anchor = parts[1].strip() if len(parts) == 2 else None
                print(f"[anchor -> {current_anchor or 'cleared'}]")
                continue
            print(run_once(user).strip(), flush=True)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[bridge error] {e}", flush=True)
