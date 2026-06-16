"""登录接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.accounts.service import get_or_create_user
from app.auth.wechat import AuthError, code_to_openid
from app.db import get_db
from app.schemas import LoginRequest, UserInfo

router = APIRouter(tags=["auth"])


@router.post("/auth/wechat/login", response_model=UserInfo)
def wechat_login(req: LoginRequest, db: Session = Depends(get_db)):
    """小程序登录：code 换 openid，返回（创建）用户。"""
    try:
        openid = code_to_openid(req.code)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    user = get_or_create_user(db, openid, req.nickname)
    return UserInfo(
        id=user.id, openid=user.openid, nickname=user.nickname or "",
        balance=float(user.balance or 0), credit_score=user.credit_score,
    )
