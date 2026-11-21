from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.core.config import settings
from app.services.knowledge_hub import (
    _build_uploaded_textbook_chapters,
    format_references,
    ingest_textbook,
    search_index,
)

RUNTIME = Path("D:/工作区/_runtime")


def _tmp_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="page-anchor-", dir=str(RUNTIME)))


def _make_pdf(chapters: list[tuple[str, str]], fill_pages: int = 2) -> bytes:
    """用 fitz 生成多页 PDF：每章独立成页，章与章之间垫空页拉开页距。"""
    import fitz

    doc = fitz.open()
    page_no = 0
    for title, body in chapters:
        if page_no:
            for _ in range(fill_pages):
                doc.new_page()
                page_no += 1
        page = doc.new_page()
        page_no += 1
        # fitz 内置 CJK 字体：保证生成的 PDF 能被 get_text 正确回读中文。
        page.insert_text((72, 96), title, fontsize=18, fontname="china-s")
        page.insert_text((72, 140), body, fontsize=11, fontname="china-s")
    content = doc.tobytes()
    doc.close()
    return content


class PageAnchorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_data_dir = settings.data_dir
        self.tmp = _tmp_dir()
        settings.data_dir = str(self.tmp)

    def tearDown(self) -> None:
        settings.data_dir = self.original_data_dir
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_pdf_textbook_carries_page_anchors(self) -> None:
        chapters = [
            ("第1章 需求获取", "需求访谈要覆盖干系人、业务场景与系统边界，用户故事用于表达目标，访谈提纲应按角色分组设计。"),
            ("第2章 用例建模", "用例图描述参与者与系统行为，包含包含关系与扩展关系两种依赖，用例规约要写前置条件与主成功场景。"),
            ("第3章 领域建模", "领域模型用类图表达核心实体与关联，聚合根划定一致性边界，值对象应设计为不可变类型并重写相等判断。"),
        ]
        content = _make_pdf(chapters, fill_pages=2)
        result = ingest_textbook("page-anchor-learner", "教材.pdf", content)

        payload_dir = Path(settings.data_path) / "uploads" / "textbooks" / "chapter_knowledge"
        index = json.loads((payload_dir / "index.json").read_text(encoding="utf-8"))
        textbook_id = next(iter(index))
        payload = json.loads((payload_dir / ("book_" + textbook_id + ".json")).read_text(encoding="utf-8"))
        # PDF 必须记下页偏移，且三条章数据带递增页码。
        self.assertTrue(payload.get("page_offsets"))
        pages = [(c.get("page_start"), c.get("page_end")) for c in payload["chapters"]]
        self.assertTrue(all(s > 0 and e >= s for s, e in pages))
        self.assertTrue(pages[1][0] > pages[0][0])
        self.assertTrue(pages[2][0] > pages[1][0])

        results = search_index("page-anchor-learner", "用例图 参与者", limit=5)
        self.assertTrue(results)
        hits = [r for r in results if r.get("chapter")]
        self.assertTrue(hits)
        for hit in hits:
            self.assertGreater(int(hit.get("page_start") or 0), 0)
            self.assertGreaterEqual(int(hit.get("page_end") or 0), int(hit.get("page_start") or 0))
        text = format_references(results)
        self.assertIn("第 ", text)
        self.assertIn(" 页）", text)

    def test_non_pdf_textbook_degrades_without_pages(self) -> None:
        body = ("需求分析需要先识别业务场景、干系人和系统边界，再通过需求访谈和用户故事表达目标。"
                "用例图描述参与者与系统行为，领域模型和类图帮助建立结构。") * 120
        chapters = _build_uploaded_textbook_chapters(body, "讲义正文")
        self.assertTrue(chapters)
        for chapter in chapters:
            self.assertEqual(chapter.get("page_start"), 0)
            self.assertEqual(chapter.get("page_end"), 0)


if __name__ == "__main__":
    unittest.main()
