const app = getApp();

Page({
  data: { user: null, loading: true, error: "" },

  onShow() {
    this.refresh();
  },

  refresh() {
    this.setData({ loading: true, error: "" });
    const openid = app.globalData.openid;
    const after = () => this.loadUser();
    if (!openid) {
      app.login().then(after).catch((e) => this.setData({ error: e.message, loading: false }));
    } else {
      after();
    }
  },

  loadUser() {
    app
      .api("GET", "/users/" + app.globalData.openid)
      .then((user) => {
        app.globalData.user = user;
        this.setData({
          user: Object.assign({}, user, { balanceText: "¥" + Number(user.balance || 0).toFixed(2) }),
          loading: false,
        });
      })
      .catch((e) => this.setData({ error: e.message, loading: false }));
  },
});
