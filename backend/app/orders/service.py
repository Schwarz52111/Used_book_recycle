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
from app.models import Book, Inventory, InventoryStatus, Order, OrderStatus, User
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


def pay_order(db: Session, order_id: int, provider_name: str | None = None) -> tuple[Order, dict | None]:
    """发起支付。

    返回 (order, pay_params)：
      - 同步支付（mock）：直接标记已付并出货，pay_params 为 None。
      - 异步支付（wechat）：返回小程序拉起参数，订单留待回调置为已付。
    """
    order = db.get(Order, order_id)
    if order is None:
        raise OrderError(f"订单不存在：{order_id}")
    if order.status == OrderStatus.completed:
        return order, None
    if order.status != OrderStatus.created:
        raise OrderError(f"订单状态不可支付：{order.status.value}")

    settings = get_settings()
    provider = get_payment_provider(provider_name or settings.payment_provider)

    openid = ""
    if order.buyer_id:
        buyer = db.get(User, order.buyer_id)
        openid = buyer.openid if buyer else ""

    intent = provider.create_payment(order.order_no, float(order.amount), "二手书购买", openid)
    order.pay_provider = provider.name
    if intent.txn_id:
        order.pay_txn_id = intent.txn_id

    if not intent.ok:
        db.commit()
        raise OrderError(intent.message or "发起支付失败")

    if intent.status == "paid":          # 同步成功（mock）
        _settle(db, order, intent.txn_id)
        return order, None

    db.commit()                          # 异步（wechat）：等回调
    return order, intent.pay_params


def _settle(db: Session, order: Order, txn_id: str | None) -> None:
    """标记已付并履约。"""
    order.status = OrderStatus.paid
    if txn_id:
        order.pay_txn_id = txn_id
    order.paid_at = datetime.now()
    db.commit()
    _fulfill(db, order)


def settle_by_order_no(db: Session, order_no: str, txn_id: str | None = None) -> Order | None:
    """支付回调用：按业务单号确认支付并出货（幂等）。"""
    order = db.scalar(select(Order).where(Order.order_no == order_no))
    if order is None:
        return None
    if order.status == OrderStatus.completed:
        return order
    if order.status in (OrderStatus.created, OrderStatus.paid):
        _settle(db, order, txn_id)
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
    # 完成购书给买家 +1 信用分。
    if order.buyer_id:
        from app.accounts.service import adjust_credit

        buyer = db.get(User, order.buyer_id)
        if buyer:
            adjust_credit(db, buyer, 1)
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


STATUS_LABEL = {
    OrderStatus.created: "待支付",
    OrderStatus.paid: "待出货",
    OrderStatus.completed: "已完成",
    OrderStatus.cancelled: "已取消",
    OrderStatus.refunded: "已退款",
}


def user_orders(db: Session, openid: str, limit: int = 50) -> list[dict]:
    """按 openid 列出用户订单（含书目信息），供个人中心展示。"""
    user = db.scalar(select(User).where(User.openid == openid))
    if not user:
        return []
    rows = db.execute(
        select(
            Order.order_no, Order.amount, Order.status, Order.created_at,
            Book.title, Book.cover_url, Book.isbn,
        )
        .select_from(Order)
        .join(Inventory, Order.inventory_id == Inventory.id)
        .join(Book, Inventory.book_id == Book.id)
        .where(Order.buyer_id == user.id)
        .order_by(Order.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "order_no": no,
            "amount": round(float(amt or 0), 2),
            "status": status.value,
            "status_label": STATUS_LABEL.get(status, status.value),
            "time": created.isoformat() if created else "",
            "title": title,
            "cover_url": cover or "",
            "isbn": isbn or "",
        }
        for no, amt, status, created, title, cover, isbn in rows
    ]


def list_orders(db: Session, buyer_id: int | None = None, limit: int = 50) -> list[Order]:
    stmt = select(Order).order_by(Order.id.desc()).limit(limit)
    if buyer_id:
        stmt = select(Order).where(Order.buyer_id == buyer_id).order_by(Order.id.desc()).limit(limit)
    return list(db.scalars(stmt).all())
