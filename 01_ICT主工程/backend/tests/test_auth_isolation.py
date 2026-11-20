from __future__ import annotations

import base64
import re
import unittest

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.app_router import api_router
from app.api.routers.auth import enforce_student_isolation
from app.core import security
from app.core.config import settings


_probe_router = APIRouter()


@_probe_router.post("/api/_probe/echo")
async def _probe_echo(body: dict) -> dict:
    # 探针端点：验证依赖读取 body 后，路由自身的 JSON 解析仍能拿到完整 body。
    return {"student_id": body.get("student_id")}


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(api_router, dependencies=[Depends(enforce_student_isolation)])
    app.include_router(_probe_router, dependencies=[Depends(enforce_student_isolation)])
    return TestClient(app)


class SecurityPrimitiveTest(unittest.TestCase):
    """令牌与验证码原语（与 HTTP 层无关）。"""

    def test_token_roundtrip_and_tamper(self) -> None:
        token, expires_at = security.issue_token("demo")
        payload = security.verify_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["student_id"], "demo")
        self.assertEqual(payload["exp"], expires_at)

        body, _, sig = token.partition(".")
        self.assertIsNone(security.verify_token(body + "." + "A" * len(sig)))
        self.assertIsNone(security.verify_token("not-a-token"))
        self.assertIsNone(security.verify_token(""))

    def test_token_expiry(self) -> None:
        token, _ = security.issue_token("demo", ttl_sec=-10)
        self.assertIsNone(security.verify_token(token))

    def test_captcha_one_shot(self) -> None:
        captcha_id, code = security.create_captcha()
        self.assertEqual(len(code), 4)
        self.assertTrue(security.consume_captcha(captcha_id, code.lower()))
        self.assertFalse(security.consume_captcha(captcha_id, code))
        captcha_id2, code2 = security.create_captcha()
        self.assertFalse(security.consume_captcha(captcha_id2, "ZZZZ"))

    def test_captcha_svg_contains_code(self) -> None:
        _, code = security.create_captcha()
        svg = security.captcha_svg(code)
        for ch in code:
            self.assertIn(ch, svg)


class StudentIsolationEnforcementTest(unittest.TestCase):
    """AUTH_REQUIRED=1 时的全接口会话隔离行为。"""

    def setUp(self) -> None:
        self._original = settings.auth_required
        settings.auth_required = True
        self.client = _build_client()

    def tearDown(self) -> None:
        settings.auth_required = self._original
        self.client.close()

    def _login(self, student_id: str) -> str:
        captcha_id, code = security.create_captcha()
        resp = self.client.post(
            "/api/auth/login",
            json={"student_id": student_id, "captcha_id": captcha_id, "captcha_code": code},
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertTrue(payload["success"], payload)
        return payload["data"]["token"]

    def test_config_reports_auth_required(self) -> None:
        resp = self.client.get("/api/auth/config")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["data"]["auth_required"])

    def test_login_rejects_wrong_captcha(self) -> None:
        captcha_id, _ = security.create_captcha()
        resp = self.client.post(
            "/api/auth/login",
            json={"student_id": "demo", "captcha_id": captcha_id, "captcha_code": "ZZZZ"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["success"])

    def test_captcha_svg_code_can_login(self) -> None:
        resp = self.client.get("/api/auth/captcha")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        svg = base64.b64decode(data["image"].split(",", 1)[1]).decode("utf-8")
        code = "".join(re.findall(r"<text[^>]*>([A-Z0-9])</text>", svg))
        self.assertEqual(len(code), 4)
        resp = self.client.post(
            "/api/auth/login",
            json={"student_id": "demo", "captcha_id": data["captcha_id"], "captcha_code": code},
        )
        self.assertTrue(resp.json()["success"])

    def test_me_requires_valid_token(self) -> None:
        resp = self.client.get("/api/auth/me")
        self.assertEqual(resp.status_code, 401)
        token = self._login("demo")
        resp = self.client.get("/api/auth/me", headers={"X-Session-Token": token})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["student_id"], "demo")

    def test_query_scoped_route_enforced(self) -> None:
        token = self._login("demo")
        resp = self.client.get("/api/dashboard/overview", params={"student_id": "demo"})
        self.assertEqual(resp.status_code, 401)
        resp = self.client.get(
            "/api/dashboard/overview", params={"student_id": "demo"}, headers={"X-Session-Token": token}
        )
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(
            "/api/dashboard/overview",
            params={"student_id": "someone-else"},
            headers={"X-Session-Token": token},
        )
        self.assertEqual(resp.status_code, 403)

    def test_path_scoped_route_enforced(self) -> None:
        token = self._login("demo")
        resp = self.client.get("/api/profile/demo/overview", headers={"X-Session-Token": token})
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(
            "/api/profile/someone-else/overview", headers={"X-Session-Token": token}
        )
        self.assertEqual(resp.status_code, 403)

    def test_body_scoped_route_enforced(self) -> None:
        token = self._login("demo")
        resp = self.client.post("/api/_probe/echo", json={"student_id": "demo"})
        self.assertEqual(resp.status_code, 401)
        resp = self.client.post(
            "/api/_probe/echo", json={"student_id": "demo"}, headers={"X-Session-Token": token}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["student_id"], "demo")
        resp = self.client.post(
            "/api/_probe/echo", json={"student_id": "other"}, headers={"X-Session-Token": token}
        )
        self.assertEqual(resp.status_code, 403)

    def test_non_student_route_passes_without_token(self) -> None:
        resp = self.client.get("/api/config/llm")
        self.assertEqual(resp.status_code, 200)


class AuthDisabledPassThroughTest(unittest.TestCase):
    """AUTH_REQUIRED=0（默认）时全部请求照旧放行。"""

    def test_flag_off_no_token_needed(self) -> None:
        settings.auth_required = False
        client = _build_client()
        try:
            resp = client.get("/api/dashboard/overview", params={"student_id": "demo"})
            self.assertEqual(resp.status_code, 200)
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
