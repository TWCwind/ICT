from __future__ import annotations

import re
from collections import Counter

CJK_RUN = re.compile(r"[\u4e00-\u9fff]{2,}")
LATIN_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]{1,20}")
CODE_BLOCK = re.compile(r"```.*?```", re.S)
INLINE_CODE = re.compile(r"`[^`\n]*`")
HTML_TAG = re.compile(r"<[^>]+>")
URL = re.compile(r"https?://\S+")
MD_MARK = re.compile(r"[#>*_~\[\]()|`\-]+")

# 中文停用/泛用词：命中就丢弃，避免提出「我们可以」「这个内容」这类噪音
STOPWORDS = {
    "我们", "你们", "他们", "她们", "它们", "这个", "那个", "这些", "那些", "这样", "那样",
    "什么", "怎么", "为什么", "如何", "一个", "一些", "一般", "一样", "一定", "可以", "可能",
    "需要", "应该", "如果", "因为", "所以", "但是", "而且", "然后", "因此", "由于", "对于",
    "通过", "进行", "以及", "并且", "或者", "还是", "已经", "正在", "其中", "之后", "之前",
    "同时", "另外", "例如", "比如", "如下", "首先", "其次", "再次", "最后", "总结", "注意",
    "建议", "内容", "本文", "本节", "本章", "文档", "章节", "部分", "方面", "问题", "情况",
    "过程", "方式", "方法", "步骤", "结果", "目标", "重点", "难点", "要点", "例子", "示例",
    "说明", "介绍", "分析", "学习", "学生", "老师", "教师", "课程", "知识", "资源", "能力",
    "水平", "时间", "工作", "系统", "平台", "使用", "提供", "帮助", "支持", "完成", "包括",
    "不同", "相同", "相关", "主要", "非常", "十分", "比较", "更加", "最好", "这里", "那里",
    "此时", "当你", "你能", "你要", "你会", "你先", "请先", "请看", "记住", "掌握", "理解",
    "了解", "定义", "含义", "概念", "判断", "判定", "应用", "场景", "作用", "特点", "优势",
    "不足", "结论", "总体", "以上", "以下", "下面", "上面", "接着", "继续", "直接", "具体",
    "实际", "本轮", "全局", "修正", "动作", "分资源", "依据", "知识库", "质检", "幻觉",
    "审查", "报告", "讲解", "专业", "生成", "已生成", "保存", "预览", "阅读", "章节",
    "给出", "满足", "正确", "来源", "官方", "回答", "追问", "体现", "涉及", "包含", "属于",
    "采用", "得到", "存在", "产生", "导致", "避免", "确保", "提升", "后续", "当前", "整个",
    "单个", "多个", "每个", "各个", "其他", "其余", "对应", "进行", "作为", "成为", "形成",
    "关注", "参考", "查看", "选择", "输入", "输出", "返回", "调用", "默认", "扩展", "描述",
    "表中", "表中数据", "如下表", "如下表所", "如上所述", "行数据", "所示", "如图", "见下",
}

LATIN_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "you", "your", "are", "was",
    "will", "can", "not", "but", "http", "https", "www", "com", "md", "id", "null",
    "true", "false", "def", "return", "import", "class", "self", "print", "str", "int",
    "json", "true", "none", "frac", "sqrt", "left", "right", "begin", "end", "text", "mathrm", "cdot", "times", "leq", "geq", "neq", "infty", "alpha", "beta", "theta", "lambda", "sigma", "sum", "int", "lim", "dir", "print", "def", "self", "none",
}

# 结构化资源里的 JSON 键名/枚举值，不是关键词
JSON_KEYS = {
    "answer", "answers", "explanation", "explanations", "options", "option", "question",
    "questions", "stem", "choices", "choice", "type", "types", "difficulty", "concept",
    "concepts", "keywords", "title", "subtitle", "body", "bullets", "cards", "steps",
    "takeaway", "meta", "course", "chapter", "chapters", "lesson", "score", "mastery",
    "correct", "wrong", "tags", "summary", "content", "markdown", "mermaid", "root",
    "mindmap", "question_bank", "single", "multiple", "judge", "short", "case", "name",
    "label", "value", "data", "result", "success", "error", "message", "reason", "stage",
}

# 出现在词首/词尾通常是断句残片，直接丢弃
BAD_EDGE = set("的了着过与和及或在把被对为于从向往已经但而而且还只等都就也是要能可很更最又如有如若则不我你他她它这那哪么什怎样")

MIN_LEN = 2
MAX_LEN = 6


LATEX_CMD = re.compile(r"\\[A-Za-z]+")
ORDINAL = re.compile(r"^第[一二三四五六七八九十0-9]+[步条点章节部个]$")

def _clean(text: str) -> str:
    text = LATEX_CMD.sub(" ", text)
    text = text.replace("$", " ").replace("{", " ").replace("}", " ")
    text = CODE_BLOCK.sub(" ", text)
    text = INLINE_CODE.sub(" ", text)
    text = HTML_TAG.sub(" ", text)
    text = URL.sub(" ", text)
    text = MD_MARK.sub(" ", text)
    return text


def _candidates(run: str) -> list[str]:
    grams: list[str] = []
    for size in range(MIN_LEN, MAX_LEN + 1):
        for index in range(0, len(run) - size + 1):
            gram = run[index:index + size]
            if gram[0] in BAD_EDGE or gram[-1] in BAD_EDGE:
                continue
            if gram in STOPWORDS or ORDINAL.match(gram):
                continue
            grams.append(gram)
    return grams


def _headings(text: str) -> list[str]:
    result: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        title = MD_MARK.sub(" ", stripped).strip()
        for run in CJK_RUN.findall(title):
            result.extend(_candidates(run))
        for token in LATIN_TOKEN.findall(title):
            lower = token.lower()
            if lower not in LATIN_STOPWORDS and len(lower) > 2:
                result.append(token)
    return result


def _overlaps(candidate: str, chosen: str) -> bool:
    return candidate != chosen and (candidate in chosen or chosen in candidate)


def extract_keywords(text: str, limit: int = 6) -> list[str]:
    """从生成的资源正文里提取少量可展示的关键词（纯本地规则，不调用 LLM）。"""
    if not text or not text.strip():
        return []

    cleaned = _clean(text)
    heading_hits = Counter(_headings(text))

    body: Counter[str] = Counter()
    for run in CJK_RUN.findall(cleaned):
        body.update(_candidates(run))

    scored: dict[str, float] = {}
    for word, count in heading_hits.items():
        scored[word] = scored.get(word, 0.0) + count * 2.0 + 2.0
    for word, count in body.items():
        if len(word) >= 3 and count < 2:
            continue
        if len(word) == 2 and count < 3:
            continue
        scored[word] = scored.get(word, 0.0) + count * (1 + 0.18 * (len(word) - 2))
    json_keys = {k.lower() for k in re.findall(r"[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']\s*:", cleaned)}
    for token, count in Counter(
        t
        for t in LATIN_TOKEN.findall(cleaned)
        if t.lower() not in LATIN_STOPWORDS
        and t.lower() not in JSON_KEYS
        and t.lower() not in json_keys
        and len(t) > 2
    ).items():
        scored[token] = scored.get(token, 0.0) + count * 1.5

    ordered = sorted(scored.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))
    chosen: list[str] = []
    for word, score in ordered:
        if score < 2.0:
            continue
        # 任一词若是同分或更高分的更长词的一部分，多半是断句残片，丢掉
        if any(
            word != other
            and len(other) > len(word)
            and word in other
            and other_score >= score * 0.9
            for other, other_score in ordered
        ):
            continue
        if any(_overlaps(word, item) for item in chosen):
            continue
        chosen.append(word)
        if len(chosen) >= limit:
            break
    return chosen