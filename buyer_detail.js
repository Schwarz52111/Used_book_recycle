const detailPageContent = document.getElementById("detailPageContent");

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

function currentRecordId() {
  const match = window.location.pathname.match(/\/buyer\/book\/(\d+)/);
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

async function loadDetail() {
  const recordId = currentRecordId();
  if (!recordId) {
    detailPageContent.innerHTML = '<strong>缺少图书编号</strong>';
    return;
  }

  try {
    const payload = await fetchJson(`/api/shop/books/${recordId}`);
    renderDetail(payload.book);
  } catch (error) {
    detailPageContent.className = "empty-result";
    detailPageContent.innerHTML = `<strong>${escapeHtml(error.message)}</strong>`;
  }
}

function renderDetail(book) {
  detailPageContent.className = "book-detail page-detail";
  detailPageContent.innerHTML = `
    <div class="detail-layout">
      <div class="detail-image large">
        ${book.image_url ? `<img src="${escapeHtml(book.image_url)}" alt="${escapeHtml(book.title)}">` : "<span>暂无图片</span>"}
      </div>
      <div class="detail-main">
        <div class="store-status">${escapeHtml(book.status_label || (book.available ? "可购买" : "不可购买"))}</div>
        <h2>${escapeHtml(book.title)}</h2>
        <div class="detail-price">${formatMoney(book.sale_price)}</div>
        <dl class="book-fields single">
          <div><dt>ISBN</dt><dd>${escapeHtml(book.isbn)}</dd></div>
          <div><dt>作者</dt><dd>${escapeHtml(book.author)}</dd></div>
          <div><dt>出版社</dt><dd>${escapeHtml(book.publisher)}</dd></div>
          <div><dt>分类</dt><dd>${escapeHtml(book.category)}</dd></div>
          <div><dt>市场参考价</dt><dd>${formatMoney(book.market_price)}</dd></div>
          <div><dt>品相</dt><dd>${escapeHtml(book.condition_label)}</dd></div>
          <div><dt>入库时间</dt><dd>${escapeHtml(book.created_at)}</dd></div>
          <div><dt>库存状态</dt><dd>${escapeHtml(book.status_label || (book.available ? "可购买" : "不可购买"))}</dd></div>
        </dl>
        <form class="purchase-form" id="purchaseForm">
          <input id="buyerName" type="text" placeholder="买家姓名" ${book.available ? "" : "disabled"}>
          <input id="buyerPhone" type="tel" placeholder="手机号" ${book.available ? "" : "disabled"}>
          <button class="button primary" type="submit" ${book.available ? "" : "disabled"}>加入购物车</button>
        </form>
      </div>
    </div>
    <details class="recognized-text">
      <summary>查看入库识别文本</summary>
      <pre>${escapeHtml(book.recognized_text || "无")}</pre>
    </details>
  `;

  document.getElementById("purchaseForm").addEventListener("submit", (event) => buyBook(event, book.record_id));
}

async function buyBook(event, recordId) {
  event.preventDefault();
  const buyerName = document.getElementById("buyerName").value.trim();
  const buyerPhone = document.getElementById("buyerPhone").value.trim();

  try {
    const payload = await fetchJson("/api/shop/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        record_id: recordId,
        buyer_name: buyerName,
        buyer_phone: buyerPhone,
      }),
    });
    window.location.href = payload.order.cart_url || `/buyer/cart/${payload.order.id}`;
  } catch (error) {
    alert(error.message);
  }
}

loadDetail();
