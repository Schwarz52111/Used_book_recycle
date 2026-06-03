const app = getApp();

const LEDGER_LABEL = {
  payout: { text: "回收到账", sign: "+", color: "#2d4a2b" },
  purchase: { text: "购书支出", sign: "", color: "#b06a3b" },
  topup: { text: "充值", sign: "+", color: "#2d4a2b" },
  refund: { text: "退款", sign: "+", color: "#2d4a2b" },
};

Page({
  data: { user: null, ledger: [], loading: true, error: "" },

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
    ])
      .then(([user, ledger]) => {
        app.globalData.user = user;
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
        this.setData({
          user: Object.assign({}, user, { balanceText: "¥" + Number(user.balance || 0).toFixed(2) }),
          ledger: list,
          loading: false,
        });
      })
      .catch((e) => this.setData({ error: e.message, loading: false }));
  },

  goSell() { wx.switchTab({ url: "/pages/sell/sell" }); },
  goBuy() { wx.switchTab({ url: "/pages/index/index" }); },
});
