const camera = document.getElementById("camera");
const snapshot = document.getElementById("snapshot");
const cameraEmpty = document.getElementById("cameraEmpty");
const videoWrap = document.getElementById("videoWrap");
const startCamera = document.getElementById("startCamera");
const stopCamera = document.getElementById("stopCamera");
const recognizeBook = document.getElementById("recognizeBook");
const hint = document.getElementById("hint");
const serverState = document.getElementById("serverState");
const emptyResult = document.getElementById("emptyResult");
const bookResult = document.getElementById("bookResult");
const recordsList = document.getElementById("recordsList");

let stream = null;

const conditionLabels = {
  like_new: "近全新",
  good: "良好",
  acceptable: "可接受",
  damaged: "破损",
};

function setState(text, type = "") {
  serverState.textContent = text;
  serverState.className = `server-state ${type}`.trim();
}

function setHint(text, type = "") {
  hint.textContent = text;
  hint.style.color = type === "error" ? "#a64032" : "";
}

function formatMoney(value) {
  return `¥${Number(value || 0).toFixed(2)}`;
}

function formatScore(value) {
  return Number(value || 0).toFixed(2);
}

async function checkServer() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error("health check failed");
    setState("后端已连接", "ok");
  } catch (error) {
    setState("后端未连接", "error");
  }
}

async function loadRecords() {
  try {
    const response = await fetch("/api/records");
    if (!response.ok) return;
    const payload = await response.json();
    renderRecords(payload.records || []);
  } catch (error) {
    renderRecords([]);
  }
}

function renderRecords(records) {
  if (!records.length) {
    recordsList.innerHTML = '<div class="record-empty">暂无记录</div>';
    return;
  }

  recordsList.innerHTML = records.map((record) => `
    <article class="record-card">
      <h3>${escapeHtml(record.title)}</h3>
      <p>${escapeHtml(record.author)} · ${escapeHtml(record.condition_label)}</p>
      <p>${escapeHtml(record.created_at)}</p>
      <div class="record-price">${formatMoney(record.evaluated_price)}</div>
    </article>
  `).join("");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function openCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: "environment",
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
      audio: false,
    });
    camera.srcObject = stream;
    await camera.play();
    videoWrap.classList.add("camera-active");
    cameraEmpty.hidden = true;
    startCamera.disabled = true;
    stopCamera.disabled = false;
    recognizeBook.disabled = false;
    setHint("摄像头已打开。将书籍封面或 ISBN 条码放入画面后点击“识别图书”。");
  } catch (error) {
    setHint("无法打开摄像头。请确认浏览器权限已允许，且通过 http://127.0.0.1:5000 访问页面。", "error");
  }
}

function closeCamera() {
  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
    stream = null;
  }
  camera.srcObject = null;
  videoWrap.classList.remove("camera-active");
  cameraEmpty.hidden = false;
  startCamera.disabled = false;
  stopCamera.disabled = true;
  recognizeBook.disabled = true;
  setHint("摄像头已关闭。");
}

function captureFrame() {
  const width = camera.videoWidth;
  const height = camera.videoHeight;
  if (!width || !height) {
    throw new Error("摄像头画面尚未准备好");
  }
  snapshot.width = width;
  snapshot.height = height;
  const context = snapshot.getContext("2d");
  context.drawImage(camera, 0, 0, width, height);
  return snapshot.toDataURL("image/jpeg", 0.9);
}

async function recognizeCurrentBook() {
  recognizeBook.disabled = true;
  setHint("正在识别，请保持书籍稳定...");

  try {
    const image = captureFrame();
    const response = await fetch("/api/recognize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || "识别失败");
    }
    renderResult(payload.result);
    await loadRecords();
    setHint("识别完成，结果已写入回收记录。");
  } catch (error) {
    setHint(error.message || "识别失败，请调整光线、距离或更换角度后重试。", "error");
  } finally {
    recognizeBook.disabled = false;
  }
}

function renderResult(result) {
  emptyResult.hidden = true;
  bookResult.hidden = false;

  document.getElementById("evaluatedPrice").textContent = formatMoney(result.evaluated_price);
  document.getElementById("bookTitle").textContent = result.book.title;
  document.getElementById("bookIsbn").textContent = result.book.isbn;
  document.getElementById("bookAuthor").textContent = result.book.author;
  document.getElementById("bookPublisher").textContent = result.book.publisher;
  document.getElementById("bookCategory").textContent = result.book.category;
  document.getElementById("marketPrice").textContent = formatMoney(result.book.market_price);
  document.getElementById("conditionLevel").textContent = result.condition_label;
  document.getElementById("damageScore").textContent = formatScore(result.damage_score);
  document.getElementById("completenessScore").textContent = formatScore(result.completeness_score);
  document.getElementById("recognizedText").textContent = result.recognized_text || "无";
}

startCamera.addEventListener("click", openCamera);
stopCamera.addEventListener("click", closeCamera);
recognizeBook.addEventListener("click", recognizeCurrentBook);

checkServer();
loadRecords();
