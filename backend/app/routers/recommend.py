"""推荐接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.recommend.service import recommend

router = APIRouter(tags=["recommend"])


@router.get("/recommend")
def recommend_endpoint(openid: str = "", limit: int = 6, db: Session = Depends(get_db)):
    """为用户推荐在库书；openid 为空则返回热门冷启动结果。"""
    return recommend(db, openid, limit)
