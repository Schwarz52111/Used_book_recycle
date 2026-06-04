"""订单与账户接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.accounts.service import get_or_create_user, list_ledger
from app.db import get_db
from app.orders import service as orders
from app.schemas import (
    LedgerEntryInfo,
    OrderCreateRequest,
    OrderInfo,
    PayRequest,
    PayResult,
    UserInfo,
)

router = APIRouter(tags=["orders"])


def _to_order_info(order) -> OrderInfo:
    return OrderInfo(
        id=order.id,
        order_no=order.order_no,
        inventory_id=order.inventory_id,
        amount=float(order.amount or 0),
        status=order.status.value,
        pay_provider=order.pay_provider or "",
        machine_id=order.machine_id or "",
    )


@router.post("/orders", response_model=OrderInfo)
def create_order_endpoint(req: OrderCreateRequest, db: Session = Depends(get_db)):
    """下单：锁定库存，生成待支付订单。"""
    buyer_id = None
    if req.buyer_openid:
        buyer_id = get_or_create_user(db, req.buyer_openid).id
    try:
        order = orders.create_order(db, req.inventory_id, req.machine_id, buyer_id)
    except orders.OrderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_order_info(order)


@router.post("/orders/pay", response_model=PayResult)
def pay_order_endpoint(req: PayRequest, db: Session = Depends(get_db)):
    """发起支付。mock 直接完成；wechat 返回拉起参数，由回调确认。"""
    try:
        order, pay_params = orders.pay_order(db, req.order_id, req.provider)
    except orders.OrderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PayResult(order=_to_order_info(order), paid=pay_params is None, pay_params=pay_params)


@router.post("/orders/cancel", response_model=OrderInfo)
def cancel_order_endpoint(order_id: int, db: Session = Depends(get_db)):
    try:
        order = orders.cancel_order(db, order_id)
    except orders.OrderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_order_info(order)


@router.get("/orders/{order_id}", response_model=OrderInfo)
def get_order_endpoint(order_id: int, db: Session = Depends(get_db)):
    order = orders.get_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    return _to_order_info(order)


@router.get("/users/{openid}", response_model=UserInfo)
def get_user_endpoint(openid: str, db: Session = Depends(get_db)):
    """查询/创建用户（设备端用 openid 取账户余额）。"""
    user = get_or_create_user(db, openid)
    return UserInfo(
        id=user.id, openid=user.openid, nickname=user.nickname or "",
        balance=float(user.balance or 0), credit_score=user.credit_score,
    )


@router.get("/users/{openid}/orders")
def user_orders_endpoint(openid: str, db: Session = Depends(get_db)):
    """用户订单历史（含书目信息）。"""
    return orders.user_orders(db, openid)


@router.get("/users/{openid}/ledger", response_model=list[LedgerEntryInfo])
def user_ledger_endpoint(openid: str, db: Session = Depends(get_db)):
    user = get_or_create_user(db, openid)
    return [
        LedgerEntryInfo(
            id=e.id, entry_type=e.entry_type.value, amount=float(e.amount),
            balance_after=float(e.balance_after), ref_type=e.ref_type or "",
            ref_id=e.ref_id, note=e.note or "",
        )
        for e in list_ledger(db, user.id)
    ]
