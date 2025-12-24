from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.db.mongo import db
from src.routes import files, chat

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    yield
    await db.close()

app = FastAPI(title="Knowledge Capture API", version="1.0", lifespan=lifespan)

app.include_router(files.router)
app.include_router(chat.router)

@app.get("/")
def health():
    return {"status": "ok"}
