#!/usr/bin/env python3
"""
量化指标计算 — Compute Metrics for WeRead Notes

读取 raw_data.json，计算对比分析所需的量化指标，输出 metrics.json。

用法（独立调试）:
    python compute_metrics.py <raw_data.json路径>
    python compute_metrics.py data/books/3300128993/raw_data.json

注意：标准流水线中本脚本不直接调用。量化指标由 compute_quality.py 在组装
notes_scored.json 时内嵌计算，metrics.json 仅供调试和手动检查使用。

输出:
    同级目录下生成 metrics.json，包含:
    - chapter_concentration: 章节集中度（熵值）
    - topic_centrality: 个人笔记主题词频 TOP10
    - public_topic_centrality: 大众热门划线主题词频 TOP10
    - deviation_score: 偏离度（余弦距离）
    - note_density: 笔记密度（条/小时）
    - time_curve: 按日统计的笔记数量与平均长度
"""

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# 中文分词 — 基于 jieba 词性标注，只保留名词
# ---------------------------------------------------------------------------

import jieba.posseg as pseg

# jieba 词性标签中定义为「名词」的标签集合
_NOUN_TAGS = {"n",     # 名词
              "nr",    # 人名
              "ns",    # 地名
              "nt",    # 机构名
              "nz",    # 其他专名
              "ng",    # 名词性语素
              }


def tokenize(text: str) -> list[str]:
    """用 jieba 词性标注分词，只保留名词（标签 n/nr/ns/nt/nz/ng）。"""
    tokens = []
    for word, flag in pseg.cut(text):
        if flag in _NOUN_TAGS and len(word) >= 2:
            tokens.append(word)
    return tokens


def compute_chapter_entropy(items: list, chapters: list) -> dict:
    """计算笔记在章节间的分布熵。"""
    ch_counter = Counter()
    for item in items:
        ch_uid = item.get("chapterUid")
        ch_counter[ch_uid] += 1

    total = sum(ch_counter.values())
    if total == 0:
        return {"entropy": 0, "chapter_count": 0, "total_items": 0, "distribution": []}

    entropy = 0
    for count in ch_counter.values():
        p = count / total
        entropy -= p * math.log2(p)

    # 按章节排序输出分布
    ch_map = {c["chapterUid"]: c.get("title", "") for c in chapters}
    distribution = sorted(
        [{"chapterUid": uid, "title": ch_map.get(uid, ""), "count": cnt, "ratio": round(cnt / total, 3)}
         for uid, cnt in ch_counter.items()],
        key=lambda x: x["count"], reverse=True,
    )

    return {
        "entropy": round(entropy, 3),
        "max_entropy": round(math.log2(len(ch_counter)), 3),
        "chapter_count_with_notes": len(ch_counter),
        "total_items": total,
        "distribution": distribution[:10],  # top 10 chapters
    }


def compute_topic_centrality(texts: list[str], top_n: int = 10) -> list[dict]:
    """计算主题词频（tokenize 已过滤停用词）。"""
    all_tokens = []
    for text in texts:
        all_tokens.extend(tokenize(text))
    counter = Counter(all_tokens)
    return [{"word": w, "count": c} for w, c in counter.most_common(top_n)]


def compute_deviation(my_texts: list[str], public_texts: list[str]) -> dict:
    """计算个人笔记与大众热门划线的主题偏离度（余弦距离）。"""
    my_tokens = []
    for t in my_texts:
        my_tokens.extend(tokenize(t))
    public_tokens = []
    for t in public_texts:
        public_tokens.extend(tokenize(t))

    my_freq = Counter(my_tokens)
    pub_freq = Counter(public_tokens)

    # 取并集词汇
    all_words = set(my_freq.keys()) | set(pub_freq.keys())

    # 构建向量
    vec_my = [my_freq.get(w, 0) for w in all_words]
    vec_pub = [pub_freq.get(w, 0) for w in all_words]

    # 余弦相似度
    dot = sum(a * b for a, b in zip(vec_my, vec_pub))
    norm_my = math.sqrt(sum(a * a for a in vec_my))
    norm_pub = math.sqrt(sum(b * b for b in vec_pub))

    if norm_my == 0 or norm_pub == 0:
        cosine_sim = 0
    else:
        cosine_sim = round(dot / (norm_my * norm_pub), 4)

    cosine_dist = round(1 - cosine_sim, 4)

    # 我的独特词汇（仅出现在我的笔记中，不在大众中的高频词）
    unique_to_me = sorted(
        [(w, my_freq[w]) for w in my_freq if w not in pub_freq and my_freq[w] >= 2],
        key=lambda x: x[1], reverse=True,
    )[:20]

    return {
        "cosine_similarity": cosine_sim,
        "cosine_distance": cosine_dist,
        "vocab_size_my": len(my_freq),
        "vocab_size_public": len(pub_freq),
        "shared_vocab": len(set(my_freq.keys()) & set(pub_freq.keys())),
        "unique_to_me_top20": [{"word": w, "count": c} for w, c in unique_to_me],
    }


def compute_note_density(reading_hours: float, thought_count: int,
                          bookmark_count: int) -> dict:
    """笔记密度：条/小时。"""
    total = thought_count + bookmark_count
    if reading_hours <= 0:
        return {"total_notes": total, "reading_hours": reading_hours, "density": 0}
    return {
        "total_notes": total,
        "reading_hours": round(reading_hours, 1),
        "density": round(total / reading_hours, 1),
    }


def compute_time_curve(items: list) -> list[dict]:
    """按日统计笔记数量与平均长度（内容字符数）。"""
    daily = {}
    for item in items:
        raw_date = item.get("createTime") or ""
        date = raw_date[:10] if raw_date else ""
        if not date:
            continue
        if date not in daily:
            daily[date] = {"count": 0, "total_len": 0}
        content = item.get("content") or item.get("text") or ""
        daily[date]["count"] += 1
        daily[date]["total_len"] += len(content)

    result = []
    for date in sorted(daily.keys()):
        d = daily[date]
        result.append({
            "date": date,
            "count": d["count"],
            "avg_length": round(d["total_len"] / d["count"], 1),
        })
    return result


def main():
    if len(sys.argv) < 2:
        print("用法: python compute_metrics.py <raw_data.json路径>")
        sys.exit(1)

    raw_path = Path(sys.argv[1])
    if not raw_path.exists():
        print(f"❌ 文件不存在: {raw_path}")
        sys.exit(1)

    with open(raw_path, encoding="utf-8") as f:
        data = json.load(f)

    thoughts = data.get("thoughts", [])
    bookmarks = data.get("bookmarks", [])
    interleaved = data.get("interleaved", [])
    chapters = data.get("chapters", [])
    hot_underlines = data.get("hot_underlines", [])
    reading = data.get("reading", {})

    # 文本集合
    my_texts = [t.get("content", "") for t in thoughts]
    public_texts = [h.get("text", "") for h in hot_underlines]

    metrics = {
        "book_id": data["metadata"]["book_id"],
        "book_name": data["metadata"]["book_name"],
        "computed_at": data["metadata"]["fetched_at"],
        "chapter_concentration": compute_chapter_entropy(interleaved, chapters),
        "topic_centrality_my": compute_topic_centrality(my_texts),
        "topic_centrality_public": compute_topic_centrality(public_texts),
        "deviation": compute_deviation(my_texts, public_texts),
        "note_density": compute_note_density(
            (reading.get("reading_time_sec", 0) or 0) / 3600,
            len(thoughts),
            len(bookmarks),
        ),
        "time_curve": compute_time_curve(interleaved),
    }

    out_path = raw_path.parent / "metrics.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print(f"✅ 指标已保存至: {out_path}")
    print(f"   章节集中度熵: {metrics['chapter_concentration']['entropy']} "
          f"(max={metrics['chapter_concentration']['max_entropy']})")
    print(f"   偏离度: {metrics['deviation']['cosine_distance']}")
    print(f"   笔记密度: {metrics['note_density']['density']} 条/小时")
    print(f"   时间跨度: {len(metrics['time_curve'])} 天")


if __name__ == "__main__":
    main()
