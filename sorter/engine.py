"""Ядро сортировки: сопоставление файла с правилом и перемещение.

Модуль не знает ни про консоль, ни про GUI — его вызывают оба интерфейса.
"""
import shutil
from pathlib import Path


def match_rule(file_path, config):
    """Возвращает правило по расширению (регистронезависимо) или None."""
    ext = Path(file_path).suffix.lower()
    if not ext:
        return None
    for rule in config.get("rules", []):
        if ext in rule.get("extensions", []):
            return rule
    return None


def resolve_target(rule, base_dir):
    """Абсолютный путь цели: абсолютный target как есть, относительный — от папки-источника."""
    t = Path(str(rule["target"])).expanduser()
    if not t.is_absolute():
        t = Path(base_dir) / t
    return t


def unique_path(dst):
    """Конфликт имён: не перезаписывать, добавлять суффикс ' (1)', ' (2)' и т.д."""
    if not dst.exists():
        return dst
    stem, suffix = dst.stem, dst.suffix
    i = 1
    while True:
        cand = dst.with_name(f"{stem} ({i}){suffix}")
        if not cand.exists():
            return cand
        i += 1


def plan_sort(files, sources, config):
    """План сортировки: [{src, dst_dir, rule}] + файлы без правила."""
    bases = [Path(s).expanduser().resolve() for s in sources]
    ops, skipped = [], []
    for f in files:
        f = Path(f)
        rule = match_rule(f, config)
        if rule is None:
            skipped.append(f)
            continue
        base = next((b for b in bases if b == f.resolve() or b in f.resolve().parents), f.parent)
        ops.append({"src": f, "dst_dir": resolve_target(rule, base), "rule": rule.get("name", "")})
    return ops, skipped


def unsafe_target(dst_dir):
    """Путь первого уровня от корня ('/', '/Documents', 'C:\\') — туда нельзя писать."""
    p = Path(dst_dir)
    return p.is_absolute() and len(p.parts) <= 2


def execute(ops):
    """Выполняет перемещения. Возвращает (перемещено, ошибки). Ошибки не прерывают работу."""
    moved, errors = [], []
    for op in ops:
        src, dst_dir = Path(op["src"]), Path(op["dst_dir"])
        if unsafe_target(dst_dir):
            # защита от испорченных правил: корень ФС read-only (macOS) или опасен
            msg = f"небезопасная цель '{dst_dir}' (путь первого уровня от корня) — перемещение отклонено"
            errors.append({"file": str(src), "error": msg})
            continue
        try:
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst = unique_path(dst_dir / src.name)
            shutil.move(str(src), str(dst))
            moved.append({"from": str(src), "to": str(dst), "rule": op.get("rule", "")})
        except Exception as e:  # файл занят, нет прав и т.п. — пишем и продолжаем
            errors.append({"file": str(src), "error": str(e)})
    return moved, errors
