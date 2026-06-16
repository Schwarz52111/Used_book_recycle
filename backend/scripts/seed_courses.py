"""灌入示例课程教材表（专业 + 学期 → 课程 + 教材 ISBN）。

用法（在 backend 目录）：
    python -m scripts.seed_courses

ISBN 对应 init_db / seed_demo 里已存在的书目，便于教材推荐能命中在库书。
幂等：已有课程数据则跳过。
"""

from __future__ import annotations

from sqlalchemy import select

from app.db import Base, get_engine, get_sessionmaker
from app.models import CourseTextbook

# major, semester, course_name, isbn
COURSES = [
    ("计算机", 1, "算法设计与分析", "9787111407010"),   # 算法导论
    ("计算机", 1, "计算机系统基础", "9787111213826"),   # 深入理解计算机系统
    ("计算机", 1, "高等数学", "9787040396638"),         # 高等数学（上册）
    ("计算机", 2, "Python程序设计", "9787115546081"),   # 流畅的Python
    ("计算机", 2, "线性代数", "9787121401571"),         # 线性代数
    ("计算机", 2, "大学英语", "9787513598200"),         # 新概念英语2
]


def main() -> None:
    Base.metadata.create_all(get_engine())
    db = get_sessionmaker()()
    try:
        if db.scalar(select(CourseTextbook.id).limit(1)):
            print("课程教材数据已存在，跳过。")
            return
        for major, sem, course, isbn in COURSES:
            db.add(CourseTextbook(major=major, semester=sem, course_name=course, isbn=isbn))
        db.commit()
        print(f"✅ 已写入 {len(COURSES)} 条课程教材（专业「计算机」第 1/2 学期）。")
        print("   测试：给某 openid 设档案 major=计算机 semester=1，再看 /recommend/textbooks。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
