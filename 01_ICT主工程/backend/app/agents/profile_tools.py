from __future__ import annotations

from typing import Any, AsyncIterator
import re

from app.llm import parse_json_content

from app.agents.text_utils import _safe_text

"""画像解析工具：六维取值清洗、偏好推断、关键词与薄弱点抽取、JSON 宽松解析。"""

def _guess_modality(text: str) -> str:
    t = text
    if any(k in t for k in ["视频", "动画", "讲解视频", "短视频"]):
        return "视频/动画优先"
    if any(k in t for k in ["图解", "流程图", "思维导图", "示意图"]):
        return "图解优先"
    if any(k in t for k in ["题", "刷题", "练习"]):
        return "练习驱动"
    return "文字优先"


def _guess_pace(text: str) -> str:
    if any(k in text for k in ["快", "速成", "赶进度"]):
        return "快节奏"
    if any(k in text for k in ["慢", "细讲", "从零"]):
        return "慢节奏"
    return "中等节奏"


def _guess_cognitive_style(text: str) -> str:
    if any(k in text for k in ["推导", "证明", "原理", "为什么"]):
        return "原理推导型"
    if any(k in text for k in ["例子", "类比", "直观"]):
        return "例子直观型"
    return "结构化步骤型"


_DIM_PLACEHOLDERS = {"", "待评估", "待采集", "未记录"}


def _clean_dim_value(value: Any) -> str:
    """把占位值当成"还没有"，否则首次写入的"待评估/待采集"会永久锁死该维度。"""
    text = _safe_text(value or "").strip()
    return "" if text in _DIM_PLACEHOLDERS else text


def _infer_preferences(text: str) -> dict[str, str]:
    """只返回本轮文本里"确实说了"的偏好维度，没说的不碰，避免覆盖用户手动结论。"""
    inferred: dict[str, str] = {}
    if any(k in text for k in ["视频", "动画", "演示"]):
        inferred["modality_preference"] = "视觉优先"
    elif any(k in text for k in ["图", "图解", "可视化", "画出来", "思维导图"]):
        inferred["modality_preference"] = "图示优先"
    elif any(k in text for k in ["动手", "敲一遍", "实操", "上手", "自己写"]):
        inferred["modality_preference"] = "动手实践型"
    elif any(k in text for k in ["讲解", "语音", "听", "播客", "朗诵", "念给我"]):
        inferred["modality_preference"] = "听觉优先"
    elif any(k in text for k in ["看书", "读文档", "文字", "笔记"]):
        inferred["modality_preference"] = "文字优先"

    if any(k in text for k in ["慢一点", "慢慢来", "别催", "不着急", "进度慢", "一点点来"]):
        inferred["pace_preference"] = "慢节奏"
    elif any(k in text for k in ["快一点", "加速", "节奏快", "速成", "赶进度"]):
        inferred["pace_preference"] = "快节奏"
    elif any(k in text for k in ["分步骤", "一步一步", "步骤", "拆开讲"]):
        inferred["pace_preference"] = "分步骤"

    if any(k in text for k in ["目标", "分数", "绩点", "及格", "上岸", "证书", "拿高分"]):
        inferred["motivation_style"] = "目标驱动"
    elif any(k in text for k in ["兴趣", "好奇", "好玩", "喜欢这门", "有意思"]):
        inferred["motivation_style"] = "兴趣驱动"

    if any(k in text for k in ["为什么", "原理", "推导", "证明", "底层"]):
        inferred["cognitive_style"] = "原理推导型"
    elif any(k in text for k in ["例子", "类比", "直观", "打个比方"]):
        inferred["cognitive_style"] = "例子直观型"
    return inferred


_KEYWORD_BLACKLIST = {"这个", "那个", "我们", "我的", "这门", "课程", "学期", "内容", "方法", "系统学习"}


_COURSE_WORDS = (
    "高等数学", "高数", "线性代数", "概率论", "离散数学", "数据结构", "操作系统",
    "计算机网络", "编译原理", "软件工程", "数据库原理", "机器学习", "深度学习",
    "人工智能", "软件测试", "面向对象", "需求分析", "统一建模",
)


def _extract_keywords(text: str, limit: int = 5) -> list[str]:
    """从自述里抽"像课程/技术名词"的词，供右侧画像标签使用。"""
    found: list[str] = []
    for word in _COURSE_WORDS:
        if word in text:
            found.append(word)
    for pattern in (
        r"《([^》]{2,20})》",
        r"([\u4e00-\u9fa5]{2,10}?(?:原理|工程|测试|设计|开发|建模|算法|数据库|网络|语言|框架|导论|概论|公式|定理))",
        r"\b([A-Za-z][A-Za-z0-9+#.]{1,15})\b",
    ):
        for match in re.finditer(pattern, text):
            token = match.group(1).strip()
            if len(token) >= 2 and token not in _KEYWORD_BLACKLIST:
                found.append(token)
    ordered: list[str] = []
    for token in found:
        for noise in ("我的薄弱点是", "薄弱点是", "薄弱点", "不会的是", "搞不懂的是", "另外", "还有", "我是", "我读", "我学", "我在"):
            if token.startswith(noise):
                token = token[len(noise):].strip()
                break
        if len(token) < 2:
            continue
        if any(token in kept for kept in ordered):
            continue
        ordered = [kept for kept in ordered if kept not in token]
        ordered.append(token)
    return ordered[:limit]


def _extract_weak_points(text: str) -> list[str]:
    patterns = [
        r"(?:薄弱点是|薄弱点：|薄弱点:)([^，。；\n]{2,60})",
        r"(?:不懂|薄弱|不会|卡在|容易错在|容易错|总是错在)([^，。；\n]{2,40})",
    ]
    raw: list[str] = []
    for p in patterns:
        raw.extend(re.findall(p, text))
    items: list[str] = []
    for r in raw:
        for part in re.split(r"[、,，和\s]+", r):
            part = _safe_text(part)
            if part.startswith("点是"):
                part = _safe_text(part[2:])
            if part.startswith("是"):
                part = _safe_text(part[1:])
            if not part:
                continue
            if len(part) > 30:
                continue
            items.append(part)
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out[:8]


def _extract_field(text: str, key: str) -> str:
    m = re.search(rf"{key}\s*[:：]\s*([^，。；\n]{{2,40}})", text)
    return _safe_text(m.group(1)) if m else ""


def _extract_basic_info(text: str) -> dict[str, str]:
    """从自然语言里抽取身份类基本信息（专业/年级/当前课程/学习目标），只返回抽到的字段。"""
    info: dict[str, str] = {}

    major = ""
    for pattern in (
        r"(?:我是|就读于|学的|学习|所在专业是)\s*([\u4e00-\u9fa5]{2,12}?)专业",
        r"([\u4e00-\u9fa5]{2,12}?)专业",
    ):
        m = re.search(pattern, text)
        if m:
            major = _safe_text(m.group(1))
            break
    if major:
        info["major"] = major

    m = re.search(r"(博士[一二三四]|硕士[一二三]|研[一二三]|大[一二三四]|高[一二三]|初中|本科[一二三四]|研究生)", text)
    if m:
        info["grade"] = _safe_text(m.group(1))

    course = ""
    for pattern in (
        r"《([^》]{2,30})》",
        r"(?:在学|正在学|本学期在学|上课的是)\s*《?([^》，。；\n]{2,30})》?",
    ):
        m = re.search(pattern, text)
        if m:
            course = _safe_text(m.group(1))
            break
    if course:
        info["current_course"] = course

    m = re.search(r"(?:目标|希望|想要|打算)(?:是|能)?\s*([^。；;\n]{4,60})", text)
    if m:
        goal = _safe_text(m.group(1)).strip("，,、 ")
        if goal:
            info["goals"] = goal

    return info


def _parse_json_maybe(text: str) -> dict[str, Any] | None:
    try:
        parsed = parse_json_content(text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None
