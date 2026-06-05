# 即刻小绿 · 校园二手图书自助回收售卖一体机

面向高校师生的二手书自助回收与售卖系统：用户投书后由 AI 识别书目、结构化评估品相并给出可解释的回收价；书籍自动上架，其他师生可在设备触屏或微信小程序浏览购买。系统以热度分析驱动动态定价与回收准入，配人工复核保证质量，实现旧书的高效循环利用与绿色低碳。

> 本仓库由最初的“单机摄像头识别原型”演进为一套完整系统：FastAPI 后端 + 微信小程序 + 设备触屏页 + 运营后台。最早的原型脚本（`camera_book_recognition.py` 等）保留在根目录，见文末“遗留原型”。

---

## 一、功能总览

**回收侧**
- 多级图像识别：ISBN 条码 → 封面 OCR → 视觉大模型（Moonshot/Kimi）→ 外部 ISBN 元数据；库里没有的书用识别结果新建书目并转复核。
- AI 结构化品相评估：6 维（封面/书脊/污渍/划线/折角/缺页）评分 + 证据 + 置信度，低置信度转人工复核。
- 可解释定价：市场价 × 回收率 × 品相 × 热度 × 库存 × 信用 系数，输出完整算式。
- 卖家手动改价：调低直接采用，调高按估价先到账并转复核。
- 回收到账：小程序按 openid、设备端按手机号入账。

**售卖侧**
- 在库书浏览、搜索（书名/作者/ISBN）、分类筛选、真实书封（OpenLibrary，缺失回退生成式封面）。
- 下单 → 支付 → 出货：模拟支付即时完成；微信支付 v3（JSAPI+异步回调）代码就位，待商户凭证。
- 个性化推荐：按用户购买/回收的品类偏好 × 书目热度，冷启动走热门。

**数据与运营**
- 热度分析与动态回收准入（超储/冷门暂停或限流回收）。
- 信用分机制：正常回收 +2、购书 +1、复核驳回 −15；信用分映射差异化回收率。
- 人工复核控制台、运营数据看板（KPI / 热度排行 / 近期成交）。

**账户**
- 微信 openid / 手机号账户，余额 + 信用分 + 账本流水 + 订单历史。

---

## 二、技术栈与架构

- **后端**：Python 3.11+ / FastAPI / SQLAlchemy；数据库 SQLite（开发）或 MySQL（生产）；对象存储放书籍照片。
- **识别**：pyzbar（条码）、Tesseract（OCR，可选）、OpenCV；视觉大模型云端为主（Moonshot/Kimi），本地 Ollama 降级。
- **前端**：微信小程序（买/卖/我的）、设备触屏页（HTML，FastAPI 同源托管）、运营后台网页。
- **支付/出货/登录**：均为抽象适配层（mock ↔ 真实），便于在拿到凭证前先跑通。

```
即刻小绿/
├─ backend/                 FastAPI 后端
│  ├─ app/
│  │  ├─ recognition/       识别 agent（条码/OCR/VLM/元数据/新建书目）
│  │  ├─ grading/           AI 品相评估
│  │  ├─ pricing/           可解释定价（含信用系数）
│  │  ├─ inventory/         库存状态机 + 出货抽象（货道/RFID）
│  │  ├─ orders/            订单状态机
│  │  ├─ payment/           支付抽象 + 微信支付 v3
│  │  ├─ accounts/          账户/账本/信用分
│  │  ├─ auth/              微信登录（mock/真实）
│  │  ├─ analytics/         热度分析 + 动态准入 + 看板聚合
│  │  ├─ recommend/         个性化推荐
│  │  ├─ review/            人工复核
│  │  ├─ routers/           接口层
│  │  └─ main.py            应用入口（含 /ui 静态托管、CORS）
│  ├─ static/               设备触屏页 index.html、复核台 review.html、看板 dashboard.html
│  ├─ scripts/              init_db / seed_demo / fetch_covers
│  └─ tests/                单元测试（25 项，SQLite，不依赖外部服务）
├─ miniprogram/             微信小程序
└─ 团队同步_*.md / 第三章*  文档
```

---

## 三、快速开始

### 后端

```powershell
cd backend
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env       # 用 SQLite 可设 DATABASE_URL=sqlite:///./used_books.db
python -m scripts.init_db    # 建表 + 示例书目 + 示例在库
python -m scripts.seed_demo  # 可选：演示数据（成交/回收/待复核），便于看板与推荐
uvicorn app.main:app --reload
```

- 设备触屏页：http://127.0.0.1:8000/ui/
- 人工复核台：http://127.0.0.1:8000/ui/review.html
- 运营数据看板：http://127.0.0.1:8000/ui/dashboard.html
- 交互式接口文档：http://127.0.0.1:8000/docs

视觉识别需在 `.env` 配置 VLM（如 Moonshot：`VLM_BASE_URL`、`VLM_API_KEY`、`VLM_MODEL=moonshot-v1-8k-vision-preview`），并安装 `opencv-python`、`pyzbar`。

### 微信小程序

微信开发者工具导入 `miniprogram/`，AppID 选“测试号”，详情里勾“不校验合法域名”，编译即可。详见 `miniprogram/README.md`。

### 测试

```powershell
cd backend
python -m pytest -q     # 25 项全过
```

---

## 四、接口清单（主要）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/recognize` | 仅识别书目 |
| POST | `/appraise` | 识别+品相+定价（可带 `seller_openid` 按信用估价） |
| POST | `/inventory/intake` | 确认回收入库（`seller_openid`/`seller_phone`/`seller_price`） |
| GET | `/inventory` | 在库列表（支持 `q`、`category`、`machine_id`） |
| GET | `/inventory/categories` | 在库书分类 |
| POST | `/inventory/dispense` | 出货 |
| POST | `/orders` / `/orders/pay` | 下单 / 支付（mock 即时；wechat 返回拉起参数） |
| GET | `/orders/{id}` | 订单详情 |
| POST | `/pay/wechat/notify` | 微信支付回调 |
| POST | `/auth/wechat/login` | 小程序登录（code→openid） |
| GET | `/users/{openid}` `/ledger` `/orders` | 账户 / 账单 / 订单历史 |
| GET | `/recommend` | 个性化推荐（带 `openid`） |
| POST | `/analytics/heat/recompute` | 重算热度 |
| GET | `/analytics/dashboard` `/overview` | 运营聚合 |
| GET | `/review/tasks` · POST `/review/tasks/{id}/resolve` | 复核列表 / 处理（通过/修正/驳回） |

---

## 五、配置说明（.env）

数据库（`DATABASE_URL` 或 `DB_*`）、VLM（`VLM_*` / `OLLAMA_*`）、登录（`AUTH_PROVIDER`、`WECHAT_APPID/SECRET`）、支付（`PAYMENT_PROVIDER`、`WECHAT_MCHID/API_V3_KEY/CERT_SERIAL/PRIVATE_KEY/NOTIFY_URL`）、出货（`DISPENSE_MECHANISM`）、业务阈值（复核置信度、默认回收率）。详见 `backend/.env.example`。密钥一律走 `.env`，已在 `.gitignore` 中排除，切勿提交。

---

## 六、待商务/运维推进

微信支付商户号、微信小程序 AppID、出货书柜机制定型（货道/RFID）、稳定的 ISBN 元数据与封面来源。

---

## 七、遗留原型（根目录脚本）

最初的单机版仍可参考：`camera_book_recognition.py`（摄像头识别）、`init_mysql_database.py` / `mysql_schema.sql`（建库）、`ollama_book_recognition.py`、`*.ps1`。新系统已将其能力服务化并大幅扩展，推荐以 `backend/` 为准。
