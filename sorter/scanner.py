"""Рекурсивный поиск файлов в одной или нескольких папках."""
import os
from pathlib import Path

# служебные файлы самой программы тип нелзя сортировать
EXCLUDED_NAMES = {"rules.json", "history.json", "log.txt", "README.md", "DEVLOG.md", ".DS_Store", "desktop.ini"}


def _excluded_dirs(base, config):
    # wелевые папки правил относительные исключаются из сканирования
    dirs = set()
    for rule in config.get("rules", []):
        t = Path(str(rule.get("target", ""))).expanduser()
        if not t.is_absolute():
            dirs.add((base / t).resolve())
    return dirs


def _walk_error(exc, errors):
    #os.walk вызывает  при ошибке доступа
    if errors is not None:
        name = getattr(exc, "filename", None) or "?"
        msg = getattr(exc, "strerror", None) or str(exc)
        errors.append(f"Нет доступа: {name} ({msg})")


def scan(sources, config=None, recursive=True, errors=None):
    # Список файлов из папок-источников.

    # errors — список, куда складываются проблемы доступа

    files = []
    for s in sources:
        base = Path(s).expanduser()
        if not base.is_dir():
            if errors is not None:
                errors.append(f"Папка не найдена: {base}")
            continue
        excluded = _excluded_dirs(base, config) if config else set()
        if recursive:
            for root, dirs, names in os.walk(base, onerror=lambda e: _walk_error(e, errors)):
                rootp = Path(root)
                keep = []
                for d in dirs:
                    if d.startswith(".") or d == "__pycache__":
                        continue
                    if excluded and (rootp / d).resolve() in excluded:
                        continue
                    keep.append(d)
                dirs[:] = keep
                for name in names:
                    if name in EXCLUDED_NAMES or name.startswith("rules-"):
                        continue
                    files.append(rootp / name)
        else:
            try:
                entries = list(base.iterdir())
            except PermissionError as e:
                if errors is not None:
                    errors.append(f"Нет доступа: {base} ({e.strerror})")
                continue
            for p in entries:
                if p.is_file() and p.name not in EXCLUDED_NAMES and not p.name.startswith("rules-"):
                    files.append(p)
    return files
