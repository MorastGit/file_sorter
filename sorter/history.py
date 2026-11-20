import json
from datetime import datetime
from pathlib import Path

from .engine import unique_path

BASE_DIR = Path(__file__).resolve().parent.parent
HISTORY_FILE = BASE_DIR / "history.json"

MAX_SESSIONS = 20 





def load_history(path=HISTORY_FILE):
    path = Path(path)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def record_session(moved, path=HISTORY_FILE):
    path = Path(path)
    sessions = load_history(path)
    session = {
        "id": datetime.now().strftime("%Y%m%d-%H%M%S"),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "operations": moved,
    }

    sessions.append(session)
    sessions = sessions[-MAX_SESSIONS:]
    path.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")
    return session["id"]


def undo_last(path=HISTORY_FILE):
    #  откал ласт сорт
    path = Path(path)
    sessions = load_history(path)
    if not sessions:
        return None
    session = sessions.pop()
    result = {"restored": [], "renamed": [], "skipped": []}
    for op in reversed(session.get("operations", [])):
        src, dst = Path(op["from"]), Path(op["to"])


        if not dst.exists():
            # при удалении файла или если он перемещн польщователем 
            result["skipped"].append(str(dst))
            continue
        if src.exists():
            new = unique_path(src)
            dst.rename(new)
            result["renamed"].append(f"{dst} -> {new}")
        else:
            dst.rename(src)
            result["restored"].append(str(src))
    path.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def clear(path=HISTORY_FILE):
    Path(path).write_text("[]", encoding="utf-8")
