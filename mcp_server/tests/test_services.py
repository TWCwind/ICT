from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from mcp_server import services
from mcp_server.services import (
    add_learning_branch_data,
    get_exercise_session_data,
    get_learning_evaluation_data,
    get_project_status_data,
    get_role_competency_data,
    get_student_profile_data,
    get_wrong_book_data,
    search_knowledge_data,
    submit_exercise_answer_data,
)
from mcp_server.test_support import TEST_STUDENT_ID, prepare_generated_test_data


class MCPToolServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory(prefix="ict-mcp-unit-")
        cls.data_root = prepare_generated_test_data(Path(cls.temp_dir.name) / "test" / "generated" / "data")
        cls.original_data_root = services.BACKEND_DATA_ROOT
        cls.original_data_dir = services._backend_settings.data_dir
        services.BACKEND_DATA_ROOT = cls.data_root
        services._backend_settings.data_dir = str(cls.data_root)

    @classmethod
    def tearDownClass(cls) -> None:
        services.BACKEND_DATA_ROOT = cls.original_data_root
        services._backend_settings.data_dir = cls.original_data_dir
        cls.temp_dir.cleanup()

    def test_student_profile_reads_project_data(self) -> None:
        result = get_student_profile_data(TEST_STUDENT_ID)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["student_id"], TEST_STUDENT_ID)
        self.assertGreater(len(result["data"]["abilities"]), 0)
        self.assertEqual(result["meta"]["data_mode"], "bundled_demo_data")

    def test_unknown_student_and_path_traversal_are_explained(self) -> None:
        missing = get_student_profile_data("not-present")
        self.assertFalse(missing["ok"])
        self.assertEqual(missing["error"]["code"], "STUDENT_NOT_FOUND")

        invalid = get_student_profile_data("../demo")
        self.assertFalse(invalid["ok"])
        self.assertEqual(invalid["error"]["code"], "INVALID_STUDENT_ID")

    def test_role_competency_supports_name_and_id(self) -> None:
        by_id = get_role_competency_data(role_id="job_001")
        self.assertTrue(by_id["ok"], by_id)
        self.assertEqual(by_id["data"]["role_name"], "Java开发工程师")
        self.assertIn("Java", by_id["data"]["requirements"]["hard_skills"])

        by_name = get_role_competency_data(role_name="前端开发工程师")
        self.assertTrue(by_name["ok"], by_name)
        self.assertEqual(by_name["data"]["role_id"], "job_002")

    def test_project_status_returns_generated_path(self) -> None:
        result = get_project_status_data(TEST_STUDENT_ID)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["path"]["nodes"][0]["id"], "mcp-smoke-stage-1")

    def test_knowledge_search_returns_explainable_result(self) -> None:
        result = search_knowledge_data(TEST_STUDENT_ID, "软件需求分析")
        self.assertTrue(result["ok"], result)
        self.assertIn("results", result["data"])
        self.assertGreaterEqual(result["data"]["result_count"], 0)

    def test_generated_question_bank_is_available_for_session(self) -> None:
        result = get_exercise_session_data(TEST_STUDENT_ID)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["data"]["source"], "generated_question_bank")
        self.assertGreater(result["data"]["question_count"], 0)

    def test_answer_submission_updates_wrong_book_and_evaluation(self) -> None:
        session = get_exercise_session_data(TEST_STUDENT_ID)
        self.assertTrue(session["ok"], session)
        question_id = session["data"]["questions"][0]["id"]

        submitted = submit_exercise_answer_data(TEST_STUDENT_ID, question_id, "A")
        self.assertTrue(submitted["ok"], submitted)
        self.assertTrue(submitted["data"]["correct"])

        wrong_book = get_wrong_book_data(TEST_STUDENT_ID)
        self.assertTrue(wrong_book["ok"], wrong_book)
        self.assertIn("records", wrong_book["data"])

        evaluation = get_learning_evaluation_data(TEST_STUDENT_ID)
        self.assertTrue(evaluation["ok"], evaluation)
        self.assertIn("evaluation", evaluation["data"])
        self.assertGreater(evaluation["data"]["evaluation"]["evidence"]["total"], 0)

    def test_learning_branch_writes_to_isolated_test_data(self) -> None:
        status = get_project_status_data(TEST_STUDENT_ID)
        self.assertTrue(status["ok"], status)
        node_id = status["data"]["path"]["nodes"][0]["id"]

        result = add_learning_branch_data(
            TEST_STUDENT_ID,
            knowledge_node_id=node_id,
            title="MCP 自动化补充分支",
            description="验证写入型工具闭环",
        )
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["data"]["created"])
        self.assertEqual(result["meta"]["data_mode"], "bundled_demo_data")


if __name__ == "__main__":
    unittest.main()
