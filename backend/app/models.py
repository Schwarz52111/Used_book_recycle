"""ORM 模型：在原型三表（books / condition_rules / recycle_records）基础上扩展。"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    DECIMAL,
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ConditionLevel(str, enum.Enum):
    like_new = "like_new"
    good = "good"
    acceptable = "acceptable"
    damaged = "damaged"


class InventoryStatus(str, enum.Enum):
    in_stock = "in_stock"   # 在库
    sold = "sold"           # 已售
    returned = "returned"   # 退回
    donated = "donated"     # 捐赠
    scrapped = "scrapped"   # 报废
    reserved = "reserved"   # 锁定（下单未支付）


class ReviewStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    corrected = "corrected"
    rejected = "rejected"


class OrderStatus(str, enum.Enum):
    created = "created"        # 已下单，待支付（库存锁定）
    paid = "paid"             # 已支付，待出货
    completed = "completed"   # 已出货完成
    cancelled = "cancelled"   # 已取消（库存释放）
    refunded = "refunded"     # 已退款


class LedgerType(str, enum.Enum):
    payout = "payout"     # 回收到账（+）
    purchase = "purchase"  # 购书支出（-）
    topup = "topup"       # 充值（+）
    refund = "refund"     # 退款（+）


class Book(Base):
    """书目基础信息与市场参考价（保留原表，新增封面/来源/热度）。"""

    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    isbn: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    author: Mapped[str] = mapped_column(String(255), default="")
    publisher: Mapped[str] = mapped_column(String(255), default="")
    category: Mapped[str] = mapped_column(String(100), default="")
    original_price: Mapped[float] = mapped_column(DECIMAL(10, 2), default=0)
    market_price: Mapped[float] = mapped_column(DECIMAL(10, 2), default=0)
    base_recycle_rate: Mapped[float] = mapped_column(DECIMAL(5, 2), default=0.35)
    # 扩展字段
    cover_url: Mapped[str] = mapped_column(String(512), default="")
    source: Mapped[str] = mapped_column(String(50), default="seed")  # seed | metadata_api | manual
    heat_score: Mapped[float] = mapped_column(DECIMAL(6, 4), default=0)  # 0~1 热度，热度 agent 维护
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ConditionRule(Base):
    """品相等级与估价系数（保留原表）。"""

    __tablename__ = "condition_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    condition_level: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    price_factor: Mapped[float] = mapped_column(DECIMAL(5, 2), default=0.5)


class RecycleRecord(Base):
    """每次识别+估价记录（保留原表，扩展定价理由与复核状态）。"""

    __tablename__ = "recycle_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[int | None] = mapped_column(ForeignKey("books.id"), nullable=True)
    condition_level: Mapped[str] = mapped_column(String(50), default="")
    damage_score: Mapped[float] = mapped_column(DECIMAL(6, 4), default=0)
    completeness_score: Mapped[float] = mapped_column(DECIMAL(6, 4), default=0)
    evaluated_price: Mapped[float] = mapped_column(DECIMAL(10, 2), default=0)
    recognized_text: Mapped[str] = mapped_column(Text, default="")
    # 扩展
    recognize_confidence: Mapped[float] = mapped_column(DECIMAL(6, 4), default=0)
    condition_confidence: Mapped[float] = mapped_column(DECIMAL(6, 4), default=0)
    pricing_reason: Mapped[str] = mapped_column(Text, default="")
    photo_url: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Inventory(Base):
    """库存条目：每本入库书占一个货道，含成本/售价/状态。"""

    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    recycle_record_id: Mapped[int | None] = mapped_column(ForeignKey("recycle_records.id"), nullable=True)
    condition_level: Mapped[str] = mapped_column(String(50), default="")
    cost_price: Mapped[float] = mapped_column(DECIMAL(10, 2), default=0)   # 回收成本
    sale_price: Mapped[float] = mapped_column(DECIMAL(10, 2), default=0)   # 上架售价
    machine_id: Mapped[str] = mapped_column(String(64), default="")        # 设备编号
    slot_code: Mapped[str] = mapped_column(String(64), default="")         # 货道编号
    rfid_tag: Mapped[str] = mapped_column(String(64), default="")          # RFID（电子门型号用）
    status: Mapped[InventoryStatus] = mapped_column(
        Enum(InventoryStatus), default=InventoryStatus.in_stock, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    book: Mapped[Book] = relationship("Book", lazy="joined")


class ReviewTask(Base):
    """人工复核队列：低置信度识别/估价、拒收申诉等。"""

    __tablename__ = "review_tasks"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    recycle_record_id: Mapped[int | None] = mapped_column(ForeignKey("recycle_records.id"), nullable=True)
    reason: Mapped[str] = mapped_column(String(255), default="")       # low_confidence | reject_appeal | anomaly
    payload: Mapped[str] = mapped_column(Text, default="")            # JSON 快照
    status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus), default=ReviewStatus.pending, index=True)
    operator: Mapped[str] = mapped_column(String(64), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BookMetadataCache(Base):
    """外部 ISBN 元数据缓存，避免重复查询。"""

    __tablename__ = "book_metadata_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    isbn: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    payload: Mapped[str] = mapped_column(Text, default="")  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class User(Base):
    """用户：微信 openid 登录，含余额与信用分。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    openid: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # 微信 openid
    nickname: Mapped[str] = mapped_column(String(64), default="")
    phone: Mapped[str] = mapped_column(String(20), default="")
    balance: Mapped[float] = mapped_column(DECIMAL(10, 2), default=0)     # 账户余额（元）
    credit_score: Mapped[int] = mapped_column(Integer, default=100)       # 信用分
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Order(Base):
    """订单：购书。下单锁库存，支付后出货完成。"""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    order_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)  # 业务单号
    inventory_id: Mapped[int] = mapped_column(ForeignKey("inventory.id"))
    buyer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # 可匿名（设备直接购买）
    amount: Mapped[float] = mapped_column(DECIMAL(10, 2), default=0)
    machine_id: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.created, index=True)
    # 支付信息
    pay_provider: Mapped[str] = mapped_column(String(32), default="")
    pay_txn_id: Mapped[str] = mapped_column(String(64), default="")   # 第三方支付流水号
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    inventory: Mapped[Inventory] = relationship("Inventory", lazy="joined")


class LedgerEntry(Base):
    """账本流水：回收到账 / 购书支出 / 充值 / 退款，记录每笔余额变动。"""

    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    entry_type: Mapped[LedgerType] = mapped_column(Enum(LedgerType))
    amount: Mapped[float] = mapped_column(DECIMAL(10, 2))            # 正为入账，负为出账
    balance_after: Mapped[float] = mapped_column(DECIMAL(10, 2))
    ref_type: Mapped[str] = mapped_column(String(32), default="")   # order | recycle_record
    ref_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    note: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
