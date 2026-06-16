# 后端服务（FastAPI）

> 系统已从 Phase 0 演进为完整后端（识别/品相/定价/库存/订单/支付/账户/热度/准入/推荐/复核/信用分）。
> **完整说明、架构图、接口清单、运行方式请见仓库根目录 [`README.md`](../README.md)。** 本文保留 Phase 0 的模块速览。

校园二手图书自助回收售卖一体机的后端，基于 FastAPI。最初聚焦四件事：

1. **识别服务** `/recognize`：复用 ISBN条码 → OCR → VLM → 外部ISBN元数据 链路。
2. **VLM 品相 agent**：结构化评分替换原型里的假 CV（边缘/边框启发式）。
3. **定价引擎**：品相 × 市场价 × 回收率 × 热度 × 库存，输出可解释回收价/售价。
4. **抽象出货接口 + 库存模型**：适配机械货道 / RFID电子门两类书柜。

## 目录结构

```
backend/
  app/
    config.py            # 环境变量配置（无硬编码密钥）
    db.py                # SQLAlchemy 引擎/会话
    models.py            # ORM：books/condition_rules/recycle_records/inventory/review_tasks/...
    schemas.py           # Pydantic 请求/响应
    vlm_client.py        # 统一 VLM 客户端（云为主 + Ollama 降级）
    recognition/         # 识别 agent：imaging/local_cv/matcher/metadata/vlm_recognize/pipeline
    grading/             # 品相 agent：condition_agent
    pricing/             # 定价引擎：engine
    inventory/           # 出货抽象接口 dispense + 库存服务 service
    appraisal.py         # 识别→品相→定价→落库 编排
    routers/             # appraise / inventory 路由
    main.py              # FastAPI 入口
  scripts/init_db.py     # 建表 + 种子数据
  tests/test_pricing.py  # 单元测试（SQLite，不依赖 MySQL/VLM）
  requirements.txt
  .env.example
```

## 快速开始（Windows 原生，无需 Linux/WSL）

在 PowerShell 里：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# 想零配置先试跑：编辑 .env，取消注释这行用 SQLite
#   DATABASE_URL=sqlite:///./used_books.db
python -m scripts.init_db        # 建表 + 写入示例书目
uvicorn app.main:app --reload
```

打开 http://127.0.0.1:8000/docs 看交互式接口文档。

说明：
- **不需要 Linux/WSL**，这是普通 Windows Python 服务。
- `pyzbar` 在 Windows 上 pip 装好即自带 zbar，无需额外安装。
- OCR 可选：要封面文字识别才需另装 [Tesseract-OCR](https://github.com/UB-Mannheim/tesseract/wiki)（含 `chi_sim` 中文包），并在 `.env` 设 `TESSERACT_CMD`。不装则走条码 + VLM。
- 用 MySQL 时填 `.env` 的 DB_* 并确保服务已启动；用 SQLite 则填 `DATABASE_URL` 即可，二选一。

### macOS / Linux

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m scripts.init_db
uvicorn app.main:app --reload
```
Linux 下 `pyzbar` 需先 `sudo apt-get install libzbar0`。

## 主要接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/recognize` | 上传图片，仅识别书目 |
| POST | `/appraise` | 上传图片，识别+品相+定价，落库（必要时挂复核） |
| POST | `/inventory/intake` | 确认回收入库 |
| GET  | `/inventory` | 列库存 |
| POST | `/inventory/dispense` | 出货（mechanism=vend_channel/rfid_door/simulated） |
| GET  | `/health` | 健康检查 |

## 测试

```bash
cd backend
pip install pytest
python -m pytest -q          # 或 python tests/test_pricing.py
```

## 与原型的差异（重点）

- **品相不再是假的**：`grading/condition_agent.py` 用 VLM 按 6 维 rubric 评分并给证据/置信度，低置信度自动进复核队列；原型的 `estimate_condition()`（Canny 边缘均值当破损分）已弃用。
- **真实书目**：本地未命中时用 ISBN 调外部元数据并落库，解决"真实书匹配不上"。
- **可解释定价**：每次定价的系数与中间值都写进 `reason`/`factors`，可复核。
- **VLM 云优先**：默认走云 VLM（OpenAI 兼容接口），失败自动降级本地 Ollama。
- **出货可适配**：硬件出货机制未定，先用抽象接口隔离，确定型号后只换适配器。

## 待办（进入 Phase 1）

支付（微信优先）与订单、用户账户与到账、微信小程序购书入口、Kiosk 前端、热度分析与动态准入、人工复核后台 UI。
