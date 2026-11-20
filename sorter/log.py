
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_FILE = BASE_DIR / "log.txt"

MAX_LINES = 1000  
KEEP_LINES = 500   


def _trim(path):
    # обрезка логов
    try:
        if path.stat().st_size == 0:
            return
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > MAX_LINES:
            with path.open("w", encoding="utf-8") as f:
                f.writelines(lines[-KEEP_LINES:])
    except OSError:
        pass


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
    Path(path).unlink(missing_ok=True)
