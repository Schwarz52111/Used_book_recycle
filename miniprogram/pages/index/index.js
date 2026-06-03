const app = getApp();

const CONDITION = {
  like_new: { label: "近全新", color: "#3a5d37" },
  good: { label: "良好", color: "#5a7a4e" },
  acceptable: { label: "可接受", color: "#b06a3b" },
  damaged: { label: "破损", color: "#9a4b2e" },
  reject: { label: "拒收", color: "#7d8471" },
};

// 生成封面：由书名确定性取色（书脊档案 · 8 组深色调）
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
          const [c1, c2] = coverPair(it.title || String(it.id));
          return Object.assign({}, it, {
            condLabel: c.label, condColor: c.color,
            priceText: "¥" + Number(it.sale_price || 0).toFixed(2),
            c1, c2,
          });
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
