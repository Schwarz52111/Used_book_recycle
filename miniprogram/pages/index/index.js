const app = getApp();

const CONDITION = {
  like_new: { label: "近全新", color: "#3a5d37" },
  good: { label: "良好", color: "#5a7a4e" },
  acceptable: { label: "可接受", color: "#b06a3b" },
  damaged: { label: "破损", color: "#9a4b2e" },
  reject: { label: "拒收", color: "#7d8471" },
};

Page({
  data: { items: [], loading: true, error: "" },

  onShow() {
    this.load();
  },

  load() {
    this.setData({ loading: true, error: "" });
    const mid = encodeURIComponent(app.globalData.machineId);
    app
      .api("GET", "/inventory?status=in_stock&machine_id=" + mid)
      .then((items) => {
        const list = (items || []).map((it) => {
          const c = CONDITION[it.condition_level] || { label: it.condition_level, color: "#7d8471" };
          return Object.assign({}, it, { condLabel: c.label, condColor: c.color, priceText: "¥" + Number(it.sale_price || 0).toFixed(2) });
        });
        this.setData({ items: list, loading: false });
      })
      .catch((e) => this.setData({ error: e.message, loading: false }));
  },

  openDetail(e) {
    app.globalData.selected = e.currentTarget.dataset.item;
    wx.navigateTo({ url: "/pages/detail/detail" });
  },
});
