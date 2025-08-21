from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
from schema import EngineTurn, NarrativeTurn
from spine import Spine

app = FastAPI()
spine = Spine()

@app.post("/turn")
async def process_turn(request: Request):
    try:
        data = await request.json()
        narrative = NarrativeTurn(**data)
        engine_turn = spine.process_turn(narrative)
        return JSONResponse(engine_turn.dict())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
