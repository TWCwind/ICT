"""Focused offline regression checks for chapter and citation evidence."""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

MAIN = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(MAIN / "backend"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from app.services.knowledge_documents import _chapter_documents
from app.services.knowledge_text import _read_text
from cite_check import check_citation
from route_eval import parse_tools, plan_tools


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.payload = {"chapters": [{"chapter_title": "业务场景与范围"}, {"chapter_title": "需求获取与表达"}]}
        self.body = ("目录\n业务场景与范围\n需求获取与表达\n\n"
                     "## 业务场景与范围\n" + "范围正文内容。" * 12 + "\n"
                     "## 需求获取与表达\n" + "访谈正文内容。" * 12)

    def test_toc_is_not_chapter(self):
        docs = _chapter_documents("x", "讲义", self.body, self.payload, pathlib.Path("demo.md"))
        self.assertEqual([d["chapter_index"] for d in docs], [1, 2])
        self.assertTrue(docs[0]["text"].startswith("## 业务场景与范围"))
        self.assertNotIn("访谈正文", docs[0]["text"])

    def test_missing_or_reordered_heading_falls_back(self):
        self.assertEqual(_chapter_documents("x", "讲义", self.body.replace("## 需求获取与表达", "## 其他"), self.payload, pathlib.Path("demo.md")), [])
        reversed_body = "## 需求获取与表达\n" + "正文" * 20 + "\n## 业务场景与范围\n" + "正文" * 20
        self.assertEqual(_chapter_documents("x", "讲义", reversed_body, self.payload, pathlib.Path("demo.md")), [])

    def test_real_demo_lecture(self):
        root = MAIN / "roadshow-seed"
        source = root / "files/demo/软件需求分析与建模-演示讲义.md"
        payload = json.loads((root / "uploads/textbooks/chapter_knowledge/book_roadshow-requirements.json").read_text(encoding="utf-8"))
        docs = _chapter_documents("roadshow-requirements", "讲义", _read_text(source), payload, source)
        self.assertEqual(len(docs), 6)
        self.assertEqual([d["chapter_index"] for d in docs], list(range(1, 7)))

    def test_excerpt_and_claimed_chapter(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            source = root / "demo.md"
            source.write_text(self.body, encoding="utf-8")
            metadata = root / "book_x.json"
            metadata.write_text(json.dumps(self.payload, ensure_ascii=False), encoding="utf-8")
            item = {"id": "textbook:x#1", "title": "讲义", "path": str(source), "chapter": "需求获取与表达", "chapter_index": 2, "excerpt": "访谈正文内容。"}
            self.assertTrue(check_citation(item, _read_text, [root], root)["source_verified"])
            item["excerpt"] = "范围正文内容。"
            wrong_chapter = check_citation(item, _read_text, [root], root)
            self.assertEqual(wrong_chapter["reason"], "excerpt_not_in_claimed_chapter")
            self.assertTrue(wrong_chapter["source_verified"])
            self.assertFalse(wrong_chapter["chapter_verified"])
            item["excerpt"] = "伪造片段"
            self.assertEqual(check_citation(item, _read_text, [root], root)["reason"], "excerpt_not_in_source")

    def test_tags_and_missing_source_do_not_verify(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            item = {"title": "讲义", "path": str(root / "missing.md"), "excerpt": "示例", "tags": ["第一章"]}
            result = check_citation(item, _read_text, [root], root)
            self.assertTrue(result["metadata_complete"])
            self.assertFalse(result["source_verified"])
            self.assertFalse(result["chapter_verified"])

    def test_route_schema_must_be_real(self):
        with patch.dict(sys.modules, {"mcp_server.server": None}):
            with self.assertRaisesRegex(RuntimeError, "FastMCP"):
                parse_tools()

    def test_plan_http_failure_is_recordable(self):
        client = Mock()
        client.post.return_value.status_code = 503
        tools = [{"function": {"name": "search_knowledge"}}]
        with self.assertRaisesRegex(RuntimeError, "plan_http_503"):
            plan_tools(client, "https://example.invalid", {}, "test-model", tools, {"prompt": "test"})


if __name__ == "__main__":
    unittest.main()
