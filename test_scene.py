# Set your endpoint URL (copy from "Open in Browser")
export BASE="https://1d7e4528-1222-4384-8168-8a3babd3a5fa-00-321w9gm529wgx.janeway.replit.dev"
export VV_SHARED_SECRET="defgoose2"

# Pull the exact server version so you don't fat-finger it
export ENGINE_VERSION="$(curl -sS "$BASE/healthz" | python3 - <<'PY'
import sys,json
try: print(json.load(sys.stdin)["version"])
except: print("")
PY
)"
