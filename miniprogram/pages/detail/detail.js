const app = getApp();

const CONDITION = {
  like_new: { label: "近全新", color: "#3a5d37" },
  good: { label: "良好", color: "#5a7a4e" },
  acceptable: { label: "可接受", color: "#b06a3b" },
  damaged: { label: "破损", color: "#9a4b2e" },
  reject: { label: "拒收", color: "#7d8471" },
};

const COVER_PALETTE = [
  ["#2f5d50", "#1f3d34"], ["#9c5a3c", "#6f3d28"], ["#2f4858", "#1d2e39"],
  ["#5e3a55", "#3f263a"], ["#6b6f3a", "#474a26"], ["#2c5f63", "#1c3f42"],
  ["#8a4b34", "#5d3122"], ["#44504a", "#2c352f"],
];
function coverPair(seed) {
  let h = 0;
  for (let i = 0; i < (seed || "").length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return COVER_PALETTE[h % COVER_PALETTE.length];
}

Page({
  data: { item: null, condLabel: "", condColor: "", priceText: "", c1: "", c2: "", paying: false, done: false, orderNo: "", error: "" },

  onLoad() {
    const it = app.globalData.selected;
    if (!it) {
      this.setData({ error: "未选择书籍" });
      return;
    }
    const c = CONDITION[it.condition_level] || { label: it.condition_level, color: "#7d8471" };
    const [c1, c2] = coverPair(it.title || String(it.id));
    this.setData({ item: it, condLabel: c.label, condColor: c.color, c1, c2, priceText: "¥" + Number(it.sale_price || 0).toFixed(2) });
  },

  buy() {
    const it = this.data.item;
    if (!it || this.data.paying) return;
    this.setData({ paying: true, error: "" });
    app
      .api("POST", "/orders", { inventory_id: it.id, machine_id: app.globalData.machineId, buyer_openid: app.globalData.openid })
      .then((order) => app.api("POST", "/orders/pay", { order_id: order.id }))
      .then((paid) => this.setData({ paying: false, done: true, orderNo: paid.order_no }))
      .catch((e) => this.setData({ paying: false, error: e.message }));
  },

  backToList() {
    wx.navigateBack();
  },
});
