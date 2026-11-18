"""Business errors returned by MCP tools must count as unsuccessful calls."""
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from answer_eval import call_tool, judge


class AnswerEvalStatusTests(unittest.TestCase):
    def test_business_error_is_not_success(self):
        server = types.SimpleNamespace(get_role_competency=lambda **_: {"ok": False, "error": {"code": "ROLE_NOT_FOUND"}})
        package = types.ModuleType("mcp_server")
        package.server = server
        with patch.dict(sys.modules, {"mcp_server": package}):
            result = call_tool("get_role_competency", {"role_name": "missing"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["result"]["error"]["code"], "ROLE_NOT_FOUND")
        row = judge({"tool": "get_role_competency"}, [{"name": "get_role_competency", "ok": result["ok"], "output": result["result"]}], "没有找到岗位")
        self.assertFalse(row["tools_ok"])


if __name__ == "__main__":
    unittest.main()
