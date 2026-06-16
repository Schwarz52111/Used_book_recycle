// 即刻小绿 · 购书小程序
App({
  globalData: {
    baseUrl: "http://127.0.0.1:8000", // 后端地址；真机调试改为可访问的域名
    machineId: "KIOSK-01",
    openid: "",
    user: null,
    selected: null, // 列表→详情传递的库存项
  },

  onLaunch() {
    this.login().catch((e) => console.warn("登录失败：", e.message));
  },

  // wx.login 拿 code → 后端换 openid（mock 模式无需 AppID 即可成功）
  login() {
    return new Promise((resolve, reject) => {
      wx.login({
        success: (res) => {
          if (!res.code) return reject(new Error("wx.login 未返回 code"));
          this.api("POST", "/auth/wechat/login", { code: res.code })
            .then((user) => {
              this.globalData.openid = user.openid;
              this.globalData.user = user;
              resolve(user);
            })
            .catch(reject);
        },
        fail: (e) => reject(new Error(e.errMsg || "wx.login 失败")),
      });
    });
  },

  // 统一请求封装
  api(method, path, data) {
    return new Promise((resolve, reject) => {
      wx.request({
        url: this.globalData.baseUrl + path,
        method,
        data,
        header: { "Content-Type": "application/json" },
        success: (r) => {
          if (r.statusCode >= 200 && r.statusCode < 300) resolve(r.data);
          else reject(new Error((r.data && r.data.detail) || "HTTP " + r.statusCode));
        },
        fail: (e) => reject(new Error(e.errMsg || "网络错误")),
      });
    });
  },
});
