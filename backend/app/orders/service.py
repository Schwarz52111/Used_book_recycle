"""订单服务。

下单：校验库存在库 → 锁定库存(reserved) → 生成订单(created)。
支付：发起支付 → 成功则标记订单 paid → 触发出货 → 库存 sold、订单 completed
      → 如有买家账户，记一笔购书流水。
取消：释放库存、订单置 cancelled。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.inventory.dispense import get_dispenser
from app.models import Inventory, InventoryStatus, Order, OrderStatus
from app.payment.provider import get_payment_provider


class OrderError(RuntimeError):
    pass


def _gen_order_no() -> str:
    return "BK" + datetime.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:6].upper()


def create_order(db: Session, inventory_id: int, machine_id: str, buyer_id: int | None = None) -> Order:
    item = db.get(Inventory, inventory_id)
    if item is None:
        raise OrderError(f"库存不存在：{inventory_id}")
    if item.status != InventoryStatus.in_stock:
        raise OrderError(f"该书不可购买，当前状态：{item.status.value}")

    item.status = InventoryStatus.reserved  # 锁库存，避免并发重复售卖
    order = Order(
        order_no=_gen_order_no(),
        inventory_id=item.id,
        buyer_id=buyer_id,
        amount=item.sale_price,
        machine_id=machine_id or item.machine_id,
        status=OrderStatus.created,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def pay_order(db: Session, order_id: int, provider_name: str | None = None) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise OrderError(f"订单不存在：{order_id}")
    if order.status == OrderStatus.completed:
        return order
    if order.status != OrderStatus.created:
        raise OrderError(f"订单状态不可支付：{order.status.value}")

    settings = get_settings()
    provider = get_payment_provider(provider_name or settings.payment_provider)
    intent = provider.create_payment(order.order_no, float(order.amount), description="二手书购买", openid="")
    if not intent.ok or intent.status != "paid":
        # 真实支付场景下这里应返回拉起参数、由回调更新；模拟支付直接成功
        order.pay_provider = provider.name
        raise OrderError(intent.message or "支付未完成，请在前端完成支付后回调")

    order.status = OrderStatus.paid
    order.pay_provider = provider.name
    order.pay_txn_id = intent.txn_id
    order.paid_at = datetime.now()
    db.commit()

    _fulfill(db, order)
    return order


def _fulfill(db: Session, order: Order) -> None:
    """支付成功后的履约：出货 → 库存置已售 → 订单完成 → 记账。"""
    item = db.get(Inventory, order.inventory_id)
    settings = get_settings()
    dispenser = get_dispenser(settings.dispense_mechanism)
    result = dispenser.dispense(order.machine_id, item.slot_code, item.rfid_tag)
    if not result.ok:
        raise OrderError(f"出货失败：{result.message}")
    if result.requires_user_action:
        dispenser.confirm_taken(order.machine_id, item.slot_code, item.rfid_tag)

    item.status = InventoryStatus.sold
    order.status = OrderStatus.completed
    # 说明：买家通过微信外部支付，不扣内部钱包余额；buyer_id 仅用于订单归属与历史。
    # 若将来支持"用回收余额购书"，可在此按 balance 支付方式扣减。
    db.commit()


def cancel_order(db: Session, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise OrderError(f"订单不存在：{order_id}")
    if order.status not in (OrderStatus.created, OrderStatus.paid):
        raise OrderError(f"订单状态不可取消：{order.status.value}")
    item = db.get(Inventory, order.inventory_id)
    if item and item.status == InventoryStatus.reserved:
        item.status = InventoryStatus.in_stock  # 释放库存
    order.status = OrderStatus.cancelled
    db.commit()
    db.refresh(order)
    return order


def get_order(db: Session, order_id: int) -> Order | None:
    return db.get(Order, order_id)


def list_orders(db: Session, buyer_id: int | None = None, limit: int = 50) -> list[Order]:
    stmt = select(Order).order_by(Order.id.desc()).limit(limit)
    if buyer_id:
        stmt = select(Order).where(Order.buyer_id == buyer_id).order_by(Order.id.desc()).limit(limit)
    return list(db.scalars(stmt).all())
