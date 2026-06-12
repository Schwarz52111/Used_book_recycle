"""推荐接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.recommend.service import (
    get_profile,
    recommend,
    set_profile,
    textbook_recommend,
)

router = APIRouter(tags=["recommend"])


class ProfileRequest(BaseModel):
    major: str = ""
    semester: int = 0


@router.get("/recommend")
def recommend_endpoint(openid: str = "", limit: int = 6, db: Session = Depends(get_db)):
    """为用户推荐在库书；openid 为空则返回热门冷启动结果。"""
    return recommend(db, openid, limit)


@router.get("/recommend/textbooks")
def textbooks_endpoint(openid: str = "", limit: int = 8, db: Session = Depends(get_db)):
    """按用户专业+学期推本学期在库教材。"""
    return textbook_recommend(db, openid, limit)


@router.get("/users/{openid}/profile")
def get_profile_endpoint(openid: str, db: Session = Depends(get_db)):
    return get_profile(db, openid)


@router.post("/users/{openid}/profile")
def set_profile_endpoint(openid: str, req: ProfileRequest, db: Session = Depends(get_db)):
    return set_profile(db, openid, req.major, req.semester)
