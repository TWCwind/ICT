from __future__ import annotations

import json
import unittest
from pathlib import Path

from app.core.config import settings
from app.services.knowledge_hub import graph_data


class RoadshowKnowledgeDataTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_data_dir = settings.data_dir
        project_root = Path(__file__).resolve().parents[2]
        runtime_dir = settings.data_path
        if not (runtime_dir / "uploads" / "textbooks" / "chapter_knowledge" / "index.json").exists():
            settings.data_dir = str(project_root / "roadshow-seed")

    def tearDown(self) -> None:
        settings.data_dir = self.original_data_dir

    def test_demo_graph_has_semantic_course_structure(self) -> None:
        graph = graph_data("demo", max_nodes=56)
        self.assertGreaterEqual(graph["stats"]["chapters"], 6)
        self.assertGreaterEqual(graph["stats"]["concepts"], 18)
        self.assertGreaterEqual(graph["stats"]["resources"], 2)
        chapter_names = [node["name"] for node in graph["nodes"] if node["kind"] == "chapter"]
        self.assertEqual(
            chapter_names,
            ["业务场景与范围", "需求获取与表达", "用例与行为建模", "领域结构建模", "质量与约束", "验证与变更"],
        )
        for name in chapter_names:
            self.assertNotRegex(name, r"[0-9a-f]{16,32}|book_|textbook_|第1部分|视频推荐|B站|腾讯视频", name)

    def test_chapters_and_points_are_in_lecture_body(self) -> None:
        data_root = settings.data_path
        index_path = data_root / "uploads" / "textbooks" / "chapter_knowledge" / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        textbook_id = next(iter(index))
        payload_path = index_path.parent / f"book_{textbook_id}.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        lecture_path = data_root / str(payload["source_document"])
        body = lecture_path.read_text(encoding="utf-8")
        for chapter in payload["chapters"]:
            self.assertIn(chapter["chapter_title"], body)
            for point in chapter["keywords"]:
                self.assertIn(point, body)

    def test_new_learner_does_not_inherit_demo_course(self) -> None:
        graph = graph_data("new-roadshow-learner", max_nodes=56)
        self.assertEqual(graph["nodes"], [])
        self.assertEqual(graph["stats"]["chapters"], 0)


if __name__ == "__main__":
    unittest.main()
