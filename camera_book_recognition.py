import argparse
import os
import re
import shutil
from dataclasses import dataclass
from difflib import SequenceMatcher
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import cv2
import mysql.connector
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from ollama_book_recognition import (
    OllamaRecognizerConfig,
    local_ai_result_to_text,
    recognize_book_with_ollama,
)

try:
    from pyzbar.pyzbar import decode as decode_barcodes
except ImportError:
    decode_barcodes = None

try:
    import pytesseract
    from pytesseract import TesseractNotFoundError
except ImportError:
    pytesseract = None
    TesseractNotFoundError = RuntimeError


OCR_DISABLED_REASON = ""
DEBUG_OCR = False
FONT_PATHS = [
    Path(r"C:\Windows\Fonts\msyh.ttc"),
    Path(r"C:\Windows\Fonts\simhei.ttf"),
    Path(r"C:\Windows\Fonts\simsun.ttc"),
]


@dataclass
class Book:
    id: int
    isbn: str
    title: str
    author: str
    publisher: str
    category: str
    original_price: float
    market_price: float
    base_recycle_rate: float


def get_connection(config: dict[str, Any]) -> mysql.connector.MySQLConnection:
    return mysql.connector.connect(**config)


def as_float(value: Decimal | float) -> float:
    return float(value)


def row_to_book(row: dict[str, Any]) -> Book:
    return Book(
        id=row["id"],
        isbn=row["isbn"],
        title=row["title"],
        author=row["author"],
        publisher=row["publisher"],
        category=row["category"],
        original_price=as_float(row["original_price"]),
        market_price=as_float(row["market_price"]),
        base_recycle_rate=as_float(row["base_recycle_rate"]),
    )


def normalize_text(value: str) -> str:
    return "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", value)).lower()


def partial_similarity(needle: str, haystack: str) -> float:
    if not needle or not haystack:
        return 0.0
    if needle in haystack:
        return 1.0
    if haystack in needle:
        return 0.92
    if len(haystack) <= len(needle):
        return SequenceMatcher(None, needle, haystack).ratio()

    best = 0.0
    min_size = max(2, int(len(needle) * 0.7))
    max_size = min(len(haystack), int(len(needle) * 1.4) + 1)
    for size in range(min_size, max_size + 1):
        step = max(1, size // 4)
        for start in range(0, len(haystack) - size + 1, step):
            fragment = haystack[start : start + size]
            best = max(best, SequenceMatcher(None, needle, fragment).ratio())
    return best


def find_book_by_isbn(conn: mysql.connector.MySQLConnection, isbn: str) -> Optional[Book]:
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM books WHERE isbn = %s", (isbn,))
    row = cursor.fetchone()
    cursor.close()
    return row_to_book(row) if row else None


def find_book_by_text(conn: mysql.connector.MySQLConnection, text: str) -> Optional[Book]:
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM books")
    rows = cursor.fetchall()
    cursor.close()
    normalized = normalize_text(text)
    best_score = 0.0
    best_row = None

    for row in rows:
        row_best = 0.0
        candidates = [
            row["title"],
            row["author"],
            row["publisher"],
            f'{row["title"]}{row["author"]}',
            f'{row["title"]}{row["publisher"]}',
        ]
        for candidate in candidates:
            score = partial_similarity(normalize_text(candidate), normalized)
            row_best = max(row_best, score)
            if score > best_score:
                best_score = score
                best_row = row
        if DEBUG_OCR:
            print(f"OCR候选分数: {row['title']} -> {row_best:.3f}")

    if DEBUG_OCR:
        print(f"OCR最佳匹配: {best_row['title'] if best_row else '无'}，分数: {best_score:.3f}")

    return row_to_book(best_row) if best_row and best_score >= 0.58 else None


def decode_isbn(frame) -> Optional[str]:
    if decode_barcodes is None:
        return None

    for barcode in decode_barcodes(frame):
        value = barcode.data.decode("utf-8", errors="ignore").strip()
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) in (10, 13):
            return digits
    return None


def configure_tesseract(tesseract_cmd: Optional[str]) -> None:
    global OCR_DISABLED_REASON

    if pytesseract is None:
        OCR_DISABLED_REASON = "未安装 pytesseract，OCR 已关闭"
        return

    local_tessdata = Path(__file__).with_name("tessdata")
    if local_tessdata.exists():
        os.environ.setdefault("TESSDATA_PREFIX", str(local_tessdata))

    if tesseract_cmd:
        path = Path(tesseract_cmd)
        if path.exists():
            pytesseract.pytesseract.tesseract_cmd = str(path)
            OCR_DISABLED_REASON = ""
            return
        OCR_DISABLED_REASON = f"指定的 tesseract 路径不存在：{tesseract_cmd}"
        return

    default_windows_path = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if default_windows_path.exists():
        pytesseract.pytesseract.tesseract_cmd = str(default_windows_path)
        OCR_DISABLED_REASON = ""
        return

    current_cmd = getattr(pytesseract.pytesseract, "tesseract_cmd", "tesseract")
    if shutil.which(current_cmd) is None:
        OCR_DISABLED_REASON = "未找到 tesseract.exe，OCR 已关闭，仅使用 ISBN 条码识别"
    else:
        OCR_DISABLED_REASON = ""


def ocr_frame(frame) -> str:
    if pytesseract is None or OCR_DISABLED_REASON:
        return ""

    height, width = frame.shape[:2]
    if max(height, width) < 1400:
        frame = cv2.resize(frame, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 50, 50)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    adaptive = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        9,
    )

    images = [gray, binary, adaptive]
    configs = ["--psm 6", "--psm 11", "--psm 12"]
    results = []
    try:
        for image in images:
            for config in configs:
                value = pytesseract.image_to_string(image, lang="chi_sim+eng", config=config).strip()
                if value:
                    results.append(value)
    except TesseractNotFoundError:
        return ""
    except pytesseract.TesseractError as exc:
        print(f"OCR 识别失败，已跳过本次 OCR：{exc}")
        return ""

    text = "\n".join(dict.fromkeys(results))
    if DEBUG_OCR:
        print("\n===== OCR原文开始 =====")
        print(text if text else "<空>")
        print("===== OCR原文结束 =====")
    return text


def estimate_condition(frame) -> tuple[str, float, float]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 180)
    damage_score = min(float(edges.mean()) / 35.0, 1.0)

    height, width = gray.shape
    border = max(min(height, width) // 20, 8)
    border_pixels = cv2.vconcat(
        [
            gray[:border, :],
            gray[-border:, :],
        ]
    )
    border_std = float(border_pixels.std())
    completeness_score = max(0.0, min(1.0, 1.0 - border_std / 95.0))

    if completeness_score < 0.45 or damage_score > 0.78:
        return "damaged", damage_score, completeness_score
    if damage_score > 0.55:
        return "acceptable", damage_score, completeness_score
    if damage_score > 0.32:
        return "good", damage_score, completeness_score
    return "like_new", damage_score, completeness_score


def evaluate_price(conn: mysql.connector.MySQLConnection, book: Book, condition_level: str) -> float:
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT price_factor FROM condition_rules WHERE condition_level = %s",
        (condition_level,),
    )
    row = cursor.fetchone()
    cursor.close()
    factor = as_float(row["price_factor"]) if row else 0.5
    price = book.market_price * book.base_recycle_rate * factor
    return round(max(price, 1.0), 2)


def save_record(
    conn: mysql.connector.MySQLConnection,
    book: Book,
    condition_level: str,
    damage_score: float,
    completeness_score: float,
    evaluated_price: float,
    recognized_text: str,
) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO recycle_records
            (book_id, condition_level, damage_score, completeness_score, evaluated_price, recognized_text)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (book.id, condition_level, damage_score, completeness_score, evaluated_price, recognized_text[:1000]),
    )
    conn.commit()
    cursor.close()


def load_display_font(size: int) -> ImageFont.ImageFont:
    for font_path in FONT_PATHS:
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size)
    return ImageFont.load_default()


def draw_status(frame, lines: list[str]) -> None:
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image)
    font = load_display_font(24)
    y = 18
    for line in lines:
        draw.text((18, y), line, font=font, fill=(0, 255, 0), stroke_width=2, stroke_fill=(0, 0, 0))
        y += 34
    frame[:, :] = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def print_result(book: Book, condition_level: str, damage_score: float, completeness_score: float, price: float) -> None:
    print("\n识别结果")
    print(f"ISBN: {book.isbn}")
    print(f"书名: {book.title}")
    print(f"作者: {book.author}")
    print(f"出版社: {book.publisher}")
    print(f"分类: {book.category}")
    print(f"市场参考价: {book.market_price:.2f} 元")
    print(f"品相等级: {condition_level}")
    print(f"破损评分: {damage_score:.2f}")
    print(f"完整度评分: {completeness_score:.2f}")
    print(f"建议回收价: {price:.2f} 元")


def recognize_from_frame(
    conn: mysql.connector.MySQLConnection,
    frame,
    ai_config: Optional[OllamaRecognizerConfig] = None,
) -> tuple[Optional[Book], str]:
    isbn = decode_isbn(frame)
    if isbn:
        book = find_book_by_isbn(conn, isbn)
        if book:
            return book, f"ISBN:{isbn}"

    text = ocr_frame(frame)
    if text:
        book = find_book_by_text(conn, text)
        if book:
            return book, text

    if ai_config and ai_config.enabled:
        print("本地识别未命中，正在调用 Ollama 本地 AI 辅助识别...")
        ai_result = recognize_book_with_ollama(frame, ai_config)
        if ai_result:
            ai_text = local_ai_result_to_text(ai_result)
            if DEBUG_OCR:
                print(f"Ollama识别结果: {ai_text}")

            if ai_result.isbn:
                book = find_book_by_isbn(conn, "".join(ch for ch in ai_result.isbn if ch.isdigit()))
                if book:
                    return book, ai_text

            book = find_book_by_text(
                conn,
                "\n".join(
                    [
                        ai_result.title,
                        ai_result.author,
                        ai_result.publisher,
                        ai_result.damage_description,
                    ]
                ),
            )
            if book:
                return book, ai_text

    return None, text if "text" in locals() else ""


def run_camera(camera_index: int, db_config: dict[str, Any], ai_config: OllamaRecognizerConfig) -> None:
    conn = get_connection(db_config)
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开摄像头：{camera_index}")

    last_lines = ["Press SPACE to recognize", "Press Q to quit"]
    if OCR_DISABLED_REASON:
        print(OCR_DISABLED_REASON)
        print("如需封面文字识别，请安装 Tesseract OCR，或使用 --tesseract-cmd 指定 tesseract.exe。")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError("摄像头画面读取失败")

            preview = frame.copy()
            draw_status(preview, last_lines)
            cv2.imshow("Used Book Recognition", preview)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break
            if key == 32:
                book, recognized_text = recognize_from_frame(conn, frame, ai_config)
                if not book:
                    last_lines = ["No matched book", "Try ISBN barcode or clearer cover"]
                    print("未匹配到数据库中的书籍，可补充 books 表或调整摄像头距离/光线。")
                    continue

                condition_level, damage_score, completeness_score = estimate_condition(frame)
                price = evaluate_price(conn, book, condition_level)
                save_record(conn, book, condition_level, damage_score, completeness_score, price, recognized_text)
                print_result(book, condition_level, damage_score, completeness_score, price)
                last_lines = [
                    f"Matched: {book.title[:22]}",
                    f"Condition: {condition_level}  Price: {price:.2f} CNY",
                ]
    finally:
        cap.release()
        cv2.destroyAllWindows()
        conn.close()


def main() -> None:
    global DEBUG_OCR

    parser = argparse.ArgumentParser(description="二手图书自助回收售卖一体机：摄像头识别与估价")
    parser.add_argument("--camera", type=int, default=0, help="摄像头编号，默认 0")
    parser.add_argument("--db-host", default=os.getenv("MYSQL_HOST", "127.0.0.1"), help="MySQL 地址")
    parser.add_argument("--db-port", type=int, default=int(os.getenv("MYSQL_PORT", "3306")), help="MySQL 端口")
    parser.add_argument("--db-user", default=os.getenv("MYSQL_USER", "root"), help="MySQL 用户名")
    parser.add_argument("--db-password", default=os.getenv("MYSQL_PASSWORD", ""), help="MySQL 密码")
    parser.add_argument("--db-name", default=os.getenv("MYSQL_DATABASE", "used_book_recycle"), help="MySQL 数据库名")
    parser.add_argument("--ollama-host", default=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"), help="Ollama 服务地址")
    parser.add_argument("--ollama-model", default=os.getenv("OLLAMA_MODEL", "qwen2.5vl:3b"), help="Ollama 本地视觉模型")
    parser.add_argument("--disable-ai", action="store_true", help="关闭 Ollama 本地 AI 辅助识别")
    parser.add_argument(
        "--tesseract-cmd",
        default=None,
        help="tesseract.exe 完整路径，例如 C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
    )
    parser.add_argument("--debug-ocr", action="store_true", help="打印 OCR 原文和数据库匹配分数")
    args = parser.parse_args()
    DEBUG_OCR = args.debug_ocr
    configure_tesseract(args.tesseract_cmd)
    run_camera(
        args.camera,
        {
            "host": args.db_host,
            "port": args.db_port,
            "user": args.db_user,
            "password": args.db_password,
            "database": args.db_name,
            "charset": "utf8mb4",
        },
        OllamaRecognizerConfig(
            host=args.ollama_host,
            model=args.ollama_model,
            enabled=not args.disable_ai,
        ),
    )


if __name__ == "__main__":
    main()
