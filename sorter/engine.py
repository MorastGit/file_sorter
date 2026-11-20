
import shutil
from pathlib import Path


# гет правило по расширению файла нон регистр
def match_rule(file_path, config):
    ext = Path(file_path).suffix.lower()
    if not ext:
        return None
    for rule in config.get("rules", []):
        if ext in rule.get("extensions", []):
            return rule
    return None


 # гет путь назначения по правилу и базовой папке
def resolve_target(rule, base_dir):
    t = Path(str(rule["target"])).expanduser()
    if not t.is_absolute():
        t = Path(base_dir) / t
    return t


# обрбаотчник конфликта имен
def unique_path(dst):
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


# проверка на опасность перемещения в корень ФС макос ридонли 
def unsafe_target(dst_dir):
    p = Path(dst_dir)
    return p.is_absolute() and len(p.parts) <= 2




#  само перемещение
def execute(ops):
    moved, errors = [], []
    for op in ops:
        src, dst_dir = Path(op["src"]), Path(op["dst_dir"])


        # защита от говноправил
        if unsafe_target(dst_dir):
            msg = f"небезопасная цель '{dst_dir}' (путь первого уровня от корня) — перемещение отклонено"
            errors.append({"file": str(src), "error": msg})
            continue
        try:
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst = unique_path(dst_dir / src.name)
            shutil.move(str(src), str(dst))
            moved.append({"from": str(src), "to": str(dst), "rule": op.get("rule", "")})
        
        except Exception as e:  # файл занят  нет прав и тд
            errors.append({"file": str(src), "error": str(e)})
    return moved, errors
