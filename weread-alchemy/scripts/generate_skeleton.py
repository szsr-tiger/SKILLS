#!/usr/bin/env python3
"""
报告骨架生成 — Report Skeleton Generator

读取 raw_data.json + metrics.json + book_catalog.json，
预填所有结构化数据，生成报告骨架。Agent 只需填写分析性章节。

用法:
    python generate_skeleton.py data/books/3300128993/

输出:
    data/books/{bookId}/ 目录下生成 skeleton.md（报告骨架，中间产物），包含:
    - ✅ 头部卡片
    - ✅ 一、笔记与划线清单（混排 + 全书点评）
    - ✅ 二、大众热门划线 TOP20 表格
    - ✅ 二、热门书评 TOP10 列表
    - 🔲 核心发现（TODO）
    - 🔲 雷达图（TODO）
    - 🔲 关键差异对比（TODO）
    - 🔲 对比洞察（TODO）
    - 🔲 三~七章（TODO）
    - ✅ 六、跨书对比表格（从 book_catalog.json）
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SKILL_ROOT = Path(__file__).resolve().parent.parent
TZ = timezone(timedelta(hours=8))  # 时区（微信读书服务器时区，可按需修改）

# 骨架报告中跳过的章节关键词（封面、版权页等不含实质内容的页面）
_SKIP_CHAPTER_KEYWORDS = [
    "封面", "版权", "献词", "目录", "序言", "前言", "扉页", "出版信息",
    "Cover", "Copyright", "Title Page", "Preface",
]


def _category_key(book: dict) -> str:
    """提取书籍的大类：category 字段第一个 '-' 之前的部分，缺失时返回空字符串。"""
    cat = (book.get("category") or "").strip()
    return cat.split("-")[0] if cat else ""


def _star_label(star):
    if star is None:
        return "未评"
    s = int(star)
    if s == 100:
        return "推荐"
    elif s == 60:
        return "一般"
    elif s == 20:
        return "不行"
    return str(s)


def _rating_to_10(rating_1000):
    """千分制 → 十分制"""
    if not rating_1000:
        return "暂无"
    return f"{rating_1000 / 100:.2f}"


def generate_header(data: dict) -> str:
    bi = data.get("book_info", {}) or {}
    rd = data.get("reading", {}) or {}
    cnt = data.get("counts", {}) or {}
    meta = data.get("metadata", {}) or {}

    lines = []
    lines.append(f"# 《{meta.get('book_name', '未知')}》微信读书笔记总结与反思")
    lines.append("")
    lines.append("📖 **书籍信息**")
    author = bi.get("author", "未知")
    translator = bi.get("translator", "")
    t_info = f"　|　译者：{translator}" if translator else ""
    lines.append(f"作者：{author}{t_info}　|　分类：{bi.get('category', '未知')}")
    lines.append(f"出版社：{bi.get('publisher', '未知')}　|　出版时间：{bi.get('publishTime', '未知')[:10]}")
    lines.append("")
    lines.append("⭐ **评分口碑**")
    rating = _rating_to_10(bi.get("newRating"))
    rating_count = bi.get("newRatingCount", 0)
    tag = (bi.get("newRatingDetail") or {}).get("title", "")
    lines.append(f"评分：{rating}/10　|　{rating_count}人评价　|　标签：{tag}")
    lines.append("")
    lines.append("📅 **阅读档案**")
    start = rd.get("start_date", "?")
    end = rd.get("finish_date", "进行中")
    lines.append(f"阅读周期：{start} → {end}")
    lines.append(f"累计阅读 {rd.get('reading_days', 0)}天 / {rd.get('reading_time_display', '0分钟')}")
    lines.append(f"笔记统计：划线{cnt.get('underline_count', 0)}条　|　"
                 f"想法{cnt.get('thought_count', 0)}条　|　"
                 f"全书点评{cnt.get('book_review_count', 0)}条")
    lines.append("")
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    lines.append(f"📄 报告生成日期：{today}")
    lines.append("")
    lines.append("---")
    return "\n".join(lines)


def _notes_line(item: dict, book_id: str = "") -> str:
    """单条笔记/划线 → Markdown 文本（纯模板填入，零文本匹配）。"""
    lines = []
    seq = item["seq"]

    if item["type"] == "bookmark":
        text = item.get("text", "")
        lines.append(f"**{seq}.** 划线：「{text}」")
        if item.get("createTime"):
            lines.append(f"    划线时间：{item['createTime']}")
        # 深度链接
        rng = item.get("range", "")
        if rng:
            parts_range = rng.split("-")
            rs = parts_range[0] if len(parts_range) > 0 else ""
            re_ = parts_range[1] if len(parts_range) > 1 else rs
            lines.append(f"    [📖 跳转原文](weread://bestbookmark?bookId={book_id}&chapterUid={item.get('chapterUid','')}&rangeStart={rs}&rangeEnd={re_})")
    else:
        lines.append(f"**{seq}.** 原文：「{item.get('abstract', '')}」")
        lines.append(f"    想法：{item.get('content', '')}")
        parts = [
            f"写作时间：{item.get('createTime', '')}",
            f"点赞：{item.get('likesCount', 0)}",
            f"评论：{item.get('commentsCount', 0)}",
        ]
        lines.append("    " + "　|　".join(parts))
        # 质量评分（来自 notes_scored.json）
        avg = item.get("quality_avg")
        if avg is not None:
            lines.append(f"    质量：{avg}/5")
        # 评论
        for cm in item.get("comments", []) or []:
            lines.append(f"    　评论：{cm.get('content', '')}")
            lines.append(f"    　评论者：{cm.get('author', '')}　|　"
                         f"时间：{cm.get('createTime', '')}　|　点赞：{cm.get('likesCount', 0)}")
    lines.append("")
    return "\n".join(lines)


def generate_interleaved_section(book_dir: Path, data: dict, scored: dict = None) -> str:
    """从 notes_scored.json（优先）或 raw_data.json 生成笔记与划线清单。"""
    if scored:
        items = scored.get("items", [])
        book_reviews = scored.get("book_reviews", [])
    else:
        items = data.get("interleaved", [])
        book_reviews = data.get("book_reviews", [])

    lines = []
    lines.append("## 一、笔记与划线清单")
    lines.append("")

    current_ch = None
    max_seq = 0
    for item in items:
        ch_title = item.get("chapterTitle", "")
        if any(w in ch_title for w in _SKIP_CHAPTER_KEYWORDS):
            ch_title_display = None
        else:
            ch_title_display = ch_title

        if ch_title_display and ch_title_display != current_ch:
            current_ch = ch_title_display
            lines.append(f"### {ch_title_display}")
            lines.append("")

        lines.append(_notes_line(item, data.get("metadata", {}).get("book_id", "")))
        max_seq = max(max_seq, item["seq"])

    # 全书点评
    if book_reviews:
        lines.append("### 全书点评")
        lines.append("")
        for r in book_reviews:
            max_seq += 1
            star = _star_label(r.get("star"))
            lines.append(f"**{max_seq}.** 点评：{r.get('content', '')}")
            lines.append(f"    读后认为：{star}")
            lines.append(f"    写作时间：{r.get('createTime', '')}　|　"
                         f"点赞：{r.get('likesCount', 0) or 0}　|　评论：{r.get('commentsCount', 0) or 0}")
            avg = r.get("quality_avg")
            if avg is not None:
                lines.append(f"    质量：{avg}/5")
            lines.append("")

    return "\n".join(lines)


def generate_hot_underlines_table(data: dict) -> str:
    """生成热门划线 TOP20 表格。"""
    hot = data.get("hot_underlines", [])
    lines = []
    lines.append("### （一）大众热门划线 TOP20")
    lines.append("")
    lines.append("| 排名 | 划线内容 | 人数 | 主题归类 |")
    lines.append("|------|---------|------|----------|")
    for i, hl in enumerate(hot[:20], 1):
        text = hl.get("text", "").replace("|", "｜")[:80]
        lines.append(f"| {i} | {text} | {hl.get('count', 0)}人 | {{TODO}} |")
    lines.append("")
    return "\n".join(lines)


def generate_public_reviews_section(data: dict) -> str:
    """生成热门书评 TOP10 列表。"""
    reviews = data.get("top_public_reviews", [])
    lines = []
    lines.append("### （二）大众热门点评 TOP10")
    lines.append("")
    for i, pr in enumerate(reviews, 1):
        author = pr.get("author", "匿名")
        time = pr.get("createTime", "")
        star = pr.get("star")
        star_display = _star_label(star)
        likes = pr.get("likesCount", 0)
        content = pr.get("content", "")[:200]
        lines.append(f"**{i}.** {author}，{time}，评价：{star_display}，点赞{likes}")
        lines.append(f"> {content}...")
        lines.append("")
    return "\n".join(lines)


def _select_books(book_id: str, catalog: dict) -> list:
    """选择跨书对比的书籍（最多5本）。

    规则：
    1. 优先同大类（category 第一个'-'之前的部分）
    2. 同大类 >= 2 本：只选同大类（≤5本）
    3. 同大类 < 2 本：选全部同大类，再按 analyzed_at 倒序补齐其他大类
    """
    all_books = catalog.get("books", [])
    if len(all_books) <= 1:
        return all_books

    # 找当前书的大类
    current = next((b for b in all_books if b["book_id"] == book_id), None)
    if not current:
        return all_books[:5]

    current_cat = _category_key(current)

    same_cat = [b for b in all_books if _category_key(b) == current_cat]
    other_cat = [b for b in all_books if _category_key(b) != current_cat]
    # 其他类别按 analyzed_at 倒序
    other_cat.sort(key=lambda b: b.get("analyzed_at", ""), reverse=True)

    if len(same_cat) >= 2:
        return same_cat[:5]
    else:
        return same_cat + other_cat[:5 - len(same_cat)]


def generate_cross_book_table(book_id: str) -> str:
    """从 book_catalog.json 生成跨书对比表格。"""
    catalog_path = SKILL_ROOT / "data" / "book_catalog.json"
    if not catalog_path.exists():
        return ""

    with open(catalog_path, encoding="utf-8") as f:
        catalog = json.load(f)

    books = _select_books(book_id, catalog)
    if len(books) <= 1:
        return ""

    lines = []
    lines.append("## 六、跨书对比")
    lines.append("")
    lines.append("| 维度 | " + " | ".join(f"《{b['title']}》" for b in books) + " |")
    lines.append("|------|" + "|".join("-----" for _ in books) + "|")

    # 严格按 report-template.md 顺序：
    # 阅读天数 → 阅读时长 → 笔记密度 → 划线/想法比 → 五维均分 → 综合评分

    # 阅读天数
    days = [str(b.get("summary", {}).get("reading_days", "?")) for b in books]
    lines.append("| 阅读天数 | " + " | ".join(days) + " |")

    # 阅读时长
    hours = [str(b.get("summary", {}).get("reading_hours") or "?") + "h" for b in books]
    lines.append("| 阅读时长 | " + " | ".join(hours) + " |")

    # 笔记密度
    densities = []
    for b in books:
        s = b.get("summary", {})
        tn = s.get("thought_count", 0) + s.get("underline_count", 0)
        rh = s.get("reading_hours", 0)
        d = round(tn / rh, 1) if rh else 0
        densities.append(str(d))
    lines.append("| 笔记密度（条/小时） | " + " | ".join(densities) + " |")

    # 划线/想法比
    ratios = []
    for b in books:
        s = b.get("summary", {})
        uc = s.get("underline_count", 0)
        tc = s.get("thought_count", 0)
        r = round(uc / tc, 1) if tc else 0
        ratios.append(str(r))
    lines.append("| 划线/想法比 | " + " | ".join(ratios) + " |")

    # 偏离度（余弦距离）—— 优先 catalog，兜底从 notes_scored.json 读取
    devs = []
    for b in books:
        dev = b.get("summary", {}).get("deviation")
        if dev is None or dev == "?":
            ns = SKILL_ROOT / "data" / "books" / b["book_id"] / "notes_scored.json"
            if ns.exists():
                with open(ns, encoding="utf-8") as f:
                    nsd = json.load(f)
                dev = nsd.get("metrics", {}).get("deviation", {}).get("cosine_distance", "?")
        devs.append(str(dev if dev is not None else "?"))
    lines.append("| 偏离度 | " + " | ".join(devs) + " |")

    # 章节集中度熵 —— 兜底逻辑同上
    ents = []
    for b in books:
        ent = b.get("summary", {}).get("chapter_entropy")
        if ent is None or ent == "?":
            ns = SKILL_ROOT / "data" / "books" / b["book_id"] / "notes_scored.json"
            if ns.exists():
                with open(ns, encoding="utf-8") as f:
                    nsd = json.load(f)
                ent = nsd.get("metrics", {}).get("chapter_concentration", {}).get("entropy", "?")
        ents.append(str(ent if ent is not None else "?"))
    lines.append("| 章节集中度熵 | " + " | ".join(ents) + " |")

    # 五维均分
    for dim in ["方法论", "批判性", "创新性", "审美性", "行动性"]:
        scores = []
        for b in books:
            s = b.get("summary", {}).get("quality_scores", {})
            scores.append(str(s.get(dim, "?")))
        lines.append(f"| {dim}均分 | " + " | ".join(scores) + " |")

    # 综合评分（模板用"综合评分"非"综合均分"）
    overalls = []
    for b in books:
        ov = b.get("summary", {}).get("overall_score", "?")
        overalls.append(str(ov))
    lines.append("| 综合评分 | " + " | ".join(overalls) + " |")

    lines.append("")
    lines.append("{TODO: Agent — 趋势分析与读物品味演变洞察}")
    lines.append("")
    lines.append("---")
    return "\n".join(lines)


def generate_skeleton(data_dir: Path) -> Path:
    """主函数：生成报告骨架。"""
    raw_path = data_dir / "raw_data.json"
    if not raw_path.exists():
        print(f"❌ raw_data.json 不存在: {raw_path}")
        sys.exit(1)

    with open(raw_path, encoding="utf-8") as f:
        data = json.load(f)

    book_name = data["metadata"]["book_name"]
    book_id = data["metadata"]["book_id"]

    # 从 notes_scored.json 读取量化指标和质量聚合（由 compute_quality.py 统一计算）
    scored_path = data_dir / "notes_scored.json"
    scored = {}
    if scored_path.exists():
        with open(scored_path, encoding="utf-8") as f:
            scored = json.load(f)
    metrics = scored.get("metrics", {})
    aggregates = scored.get("aggregates", {})

    parts = []

    # 头部卡片
    parts.append(generate_header(data))
    parts.append("")

    # 一、笔记与划线清单
    parts.append(generate_interleaved_section(data_dir, data, scored))

    # 笔记质量评价（自动生成：五维雷达表 + 柱形图）
    parts.append("### 笔记质量评价")
    parts.append("")
    if aggregates:
        dims = ["方法论", "批判性", "创新性", "审美性", "行动性"]
        parts.append("| 维度 | " + " | ".join(dims) + " | **综合** |")
        parts.append("|------|" + "|".join(["--------"] * (len(dims) + 1)) + "|")
        overall_str = str(scored.get("overall", "?"))
        parts.append("| 均分 | " + " | ".join(str(aggregates.get(d, "?")) for d in dims) + " | **" + overall_str + "** |")
        parts.append("")
        parts.append("```")
        for d in dims:
            s = aggregates.get(d, 0)
            n = min(20, int(s * 4))
            bar = chr(9608) * n + chr(9617) * (20 - n)
            parts.append(d + "  " + bar + "  " + str(s))
        parts.append("```")
    parts.append("")

    # 核心发现（TODO — Agent 基于评分分布提炼）
    parts.append("### 核心发现")
    parts.append("{TODO: Agent — 基于评分分布提炼 3-5 条核心发现}")
    parts.append("")
    parts.append("")
    parts.append("---")
    parts.append("")

    # 二、对比分析
    parts.append("## 二、你的笔记 vs 大众热门笔记")
    parts.append("")
    parts.append(generate_hot_underlines_table(data))

    if metrics:
        parts.append("### 量化指标速览")
        parts.append("")
        dev = metrics.get("deviation", {})
        parts.append(f"- 偏离度（余弦距离）: **{dev.get('cosine_distance', '?')}** "
                     f"（越接近 1 越独特）")
        nc = metrics.get("note_density", {})
        parts.append(f"- 笔记密度: **{nc.get('density', '?')} 条/小时**")
        ch = metrics.get("chapter_concentration", {})
        parts.append(f"- 章节集中度熵: **{ch.get('entropy', '?')}** "
                     f"（max={ch.get('max_entropy', '?')})")
        parts.append("")
        tc_my = metrics.get("topic_centrality_my", [])
        tc_pub = metrics.get("topic_centrality_public", [])
        if tc_my:
            parts.append(f"- 你的笔记主题词: {', '.join(w['word'] + '(' + str(w['count']) + ')' for w in tc_my[:8])}")
        if tc_pub:
            parts.append(f"- 大众划线主题词: {', '.join(w['word'] + '(' + str(w['count']) + ')' for w in tc_pub[:8])}")
        if metrics.get("deviation", {}).get("unique_to_me_top20"):
            uniq = metrics["deviation"]["unique_to_me_top20"][:8]
            parts.append(f"- 你的独特词汇: {', '.join(w['word'] for w in uniq)}")
        parts.append("")

    # 关键差异对比（TODO）
    parts.append("### 关键差异对比")
    parts.append("{TODO: Agent — 五维+量化指标对比表格}")
    parts.append("")
    parts.append("### 具体对比示例")
    parts.append("{TODO: Agent — 最多 5 段重合原文对比}")
    parts.append("")

    parts.append(generate_public_reviews_section(data))
    parts.append("{TODO: Agent — 与你的书评的差异分析}")
    parts.append("")

    parts.append("### （三）对比洞察")
    parts.append("{TODO: Agent — 一句话核心洞察}")
    parts.append("")
    parts.append("---")
    parts.append("")

    # 三~五（TODO — 各章独立标记，防止泛型替换误伤）
    section_todos = {
        "三、你的心智模式": "心智模式（5+ 条可迁移规则）",
        "四、你最独特的发现": "独特发现（3+ 条）",
        "五、努力提升的方向": "提升方向（3+ 条）",
    }
    for title, desc in section_todos.items():
        parts.append(f"## {title}")
        parts.append(f"{{TODO: Agent — {desc}}}")
        parts.append("")
        parts.append("---")
        parts.append("")

    # 六、跨书对比
    cross = generate_cross_book_table(book_id)
    if cross:
        parts.append(cross)
    else:
        parts.append("## 六、跨书对比")
        parts.append("")
        parts.append("> 这是本 skill 分析的第一本书。暂无其他书籍可供跨书对比。")
        parts.append("")
        parts.append("---")

    parts.append("")
    parts.append("## 七、一句话总结")
    parts.append("{TODO: Agent — 一句话总结}")
    parts.append("")
    parts.append("---")
    parts.append("")
    parts.append("*本文档由 weread-alchemy skill 自动生成。"
                 "数据全部来自微信读书 API。因系 AI 智能生成，仅供参考。*")

    skeleton = "\n".join(parts)
    # 骨架存到 data/ 目录（中间产物），最终报告由 Agent 写入 output/
    out_path = data_dir / "skeleton.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(skeleton)

    print(f"✅ 报告骨架已保存至: {out_path}")
    return out_path


def main():
    if len(sys.argv) < 2:
        print("用法: python generate_skeleton.py <书籍数据目录>")
        print("示例: python generate_skeleton.py data/books/3300128993/")
        sys.exit(1)

    data_dir = Path(sys.argv[1]).resolve()
    if not str(data_dir).startswith(str(SKILL_ROOT.resolve())):
        print(f"路径必须在 skill 目录内: {data_dir}", file=sys.stderr)
        sys.exit(1)
    generate_skeleton(data_dir)


if __name__ == "__main__":
    main()
