# 即刻小绿 · 购书小程序

校园二手书购书入口的微信小程序前端，调用 `backend` 的接口（买书下单、支付、登录、账户）。

## 页面

- **买书**（`pages/index`）：在库二手书网格，点进详情。
- **书籍详情**（`pages/detail`）：查看品相与售价，下单并支付（开发期为模拟支付，自动出货）。
- **我的**（`pages/me`）：微信登录、账户余额（卖书回收到账）、信用分。

## 本地运行（微信开发者工具）

1. 先把后端跑起来（在 `backend` 目录）：
   ```
   uvicorn app.main:app --reload
   ```
   确认 http://127.0.0.1:8000/health 正常。库里要有在库书才能看到列表——先用设备触屏页或 /docs 走一遍回收入库。

2. 下载安装 **微信开发者工具**（稳定版即可）。

3. 打开工具 → 导入项目 → 选择本 `miniprogram` 文件夹。
   - **AppID**：没有就选「测试号」或使用项目里预填的 `touristappid`（游客模式）。游客模式下 `wx.login` 仍可用，后端用 mock 登录换 openid。
   - 项目已设置「不校验合法域名」(`urlCheck:false`)，所以模拟器能直接访问 `http://127.0.0.1:8000`。

4. 编译运行，即可在模拟器里浏览、购买、查看账户。

## 配置

- 后端地址：`app.js` 里 `globalData.baseUrl`，默认 `http://127.0.0.1:8000`。真机调试需改成可公网访问的 HTTPS 域名。
- 设备编号：`app.js` 里 `globalData.machineId`，默认 `KIOSK-01`。

## 上线前要做

- 申请正式小程序 AppID，填到工具与 `project.config.json`。
- 后端 `.env` 设 `AUTH_PROVIDER=wechat` 并填 `WECHAT_APPID`/`WECHAT_SECRET`（真实登录）。
- 接入真实微信支付（`PAYMENT_PROVIDER=wechat` + 商户凭证），把 `detail.js` 的支付改为 `wx.requestPayment`。
- 在小程序后台配置服务器合法域名（HTTPS）。
