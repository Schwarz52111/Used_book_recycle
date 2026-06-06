import argparse
import base64
import html
import os
import uuid
from typing import Any

import cv2
import numpy as np
from flask import Flask, Response, jsonify, request, send_from_directory

from camera_book_recognition import (
    Book,
    ai_condition_scores,
    choose_condition_level,
    configure_tesseract,
    evaluate_price,
    get_connection,
    recognize_from_frame,
    save_record,
)
from ollama_book_recognition import OllamaRecognizerConfig


CONDITION_LABELS = {
    "like_new": "近全新",
    "good": "良好",
    "acceptable": "可接受",
    "damaged": "破损",
}
APP_VERSION = "ai_title_price_rate_2026_06_05"


SALE_PRICE_RATES = {
    "like_new": 0.90,
    "good": 0.80,
    "acceptable": 0.65,
    "damaged": 0.35,
}

ORDER_STATUS_LABELS = {
    "pending": "待支付",
    "paid": "已支付",
    "canceled": "已取消",
    "refunded": "已退款",
}


def create_app(db_config: dict[str, Any], ai_config: OllamaRecognizerConfig) -> Flask:
    app = Flask(__name__, static_folder=None)
    root_dir = os.path.dirname(os.path.abspath(__file__))

    @app.get("/")
    def index():
        return send_from_directory(root_dir, "index.html")

    @app.get("/styles.css")
    def styles():
        return send_from_directory(root_dir, "styles.css")

    @app.get("/app.js")
    def script():
        return send_from_directory(root_dir, "app.js")

    @app.get("/buyer")
    def buyer_index():
        return send_from_directory(root_dir, "buyer.html")

    @app.get("/buyer/book/<int:record_id>")
    def buyer_book_page(record_id: int):
        return send_from_directory(root_dir, "buyer_book.html")

    @app.get("/buyer/order/<int:order_id>")
    def buyer_order_page(order_id: int):
        return send_from_directory(root_dir, "buyer_order.html")

    @app.get("/buyer/cart/<int:order_id>")
    def buyer_cart_page(order_id: int):
        return send_from_directory(root_dir, "buyer_cart.html")

    @app.get("/buyer.js")
    def buyer_script():
        return send_from_directory(root_dir, "buyer.js")

    @app.get("/buyer_detail.js")
    def buyer_detail_script():
        return send_from_directory(root_dir, "buyer_detail.js")

    @app.get("/buyer_order.js")
    def buyer_order_script():
        return send_from_directory(root_dir, "buyer_order.js")

    @app.get("/buyer_cart.js")
    def buyer_cart_script():
        return send_from_directory(root_dir, "buyer_cart.js")

    @app.get("/uploads/<path:filename>")
    def uploaded_image(filename: str):
        return send_from_directory(os.path.join(root_dir, "uploads"), filename)

    @app.get("/api/shop/books/<int:record_id>/cover.svg")
    def generated_cover(record_id: int):
        conn = None
        try:
            conn = get_connection(db_config)
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT b.title, b.publisher
                FROM recycle_records r
                JOIN books b ON b.id = r.book_id
                WHERE r.id = %s
                """,
                (record_id,),
            )
            row = cursor.fetchone()
            cursor.close()
            if not row:
                return Response("", status=404)
            return Response(
                generated_cover_svg(row["title"], row["publisher"]),
                mimetype="image/svg+xml",
            )
        finally:
            if conn is not None:
                conn.close()

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "version": APP_VERSION})

    @app.post("/api/recognize")
    def recognize():
        payload = request.get_json(silent=True) or {}
        image_data = payload.get("image", "")
        try:
            frame = decode_data_url_image(image_data)
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

        conn = None
        try:
            conn = get_connection(db_config)
            ensure_runtime_schema(conn)
            recognition = recognize_from_frame(conn, frame, ai_config)
            book = recognition.book
            recognized_text = recognition.recognized_text
            if not book:
                return jsonify(
                    {
                        "ok": False,
                        "message": "AI 已完成识别，但未匹配到数据库中的书籍。请补充 books 表，或让封面文字更清晰后重试。",
                    }
                ), 404

            condition_level = choose_condition_level(
                recognition.ai_condition_level,
                recognition.ai_damage_description,
                "good",
            )
            damage_score, completeness_score = ai_condition_scores(condition_level)
            evaluated_price = evaluate_price(conn, book, condition_level, recognition.ai_recycle_price_rate)
            image_path = save_recycle_image(root_dir, frame)
            save_record(
                conn,
                book,
                condition_level,
                damage_score,
                completeness_score,
                evaluated_price,
                recognized_text,
                image_path,
            )
            return jsonify(
                {
                    "ok": True,
                    "result": {
                        "book": serialize_book(book),
                        "condition_level": condition_level,
                        "condition_label": CONDITION_LABELS.get(condition_level, condition_level),
                        "damage_score": round(damage_score, 4),
                        "completeness_score": round(completeness_score, 4),
                        "evaluated_price": evaluated_price,
                        "ai_condition_level": recognition.ai_condition_level,
                        "ai_damage_description": recognition.ai_damage_description,
                        "ai_recycle_price_rate": recognition.ai_recycle_price_rate,
                        "recognized_text": recognized_text,
                    },
                }
            )
        except Exception as exc:
            return jsonify({"ok": False, "message": f"后端识别失败：{exc}"}), 500
        finally:
            if conn is not None:
                conn.close()

    @app.get("/api/records")
    def records():
        conn = None
        try:
            conn = get_connection(db_config)
            ensure_runtime_schema(conn)
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT
                    r.id,
                    b.title,
                    b.author,
                    r.condition_level,
                    r.evaluated_price,
                    r.image_path,
                    DATE_FORMAT(r.created_at, '%Y-%m-%d %H:%i:%s') AS created_at
                FROM recycle_records r
                JOIN books b ON b.id = r.book_id
                ORDER BY r.created_at DESC
                LIMIT 8
                """
            )
            rows = cursor.fetchall()
            cursor.close()
            return jsonify(
                {
                    "ok": True,
                    "records": [
                        {
                            "id": row["id"],
                            "title": row["title"],
                            "author": row["author"],
                            "condition_level": row["condition_level"],
                            "condition_label": CONDITION_LABELS.get(row["condition_level"], row["condition_level"]),
                            "evaluated_price": float(row["evaluated_price"]),
                            "image_url": image_url(row["image_path"], row["id"]),
                            "created_at": row["created_at"],
                        }
                        for row in rows
                    ],
                }
            )
        except Exception:
            return jsonify({"ok": True, "records": []})
        finally:
            if conn is not None:
                conn.close()

    @app.get("/api/shop/books")
    def shop_books():
        conn = None
        try:
            conn = get_connection(db_config)
            ensure_runtime_schema(conn)
            cursor = conn.cursor(dictionary=True)
            cursor.execute(shop_books_query() + " ORDER BY r.created_at DESC")
            rows = cursor.fetchall()
            cursor.close()
            return jsonify({"ok": True, "books": [serialize_listing(row) for row in rows]})
        except Exception as exc:
            return jsonify({"ok": False, "message": f"读取买家端库存失败：{exc}"}), 500
        finally:
            if conn is not None:
                conn.close()

    @app.get("/api/shop/books/<int:record_id>")
    def shop_book_detail(record_id: int):
        conn = None
        try:
            conn = get_connection(db_config)
            ensure_runtime_schema(conn)
            cursor = conn.cursor(dictionary=True)
            cursor.execute(shop_books_query("WHERE r.id = %s"), (record_id,))
            row = cursor.fetchone()
            cursor.close()
            if not row:
                return jsonify({"ok": False, "message": "未找到该入库图书"}), 404
            return jsonify({"ok": True, "book": serialize_listing(row, include_text=True)})
        except Exception as exc:
            return jsonify({"ok": False, "message": f"读取图书详情失败：{exc}"}), 500
        finally:
            if conn is not None:
                conn.close()

    @app.post("/api/shop/orders")
    def create_order():
        payload = request.get_json(silent=True) or {}
        record_id = int(payload.get("record_id") or 0)
        buyer_name = str(payload.get("buyer_name") or "").strip()
        buyer_phone = str(payload.get("buyer_phone") or "").strip()

        if not record_id:
            return jsonify({"ok": False, "message": "缺少图书库存编号"}), 400
        if not buyer_name or not buyer_phone:
            return jsonify({"ok": False, "message": "请填写买家姓名和手机号"}), 400

        conn = None
        try:
            conn = get_connection(db_config)
            ensure_runtime_schema(conn)
            cursor = conn.cursor(dictionary=True)
            cursor.execute(shop_books_query("WHERE r.id = %s"), (record_id,))
            listing = cursor.fetchone()
            if not listing:
                cursor.close()
                return jsonify({"ok": False, "message": "未找到该入库图书"}), 404
            if listing["active_order_id"]:
                cursor.close()
                return jsonify({"ok": False, "message": "该图书已售出，暂不可购买"}), 409

            sale_price = calculate_sale_price(listing)
            cursor.execute(
                """
                INSERT INTO buyer_orders
                    (recycle_record_id, buyer_name, buyer_phone, sale_price, status)
                VALUES (%s, %s, %s, %s, 'pending')
                """,
                (record_id, buyer_name, buyer_phone, sale_price),
            )
            order_id = cursor.lastrowid
            conn.commit()
            cursor.close()
            return jsonify(
                {
                    "ok": True,
                    "order": {
                        "id": order_id,
                        "record_id": record_id,
                        "buyer_name": buyer_name,
                        "buyer_phone": buyer_phone,
                        "sale_price": sale_price,
                        "status": "pending",
                        "cart_url": f"/buyer/cart/{order_id}",
                    },
                }
            )
        except Exception as exc:
            if conn is not None:
                conn.rollback()
            return jsonify({"ok": False, "message": f"购买失败：{exc}"}), 500
        finally:
            if conn is not None:
                conn.close()

    @app.get("/api/shop/orders")
    def list_orders():
        phone = str(request.args.get("phone") or "").strip()
        conn = None
        try:
            conn = get_connection(db_config)
            ensure_runtime_schema(conn)
            cursor = conn.cursor(dictionary=True)
            where = "WHERE o.buyer_phone = %s" if phone else ""
            params = (phone,) if phone else ()
            cursor.execute(
                f"""
                SELECT
                    o.id,
                    o.recycle_record_id,
                    o.buyer_name,
                    o.buyer_phone,
                    o.sale_price,
                    o.status,
                    o.created_at AS created_at,
                    o.refunded_at AS refunded_at,
                    b.title,
                    b.author,
                    r.image_path
                FROM buyer_orders o
                JOIN recycle_records r ON r.id = o.recycle_record_id
                JOIN books b ON b.id = r.book_id
                {where}
                ORDER BY o.created_at DESC
                LIMIT 30
                """,
                params,
            )
            rows = cursor.fetchall()
            cursor.close()
            return jsonify({"ok": True, "orders": [serialize_order(row) for row in rows]})
        except Exception as exc:
            return jsonify({"ok": False, "message": f"读取订单失败：{exc}"}), 500
        finally:
            if conn is not None:
                conn.close()

    @app.get("/api/shop/orders/<int:order_id>")
    def order_detail(order_id: int):
        conn = None
        try:
            conn = get_connection(db_config)
            ensure_runtime_schema(conn)
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT
                    o.id,
                    o.recycle_record_id,
                    o.buyer_name,
                    o.buyer_phone,
                    o.sale_price,
                    o.status,
                    o.created_at AS created_at,
                    o.refunded_at AS refunded_at,
                    b.title,
                    b.author,
                    r.image_path
                FROM buyer_orders o
                JOIN recycle_records r ON r.id = o.recycle_record_id
                JOIN books b ON b.id = r.book_id
                WHERE o.id = %s
                """,
                (order_id,),
            )
            row = cursor.fetchone()
            cursor.close()
            if not row:
                return jsonify({"ok": False, "message": "未找到订单"}), 404
            return jsonify({"ok": True, "order": serialize_order(row)})
        except Exception as exc:
            return jsonify({"ok": False, "message": f"读取订单详情失败：{exc}"}), 500
        finally:
            if conn is not None:
                conn.close()

    @app.post("/api/shop/orders/<int:order_id>/pay")
    def pay_order(order_id: int):
        conn = None
        try:
            conn = get_connection(db_config)
            ensure_runtime_schema(conn)
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM buyer_orders WHERE id = %s", (order_id,))
            order = cursor.fetchone()
            if not order:
                cursor.close()
                return jsonify({"ok": False, "message": "未找到订单"}), 404
            if order["status"] != "pending":
                cursor.close()
                return jsonify({"ok": False, "message": "只有待支付订单可以支付"}), 409

            cursor.execute(
                """
                UPDATE buyer_orders
                SET status = 'paid'
                WHERE id = %s
                """,
                (order_id,),
            )
            conn.commit()
            cursor.close()
            return jsonify({"ok": True, "message": "支付成功", "order_url": f"/buyer/order/{order_id}"})
        except Exception as exc:
            if conn is not None:
                conn.rollback()
            return jsonify({"ok": False, "message": f"支付失败：{exc}"}), 500
        finally:
            if conn is not None:
                conn.close()

    @app.post("/api/shop/orders/<int:order_id>/cancel")
    def cancel_order(order_id: int):
        conn = None
        try:
            conn = get_connection(db_config)
            ensure_runtime_schema(conn)
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM buyer_orders WHERE id = %s", (order_id,))
            order = cursor.fetchone()
            if not order:
                cursor.close()
                return jsonify({"ok": False, "message": "未找到订单"}), 404
            if order["status"] != "pending":
                cursor.close()
                return jsonify({"ok": False, "message": "只有待支付订单可以取消"}), 409

            cursor.execute(
                """
                UPDATE buyer_orders
                SET status = 'canceled'
                WHERE id = %s
                """,
                (order_id,),
            )
            conn.commit()
            cursor.close()
            return jsonify({"ok": True, "message": "订单已取消，图书已回到可购买状态"})
        except Exception as exc:
            if conn is not None:
                conn.rollback()
            return jsonify({"ok": False, "message": f"取消订单失败：{exc}"}), 500
        finally:
            if conn is not None:
                conn.close()

    @app.post("/api/shop/orders/<int:order_id>/refund")
    def refund_order(order_id: int):
        conn = None
        try:
            conn = get_connection(db_config)
            ensure_runtime_schema(conn)
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM buyer_orders WHERE id = %s", (order_id,))
            order = cursor.fetchone()
            if not order:
                cursor.close()
                return jsonify({"ok": False, "message": "未找到订单"}), 404
            if order["status"] != "paid":
                cursor.close()
                return jsonify({"ok": False, "message": "该订单已退款或不可退款"}), 409

            cursor.execute(
                """
                UPDATE buyer_orders
                SET status = 'refunded', refunded_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (order_id,),
            )
            conn.commit()
            cursor.close()
            return jsonify({"ok": True, "message": "退款成功，图书已重新上架"})
        except Exception as exc:
            if conn is not None:
                conn.rollback()
            return jsonify({"ok": False, "message": f"退款失败：{exc}"}), 500
        finally:
            if conn is not None:
                conn.close()

    return app


def decode_data_url_image(image_data: str):
    if not image_data:
        raise ValueError("缺少摄像头截图")
    if "," in image_data:
        image_data = image_data.split(",", 1)[1]
    try:
        raw = base64.b64decode(image_data)
    except ValueError as exc:
        raise ValueError("截图格式不正确") from exc

    buffer = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("无法解析摄像头截图")
    return frame


def serialize_book(book: Book) -> dict[str, Any]:
    return {
        "id": book.id,
        "isbn": book.isbn,
        "title": book.title,
        "author": book.author,
        "publisher": book.publisher,
        "category": book.category,
        "original_price": book.original_price,
        "market_price": book.market_price,
        "base_recycle_rate": book.base_recycle_rate,
    }


def ensure_runtime_schema(conn) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'recycle_records'
          AND COLUMN_NAME = 'image_path'
        """
    )
    if cursor.fetchone()[0] == 0:
        cursor.execute("ALTER TABLE recycle_records ADD COLUMN image_path VARCHAR(255)")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS buyer_orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            recycle_record_id INT NOT NULL,
            buyer_name VARCHAR(100) NOT NULL,
            buyer_phone VARCHAR(50) NOT NULL,
            sale_price DECIMAL(10, 2) NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            refunded_at TIMESTAMP NULL DEFAULT NULL,
            INDEX idx_buyer_orders_record_status (recycle_record_id, status),
            CONSTRAINT fk_buyer_orders_record
                FOREIGN KEY (recycle_record_id) REFERENCES recycle_records(id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    conn.commit()
    cursor.close()


def save_recycle_image(root_dir: str, frame) -> str:
    upload_dir = os.path.join(root_dir, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"recycle_{uuid.uuid4().hex}.jpg"
    image_path = os.path.join(upload_dir, filename)
    ok = cv2.imwrite(image_path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        return ""
    return filename


def image_url(image_path: str | None, record_id: int | None = None) -> str:
    if not image_path:
        return f"/api/shop/books/{record_id}/cover.svg" if record_id else ""
    return f"/uploads/{image_path}"


def generated_cover_svg(title: str, publisher: str) -> str:
    safe_title = html.escape(title)
    safe_publisher = html.escape(publisher)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="880" viewBox="0 0 640 880">
  <rect width="640" height="880" fill="#263027"/>
  <rect x="38" y="38" width="564" height="804" rx="22" fill="#f7f3e8"/>
  <rect x="72" y="72" width="496" height="650" rx="12" fill="#2f6b4f"/>
  <text x="320" y="250" text-anchor="middle" font-size="54" font-family="Microsoft YaHei, Arial" font-weight="700" fill="#fff">
    <tspan x="320" dy="0">{safe_title[:8]}</tspan>
    <tspan x="320" dy="72">{safe_title[8:16]}</tspan>
    <tspan x="320" dy="72">{safe_title[16:24]}</tspan>
  </text>
  <text x="320" y="790" text-anchor="middle" font-size="28" font-family="Microsoft YaHei, Arial" fill="#2f6b4f">{safe_publisher}</text>
</svg>"""


def calculate_sale_price(row: dict[str, Any]) -> float:
    market_price = float(row["market_price"])
    condition_level = row.get("condition_level") or "good"
    rate = SALE_PRICE_RATES.get(condition_level, 0.75)
    return round(max(market_price * rate, 1.0), 2)


def format_datetime(value: Any) -> str:
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def shop_books_query(where_clause: str = "") -> str:
    return f"""
        SELECT
            r.id AS record_id,
            r.condition_level,
            r.damage_score,
            r.completeness_score,
            r.evaluated_price,
            r.image_path,
            r.recognized_text,
            r.created_at AS created_at,
            b.id AS book_id,
            b.isbn,
            b.title,
            b.author,
            b.publisher,
            b.category,
            b.original_price,
            b.market_price,
            active_order.id AS active_order_id,
            active_order.status AS active_order_status
        FROM recycle_records r
        JOIN books b ON b.id = r.book_id
        LEFT JOIN buyer_orders active_order
            ON active_order.recycle_record_id = r.id
           AND active_order.status IN ('pending', 'paid')
        {where_clause}
    """


def serialize_listing(row: dict[str, Any], include_text: bool = False) -> dict[str, Any]:
    available = row["active_order_id"] is None
    payload = {
        "record_id": row["record_id"],
        "book_id": row["book_id"],
        "isbn": row["isbn"],
        "title": row["title"],
        "author": row["author"],
        "publisher": row["publisher"],
        "category": row["category"],
        "original_price": float(row["original_price"]),
        "market_price": float(row["market_price"]),
        "condition_level": row["condition_level"],
        "condition_label": CONDITION_LABELS.get(row["condition_level"], row["condition_level"]),
        "damage_score": float(row["damage_score"]),
        "completeness_score": float(row["completeness_score"]),
        "recycle_price": float(row["evaluated_price"]),
        "sale_price": calculate_sale_price(row),
        "image_url": image_url(row["image_path"], row["record_id"]),
        "created_at": format_datetime(row["created_at"]),
        "available": available,
        "status": "available" if available else row["active_order_status"],
        "status_label": "可购买" if available else ORDER_STATUS_LABELS.get(row["active_order_status"], "不可购买"),
        "active_order_id": row["active_order_id"],
    }
    if include_text:
        payload["recognized_text"] = row.get("recognized_text") or ""
    return payload


def serialize_order(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "record_id": row["recycle_record_id"],
        "buyer_name": row["buyer_name"],
        "buyer_phone": row["buyer_phone"],
        "sale_price": float(row["sale_price"]),
        "status": row["status"],
        "status_label": ORDER_STATUS_LABELS.get(row["status"], row["status"]),
        "created_at": format_datetime(row["created_at"]),
        "refunded_at": format_datetime(row["refunded_at"]),
        "title": row["title"],
        "author": row["author"],
        "image_url": image_url(row["image_path"], row["recycle_record_id"]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="二手图书回收系统网页端")
    parser.add_argument("--host", default="127.0.0.1", help="Web 服务地址")
    parser.add_argument("--port", type=int, default=5000, help="Web 服务端口")
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_tesseract(args.tesseract_cmd)
    app = create_app(
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
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
