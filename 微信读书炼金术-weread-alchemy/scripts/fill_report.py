#!/usr/bin/env python3
"""
报告填写工具 — Fill Report TODOs

读取 skeleton.md + Agent 分析 JSON，自动替换 {TODO} 占位符，输出最终报告。

用法:
    python fill_report.py data/books/{bookId}/skeleton.md --analysis data/books/{bookId}/analysis_temp.json
    python fill_report.py data/books/{bookId}/skeleton.md --analysis analysis.json --output custom/path.md

分析 JSON 格式（所有字段可选，缺失则保留 TODO 原样）:
{
  "core_findings": "1. **发现1** ...\n2. **发现2** ...",
  "key_diffs_table": "| 维度 | ... |",
  "specific_comparisons": "例1 — ...",
  "review_comparison": "与你的书评的差异...",
  "contrast_insight": "一句话核心洞察...",
  "mental_models": "### **规则1**...",
  "unique_discoveries": "1. **发现1**...",
  "improvement_directions": "### **方向1**...",
  "one_sentence": "> 一句话总结..."
}
"""

import json
import sys
from pathlib import Path
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SKILL_ROOT = Path(__file__).resolve().parent.parent

# TODO 标记到 JSON key 的映射
TODO_MAP = [
    ("Agent — 基于评分分布提炼 3-5 条核心发现", "core_findings"),
    ("Agent — 五维+量化指标对比表格", "key_diffs_table"),
    ("Agent — 最多 5 段重合原文对比", "specific_comparisons"),
    ("Agent — 与你的书评的差异分析", "review_comparison"),
    ("Agent — 一句话核心洞察", "contrast_insight"),
    ("Agent — 心智模式（5+ 条可迁移规则）", "mental_models"),
    ("Agent — 独特发现（3+ 条）", "unique_discoveries"),
    ("Agent — 提升方向（3+ 条）", "improvement_directions"),
    ("Agent — 一句话总结", "one_sentence"),
    ("Agent — 趋势分析与读物品味演变洞察", "cross_book_insight"),
]


def fill_skeleton(skeleton_path: Path, analysis: dict, output_path: Path = None) -> Path:
    """读取骨架，替换 TODO，写入最终报告。"""
    with open(skeleton_path, encoding="utf-8") as f:
        skeleton = f.read()

    replaced = 0
    missing = 0

    for todo_desc, json_key in TODO_MAP:
        placeholder = "{TODO: " + todo_desc + "}"
        if placeholder in skeleton:
            content = analysis.get(json_key, "")
            if content:
                skeleton = skeleton.replace(placeholder, content)
                replaced += 1
            else:
                missing += 1
                print(f"  ⚠ 分析 JSON 缺少「{json_key}」，保留 TODO 原样", file=sys.stderr)

    if output_path is None:
        # Extract book name from skeleton title line: # 《书名》...
        first_line = skeleton.split("\n")[0]
        book_name = first_line.replace("# 《", "").replace("》微信读书笔记总结与反思", "")
        if not book_name or book_name == first_line:
            book_name = "未知书名"
        output_path = SKILL_ROOT / "output" / f"《{book_name}》微信读书笔记总结与反思.md"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(skeleton)

    print(f"✅ 最终报告已保存至: {output_path}")
    print(f"   已替换: {replaced} 个 TODO")
    if missing:
        print(f"   未替换: {missing} 个 TODO（JSON 中缺少对应字段）")
    return output_path


def main():
    import argparse
    parser = argparse.ArgumentParser(description="报告填写工具 — 替换骨架 {TODO} 生成最终报告")
    parser.add_argument("skeleton_path", help="skeleton.md 路径")
    parser.add_argument("--analysis", help="Agent 分析 JSON 文件路径")
    parser.add_argument("-o", "--output", help="输出路径（默认: output/《书名》...md）")
    args = parser.parse_args()

    skel_path = Path(args.skeleton_path)
    if not skel_path.exists():
        print(f"❌ skeleton.md 不存在: {skel_path}", file=sys.stderr)
        sys.exit(1)

    # 加载分析 JSON：优先 --analysis 文件，其次 stdin
    if args.analysis:
        with open(args.analysis, encoding="utf-8") as f:
            analysis = json.load(f)
    elif not sys.stdin.isatty():
        analysis = json.load(sys.stdin)
    else:
        print("用法: python fill_report.py <skeleton.md> [--analysis file.json]", file=sys.stderr)
        print("  或: cat analysis.json | python fill_report.py <skeleton.md>", file=sys.stderr)
        sys.exit(1)

    out = Path(args.output) if args.output else None
    fill_skeleton(skel_path, analysis, out)


if __name__ == "__main__":
    main()
