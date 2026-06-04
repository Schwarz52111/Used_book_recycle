const app = getApp();

const CONDITION = {
  like_new: { label: "近全新", color: "#3a5d37" },
  good: { label: "良好", color: "#5a7a4e" },
  acceptable: { label: "可接受", color: "#b06a3b" },
  damaged: { label: "破损", color: "#9a4b2e" },
  reject: { label: "建议拒收", color: "#7d8471" },
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
  data: {
    photo: "",        // 本地临时图片
    stage: "idle",    // idle | loading | result | done
    result: null,     // appraise 结果（已加工）
    editPrice: "",    // 卖家可改的回收价（字符串，绑定输入框）
    payout: 0,
    error: "",
  },

  // 拍照 / 选图
  pick() {
    wx.chooseMedia({
      count: 1,
      mediaType: ["image"],
      sourceType: ["camera", "album"],
      sizeType: ["compressed"],
      success: (res) => {
        const f = res.tempFiles[0];
        this.setData({ photo: f.tempFilePath, stage: "idle", result: null, error: "" });
      },
    });
  },

  // 上传估价
  appraise() {
    if (!this.data.photo) return;
    this.setData({ stage: "loading", error: "" });
    wx.uploadFile({
      url: app.globalData.baseUrl + "/appraise",
      filePath: this.data.photo,
      name: "file",
      success: (res) => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          this.setData({ stage: "idle", error: "估价失败：HTTP " + res.statusCode });
          return;
        }
        let data;
        try { data = JSON.parse(res.data); } catch (e) { this.setData({ stage: "idle", error: "返回解析失败" }); return; }
        this.renderResult(data);
      },
      fail: (e) => this.setData({ stage: "idle", error: e.errMsg || "网络错误" }),
    });
  },

  renderResult(data) {
    const rec = data.recognize || {};
    const c = data.condition || {};
    const p = data.price;
    const adm = data.admission;
    const cl = CONDITION[c.condition_level] || { label: c.condition_level, color: "#7d8471" };

    let canRecycle = false;
    let notice = "";
    if (!rec.matched) {
      notice = "未识别到书目，已转人工复核，请到设备端处理或换清晰的封面重拍。";
    } else if (c.rejected) {
      notice = "该书品相判定为「" + cl.label + "」，暂不回收。";
    } else if (adm && !adm.accepted) {
      notice = adm.reason;
    } else if (p) {
      canRecycle = true;
    }

    const dims = (c.dimensions || []).map((d) => ({
      name: d.name,
      pct: Math.round((d.score || 0) * 100),
      evidence: d.evidence || "",
      warn: (d.score || 0) >= 0.55,
    }));

    const title = (rec.book && rec.book.title) || "未知书名";
    const [c1, c2] = coverPair(title);
    this.setData({
      stage: "result",
      editPrice: p ? String(Number(p.recycle_price).toFixed(2)) : "",
      result: {
        aiPrice: p ? Number(p.recycle_price) : 0,
        recordId: data.record_id,
        title,
        c1, c2,
        author: (rec.book && (rec.book.author || "")) || "",
        method: rec.method,
        confidence: Math.round((rec.confidence || 0) * 100),
        condLabel: cl.label,
        condColor: cl.color,
        summary: c.summary || "",
        dims,
        recycleText: p ? "¥" + Number(p.recycle_price).toFixed(2) : "",
        saleText: p ? "¥" + Number(p.sale_price).toFixed(2) : "",
        reason: p ? p.reason : "",
        canRecycle,
        notice,
        recyclePrice: p ? Number(p.recycle_price) : 0,
      },
    });
  },

  onPriceInput(e) {
    this.setData({ editPrice: e.detail.value });
  },

  incPrice() {
    const v = (parseFloat(this.data.editPrice) || 0) + 1;
    this.setData({ editPrice: v.toFixed(2) });
  },

  decPrice() {
    const v = Math.max(0, (parseFloat(this.data.editPrice) || 0) - 1);
    this.setData({ editPrice: v.toFixed(2) });
  },

  confirmRecycle() {
    const r = this.data.result;
    if (!r || !r.canRecycle) return;
    const sp = parseFloat(this.data.editPrice);
    const sellerPrice = isNaN(sp) ? undefined : sp;
    app
      .api("POST", "/inventory/intake", {
        record_id: r.recordId,
        machine_id: app.globalData.machineId,
        seller_openid: app.globalData.openid,
        seller_price: sellerPrice,
      })
      .then((item) => {
        const payout = item && item.cost_price ? Number(item.cost_price) : r.aiPrice;
        const reviewing = sellerPrice !== undefined && sellerPrice > r.aiPrice + 0.001;
        this.setData({ stage: "done", payout: payout.toFixed(2), reviewing });
      })
      .catch((e) => this.setData({ error: "入库失败：" + e.message }));
  },

  reset() {
    this.setData({ photo: "", stage: "idle", result: null, editPrice: "", error: "", payout: 0, reviewing: false });
  },
});
