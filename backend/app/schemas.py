"""Pydantic 请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------- 识别 ----------
class BookInfo(BaseModel):
    id: int | None = None
    isbn: str = ""
    title: str = ""
    author: str = ""
    publisher: str = ""
    category: str = ""
    market_price: float = 0.0
    base_recycle_rate: float = 0.35
    source: str = ""


class RecognizeResult(BaseModel):
    matched: bool
    book: BookInfo | None = None
    method: str = ""              # isbn | ocr | vlm | metadata_api | none
    confidence: float = 0.0
    recognized_text: str = ""
    need_review: bool = False


# ---------- 品相 ----------
class ConditionDimension(BaseModel):
    name: str                    # 维度：封面磨损/书脊/污渍/划线/折角/缺页 等
    score: float = Field(ge=0, le=1)  # 0=完好 1=严重
    evidence: str = ""


class ConditionResult(BaseModel):
    condition_level: str         # like_new | good | acceptable | damaged | reject
    dimensions: list[ConditionDimension] = []
    overall_damage: float = Field(default=0.0, ge=0, le=1)
    completeness: float = Field(default=1.0, ge=0, le=1)
    confidence: float = Field(default=0.0, ge=0, le=1)
    summary: str = ""
    need_review: bool = False
    rejected: bool = False
    reject_reason: str = ""


# ---------- 定价 ----------
class PriceResult(BaseModel):
    recycle_price: float         # 回收价（给卖家）
    sale_price: float            # 上架售价（给买家）
    currency: str = "CNY"
    reason: str = ""             # 可解释定价理由
    factors: dict[str, float] = {}


# ---------- 一站式回收评估 ----------
class AppraiseResponse(BaseModel):
    recognize: RecognizeResult
    condition: ConditionResult | None = None
    price: PriceResult | None = None
    record_id: int | None = None
    review_task_id: int | None = None


# ---------- 库存 ----------
class InventoryItem(BaseModel):
    id: int
    book_id: int
    title: str
    isbn: str
    condition_level: str
    sale_price: float
    machine_id: str
    slot_code: str
    status: str

    model_config = {"from_attributes": True}


class IntakeRequest(BaseModel):
    """确认回收入库。"""

    record_id: int
    machine_id: str
    slot_code: str = ""
    rfid_tag: str = ""


class DispenseRequest(BaseModel):
    inventory_id: int
    machine_id: str
