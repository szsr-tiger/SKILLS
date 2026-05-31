---
name: weread-alchemy
description: 微信读书笔记导出、反思与方法提升。触发词："导出微信读书笔记""总结微信读书笔记""微信读书反思""读书炼金""分析我的笔记"。
metadata:
  author: Fengye, ltishere
  version: 1.0.0
  requires: weread-skills (API), Python 3, requests, jieba
---

# WeRead Alchemy — 微信读书炼金术

从微信读书导出个人笔记（划线、想法/书评），并与大众热门划线和书评做对比分析，提炼心智模式和独特发现，指出努力方向，最终生成一份结构化的读书笔记总结与反思报告。

## 设计理念

读书做笔记是一个与作者的交互过程。笔记的交互只是流动的感悟，反思才是沉淀后的洞察，转化才是洞察后的行动指南。**交互必须反思转化。**

| 阶段 | 含义 | 对应步骤 |
|------|------|---------|
| **交互** | 获取数据、整理排列 | 第一步（拉数据）+ 第二步（算指标：Agent 评分 + 量化指标） |
| **反思** | 对比分析、提炼规律、发现模式 | 第三步（对比分析）+ 第四步（心智模式）+ 第五步（独特发现） |
| **转化** | 提出改进方向、跨书追踪、提炼洞察 | 第六步（提升方向）+ 第七步（跨书对比）+ 第八步（一句话总结） |

## 触发条件

用户提及以下关键词时触发此 skill：
- "导出微信读书笔记"
- "总结微信读书笔记"
- "微信读书反思"
- "读书炼金"
- "分析我的笔记"

## 依赖声明

- **必须安装**：Python 3 + `requests` + `jieba`（`pip install requests jieba`）
- **必须配置**：环境变量 `WEREAD_API_KEY`（微信读书 API 密钥，Bearer token 格式）
- **数据来源**：微信读书 API 网关（`https://i.weread.qq.com/api/agent/gateway`）

## 工作流程

> ⚠️ **铁律：五维质量评分之外的所有结构化数据必须由脚本生成，禁止手工撰写。**
> 五维质量评分由 Agent 按照 `quality-rubric.md` 逐条打分，通过管道传给脚本完成低分补偿和格式组装。其余一切（笔记清单、热门数据、量化指标、跨书表格）均由脚本产出。Agent 只填写 `{TODO}` 占位符对应的分析性章节。

**标准流水线（四条命令，顺序执行）**：

```bash
# 第一步：拉数据
python scripts/fetch_book_data.py --book-name "{书名}"

# 第二步：算指标（Agent 评分 + 量化指标）
# 想法≤20条用管道，>20条用文件模式（bash 命令行有长度上限）
echo '{"<reviewId>":{"方法论":3,...}}' | python scripts/compute_quality.py data/books/{bookId}/raw_data.json
# 或：python scripts/compute_quality.py data/books/{bookId}/raw_data.json --scores data/books/{bookId}/scores_temp.json

# 第三步：建骨架（读取 notes_scored.json，模板填入，零文本匹配）
python scripts/generate_skeleton.py data/books/{bookId}

# 第四步：填写报告（Agent 输出分析 JSON，脚本替换骨架中的 {TODO} 占位符）
python scripts/fill_report.py data/books/{bookId}/skeleton.md --analysis data/books/{bookId}/analysis_temp.json
```

**Agent 职责边界**：

| 由脚本生成（禁止 Agent 手工写） | 由 Agent 完成 |
|--------------------------------|--------------|
| 头部卡片（书籍信息、阅读档案） | 五维质量评分（参照 rubric，管道传给脚本） |
| 笔记与划线清单（混排，从 notes_scored.json 填入） | 核心发现（3–5 条） |
| 全书点评（含质量分，从 notes_scored.json 读取） | 笔记质量雷达图 |
| 大众热门划线 TOP20 表格 | 关键差异对比 + 具体对比示例 |
| 大众热门点评 TOP10 列表 | 对比洞察 |
| 量化指标速览（主题词、偏离度等） | 心智模式（5+ 条） |
| 跨书对比表格 | 独特发现（3+ 条） |
| 报告尾部声明 | 努力提升的方向（3+ 条） |
| | 一句话总结 |

**报告构建方式**：`generate_skeleton.py` 输出的 `skeleton.md` 是最终报告的基础。Agent 将分析内容（核心发现、心智模式、独特发现、提升方向、一句话总结等）整理为结构化 JSON，通过 `fill_report.py` 自动替换骨架中的 `{TODO}` 占位符并输出最终报告到 `output/`。禁止 Agent 手工拼接 Markdown 报告。

### 第一步：获取数据（脚本执行）

```bash
python scripts/fetch_book_data.py --book-name "{书名}"
```

**脚本功能**：
- 搜索书籍（多结果时交互选择）
- 并行获取：基本信息、章节目录、阅读进度、阅读统计、个人划线、个人想法、热门划线 TOP20、热门书评 TOP100
- 对评论数/点赞数 > 0 的想法，拉取详情（上限 20 条，按互动数降序优先）
- 自动整理：按章节排序、去重、时间戳格式化
- 保存至 `data/books/{bookId}/raw_data.json`
- 各 API 独立错误处理，单个失败不阻塞整体

**降级策略**：
| 接口失败 | 降级处理 |
|---------|---------|
| 章节目录 | 跳过按章节分组，改为按时间排序 |
| 热门划线 | 跳过对比分析章节，报告中注明"暂无热门划线数据" |
| 热门书评 | 跳过公开书评对比板块 |
| 个人划线/想法均空 | 生成简化报告（仅书籍信息 + 热门数据），提示"该书暂无个人笔记" |
| 想法详情 | 仅展示列表中的基础信息，省略评论详情 |

> 详细脚本说明见 `scripts/fetch_book_data.py` 的 docstring。

### 第二步：算指标（Agent 评分 + 量化指标）

Agent 参照 `references/quality-rubric.md` 对每条想法进行五维度（方法论、批判性、创新性、审美性、行动性）2–5 分评分，将评分 JSON 通过管道传给脚本。脚本同时完成低分补偿、质量聚合和量化指标（偏离度、章节集中度熵、主题词频、笔记密度）计算：

```bash
# 少量想法（≤20条）：管道直接传入
echo '{"<reviewId>":{"方法论":3,"批判性":2,...},...}' | python scripts/compute_quality.py data/books/{bookId}/raw_data.json

# 大量想法（>20条）：先写入 JSON 文件，再通过 --scores 传入
python scripts/compute_quality.py data/books/{bookId}/raw_data.json --scores data/books/{bookId}/scores_temp.json
```

产出 `data/books/{bookId}/notes_scored.json`，包含每条笔记的五维质量分、聚合统计和量化指标。

评分输出要求：
1. 逐条给出五维分数
2. 计算各维度均分 = 该书的维度评分
3. 五维均分 = 书籍笔记质量总分
4. 基于评分分布提炼 3–5 条核心发现
5. 绘制雷达图（优先 Mermaid，降级为表格）

### 第三步：对比分析

#### 3.1 大众热门划线 TOP20 vs 你的笔记
- 对大众划线进行主题归类统计
- 从五维度 + 三个量化指标（章节集中度、主题中心熵、偏离度）进行比较
- 选择最多 5 段重合原文，逐段对比（格式：大众划线/你的笔记/差异洞察）

#### 3.2 大众热门点评 TOP10 vs 你的书评
- 列出点赞数 TOP10 公开书评，逐条进行五维质量评分
- 与你的全书点评做对比分析

#### 3.3 对比洞察
- 一句话概括核心差异

### 第四步：心智模式提炼

从个人笔记中提炼 **至少 5 条可迁移规则**，每条包含：
- 笔记支撑（你自己的笔记摘录）
- 推导过程（为什么成立，因果分析）
- 适用场景（何时可用，不局限于原书领域）

### 第五步：独特发现

列出 **至少 3 条**阅读中表现出的独特视角或模式。方向参考：
- 笔记密度分布（哪些章节密集/空白）
- 反复使用的分析框架
- 批注风格特征（理性分析 vs 感性共鸣、质疑 vs 补充）
- 时间维度上的质量变化

### 第六步：提升方向

基于对比分析和质量评分，给出 **至少 3 个**努力提升的方向。覆盖：
- 视角问题、批判性、创新性、方法论提炼、行动转化

### 第七步：跨书对比（如有历史数据）

从 `data/book_catalog.json` 读取已分析过的其他书籍摘要，横向对比（不超过5本，优先选择同类别和最近读完的书）：

| 维度 | 当前书 | 书A | 书B | ... |
|------|--------|-----|-----|-----|
| 阅读天数/时长 | ... | ... | ... | ... |
| 笔记密度 | ... | ... | ... | ... |
| 划线/想法比 | ... | ... | ... | ... |
| 五维均分 | ... | ... | ... | ... |


如尚无其他已分析书籍，跳过此步并在报告中注明。

### 第八步：一句话总结

用一句话概括核心洞察。

## 输出格式

**严格按照 `references/report-template.md` 的模板结构生成最终报告。**

### 文件路径约定

| 类型 | 路径 | 说明 |
|------|------|------|
| 原始数据 | `data/books/{bookId}/raw_data.json` | `fetch_book_data.py` 拉取的 API 原始数据 + 混排列表 |
| 指标计算 | `data/books/{bookId}/notes_scored.json` | Agent 笔记质量评分 + 脚本低分补偿 + 脚本量化指标计算 + `compute_quality.py` 组装 |
| 报告骨架 | `data/books/{bookId}/skeleton.md` | `generate_skeleton.py` 输出（读取 notes_scored.json，模板填入，中间产物） |
| 分析输入 | `data/books/{bookId}/analysis_temp.json` | Agent 输出的分析内容 JSON，供 `fill_report.py` 消费（流水线结束后可删除） |
| **最终报告** | **`output/《书名》微信读书笔记总结与反思.md`** | `fill_report.py` 替换骨架 `{TODO}` 后输出 |
| 跨书目录 | `data/book_catalog.json` | 所有已分析书籍的摘要索引 |

> **数据清零**：如需重置至发布前初始状态，仅删除以下文件（保留 `raw_data.json` 避免重复拉取 API）：`data/book_catalog.json` 中 `books` 数组置为 `[]`，删除 `data/books/*/notes_scored.json`、`data/books/*/skeleton.md`、`output/*.md`。**不要删除 `raw_data.json` 和 `scores_temp.json`**。

报告包含七个章节：
1. 笔记与划线清单（按章节混排 + 原文对照 + 质量评分 + 雷达图）
2. 你的笔记 vs 大众热门笔记（对比分析 + 量化指标速览）
3. 你的心智模式（至少 5 条可迁移规则）
4. 你最独特的发现（至少 3 条）
5. 努力提升的方向（至少 3 个方向）
6. 跨书对比（如有历史数据，由骨架自动生成表格）
7. 一句话总结

### 分析完成后的数据保存

每次分析完成后，Agent **必须**：
1. 将完整报告保存到 `output/《书名》微信读书笔记总结与反思.md`
2. 更新 `data/book_catalog.json`：
   - 若该书未分析过，追加新条目
   - 若已分析过，更新 `analyzed_at` 和 `summary` 字段
   - `summary` 包含：五维均分、划线数、想法数、阅读天数/时长、top 发现、心智模式列表、一句话总结等

## 通用规则

1. **脚本优先，强制流水线**：结构化数据（笔记清单、热门数据、跨书表格、量化指标）必须由脚本生成，禁止 Agent 手工撰写。质量评分由 Agent 参照 rubric 逐条给出，通过管道或 `--scores` 文件传给 `compute_quality.py` 统一完成低分补偿、质量聚合和量化指标计算。分析性章节（核心发现、心智模式等）由 Agent 以 JSON 格式输出，通过 `fill_report.py` 自动填入骨架。每次分析必须严格按四条命令顺序执行。禁止 Agent 手工拼接 Markdown 报告或编写临时脚本。
2. **评分标准**：Agent 笔记质量评分前必须阅读 `references/quality-rubric.md`，严格按五维度 2–5 分制逐维打分。`compute_quality.py` 自动对低于 3 分的维度加 0.5 分（以 3 分为上限）。评分结果通过管道传给脚本（不得手工写入 Markdown）。
3. **输出模板**：生成报告前须先阅读 `references/report-template.md`，严格按模板结构输出。
4. **上下文衔接**：记住脚本输出的 `bookId` 和数据路径，后续分析无需用户重复提供。
5. **隐私保护**：用户笔记内容和相关API KEY均属于个人隐私，仅向用户本人展示，不得泄露给第三方。
6. **降级优先**：任何数据缺失都不阻塞主流程，标记缺失并继续。
7. **API 版本上报**：脚本在 API 调用中自动注入 `skill_version: "1.0.3"`（微信读书 API 协议版本，用于定位微信读书 API 升级导致的兼容问题，非本 skill 自身版本）。
