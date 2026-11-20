"""Машиночитаемый журнал операций (history.json) — основа отката."""
import json
from datetime import datetime
from pathlib import Path

from .engine import unique_path

BASE_DIR = Path(__file__).resolve().parent.parent
HISTORY_FILE = BASE_DIR / "history.json"

MAX_SESSIONS = 20  # сколько последних сессий храним (откату нужна только последняя)


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
    """Каждая сессия сортировки — атомарная транзакция «откуда → куда».

    Ротация: хранятся только последние MAX_SESSIONS сессий.
    """
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
    """Откат последней сортировки. Файлы не перезаписываются: конфликт — суффикс ' (1)'."""
    path = Path(path)
    sessions = load_history(path)
    if not sessions:
        return None
    session = sessions.pop()
    result = {"restored": [], "renamed": [], "skipped": []}
    for op in reversed(session.get("operations", [])):
        src, dst = Path(op["from"]), Path(op["to"])
        if not dst.exists():
            # файл удалён/перемещён вручную — пропускаем с предупреждением
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
    """Полная очистка истории (откат будет недоступен, пока не пройдёт новая сортировка)."""
    Path(path).write_text("[]", encoding="utf-8")
