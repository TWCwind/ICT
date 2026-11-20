"""会话令牌与验证码原语（多用户会话级隔离）。

设计口径（与 README「多用户隔离」限制条目对齐）：
- 会话级隔离：登录签发绑定学号的 HMAC-SHA256 令牌，全接口校验
  「令牌学号 == 请求学号」，阻止跨学号读写。
- 不做账号体系：无密码/注册/角色；学号即身份，首次登录即建立会话。
- 验证码为 demo 级：服务端生成、一次性消费、TTL 内有效；SVG 内嵌
  明文字符，便于演示与自动化测试读取，不可用于生产防机器人场景。
- 令牌密钥来自 settings.auth_secret（环境变量 AUTH_SECRET）；
  未配置时使用开发默认值，生产部署必须显式配置。
- 验证码存储为进程内字典：当前后端以单进程 uvicorn 运行；
  若改为多进程部署需换成共享存储。
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import threading
import time

from app.core.config import settings

_CAPTCHA_CHARSET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 去掉易混淆的 I O 0 1
_CAPTCHA_LENGTH = 4
_DEFAULT_SECRET = "las-dev-secret-change-me-in-production"


def _secret() -> bytes:
    return (settings.auth_secret or _DEFAULT_SECRET).encode("utf-8")


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def issue_token(student_id: str, ttl_sec: int | None = None) -> tuple[str, int]:
    """签发绑定 student_id 的 HMAC-SHA256 令牌，返回 (token, expires_at_unix)。"""
    ttl = int(ttl_sec if ttl_sec is not None else settings.auth_token_ttl_sec)
    expires_at = int(time.time()) + ttl
    payload = {
        "student_id": student_id,
        "exp": expires_at,
        "nonce": secrets.token_hex(8),
    }
    body = _b64encode(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    sig = _b64encode(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}", expires_at


def verify_token(token: str) -> dict | None:
    """校验令牌签名与有效期；通过返回载荷 dict，任何篡改/过期/格式错误返回 None。"""
    if not token or "." not in token:
        return None
    body, _, sig = token.partition(".")
    try:
        expected = hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64decode(sig), expected):
            return None
        payload = json.loads(_b64decode(body))
    except (binascii.Error, ValueError, TypeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if not payload.get("student_id"):
        return None
    try:
        if int(payload.get("exp", 0)) < time.time():
            return None
    except (TypeError, ValueError):
        return None
    return payload


_captcha_lock = threading.Lock()
_captcha_store: dict[str, tuple[str, float]] = {}


def _captcha_cleanup_locked(now: float) -> None:
    expired = [cid for cid, (_, exp) in _captcha_store.items() if exp < now]
    for cid in expired:
        _captcha_store.pop(cid, None)


def create_captcha() -> tuple[str, str]:
    """生成一次性验证码，返回 (captcha_id, code)；TTL 由 settings.auth_captcha_ttl_sec 控制。"""
    code = "".join(secrets.choice(_CAPTCHA_CHARSET) for _ in range(_CAPTCHA_LENGTH))
    captcha_id = secrets.token_hex(12)
    with _captcha_lock:
        _captcha_cleanup_locked(time.time())
        _captcha_store[captcha_id] = (code, time.time() + settings.auth_captcha_ttl_sec)
    return captcha_id, code


def consume_captcha(captcha_id: str, code: str) -> bool:
    """一次性消费验证码：正确且未过期返回 True 并删除；其余情况一律 False。"""
    if not captcha_id or not code:
        return False
    with _captcha_lock:
        item = _captcha_store.pop(captcha_id, None)
    if not item:
        return False
    stored, expires_at = item
    if time.time() > expires_at:
        return False
    return stored.lower() == str(code).strip().lower()


def captcha_svg(code: str) -> str:
    """demo 级验证码 SVG：字符明文内嵌（<text>），便于演示与测试读取。"""
    chars = list(code)[:_CAPTCHA_LENGTH] or [" "] * _CAPTCHA_LENGTH
    texts = []
    for index, ch in enumerate(chars):
        rotate = (index * 137) % 31 - 15
        offset_y = ((index * 53) % 13) - 6
        x = 16 + index * 26
        texts.append(
            f'<text x="{x}" y="34" transform="rotate({rotate} {x} 34) translate(0 {offset_y})" '
            f'font-family="Georgia, serif" font-size="26" font-weight="bold" fill="#1f3b57">{ch}</text>'
        )
    lines = "".join(
        f'<line x1="{(i * 47) % 118}" y1="{(i * 29) % 46}" x2="{(i * 71) % 118}" y2="{(i * 43) % 46}" '
        f'stroke="#9db4c8" stroke-width="1" opacity="0.55"/>'
        for i in range(4)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="118" height="46" viewBox="0 0 118 46" role="img" aria-label="验证码">'
        f'<rect width="118" height="46" rx="6" fill="#eef4fa"/>{lines}{"".join(texts)}</svg>'
    )
