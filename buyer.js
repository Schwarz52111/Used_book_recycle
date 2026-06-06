const bookList = document.getElementById("bookList");
const refreshBooks = document.getElementById("refreshBooks");
const orderSearch = document.getElementById("orderSearch");
const orderPhone = document.getElementById("orderPhone");
const ordersList = document.getElementById("ordersList");

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

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok || !payload.ok) {
    throw new Error(payload.message || "请求失败");
  }
  return payload;
}

async function loadBooks() {
  bookList.innerHTML = '<div class="record-empty">正在加载库存...</div>';
  try {
    const payload = await fetchJson("/api/shop/books");
    renderBooks(payload.books || []);
  } catch (error) {
    bookList.innerHTML = `<div class="record-empty">${escapeHtml(error.message)}</div>`;
  }
}

function renderBooks(books) {
  if (!books.length) {
    bookList.innerHTML = '<div class="record-empty">暂无入库图书</div>';
    return;
  }

  bookList.innerHTML = books.map((book) => `
    <article class="store-card ${book.available ? "" : "sold"}" data-record-id="${book.record_id}">
      <div class="store-cover">
        ${book.image_url ? `<img src="${escapeHtml(book.image_url)}" alt="${escapeHtml(book.title)}">` : "<span>暂无图片</span>"}
      </div>
      <div class="store-info">
        <div class="store-status">${escapeHtml(book.status_label || (book.available ? "可购买" : "不可购买"))}</div>
        <h3>${escapeHtml(book.title)}</h3>
        <p>${escapeHtml(book.author)} · ${escapeHtml(book.publisher)}</p>
        <p>${escapeHtml(book.condition_label)} · 入库 ${escapeHtml(book.created_at)}</p>
        <div class="store-price">${formatMoney(book.sale_price)}</div>
      </div>
    </article>
  `).join("");

  document.querySelectorAll(".store-card").forEach((card) => {
    card.addEventListener("click", () => {
      window.location.href = `/buyer/book/${card.dataset.recordId}`;
    });
  });
}

async function loadOrders(phone = "") {
  const url = phone ? `/api/shop/orders?phone=${encodeURIComponent(phone)}` : "/api/shop/orders";
  try {
    const payload = await fetchJson(url);
    renderOrders(payload.orders || []);
  } catch (error) {
    ordersList.innerHTML = `<div class="record-empty">${escapeHtml(error.message)}</div>`;
  }
}

function renderOrders(orders) {
  if (!orders.length) {
    ordersList.innerHTML = '<div class="record-empty">暂无订单</div>';
    return;
  }

  ordersList.innerHTML = orders.map((order) => `
    <article class="order-card">
      <div class="order-cover">
        ${order.image_url ? `<img src="${escapeHtml(order.image_url)}" alt="${escapeHtml(order.title)}">` : "<span>图</span>"}
      </div>
      <div>
        <h3>${escapeHtml(order.title)}</h3>
        <p>${escapeHtml(order.buyer_name)} · ${escapeHtml(order.buyer_phone)}</p>
        <p>${escapeHtml(order.created_at)} · ${escapeHtml(order.status_label || order.status)}</p>
        <strong>${formatMoney(order.sale_price)}</strong>
        <div class="order-actions">
          <button class="button ghost order-link" data-order-id="${order.id}">查看</button>
          <button class="button ghost refund-button" data-order-id="${order.id}" ${order.status === "paid" ? "" : "disabled"}>退款</button>
        </div>
      </div>
    </article>
  `).join("");

  document.querySelectorAll(".refund-button").forEach((button) => {
    button.addEventListener("click", () => refundOrder(button.dataset.orderId));
  });
  document.querySelectorAll(".order-link").forEach((button) => {
    button.addEventListener("click", () => {
      window.location.href = `/buyer/order/${button.dataset.orderId}`;
    });
  });
}

async function refundOrder(orderId) {
  try {
    const payload = await fetchJson(`/api/shop/orders/${orderId}/refund`, { method: "POST" });
    alert(payload.message);
    await loadBooks();
    await loadOrders(orderPhone.value.trim());
  } catch (error) {
    alert(error.message);
  }
}

refreshBooks.addEventListener("click", loadBooks);
orderSearch.addEventListener("submit", (event) => {
  event.preventDefault();
  loadOrders(orderPhone.value.trim());
});

loadBooks();
loadOrders();
