#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""阶段 0 数据摸底报表：JSON 文件存储 -> SQLite 迁移前的只读盘点。

统计 data/users/<学号>/ 下每一类 JSON 的条数、字段并集、异常文件，
输出一份 Markdown 报表 + 一份机器可读 JSON（供阶段 2 迁移脚本复用）。

本脚本只读业务数据：不写 backend/app，不修改任何 *.json。

用法：
    python scripts/migrate/report.py
    python scripts/migrate/report.py --data-dir D:/工作区/_runtime/ict-data --out D:/工作区/_runtime/ict-data-report
    python scripts/migrate/report.py --top 30
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

B = chr(96)  # markdown 行内代码反引号


def c(value) -> str:
    return B + str(value) + B


KNOWN = {
    "student.json": {
        "container": "dict",
        "table": "student",
        "label": "学生基本信息",
    },
    "profiles.json": {
        "container": "list",
        "table": "profile_snapshot",
        "label": "画像快照（append-only）",
    },
    "resources.json": {
        "container": "list",
        "table": "resource_item",
        "label": "资源元数据册",
    },
    "exercise_records.json": {
        "container": "list",
        "table": "quiz_attempt",
        "label": "做题记录（错题本数据源）",
    },
    "events.json": {
        "container": "list",
        "table": "learning_event",
        "label": "学习事件流",
    },
    "usage.json": {
        "container": "list",
        "table": "resource_usage",
        "label": "资源使用记录",
    },
    "path_progress.json": {
        "container": "dict",
        "table": "path_plan + path_step（第一版可整块塞 state_json）",
        "label": "路径进度状态",
    },
    "knowledge_state.json": {
        "container": "dict",
        "table": "knowledge_node_state（现有 DDL 无此表，需新增）",
        "label": "知识节点掌握度",
    },
}

ROOT_ASSETS = (
    "agent_trace_log.json",
    "role_pipeline_trace.json",
    "multi_agent_trace.json",
)


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def default_data_dir() -> Path:
    for key in ("ICT_DATA_DIR", "DATA_DIR"):
        raw = os.environ.get(key)
        if raw:
            candidate = Path(raw)
            if (candidate / "users").is_dir():
                return candidate
    runtime = PROJECT_ROOT.parents[1] / "_runtime" / "ict-data"
    if (runtime / "users").is_dir():
        return runtime
    return PROJECT_ROOT / "data"


def human_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return "%d B" % round(value)
            return "%.2f %s" % (value, unit)
        value /= 1024.0
    return "%d B" % size


def load_json(path: Path):
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return None, "读取失败: %s" % exc
    if not text.strip():
        return None, "空文件"
    try:
        return json.loads(text), None
    except Exception as exc:
        return None, "JSON 解析失败: %s" % exc


def classify_dir(name: str) -> str:
    if name == "demo":
        return "demo（演示基线）"
    if name.startswith("acceptance-"):
        return "acceptance-*（验收脚本残留）"
    if name.startswith("learner-"):
        return "learner-*（e2e 随机访客）"
    if name in ("layout-demo", "demo_user_001"):
        return name + "（种子/演示）"
    if name.startswith("test-") or name.startswith("e2e-"):
        return "test-/e2e-*（调试残留）"
    return "其他学号"


def new_kind_stat(name: str) -> dict:
    meta = KNOWN[name]
    return {
        "file": name,
        "label": meta["label"],
        "container": meta["container"],
        "table": meta["table"],
        "dirs_with_file": 0,
        "dirs_with_content": 0,
        "files_ok": 0,
        "entries_total": 0,
        "bytes_total": 0,
        "fields": Counter(),
        "field_types": {},
        "parse_errors": [],
        "empty_containers": [],
        "type_mismatch": [],
        "missing_id": 0,
        "missing_created_at": 0,
        "duplicate_ids": 0,
        "nested": Counter(),
    }


def scan(data_dir: Path) -> dict:
    users_dir = data_dir / "users"
    result = {
        "scanned_at": now(),
        "data_dir": str(data_dir),
        "users_dir": str(users_dir),
        "student_dirs": 0,
        "groups": Counter(),
        "group_bytes": Counter(),
        "group_with_content": Counter(),
        "kinds": {name: new_kind_stat(name) for name in KNOWN},
        "unknown_json": Counter(),
        "bak_files": 0,
        "bak_bytes": 0,
        "loose_files": [],
        "total_bytes": 0,
        "per_student": {},
    }
    if not users_dir.is_dir():
        result["error"] = "数据目录不存在: %s" % users_dir
        return result

    for entry in sorted(users_dir.iterdir()):
        if entry.is_file():
            result["unknown_json"]["users 根下文件:" + entry.name] += 1
            continue
        if not entry.is_dir():
            continue
        group = classify_dir(entry.name)
        result["student_dirs"] += 1
        result["groups"][group] += 1
        student_counts = {}
        dir_bytes = 0
        has_content = False

        for path in sorted(entry.iterdir()):
            if not path.is_file():
                continue
            size = path.stat().st_size
            dir_bytes += size
            if path.suffix == ".bak":
                result["bak_files"] += 1
                result["bak_bytes"] += size
                continue
            if path.suffix != ".json":
                result["loose_files"].append(str(path))
                continue
            name = path.name
            if name not in KNOWN:
                result["unknown_json"][name] += 1
                continue

            stat = result["kinds"][name]
            stat["dirs_with_file"] += 1
            stat["bytes_total"] += size
            data, error = load_json(path)
            if error:
                stat["parse_errors"].append({"path": str(path), "error": error})
                student_counts[name] = "ERR"
                continue
            stat["files_ok"] += 1

            if stat["container"] == "list":
                if not isinstance(data, list):
                    stat["type_mismatch"].append(
                        {"path": str(path), "expected": "list", "actual": type(data).__name__}
                    )
                    student_counts[name] = "TYPE"
                    continue
                if not data:
                    stat["empty_containers"].append(str(path))
                else:
                    stat["dirs_with_content"] += 1
                    has_content = True
                stat["entries_total"] += len(data)
                student_counts[name] = len(data)
                seen_ids = set()
                for item in data:
                    if not isinstance(item, dict):
                        stat["type_mismatch"].append(
                            {"path": str(path), "expected": "object-item", "actual": type(item).__name__}
                        )
                        continue
                    for key, value in item.items():
                        stat["fields"][key] += 1
                        stat["field_types"].setdefault(key, Counter())[type(value).__name__] += 1
                    rid = item.get("id")
                    if rid in (None, ""):
                        stat["missing_id"] += 1
                    elif rid in seen_ids:
                        stat["duplicate_ids"] += 1
                    else:
                        seen_ids.add(rid)
                    if item.get("created_at") in (None, ""):
                        stat["missing_created_at"] += 1
            else:
                if not isinstance(data, dict):
                    stat["type_mismatch"].append(
                        {"path": str(path), "expected": "dict", "actual": type(data).__name__}
                    )
                    student_counts[name] = "TYPE"
                    continue
                if not data:
                    stat["empty_containers"].append(str(path))
                else:
                    stat["dirs_with_content"] += 1
                    has_content = True
                stat["entries_total"] += 1
                student_counts[name] = len(data)
                for key, value in data.items():
                    stat["fields"][key] += 1
                    stat["field_types"].setdefault(key, Counter())[type(value).__name__] += 1
                if name == "path_progress.json":
                    stages = data.get("stages")
                    if isinstance(stages, dict):
                        stat["nested"]["stages 节点"] += len(stages)
                        for stage in stages.values():
                            if isinstance(stage, dict) and stage.get("answered_count"):
                                stat["nested"]["有过作答的 stage"] += 1
                    if data.get("current_stage_id"):
                        stat["nested"]["设置了 current_stage_id"] += 1
                if name == "knowledge_state.json":
                    nodes = data.get("nodes")
                    if isinstance(nodes, dict):
                        stat["nested"]["nodes 节点"] += len(nodes)

        result["total_bytes"] += dir_bytes
        result["group_bytes"][group] += dir_bytes
        if has_content:
            result["group_with_content"][group] += 1
        result["per_student"][entry.name] = {"bytes": dir_bytes, "counts": student_counts, "group": group}

    for name in ROOT_ASSETS:
        if (data_dir / name).is_file():
            result["unknown_json"][name] += 1

    return result


def field_rows(stat: dict, limit: int = 14) -> list:
    rows = []
    for key, count in stat["fields"].most_common(limit):
        types = "/".join(sorted(stat["field_types"].get(key, {}).keys()))
        rows.append((key, count, types))
    return rows


def render(result: dict, top: int) -> str:
    lines = []
    add = lines.append
    add("# JSON 数据摸底报表（阶段 0）")
    add("")
    add("- 生成时间：" + result["scanned_at"])
    add("- 数据目录：" + c(result["data_dir"]))
    add("- 生成方式：" + c("python scripts/migrate/report.py") + "（只读，不改任何 JSON / 业务代码）")
    add("")

    if result.get("error"):
        add("> 错误：" + result["error"])
        return "\n".join(lines)

    kinds = result["kinds"]
    total_entries = sum(k["entries_total"] for k in kinds.values())
    total_errors = sum(len(k["parse_errors"]) for k in kinds.values())
    add("## 1. 摘要")
    add("")
    add("| 指标 | 数值 |")
    add("| --- | --- |")
    add("| 学号目录数 | %d |" % result["student_dirs"])
    add("| 业务 JSON 文件数（解析成功） | %d |" % sum(k["files_ok"] for k in kinds.values()))
    add("| 业务 JSON 条目总数 | %d |" % total_entries)
    add("| JSON 解析失败文件 | %d |" % total_errors)
    add("| 历史备份 .bak 文件 | %d（%s） |" % (result["bak_files"], human_bytes(result["bak_bytes"])))
    add("| 非已知 JSON 文件名 | %d 类 |" % len(result["unknown_json"]))
    add("| users 子树总字节 | %s |" % human_bytes(result["total_bytes"]))
    add("")

    add("## 2. 学号目录分类")
    add("")
    add("| 分类 | 目录数 | 含有效数据 | 体积 |")
    add("| --- | --- | --- | --- |")
    for group, count in result["groups"].most_common():
        add(
            "| %s | %d | %d | %s |"
            % (group, count, result["group_with_content"][group], human_bytes(result["group_bytes"][group]))
        )
    add("")
    add("> 含有效数据 = 至少有一个已知 JSON 解析成功且非空。")
    add("")

    add("## 3. 每类 JSON 统计")
    add("")
    add("| 文件 | 含义 | 目标表 | 出现目录 | 非空目录 | 条目总数 | 体积 | 异常 |")
    add("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for name, stat in kinds.items():
        anomalies = (
            len(stat["parse_errors"])
            + len(stat["type_mismatch"])
            + stat["duplicate_ids"]
            + stat["missing_id"]
        )
        add(
            "| %s | %s | %s | %d | %d | %d | %s | %d |"
            % (
                c(name),
                stat["label"],
                c(stat["table"]),
                stat["dirs_with_file"],
                stat["dirs_with_content"],
                stat["entries_total"],
                human_bytes(stat["bytes_total"]),
                anomalies,
            )
        )
    add("")

    add("### 字段并集（按出现次数）")
    add("")
    for name, stat in kinds.items():
        if stat["fields"]:
            add("**%s**（容器 %s）" % (c(name), c(stat["container"])))
            add("")
            add("| 字段 | 出现次数 | 值类型 |")
            add("| --- | --- | --- |")
            for key, count, types in field_rows(stat):
                add("| %s | %d | %s |" % (c(key), count, types))
            if stat["nested"]:
                add("")
                add("嵌套统计：" + "；".join("%s = %d" % (k, v) for k, v in sorted(stat["nested"].items())))
            add("")
        else:
            add("**%s** 无有效数据（未出现或全部解析失败）" % c(name))
            add("")

    add("## 4. 异常清单")
    add("")
    any_issue = False
    for name, stat in kinds.items():
        if stat["parse_errors"]:
            any_issue = True
            add("- **%s 解析失败 %d 个**（迁移必须跳过）：" % (c(name), len(stat["parse_errors"])))
            for item in stat["parse_errors"][:10]:
                add("  - %s：%s" % (c(item["path"]), item["error"]))
            if len(stat["parse_errors"]) > 10:
                add("  - 其余 %d 个见 report.json" % (len(stat["parse_errors"]) - 10))
        if stat["type_mismatch"]:
            any_issue = True
            add("- **%s 容器类型不符 %d 处**：" % (c(name), len(stat["type_mismatch"])))
            for item in stat["type_mismatch"][:5]:
                add("  - %s：期望 %s，实际 %s" % (c(item["path"]), item["expected"], item["actual"]))
        if stat["duplicate_ids"]:
            any_issue = True
            add("- **%s 文件内重复 id %d 条**（入库需主键去重）" % (c(name), stat["duplicate_ids"]))
        if stat["missing_id"]:
            any_issue = True
            add("- **%s 缺 id 的记录 %d 条**（需要生成新 id）" % (c(name), stat["missing_id"]))
        if stat["missing_created_at"] and stat["container"] == "list":
            any_issue = True
            add("- **%s 缺 created_at 的记录 %d 条**（排序/时间线会受影响）" % (c(name), stat["missing_created_at"]))
        if stat["empty_containers"]:
            any_issue = True
            add("- %s 空容器 %d 个（正常空态，迁移时跳过）" % (c(name), len(stat["empty_containers"])))
    if result["bak_files"]:
        any_issue = True
        add("- 历史备份 .bak 共 %d 个（%s），不迁移" % (result["bak_files"], human_bytes(result["bak_bytes"])))
    if result["unknown_json"]:
        any_issue = True
        add("- 非已知 JSON 文件名：")
        for name, count in result["unknown_json"].most_common():
            add("  - %s × %d" % (c(name), count))
    if result["loose_files"]:
        add("- 非 JSON 旁路文件 %d 个（如 .log/.txt），不入库" % len(result["loose_files"]))
    if not any_issue:
        add("- 未发现异常。")
    add("")

    add("## 5. 真实数据学号明细")
    add("")
    watch = [name for name, info in result["per_student"].items() if info["group"] != "learner-*（e2e 随机访客）"]
    watch.sort(key=lambda n: result["per_student"][n]["bytes"], reverse=True)
    if watch:
        columns = list(KNOWN.keys())
        add("| 学号 | 分类 | 体积 | " + " | ".join(c(col) for col in columns) + " |")
        add("| --- | --- | --- | " + " | ".join("---" for _ in columns) + " |")
        for name in watch[: max(top, 20)]:
            info = result["per_student"][name]
            cells = []
            for column in columns:
                value = info["counts"].get(column)
                cells.append("-" if value is None else str(value))
            add("| %s | %s | %s | %s |" % (c(name), info["group"], human_bytes(info["bytes"]), " | ".join(cells)))
        if len(watch) > max(top, 20):
            add("")
            add("> 仅列出体积最大的 %d 个，完整清单见 report.json。" % max(top, 20))
    else:
        add("- 无")
    add("")

    add("## 6. 体积 Top %d" % top)
    add("")
    ranked = sorted(result["per_student"].items(), key=lambda kv: kv[1]["bytes"], reverse=True)
    add("| # | 学号 | 分类 | 体积 |")
    add("| --- | --- | --- | --- |")
    for index, (name, info) in enumerate(ranked[:top], start=1):
        add("| %d | %s | %s | %s |" % (index, c(name), info["group"], human_bytes(info["bytes"])))
    add("")

    add("## 7. 迁移预估（JSON → SQLite）")
    add("")
    add("| 目标表 | 来源 | 预估行数 |")
    add("| --- | --- | --- |")
    add("| student | %s | %d |" % (c("student.json"), kinds["student.json"]["dirs_with_content"]))
    add("| profile_snapshot | %s | %d |" % (c("profiles.json"), kinds["profiles.json"]["entries_total"]))
    add("| resource_item | %s | %d |" % (c("resources.json"), kinds["resources.json"]["entries_total"]))
    add("| quiz_attempt | %s | %d |" % (c("exercise_records.json"), kinds["exercise_records.json"]["entries_total"]))
    add("| learning_event | %s | %d |" % (c("events.json"), kinds["events.json"]["entries_total"]))
    add("| resource_usage | %s | %d |" % (c("usage.json"), kinds["usage.json"]["entries_total"]))
    add(
        "| path_plan / path_step（或 state_json 一列） | %s | %d 个学号 |"
        % (c("path_progress.json"), kinds["path_progress.json"]["dirs_with_content"])
    )
    add(
        "| knowledge_node_state（需新增 DDL） | %s | %d 个学号、%d 个节点 |"
        % (
            c("knowledge_state.json"),
            kinds["knowledge_state.json"]["dirs_with_content"],
            kinds["knowledge_state.json"]["nested"]["nodes 节点"],
        )
    )
    add("")
    add("> 行数为 JSON 条目数上限，实际入库会因重复 id / 缺 id / 脏数据下调。")
    add("")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="JSON 数据摸底报表（阶段 0，只读）")
    parser.add_argument("--data-dir", default=None, help="数据根目录（含 users/）")
    parser.add_argument("--out", default=None, help="报表输出目录，默认同级 <data-dir>-report")
    parser.add_argument("--top", type=int, default=20, help="体积 Top N，默认 20")
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir).resolve() if args.data_dir else default_data_dir().resolve()
    out_dir = Path(args.out).resolve() if args.out else (data_dir.parent / ("%s-report" % data_dir.name))
    out_dir.mkdir(parents=True, exist_ok=True)

    result = scan(data_dir)
    markdown = render(result, args.top)
    report_md = out_dir / "report.md"
    report_json = out_dir / "report.json"
    report_md.write_text(markdown, encoding="utf-8", newline="\n")

    serializable = dict(result)
    serializable["kinds"] = {
        name: {
            **{k: v for k, v in stat.items() if k not in ("fields", "field_types", "nested")},
            "fields": dict(stat["fields"]),
            "field_types": {k: dict(v) for k, v in stat["field_types"].items()},
            "nested": dict(stat["nested"]),
        }
        for name, stat in result["kinds"].items()
    }
    serializable["groups"] = dict(result["groups"])
    serializable["group_bytes"] = dict(result["group_bytes"])
    serializable["group_with_content"] = dict(result["group_with_content"])
    serializable["unknown_json"] = dict(result["unknown_json"])
    report_json.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")

    print("[report] 数据目录: %s" % data_dir)
    print("[report] 学号目录: %d" % result["student_dirs"])
    if result.get("error"):
        print("[report] 错误: %s" % result["error"])
    for name, stat in result["kinds"].items():
        print(
            "[report] %-24s 目录 %3d  条目 %5d  解析失败 %d  体积 %s"
            % (name, stat["dirs_with_file"], stat["entries_total"], len(stat["parse_errors"]), human_bytes(stat["bytes_total"]))
        )
    print("[report] 输出: %s" % report_md)
    print("[report] 输出: %s" % report_json)
    return 0 if not result.get("error") else 2


if __name__ == "__main__":
    sys.exit(main())
