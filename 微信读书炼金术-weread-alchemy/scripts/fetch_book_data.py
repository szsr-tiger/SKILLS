#!/usr/bin/env python3
"""
微信读书数据批量获取脚本 — WeRead Book Data Fetcher

从微信读书 API 批量获取一本书的全部笔记相关数据，保存为结构化 JSON，
供 weread-alchemy skill 后续分析使用。

用法:
    python fetch_book_data.py --book-name "基因之河"
    python fetch_book_data.py --book-id "26640213"
    python fetch_book_data.py --book-name "三体" --output-dir ./my_data

环境变量:
    WEREAD_API_KEY  微信读书 API 密钥（Bearer token），必填
"""

import os
import re
import sys
import json
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# Windows: 强制 UTF-8 输出，防止 emoji 和中文乱码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
API_BASE = "https://i.weread.qq.com/api/agent/gateway"
SKILL_VERSION = "1.0.3"
TZ = timezone(timedelta(hours=8))  # 时区（微信读书服务器时区，可按需修改）
REQUEST_TIMEOUT = 30  # 秒
MAX_REVIEW_DETAIL = 20  # 获取详情的想法数量上限
PUBLIC_REVIEW_COUNT = 100  # 公开书评拉取数量
PUBLIC_REVIEW_LIST_TYPE = 1  # 公开书评类型: 1=推荐(资深会员)

# 脚本所在目录的父目录即为 skill 根目录
SKILL_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# 客户端
# ---------------------------------------------------------------------------

class WeReadClient:
    """微信读书 API 网关客户端。"""

    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })

    def _call(self, api_name: str, **params) -> dict:
        """调用 API 网关，自动注入 skill_version。"""
        body = {"api_name": api_name, "skill_version": SKILL_VERSION, **params}
        resp = self.session.post(API_BASE, json=body, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    # -- 搜索 --
    def search(self, keyword: str, scope: int = 10, count: int = 15) -> dict:
        return self._call("/store/search", keyword=keyword, scope=scope, count=count)

    # -- 书籍信息 --
    def book_info(self, book_id: str) -> dict:
        return self._call("/book/info", bookId=book_id)

    def chapter_info(self, book_id: str) -> dict:
        return self._call("/book/chapterinfo", bookId=book_id)

    # -- 阅读进度 & 统计 --
    def get_progress(self, book_id: str) -> dict:
        return self._call("/book/getprogress", bookId=book_id)

    def read_data_detail(self, mode: str = "overall") -> dict:
        return self._call("/readdata/detail", mode=mode)

    # -- 个人笔记 --
    def bookmark_list(self, book_id: str) -> dict:
        return self._call("/book/bookmarklist", bookId=book_id)

    def review_list_mine(self, book_id: str, count: int = 200) -> dict:
        """拉取用户全部个人想法（单次调用，大 count 避免分页）。"""
        result = self._call(
            "/review/list/mine", bookid=book_id, count=count, synckey=0
        )
        return {"reviews": result.get("reviews", []),
                "totalCount": result.get("totalCount", 0)}

    def review_single(self, review_id: str) -> dict:
        return self._call("/review/single", reviewId=review_id)

    # -- 热门数据 --
    def best_bookmarks(self, book_id: str, chapter_uid: int = 0) -> dict:
        return self._call("/book/bestbookmarks", bookId=book_id, chapterUid=chapter_uid)

    def review_list(self, book_id: str, review_list_type: int = 0,
                    count: int = 100) -> dict:
        """分页拉取公开书评，返回合并后的列表。"""
        all_reviews = []
        max_idx = 0
        while len(all_reviews) < count:
            result = self._call(
                "/review/list",
                bookId=book_id,
                reviewListType=review_list_type,
                count=min(20, count - len(all_reviews)),
                maxIdx=max_idx,
            )
            reviews = result.get("reviews", [])
            if not reviews:
                break
            all_reviews.extend(reviews)
            if not result.get("reviewsHasMore") or len(all_reviews) >= count:
                break
            max_idx += len(reviews)
        return {"reviews": all_reviews[:count], "totalCount": result.get("reviewsCnt", 0)}

    # -- 笔记本概览 --
    def user_notebooks(self) -> dict:
        return self._call("/user/notebooks")


# ---------------------------------------------------------------------------
# 依赖检查
# ---------------------------------------------------------------------------

def check_dependencies():
    """前置检查：Python 版本、依赖包、API Key。失败打印提示并退出。"""
    if sys.version_info < (3, 8):
        print("❌ 需要 Python 3.8+", file=sys.stderr)
        sys.exit(1)
    try:
        import jieba  # noqa: F401
    except ImportError:
        print("❌ 缺少 jieba 库，请运行: pip install jieba", file=sys.stderr)
        sys.exit(1)
    api_key = os.environ.get("WEREAD_API_KEY", "").strip()
    if not api_key:
        print("❌ 环境变量 WEREAD_API_KEY 未设置。", file=sys.stderr)
        print("   请先设置: export WEREAD_API_KEY=wrk-xxxxx", file=sys.stderr)
        sys.exit(1)
    if not api_key.startswith("wrk-"):
        print("⚠️  WEREAD_API_KEY 格式异常（应以 wrk- 开头），继续尝试...", file=sys.stderr)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _flatten_search_results(results: list) -> list[dict]:
    """展平搜索结果为扁平书籍列表。

    微信读书搜索返回的结构是:
      results[].books[].bookInfo  (scope 分类 → 书籍列表 → 书籍详情)
    """
    flat = []
    for group in results:
        for book in (group.get("books") or []):
            info = book.get("bookInfo") or {}
            if info.get("bookId"):
                flat.append(info)
    return flat


def _pick_book_interactive(books: list[dict]) -> dict:
    """交互式让用户选择一本书。非 TTY 时自动选第一本。"""
    import sys as _sys

    for i, item in enumerate(books[:10], 1):
        title = item.get("title", "未知")
        author = item.get("author", "未知")
        bid = item.get("bookId", "")
        print(f"  [{i}] 《{title}》 — {author}  (bookId: {bid})")

    if not _sys.stdin.isatty():
        print("\n⚠️  非交互环境，自动选择第 1 本。")
        return books[0]

    print(f"  [0] 取消")
    try:
        choice = int(input("\n请输入序号: ").strip())
        if choice == 0:
            print("已取消。")
            _sys.exit(0)
        if choice < 1 or choice > min(len(books), 10):
            print("❌ 无效选择。", file=_sys.stderr)
            _sys.exit(1)
        return books[choice - 1]
    except (ValueError, EOFError):
        print("\n⚠️  无法读取输入，自动选择第 1 本。")
        return books[0]


# ---------------------------------------------------------------------------
# 数据获取编排
# ---------------------------------------------------------------------------

def _safe_call(fn, label: str, errors: list, **kwargs):
    """安全调用 API，失败时记录到 errors 而不中断整体流程。"""
    try:
        print(f"  ✓ {label} ...", end=" ", flush=True)
        result = fn(**kwargs)
        print("OK")
        return result
    except Exception as exc:
        print(f"FAILED ({exc})")
        errors.append({"api": label, "error": str(exc)})
        return None


def _unixtime_to_date(ts) -> Optional[str]:
    """Unix 时间戳（秒）→ YYYY-MM-DD 字符串。"""
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=TZ).strftime("%Y-%m-%d")
    except (ValueError, OSError):
        return str(ts)


def _collect_review_ids(reviews: list) -> list[str]:
    """收集 评论数>0 或 点赞数>0 的想法 ID，最多 MAX_REVIEW_DETAIL 条。"""
    candidates = [
        r for r in reviews
        if r.get("review", {}).get("commentsCount", 0) > 0
        or r.get("review", {}).get("likesCount", 0) > 0
    ]
    # 按互动数降序，取前 N
    candidates.sort(
        key=lambda r: (
            r.get("review", {}).get("likesCount", 0)
            + r.get("review", {}).get("commentsCount", 0) * 2
        ),
        reverse=True,
    )
    return [r.get("reviewId") for r in candidates[:MAX_REVIEW_DETAIL]]


def fetch_book_data(book_name: Optional[str] = None,
                    book_id: Optional[str] = None,
                    output_dir: Optional[Path] = None) -> Path:
    """
    主流程：搜索 → 选择 → 并行获取 → 整理 → 落盘。

    返回保存的 JSON 文件路径。
    """
    check_dependencies()
    api_key = os.environ.get("WEREAD_API_KEY", "").strip()

    client = WeReadClient(api_key)
    errors = []

    # ---- 1. 确定 bookId ----
    if not book_id:
        if not book_name:
            print("❌ 请提供 --book-name 或 --book-id", file=sys.stderr)
            sys.exit(1)

        print(f"🔍 搜索书籍: {book_name}")
        search_result = client.search(book_name, scope=10)
        raw_results = search_result.get("results") or []

        # 展平嵌套结构: results[].books[].bookInfo → 扁平列表
        books = _flatten_search_results(raw_results)

        if not books:
            print(f"❌ 未找到与「{book_name}」相关的电子书。", file=sys.stderr)
            sys.exit(1)

        if len(books) > 1:
            print(f"\n找到 {len(books)} 本书，请选择:")
            selected = _pick_book_interactive(books)
        else:
            selected = books[0]
            print(f"\n📖 唯一匹配: 《{selected.get('title', '?')}》 — {selected.get('author', '?')}")

        book_id = selected.get("bookId", "")
        raw_title = selected.get("title") or ""
        # 书名有效性校验：排除 None、空字符串、乱码（含不可打印控制字符）
        if not raw_title or not raw_title.strip() or any(ord(c) < 32 and c not in '\n\r\t' for c in raw_title):
            raw_title = book_name  # fallback：使用搜索关键词
        book_name = raw_title
        print(f"\n📖 已选择: 《{book_name}》 (bookId: {book_id})")

    # 安全校验：book_id 必须为纯数字
    if not re.match(r"^\d+$", book_id):
        print(f"❌ 无效的 bookId: {book_id}（必须为纯数字）", file=sys.stderr)
        sys.exit(1)

    # ---- 2. 并行获取数据 ----
    print("\n📡 开始获取数据...\n")

    # 第一阶段：基本信息（可并行）
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(client.book_info, book_id): "book_info",
            pool.submit(client.chapter_info, book_id): "chapter_info",
            pool.submit(client.get_progress, book_id): "get_progress",
            pool.submit(client.read_data_detail, "overall"): "read_data_detail",
        }
        stage1 = {}
        for fut in as_completed(futures):
            label = futures[fut]
            stage1[label] = _safe_call(lambda: fut.result(), label, errors)

    book_info = stage1.get("book_info", {})
    chapter_info = stage1.get("chapter_info", {})
    progress_data = stage1.get("get_progress", {})
    read_data = stage1.get("read_data_detail", {})

    # 第二阶段：笔记数据（可并行）
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(client.bookmark_list, book_id): "bookmark_list",
            pool.submit(client.review_list_mine, book_id): "review_list_mine",
            pool.submit(client.best_bookmarks, book_id): "best_bookmarks",
            pool.submit(client.review_list, book_id, PUBLIC_REVIEW_LIST_TYPE, PUBLIC_REVIEW_COUNT): "review_list",  # 推荐(资深会员)
        }
        stage2 = {}
        for fut in as_completed(futures):
            label = futures[fut]
            stage2[label] = _safe_call(lambda: fut.result(), label, errors)

    bookmark_data = stage2.get("bookmark_list", {})
    personal_reviews_wrapped = stage2.get("review_list_mine", {})
    best_bookmarks = stage2.get("best_bookmarks", {})
    public_reviews_wrapped = stage2.get("review_list", {})

    personal_reviews = personal_reviews_wrapped.get("reviews", []) if personal_reviews_wrapped else []
    public_reviews = public_reviews_wrapped.get("reviews", []) if public_reviews_wrapped else []

    # 第三阶段：热门想法详情（仅对有互动的想法）
    review_details = {}
    if personal_reviews:
        detail_ids = _collect_review_ids(personal_reviews)
        if detail_ids:
            print(f"\n📝 获取 {len(detail_ids)} 条想法详情...")
            with ThreadPoolExecutor(max_workers=5) as pool:
                fut_map = {
                    pool.submit(client.review_single, rid): rid
                    for rid in detail_ids
                }
                for fut in as_completed(fut_map):
                    rid = fut_map[fut]
                    review_details[rid] = _safe_call(
                        lambda: fut.result(), f"review_detail:{rid[:12]}...", errors
                    )

    # 第四阶段：笔记本概览（可选）
    notebook_data = _safe_call(
        lambda: client.user_notebooks(), "user_notebooks", errors
    )

    # ---- 3. 整理数据 ----
    print("\n📦 整理数据...")

    chapters = chapter_info.get("chapters", []) if chapter_info else []

    # 阅读统计（来自 getprogress）
    book_progress = (progress_data or {}).get("book", {}) if progress_data else {}
    reading_time_sec = book_progress.get("readingTime", 0) or 0
    progress_pct = book_progress.get("progress", 0) or 0
    start_reading_raw = book_progress.get("startReadingTime", 0) or 0
    finish_time_raw = book_progress.get("finishTime", 0) or 0
    # 用起止时间跨度计算阅读天数（精确到天）
    if start_reading_raw and finish_time_raw:
        reading_days = max(1, int((finish_time_raw - start_reading_raw) / 86400) + 1)
    else:
        reading_days = 0
    # readdata/detail 的总体数据仅作参考，不用于单书统计
    total_reading_days_all_books = (read_data or {}).get("readDays", 0) if read_data else 0

    # 整理个人划线（来自 bookmarklist.updated 数组）
    bookmarks = []
    if bookmark_data:
        for bm in (bookmark_data.get("updated") or []):
            ch_uid = bm.get("chapterUid")
            bookmarks.append({
                "chapterUid": ch_uid,
                "chapterTitle": _find_chapter_title(chapters, ch_uid) or "",
                "text": bm.get("markText", ""),
                "createTime": _unixtime_to_date(bm.get("createTime")),
                "range": bm.get("range", ""),
                "bookmarkId": bm.get("bookmarkId", ""),
            })

    # 整理个人想法/书评（区分：isFinish=1 → 全书点评，其他 → 章节想法）
    thoughts = []
    book_reviews = []  # 全书点评
    for item in personal_reviews:
        r = item.get("review", {})
        rid = item.get("reviewId", "")
        detail = review_details.get(rid) or {}
        entry = {
            "reviewId": rid,
            "content": r.get("content", ""),
            "abstract": r.get("abstract", ""),
            "chapterUid": r.get("chapterUid"),
            "chapterTitle": r.get("chapterName") or "",
            "range": r.get("range", ""),  # 对应原文在章节中的位置，用于混排
            "createTime": _unixtime_to_date(r.get("createTime")),
            "star": r.get("star"),  # 100=推荐, 60=一般, 20=不行
            "likesCount": int(item.get("likesCount", 0) or 0),
            "commentsCount": int(item.get("commentsCount", 0) or 0),
            "comments": _extract_comments(detail),
            "isWholeBookReview": bool(r.get("isFinish")),
        }
        if entry["isWholeBookReview"]:
            book_reviews.append(entry)
        else:
            thoughts.append(entry)

    # 整理热门划线
    hot_underlines = []
    if best_bookmarks:
        items = best_bookmarks.get("items") or []
        for item in items:
            ch_uid = item.get("chapterUid")
            hot_underlines.append({
                "chapterUid": ch_uid,
                "chapterTitle": _find_chapter_title(chapters, ch_uid) or "",
                "text": item.get("markText", ""),
                "count": item.get("totalCount", 0) or 0,
            })
        # 按划线人数降序
        hot_underlines.sort(key=lambda x: x["count"], reverse=True)

    # 整理公开书评（取点赞数 TOP10）
    public_reviews_sorted = sorted(
        public_reviews,
        key=lambda r: (r.get("review", {}) or {}).get("likesCount", 0) or 0,
        reverse=True,
    )
    top_public_reviews = []
    for item in public_reviews_sorted[:10]:
        outer = item.get("review", {})
        # /review/list 返回结构为 { review: { review: { content, author, ... }, likesCount, ... } }
        r = outer.get("review", {}) if outer else {}
        top_public_reviews.append({
            "reviewId": outer.get("reviewId", "") or item.get("reviewId", ""),
            "content": r.get("content", ""),
            "author": (r.get("author") or {}).get("name", ""),
            "createTime": _unixtime_to_date(r.get("createTime")),
            "star": r.get("star"),
            "likesCount": int(outer.get("likesCount", 0) or 0),
            "commentsCount": int(outer.get("commentsCount", 0) or 0),
        })

    # 从 notebook 中查找本书的笔记数（作为交叉验证）
    nb_underline = 0
    nb_note = 0
    if notebook_data:
        for nb in (notebook_data.get("books") or []):
            if nb.get("bookId") == book_id:
                nb_underline = nb.get("underlineCount", 0) or 0
                nb_note = nb.get("noteCount", 0) or 0
                break

    underline_count = len(bookmarks)
    thought_count = len(thoughts)
    book_review_count = len(book_reviews)

    # ---- 4. 组装输出 ----
    output = {
        "metadata": {
            "book_id": book_id,
            "book_name": book_name,
            "fetched_at": datetime.now(TZ).isoformat(),
            "skill_version": SKILL_VERSION,
        },
        "book_info": book_info,
        "chapters": chapters,
        "reading": {
            "progress_pct": progress_pct,
            "reading_time_sec": reading_time_sec,
            "reading_time_display": _fmt_duration(reading_time_sec),
            "reading_days": reading_days,
            "start_date": _unixtime_to_date(start_reading_raw),
            "finish_date": _unixtime_to_date(finish_time_raw),
            "total_reading_days_all_books": total_reading_days_all_books,  # 仅供参考
        },
        "bookmarks": bookmarks,
        "thoughts": thoughts,
        "book_reviews": book_reviews,  # 全书点评（isFinish=1）
        "hot_underlines": hot_underlines,
        "top_public_reviews": top_public_reviews,
        "counts": {
            "underline_count": underline_count,
            "thought_count": thought_count,
            "book_review_count": book_review_count,
        },
        "interleaved": _build_interleaved(bookmarks, thoughts, chapters),
        "errors": errors if errors else [],
    }

    # ---- 5. 保存 ----
    out_dir = output_dir or (SKILL_ROOT / "data" / "books" / book_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "raw_data.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 数据已保存至: {out_path}")
    _print_summary(output, errors)
    return out_path


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _find_chapter_title(chapters: list, chapter_uid) -> Optional[str]:
    """根据 chapterUid 查找章节标题。"""
    if not chapter_uid or not chapters:
        return None
    for ch in chapters:
        if ch.get("chapterUid") == chapter_uid:
            return ch.get("title")
    return None


def _extract_comments(detail: dict) -> list:
    """从 /review/single 返回中提取评论列表。"""
    if not detail:
        return []
    comments = detail.get("comments") or []
    return [
        {
            "content": c.get("content", ""),
            "author": (c.get("author") or {}).get("name", ""),
            "createTime": _unixtime_to_date(c.get("createTime")),
            "likesCount": c.get("likesCount", 0),
        }
        for c in comments
    ]


def _fmt_duration(seconds) -> str:
    """秒 → X小时Y分钟。"""
    s = int(seconds or 0)
    h, m = divmod(s, 3600)
    m = m // 60
    if h > 0:
        return f"{h}小时{m}分钟" if m else f"{h}小时"
    return f"{m}分钟"


def _print_summary(output: dict, errors: list):
    """打印数据摘要。"""
    cnt = output["counts"]
    rd = output["reading"]
    bi = output.get("book_info", {}) or {}
    print(f"\n{'='*50}")
    print(f"📖 《{output['metadata']['book_name']}》")
    print(f"   作者: {bi.get('author', '未知')}")
    print(f"   进度: {rd['progress_pct']}%　|　"
          f"阅读 {rd['reading_days']}天 / {rd['reading_time_display']}")
    if rd.get("start_date"):
        print(f"   周期: {rd['start_date']} → {rd.get('finish_date', '进行中')}")
    print(f"   划线: {cnt['underline_count']}条　|　"
          f"想法: {cnt['thought_count']}条　|　"
          f"全书点评: {cnt['book_review_count']}条")
    print(f"   热门划线: {len(output['hot_underlines'])}条　|　"
          f"热门书评: {len(output['top_public_reviews'])}条")
    if errors:
        print(f"\n⚠️  {len(errors)} 个接口获取失败（已降级处理）:")
        for e in errors:
            print(f"   - {e['api']}: {e['error']}")




def _build_interleaved(bookmarks: list, thoughts: list, chapters: list) -> list:
    """将划线和想法按章节+位置混排，统一编号。"""
    import re

    def _parse_range(r):
        m = re.match(r"(\d+)", str(r))
        return int(m.group(1)) if m else 9999999

    def _chapter_order(ch_uid):
        if ch_uid is None:
            return 999
        for c in chapters:
            if c.get("chapterUid") == ch_uid:
                return c.get("chapterIdx", 999)
        return 999

    items = []
    for bm in bookmarks:
        items.append({
            "type": "bookmark",
            "chapterUid": bm["chapterUid"],
            "chapterTitle": bm.get("chapterTitle", ""),
            "sort_pos": _parse_range(bm.get("range", "")),
            "text": bm.get("text", ""),
            "createTime": bm.get("createTime", ""),
            "range": bm.get("range", ""),
        })
    for t in thoughts:
        items.append({
            "type": "thought",
            "chapterUid": t["chapterUid"],
            "chapterTitle": t.get("chapterTitle", ""),
            "sort_pos": _parse_range(t.get("range", "")),
            "abstract": t.get("abstract", ""),
            "content": t.get("content", ""),
            "createTime": t.get("createTime", ""),
            "likesCount": t.get("likesCount", 0),
            "commentsCount": t.get("commentsCount", 0),
            "comments": t.get("comments", []),
            "reviewId": t.get("reviewId", ""),
        })

    items.sort(key=lambda x: (_chapter_order(x["chapterUid"]), x["sort_pos"]))

    for i, item in enumerate(items, 1):
        item["seq"] = i
    return items

def main():
    parser = argparse.ArgumentParser(
        description="微信读书笔记数据批量获取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python fetch_book_data.py --book-name "基因之河"
  python fetch_book_data.py --book-id "26640213"
  python fetch_book_data.py -n "三体" -o ./my_data
        """,
    )
    parser.add_argument("-n", "--book-name", help="书名（模糊搜索，多结果时交互选择）")
    parser.add_argument("-i", "--book-id", help="书籍 ID（优先于书名）")
    parser.add_argument("-o", "--output-dir", help="输出目录（默认: data/books/{bookId}/）")
    args = parser.parse_args()

    if not args.book_name and not args.book_id:
        parser.print_help()
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else None
    fetch_book_data(
        book_name=args.book_name,
        book_id=args.book_id,
        output_dir=output_dir,
    )


if __name__ == "__main__":
    main()
