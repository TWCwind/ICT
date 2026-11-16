from __future__ import annotations

import asyncio
import json
import logging
import os
import unittest
from typing import Any, Dict, List

from mcp_server import hardening


class _DummyApp:
    """最小 ASGI 应用：所有请求回 200 text/plain，用于隔离测试加固层本身。"""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def __call__(self, scope, receive, send) -> None:
        self.calls.append({"path": scope.get("path"), "method": scope.get("method")})
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"inner-ok"})


def _call(app, path: str, method: str = "GET", headers: Dict[str, str] | None = None) -> Dict[str, Any]:
    """在线程外同步执行一次 ASGI 调用，返回 {status, body, headers}。"""
    raw_headers = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in (headers or {}).items()]
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "https",
        "path": path,
        "raw_path": path.encode("latin-1"),
        "query_string": b"",
        "headers": raw_headers,
        "client": ("203.0.113.7", 51234),
        "server": ("127.0.0.1", 8010),
    }
    captured: Dict[str, Any] = {}

    async def receive() -> Dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            captured["status"] = int(message["status"])
            captured["headers"] = {k.decode("latin-1"): v.decode("latin-1") for k, v in message.get("headers", [])}
        elif message["type"] == "http.response.body":
            captured["body"] = captured.get("body", b"") + message.get("body", b"")

    asyncio.run(app(scope, receive, send))
    body = captured.get("body", b"")
    try:
        captured["json"] = json.loads(body.decode("utf-8")) if body else None
    except json.JSONDecodeError:
        captured["json"] = None
    return captured


class _EnvMixin:
    """在用例前后保存/恢复 hardening 相关的环境变量。"""

    KEYS = ("MCP_API_KEY", "MCP_RATE_LIMIT_PER_MIN", "MCP_HEALTH_PATH", "MCP_LOG_REQUESTS")

    def setUp(self) -> None:  # noqa: D401 - unittest 钩子
        self._saved = {k: os.environ.get(k) for k in self.KEYS}
        super().setUp()

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        super().tearDown()


class HealthEndpointTests(_EnvMixin, unittest.TestCase):
    def test_healthz_reports_state_without_auth(self) -> None:
        os.environ.pop("MCP_API_KEY", None)
        app = hardening.HardeningMiddleware(_DummyApp())
        result = _call(app, "/healthz")
        self.assertEqual(result["status"], 200)
        payload = result["json"]
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["auth"], "none")
        self.assertEqual(payload["service"], hardening.SERVICE_NAME)

    def test_healthz_never_requires_api_key(self) -> None:
        os.environ["MCP_API_KEY"] = "secret-key"
        app = hardening.HardeningMiddleware(_DummyApp())
        result = _call(app, "/healthz")
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["json"]["auth"], "api_key")

    def test_custom_health_path(self) -> None:
        os.environ["MCP_HEALTH_PATH"] = "/status"
        app = hardening.HardeningMiddleware(_DummyApp())
        self.assertEqual(_call(app, "/status")["status"], 200)
        # 默认 /healthz 仍然可用，方便探针配置错时也能查到状态
        self.assertEqual(_call(app, "/healthz")["status"], 200)


class ApiKeyAuthTests(_EnvMixin, unittest.TestCase):
    def test_no_key_configured_passes_through(self) -> None:
        os.environ.pop("MCP_API_KEY", None)
        dummy = _DummyApp()
        app = hardening.HardeningMiddleware(dummy)
        result = _call(app, "/mcp", method="POST")
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["body"], b"inner-ok")
        self.assertEqual(len(dummy.calls), 1)

    def test_missing_key_is_rejected(self) -> None:
        os.environ["MCP_API_KEY"] = "secret-key"
        dummy = _DummyApp()
        app = hardening.HardeningMiddleware(dummy)
        result = _call(app, "/mcp", method="POST")
        self.assertEqual(result["status"], 401)
        self.assertEqual(result["json"]["error"]["code"], "UNAUTHORIZED")
        self.assertEqual(dummy.calls, [], "未鉴权的请求不应进入 MCP 应用")

    def test_wrong_key_is_rejected(self) -> None:
        os.environ["MCP_API_KEY"] = "secret-key"
        app = hardening.HardeningMiddleware(_DummyApp())
        result = _call(app, "/mcp", method="POST", headers={"x-api-key": "not-the-key"})
        self.assertEqual(result["status"], 401)

    def test_x_api_key_header_is_accepted(self) -> None:
        os.environ["MCP_API_KEY"] = "secret-key"
        app = hardening.HardeningMiddleware(_DummyApp())
        result = _call(app, "/mcp", method="POST", headers={"x-api-key": "secret-key"})
        self.assertEqual(result["status"], 200)

    def test_bearer_token_is_accepted(self) -> None:
        os.environ["MCP_API_KEY"] = "secret-key"
        app = hardening.HardeningMiddleware(_DummyApp())
        result = _call(app, "/mcp", method="POST", headers={"authorization": "Bearer secret-key"})
        self.assertEqual(result["status"], 200)

    def test_non_mcp_paths_are_not_gated(self) -> None:
        os.environ["MCP_API_KEY"] = "secret-key"
        app = hardening.HardeningMiddleware(_DummyApp())
        self.assertEqual(_call(app, "/favicon.ico")["status"], 200)


class RateLimitTests(_EnvMixin, unittest.TestCase):
    def test_limit_blocks_after_threshold(self) -> None:
        os.environ.pop("MCP_API_KEY", None)
        os.environ["MCP_RATE_LIMIT_PER_MIN"] = "3"
        app = hardening.HardeningMiddleware(_DummyApp())
        statuses = [_call(app, "/mcp", method="POST")["status"] for _ in range(4)]
        self.assertEqual(statuses[:3], [200, 200, 200])
        self.assertEqual(statuses[3], 429)

    def test_rate_limited_response_has_retry_after(self) -> None:
        os.environ["MCP_RATE_LIMIT_PER_MIN"] = "1"
        app = hardening.HardeningMiddleware(_DummyApp())
        _call(app, "/mcp", method="POST")
        blocked = _call(app, "/mcp", method="POST")
        self.assertEqual(blocked["status"], 429)
        self.assertIn("retry-after", blocked["headers"])
        self.assertEqual(blocked["json"]["error"]["code"], "RATE_LIMITED")

    def test_zero_limit_disables_rate_limiting(self) -> None:
        os.environ["MCP_RATE_LIMIT_PER_MIN"] = "0"
        app = hardening.HardeningMiddleware(_DummyApp())
        statuses = {_call(app, "/mcp", method="POST")["status"] for _ in range(5)}
        self.assertEqual(statuses, {200})

    def test_health_checks_do_not_consume_quota(self) -> None:
        os.environ["MCP_RATE_LIMIT_PER_MIN"] = "2"
        app = hardening.HardeningMiddleware(_DummyApp())
        for _ in range(5):
            self.assertEqual(_call(app, "/healthz")["status"], 200)
        self.assertEqual(_call(app, "/mcp", method="POST")["status"], 200)


class LogRedactionTests(_EnvMixin, unittest.TestCase):
    def test_access_log_never_contains_api_key(self) -> None:
        os.environ["MCP_API_KEY"] = "super-secret-value-123"
        app = hardening.HardeningMiddleware(_DummyApp())
        records: List[str] = []

        class _Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record.getMessage())

        handler = _Capture()
        hardening.logger.addHandler(handler)
        previous_level = hardening.logger.level
        hardening.logger.setLevel(logging.INFO)
        try:
            _call(app, "/mcp", method="POST", headers={"x-api-key": "super-secret-value-123"})
            _call(app, "/mcp", method="POST", headers={"x-api-key": "wrong-key"})
        finally:
            hardening.logger.removeHandler(handler)
            hardening.logger.setLevel(previous_level)

        joined = "\n".join(records)
        self.assertNotIn("super-secret-value-123", joined)
        self.assertNotIn("wrong-key", joined)
        # 指纹可以出现，用于对账
        self.assertIn(hardening._key_fingerprint("super-secret-value-123"), joined)

    def test_log_requests_can_be_disabled(self) -> None:
        os.environ["MCP_LOG_REQUESTS"] = "0"
        app = hardening.HardeningMiddleware(_DummyApp())
        records: List[str] = []

        class _Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record.getMessage())

        handler = _Capture()
        hardening.logger.addHandler(handler)
        previous_level = hardening.logger.level
        hardening.logger.setLevel(logging.INFO)
        try:
            _call(app, "/mcp", method="POST")
        finally:
            hardening.logger.removeHandler(handler)
            hardening.logger.setLevel(previous_level)
        self.assertEqual(records, [])


class FingerprintTests(unittest.TestCase):
    def test_fingerprint_is_short_and_stable(self) -> None:
        first = hardening._key_fingerprint("abc")
        self.assertEqual(first, hardening._key_fingerprint("abc"))
        self.assertEqual(len(first), 8)
        self.assertNotEqual(first, hardening._key_fingerprint("abd"))

    def test_anonymous_fingerprint(self) -> None:
        self.assertEqual(hardening._key_fingerprint(""), "anonymous")


class EnvParsingTests(_EnvMixin, unittest.TestCase):
    def test_invalid_rate_limit_falls_back_to_default(self) -> None:
        os.environ["MCP_RATE_LIMIT_PER_MIN"] = "not-a-number"
        app = hardening.HardeningMiddleware(_DummyApp())
        self.assertEqual(app.limiter.per_minute, 240)


if __name__ == "__main__":
    unittest.main()
