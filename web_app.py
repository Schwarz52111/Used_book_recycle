import argparse
import base64
import os
from typing import Any

import cv2
import numpy as np
from flask import Flask, jsonify, request, send_from_directory

from camera_book_recognition import (
    Book,
    configure_tesseract,
    estimate_condition,
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

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True})

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
            book, recognized_text = recognize_from_frame(conn, frame, ai_config)
            if not book:
                return jsonify(
                    {
                        "ok": False,
                        "message": "未匹配到数据库中的书籍。请让 ISBN 条码更清晰，或补充 books 表后重试。",
                    }
                ), 404

            condition_level, damage_score, completeness_score = estimate_condition(frame)
            evaluated_price = evaluate_price(conn, book, condition_level)
            save_record(
                conn,
                book,
                condition_level,
                damage_score,
                completeness_score,
                evaluated_price,
                recognized_text,
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
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT
                    r.id,
                    b.title,
                    b.author,
                    r.condition_level,
                    r.evaluated_price,
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
