"""并发写验收：20 个线程同时写事件 + 20 个线程同时追加错题，确认不再出现「读-改-写」覆盖丢失。

用法（在 backend 目录或任意位置均可）：
    python scripts/verify/concurrency_check.py sqlite <data-dir>
    python scripts/verify/concurrency_check.py json   <data-dir>

JSON 后端是改造前的对照基线：events.json / exercise_records.json 走「读全量→追加→覆写」，
并发下会互相覆盖；SQLite 后端的 append_quiz_record 是单条 INSERT，事件也是单条 INSERT。
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parents[1]
BACKEND_DIR = PROJECT_DIR / "backend"


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    mode, data_dir = sys.argv[1], Path(sys.argv[2])

    # scripts/verify/ -> scripts -> 01_主工程 -> ICT -> <workspace>，运行时目录在 workspace/_runtime
    workspace = SCRIPT_DIR.parents[3]
    runtime = Path(os.environ.get("ICT_RUNTIME_DIR") or (workspace / "_runtime"))
    tmp = runtime / "tmp"
    logs = runtime / "logs"
    tmp.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)

    os.environ["DATA_DIR"] = str(data_dir)
    os.environ["STORAGE_BACKEND"] = mode
    os.environ["DEMO_MODE"] = "true"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["TMP"] = str(tmp)
    os.environ["TEMP"] = str(tmp)
    os.environ["LOG_DIR"] = str(logs)
    for path in (str(PROJECT_DIR), str(BACKEND_DIR)):
        if path not in sys.path:
            sys.path.insert(0, path)

    import app.core.config as cfg

    cfg.settings.data_dir = str(data_dir)
    cfg.settings.storage_backend = mode

    from app import repo

    student = "concurrency-check"
    total = 20
    errors: list[str] = []

    def write_event(index: int) -> None:
        try:
            repo.insert_learning_event(student, "concurrency_probe", {"seq": index})
        except Exception as exc:  # noqa: BLE001
            errors.append(f"event {index}: {exc!r}")

    def write_quiz(index: int) -> None:
        try:
            repo.append_quiz_record(
                student,
                {"id": f"probe-{index}", "type": "choice", "stem": f"probe {index}", "correct": True},
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"quiz {index}: {exc!r}")

    threads = [threading.Thread(target=write_event, args=(i,)) for i in range(total)]
    threads += [threading.Thread(target=write_quiz, args=(i,)) for i in range(total)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    events = [item for item in repo.get_user_events(student) if item.get("event_type") == "concurrency_probe"]
    quizzes = repo.list_quiz_records(student)
    print(f"backend={mode} events={len(events)}/{total} quizzes={len(quizzes)}/{total} errors={len(errors)}")
    for line in errors[:5]:
        print("  ERR", line)
    return 0 if len(events) == total and len(quizzes) == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
