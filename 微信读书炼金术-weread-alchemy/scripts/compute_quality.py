#!/usr/bin/env python3
"""
质量评分工具 — Compute Quality Scores

用法一（Agent 直接写入）：
    内置 scores 字典后运行，将评分写入 notes_scored.json。

用法二（命令行传入 JSON 文件）：
    python compute_quality.py data/books/{bookId}/raw_data.json --scores my_scores.json

scores.json 格式:
    {"<reviewId>": {"方法论":3,"批判性":2,"创新性":4,"审美性":2,"行动性":2}, ...}

输出: notes_scored.json（标准结构，generate_skeleton.py 直接使用）
"""

import json, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKILL_ROOT = Path(__file__).resolve().parent.parent
TZ = timezone(timedelta(hours=8))  # 时区（微信读书服务器时区，可按需修改）
DIMS = ["方法论", "批判性", "创新性", "审美性", "行动性"]


def validate(scores: dict) -> dict:
    """校验并规范化为 2–5 范围，保留一位小数，缺失维度默认补 2。低于 3 分则加 0.5（以 3 分为限）。"""
    result = {}
    for d in DIMS:
        if d not in scores:
            print(f"  ⚠ 维度 {d} 缺失，补默认值 2", file=sys.stderr)
        v = max(2.0, min(5.0, round(float(scores.get(d, 2)), 1)))
        if v < 3.0:
            v = min(3.0, v + 0.5)
        result[d] = v
    return result


def build_notes_scored(raw_path: Path, scores: dict[str, dict]) -> dict:
    """从 raw_data.json + Agent 评分构建 notes_scored.json。"""
    with open(raw_path, encoding="utf-8") as f:
        data = json.load(f)

    book_name = data["metadata"]["book_name"]
    book_id = data["metadata"]["book_id"]
    interleaved = data.get("interleaved", [])
    chapters = data.get("chapters", [])
    ch_map = {c["chapterUid"]: c.get("title", "") for c in chapters}

    items = []
    agg_q = {d: [] for d in DIMS}

    for item in interleaved:
        entry = {
            "seq": item["seq"],
            "type": item["type"],
            "chapterUid": item.get("chapterUid"),
            "chapterTitle": item.get("chapterTitle") or ch_map.get(item.get("chapterUid"), ""),
            "createTime": item.get("createTime", ""),
        }
        if item["type"] == "bookmark":
            entry["text"] = item.get("text", "")
            entry["range"] = item.get("range", "")
        else:
            rid = item.get("reviewId", "")
            entry["abstract"] = item.get("abstract", "")
            entry["content"] = item.get("content", "")
            entry["likesCount"] = item.get("likesCount", 0) or 0
            entry["commentsCount"] = item.get("commentsCount", 0) or 0
            entry["comments"] = item.get("comments", [])
            q = validate(scores.get(rid, {}))
            entry["quality"] = q
            entry["quality_avg"] = round(sum(q.values()) / 5, 2)
            for d in DIMS:
                agg_q[d].append(q[d])
        items.append(entry)

    # 全书点评
    scored_reviews = []
    for r in data.get("book_reviews", []):
        rid = r.get("reviewId", "")
        q = validate(scores.get(rid, {}))
        sr = {
            "reviewId": rid,
            "content": r.get("content", ""),
            "likesCount": r.get("likesCount", 0) or 0,
            "commentsCount": r.get("commentsCount", 0) or 0,
            "createTime": r.get("createTime", ""),
            "star": r.get("star"),
            "quality": q,
            "quality_avg": round(sum(q.values()) / 5, 2),
        }
        scored_reviews.append(sr)
        for d in DIMS:
            agg_q[d].append(q[d])

    aggregates = {d: round(sum(v) / len(v), 2) for d, v in agg_q.items() if v}
    overall = round(sum(aggregates.values()) / 5, 2) if aggregates else 0

    # 量化指标（偏离度、熵、主题词、笔记密度）
    # 延迟导入：避免 --help 等无需度量的场景强制依赖 jieba
    from compute_metrics import compute_chapter_entropy, compute_topic_centrality, compute_deviation, compute_note_density
    thoughts_texts = [t.get("content","") for t in data.get("thoughts",[])]
    public_texts  = [h.get("text","") for h in data.get("hot_underlines",[])]
    reading_hours = (data.get("reading",{}).get("reading_time_sec",0) or 0) / 3600
    tc = len(data.get("thoughts",[]))
    bc = len(data.get("bookmarks",[]))
    metrics = {
        "chapter_concentration": compute_chapter_entropy(data.get("interleaved",[]), data.get("chapters",[])),
        "topic_centrality_my": compute_topic_centrality(thoughts_texts),
        "topic_centrality_public": compute_topic_centrality(public_texts),
        "deviation": compute_deviation(thoughts_texts, public_texts),
        "note_density": compute_note_density(reading_hours, tc, bc),
    }

    return {
        "book_id": book_id,
        "book_name": book_name,
        "computed_at": datetime.now(TZ).isoformat(),
        "scored_by": "agent",
        "items": items,
        "book_reviews": scored_reviews,
        "aggregates": aggregates,
        "overall": overall,
        "metrics": metrics,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="质量评分工具")
    parser.add_argument("raw_path", help="raw_data.json 路径")
    parser.add_argument("--scores", help="评分 JSON 文件路径（可选）")
    args = parser.parse_args()

    raw_path = Path(args.raw_path)
    if not raw_path.exists():
        print(f"File not found: {raw_path}"); sys.exit(1)

    # 加载评分：优先 --scores 文件，其次 stdin，最后默认全2
    if args.scores:
        scores_path = Path(args.scores)
        if not scores_path.exists():
            print(f"❌ 评分文件不存在: {scores_path}", file=sys.stderr)
            sys.exit(1)
        with open(scores_path, encoding="utf-8") as f:
            scores = json.load(f)
    elif not sys.stdin.isatty():
        raw = sys.stdin.read(2 * 1024 * 1024)  # 2MB 上限
        scores = json.loads(raw) if raw.strip() else {}
    else:
        print("用法: python compute_quality.py <raw_data.json> [--scores file.json]")
        print("  或: echo '{\"<reviewId>\":{...}}' | python compute_quality.py <raw_data.json>")
        print("  无输入时将使用默认全2分")
        scores = {}

    result = build_notes_scored(raw_path, scores)
    out_path = raw_path.parent / "notes_scored.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    n_scored = sum(1 for i in result["items"] if i["type"] == "thought")
    print(f"✅ {out_path}")
    print(f"   已评分: {n_scored} 条想法 + {len(result['book_reviews'])} 条书评")
    print(f"   综合: {result['overall']}")
    print(f"   五维: {result['aggregates']}")


if __name__ == "__main__":
    main()
