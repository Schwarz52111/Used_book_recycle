const app = getApp();

const LEDGER_LABEL = {
  payout: { text: "回收到账", sign: "+", color: "#2d4a2b" },
  purchase: { text: "购书支出", sign: "", color: "#b06a3b" },
  topup: { text: "充值", sign: "+", color: "#2d4a2b" },
  refund: { text: "退款", sign: "+", color: "#2d4a2b" },
};

Page({
  data: { user: null, level: null, ledger: [], orders: [], major: "", semester: "", savedTip: "", loading: true, error: "" },

  onShow() {
    this.refresh();
  },

  refresh() {
    this.setData({ loading: true, error: "" });
    const proceed = () => this.loadAll();
    if (!app.globalData.openid) {
      app.login().then(proceed).catch((e) => this.setData({ error: e.message, loading: false }));
    } else {
      proceed();
    }
  },

  loadAll() {
    const openid = app.globalData.openid;
    Promise.all([
      app.api("GET", "/users/" + openid),
      app.api("GET", "/users/" + openid + "/ledger"),
      app.api("GET", "/users/" + openid + "/orders"),
      app.api("GET", "/users/" + openid + "/level"),
      app.api("GET", "/users/" + openid + "/profile"),
    ])
      .then(([user, ledger, orders, level, profile]) => {
        app.globalData.user = user;
        let lv = null;
        if (level) {
          const remain = level.next_at != null ? Math.max(0, level.next_at - level.credit_score) : 0;
          lv = Object.assign({}, level, {
            coefText: (level.recycle_coef >= 1 ? "+" : "") + Math.round((level.recycle_coef - 1) * 100) + "%",
            progText: level.next_tier ? "再 " + remain + " 分升「" + level.next_tier + "」" : "已是最高等级",
          });
        }
        const list = (ledger || []).map((e) => {
          const m = LEDGER_LABEL[e.entry_type] || { text: e.entry_type, sign: "", color: "#5f6655" };
          return {
            id: e.id,
            text: e.note || m.text,
            color: m.color,
            amountText: (e.amount >= 0 ? "+" : "") + "¥" + Math.abs(Number(e.amount)).toFixed(2),
            balanceText: "余额 ¥" + Number(e.balance_after).toFixed(2),
          };
        });
        const ords = (orders || []).map((o) => ({
          order_no: o.order_no,
          title: o.title || "二手书",
          amountText: "¥" + Number(o.amount || 0).toFixed(2),
          statusLabel: o.status_label || o.status,
          done: o.status === "completed",
          time: (o.time || "").replace("T", " ").slice(5, 16),
        }));
        this.setData({
          user: Object.assign({}, user, { balanceText: "¥" + Number(user.balance || 0).toFixed(2) }),
          level: lv,
          ledger: list,
          orders: ords,
          major: (profile && profile.major) || "",
          semester: profile && profile.semester ? String(profile.semester) : "",
          loading: false,
        });
      })
      .catch((e) => this.setData({ error: e.message, loading: false }));
  },

  onMajorInput(e) { this.setData({ major: e.detail.value }); },
  onSemesterInput(e) { this.setData({ semester: e.detail.value }); },
  saveProfile() {
    const openid = app.globalData.openid;
    if (!openid) return;
    app
      .api("POST", "/users/" + openid + "/profile", {
        major: this.data.major.trim(),
        semester: parseInt(this.data.semester) || 0,
      })
      .then(() => {
        this.setData({ savedTip: "已保存，去买书页看本学期教材" });
        setTimeout(() => this.setData({ savedTip: "" }), 2500);
      })
      .catch((e) => this.setData({ savedTip: "保存失败：" + e.message }));
  },

  goSell() { wx.switchTab({ url: "/pages/sell/sell" }); },
  goBuy() { wx.switchTab({ url: "/pages/index/index" }); },
});
