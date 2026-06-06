const orderPageContent = document.getElementById("orderPageContent");

function formatMoney(value) {
  return `¥${Number(value || 0).toFixed(2)}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function currentOrderId() {
  const match = window.location.pathname.match(/\/buyer\/order\/(\d+)/);
  return match ? match[1] : "";
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok || !payload.ok) {
    throw new Error(payload.message || "请求失败");
  }
  return payload;
}

async function loadOrder() {
  const orderId = currentOrderId();
  if (!orderId) {
    orderPageContent.innerHTML = '<strong>缺少订单编号</strong>';
    return;
  }

  try {
    const payload = await fetchJson(`/api/shop/orders/${orderId}`);
    renderOrder(payload.order);
  } catch (error) {
    orderPageContent.className = "empty-result";
    orderPageContent.innerHTML = `<strong>${escapeHtml(error.message)}</strong>`;
  }
}

function renderOrder(order) {
  const paid = order.status === "paid";
  const pending = order.status === "pending";
  orderPageContent.className = "book-detail page-detail";
  orderPageContent.innerHTML = `
    <div class="detail-layout compact">
      <div class="detail-image large">
        ${order.image_url ? `<img src="${escapeHtml(order.image_url)}" alt="${escapeHtml(order.title)}">` : "<span>暂无图片</span>"}
      </div>
      <div class="detail-main">
        <div class="store-status">${escapeHtml(order.status_label || order.status)}</div>
        <h2>${escapeHtml(order.title)}</h2>
        <div class="detail-price">${formatMoney(order.sale_price)}</div>
        <dl class="book-fields single">
          <div><dt>订单号</dt><dd>${escapeHtml(order.id)}</dd></div>
          <div><dt>买家</dt><dd>${escapeHtml(order.buyer_name)}</dd></div>
          <div><dt>手机号</dt><dd>${escapeHtml(order.buyer_phone)}</dd></div>
          <div><dt>下单时间</dt><dd>${escapeHtml(order.created_at)}</dd></div>
          <div><dt>订单状态</dt><dd>${escapeHtml(order.status_label || order.status)}</dd></div>
          <div><dt>退款时间</dt><dd>${escapeHtml(order.refunded_at || "未退款")}</dd></div>
        </dl>
        <a class="button primary center-link" href="/buyer/cart/${escapeHtml(order.id)}" ${pending ? "" : "hidden"}>去购物车支付</a>
        <button class="button primary" id="refundButton" ${paid ? "" : "disabled"}>申请退款</button>
      </div>
    </div>
  `;

  document.getElementById("refundButton").addEventListener("click", refundOrder);
}

async function refundOrder() {
  const orderId = currentOrderId();
  try {
    const payload = await fetchJson(`/api/shop/orders/${orderId}/refund`, { method: "POST" });
    alert(payload.message);
    await loadOrder();
  } catch (error) {
    alert(error.message);
  }
}

loadOrder();
