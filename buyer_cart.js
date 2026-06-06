const cartPageContent = document.getElementById("cartPageContent");

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
  const match = window.location.pathname.match(/\/buyer\/cart\/(\d+)/);
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

async function loadCart() {
  const orderId = currentOrderId();
  if (!orderId) {
    cartPageContent.innerHTML = "<strong>缺少订单编号</strong>";
    return;
  }

  try {
    const payload = await fetchJson(`/api/shop/orders/${orderId}`);
    renderCart(payload.order);
  } catch (error) {
    cartPageContent.className = "empty-result";
    cartPageContent.innerHTML = `<strong>${escapeHtml(error.message)}</strong>`;
  }
}

function renderCart(order) {
  const pending = order.status === "pending";
  cartPageContent.className = "book-detail page-detail";
  cartPageContent.innerHTML = `
    <div class="checkout-layout">
      <div class="checkout-main">
        <h2>确认订单</h2>
        <article class="cart-item">
          <div class="order-cover large">
            ${order.image_url ? `<img src="${escapeHtml(order.image_url)}" alt="${escapeHtml(order.title)}">` : "<span>暂无图片</span>"}
          </div>
          <div>
            <div class="store-status">${escapeHtml(order.status_label || order.status)}</div>
            <h3>${escapeHtml(order.title)}</h3>
            <p>${escapeHtml(order.author)}</p>
            <p>订单号：${escapeHtml(order.id)}</p>
            <p>买家：${escapeHtml(order.buyer_name)} · ${escapeHtml(order.buyer_phone)}</p>
          </div>
        </article>
      </div>
      <aside class="checkout-summary">
        <h2>结算</h2>
        <dl class="summary-list">
          <div><dt>商品金额</dt><dd>${formatMoney(order.sale_price)}</dd></div>
          <div><dt>配送方式</dt><dd>到柜自取</dd></div>
          <div><dt>订单状态</dt><dd>${escapeHtml(order.status_label || order.status)}</dd></div>
        </dl>
        <div class="summary-total">${formatMoney(order.sale_price)}</div>
        <button class="button primary" id="payButton" ${pending ? "" : "disabled"}>立即支付</button>
        <button class="button ghost" id="cancelButton" ${pending ? "" : "disabled"}>取消订单</button>
        <a class="button ghost center-link" href="/buyer">继续选书</a>
      </aside>
    </div>
  `;

  document.getElementById("payButton").addEventListener("click", payOrder);
  document.getElementById("cancelButton").addEventListener("click", cancelOrder);
}

async function payOrder() {
  try {
    const payload = await fetchJson(`/api/shop/orders/${currentOrderId()}/pay`, { method: "POST" });
    alert(payload.message);
    window.location.href = payload.order_url || `/buyer/order/${currentOrderId()}`;
  } catch (error) {
    alert(error.message);
  }
}

async function cancelOrder() {
  try {
    const payload = await fetchJson(`/api/shop/orders/${currentOrderId()}/cancel`, { method: "POST" });
    alert(payload.message);
    await loadCart();
  } catch (error) {
    alert(error.message);
  }
}

loadCart();
