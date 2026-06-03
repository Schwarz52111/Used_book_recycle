"""回收侧接口：识别 + 一站式评估。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.appraisal import appraise
from app.config import get_settings
from app.db import get_db
from app.recognition.pipeline import recognize
from app.schemas import AppraiseResponse, RecognizeResult
from app.vlm_client import get_vlm_client

router = APIRouter(tags=["recycle"])


@router.post("/recognize", response_model=RecognizeResult)
async def recognize_endpoint(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """仅识别书目（不评估品相、不定价）。"""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="空文件")
    try:
        return recognize(db, data, get_vlm_client(), get_settings().review_confidence_threshold)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:  # 缺少 opencv 等识别依赖
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/appraise", response_model=AppraiseResponse)
async def appraise_endpoint(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """一站式回收评估：识别 + 品相 + 定价，并落库（必要时挂起复核）。"""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="空文件")
    try:
        return appraise(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:  # 缺少 opencv 等识别依赖
        raise HTTPException(status_code=503, detail=str(exc)) from exc
