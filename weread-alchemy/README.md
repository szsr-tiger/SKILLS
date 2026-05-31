# WeRead Alchemy — 微信读书炼金术

> 导出微信读书个人笔记，五维质量评分，与热门划线/书评对比分析，提炼心智模式，识别独特发现，提出改进提升方向，生成读书笔记总结与反思报告。

## 设计理念

读书做笔记是与作者的**交互**。但交互只是流动的感悟，**反思**才是沉淀后的洞察，**转化**才是洞察后的行动指南。**交互必须反思转化。**

```
交互（获取 & 整理） → 反思（对比 & 提炼） → 转化（行动 & 追踪）
```

## 功能

- 📡 **一键导出**：Python 脚本批量拉取，并行获取，数据落盘
- 📊 **五维评分**：方法论、批判性、创新性、审美性、行动性，2–5 分制，每档有锚定标准。由 LLM/agent 按评分标准逐条打分，并进行低分补偿
- 🔍 **对比分析**：你的笔记 vs 大众热门划线/书评，含量化指标（章节集中度、主题中心度、偏离度）
- 🧠 **心智模式提炼**：从笔记中归纳可迁移规则（至少 5 条）
- 💡 **独特发现**：识别阅读视角和思维模式
- 🎯 **提升方向**：针对性改进建议
- 📈 **跨书对比**：追踪读物品味和笔记质量的演变
- ✨ **审美评价**：不仅考察对书籍文笔的鉴赏力，也评估笔记本身文字的优美程度

## 快速开始

### 1. 环境准备

```bash
# 安装依赖
pip install requests jieba

# 设置 API 密钥
export WEREAD_API_KEY="wrk-xxxxx"
```

### 2. 分析一本书

```bash
# 第一步：拉取数据
python scripts/fetch_book_data.py --book-name "基因之河"

# 第二步：算指标（Agent 评分 + 量化指标）
# 少量想法：管道传入    大量想法：--scores 文件传入（避免命令行长度限制）
echo '{"<reviewId>":{"方法论":3,...}}' | python scripts/compute_quality.py data/books/{bookId}/raw_data.json
# 或：python scripts/compute_quality.py data/books/{bookId}/raw_data.json --scores scores_temp.json

# 第三步：建骨架（读取 notes_scored.json，模板填入，零文本匹配）
python scripts/generate_skeleton.py data/books/{bookId}

# 第四步：填写报告（Agent 输出分析 JSON，脚本替换骨架 {TODO}）
python scripts/fill_report.py data/books/{bookId}/skeleton.md --analysis analysis_temp.json
```

### 3. 报告输出

最终报告保存在 `output/` 目录下，文件名为 `《书名》微信读书笔记总结与反思.md`，包含七个章节：
1. 笔记与划线清单（按章节混排 + 原文对照 + 五维质量评分 + 雷达图）
2. 你的笔记 vs 大众热门笔记（量化对比：偏离度、章节熵、主题词频）
3. 心智模式（可迁移规则）
4. 独特发现（阅读模式洞察）
5. 努力提升的方向
6. 跨书对比（多书横向比较，自动生成）
7. 一句话总结

## 目录结构

```
weread-alchemy/
├── SKILL.md                          # Skill 主文件
├── README.md                         # 本文件
├── LICENSE                           # MIT License
├── .gitignore
├── scripts/
│   ├── fetch_book_data.py            # ① 数据批量获取（含笔记划线混排）
│   ├── compute_quality.py            # ② 评分组装（Agent 管道传入 → notes_scored.json）
│   ├── generate_skeleton.py          # ③ 报告骨架（读取 notes_scored.json，模板填入）
│   ├── fill_report.py                # ④ 报告填写（读取骨架+分析JSON，替换TODO）
│   └── compute_metrics.py            # 🔧 独立工具（量化指标调试，流水线不调用）
├── references/
│   ├── quality-rubric.md             # 五维度质量评分标准（含审美双层评分）
│   └── report-template.md            # 输出报告格式模板
├── output/                           # 最终分析报告
│   └── 《书名》微信读书笔记总结与反思.md
└── data/                             # 中间数据（不提交）
    ├── book_catalog.json             # 跨书对比目录
    └── books/
        └── {bookId}/
            ├── raw_data.json         # API 原始数据 + 混排列表
            ├── notes_scored.json     # 每条笔记的五维质量分（结构化JSON）
            └── skeleton.md           # 报告骨架（中间产物）
```

## 依赖

- **Python 3.8+** + `requests` + `jieba` 库
- **微信读书 API 密钥**（`WEREAD_API_KEY` 环境变量）
- **AI Agent**（Claude 等）用于评分、分析和报告生成

## 评分体系

五维度 2–5 分制，最低 2 分，低于 3 分自动补偿 0.5 分（3 分为限）。详见 [`references/quality-rubric.md`](references/quality-rubric.md)。

| 维度 | 考察什么（双重含义） |
|------|---------------------|
| 方法论 | 是否提炼了可复用的思维工具 |
| 批判性 | 是否质疑、反驳或提出替代观点 |
| 创新性 | 是否产生超出原文的新观点 |
| **审美性** | **对书：**是否关注文本的文学品质？**对己：**笔记本身文字是否优美？ |
| 行动性 | 是否转化为具体的行动意图 | 
💡 审美性评分采用"双层取高"原则：取"对书的审美分析"和"笔记本身的文字美"两个层面中的较高分，两方面都突出可给满分。

## 数据来源

所有数据来源于微信读书 API。

## License

MIT © Fengye, ltishere
