"""FastAPI 应用入口。"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.recognition.local_cv import configure_tesseract
from app.routers import appraise, inventory

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_tesseract()
    yield


app = FastAPI(
    title="校园二手图书自助回收售卖一体机 · 后端",
    version=__version__,
    lifespan=lifespan,
)

app.include_router(appraise.router)
app.include_router(inventory.router)


@app.get("/health")
def health():
    return {"status": "ok", "version": __version__}


@app.get("/")
def root():
    """首页直接跳转到设备触屏界面。"""
    return RedirectResponse(url="/ui/")


# 设备触屏界面（与 API 同源，避免 CORS）
if STATIC_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(STATIC_DIR), html=True), name="ui")
