"""Человекочитаемый журнал log.txt: что, куда и когда перемещено.

Ротация: при превышении MAX_LINES файл обрезается до последних KEEP_LINES строк.
"""
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_FILE = BASE_DIR / "log.txt"

MAX_LINES = 1000   # лимит строк журнала
KEEP_LINES = 500   # сколько последних строк оставляем после обрезки


def _trim(path):
    """Обрезка журнала: больше MAX_LINES -> остаются последние KEEP_LINES."""
    try:
        if path.stat().st_size == 0:
            return
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > MAX_LINES:
            with path.open("w", encoding="utf-8") as f:
                f.writelines(lines[-KEEP_LINES:])
    except OSError:
        pass  # проблемы с обрезкой не должны ломать запись


def _write(msg, path=LOG_FILE):
    path = Path(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n")
    _trim(path)


def log_move(src, dst, path=LOG_FILE):
    _write(f"MOVE: {src} -> {dst}", path)


def log_error(msg, path=LOG_FILE):
    _write(f"ERROR: {msg}", path)


def log_info(msg, path=LOG_FILE):
    _write(msg, path)


def clear(path=LOG_FILE):
    """Удаляет журнал целиком."""
    Path(path).unlink(missing_ok=True)
