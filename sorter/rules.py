
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RULES_FILE = BASE_DIR / "rules.json"

_HOME_FOLDERS = {
    "darwin": {"docs": "~/Documents", "img": "~/Pictures", "music": "~/Music", "video": "~/Movies"},
    "win32": {"docs": "~/Documents", "img": "~/Pictures", "music": "~/Music", "video": "~/Videos"},
    "linux": {"docs": "~/Documents", "img": "~/Pictures", "music": "~/Music", "video": "~/Videos"},
}


def current_os():
    if sys.platform == "darwin":
        return "macOS"
    if sys.platform.startswith("win"):
        return "Windows"
    return "Linux"


def default_config(os_name=None):
    key = {"macOS": "darwin", "Windows": "win32", "Linux": "linux"}.get(os_name) or (
        "darwin" if sys.platform == "darwin" else "win32" if sys.platform.startswith("win") else "linux"
    )

    f = _HOME_FOLDERS[key]
    return {
        "default_source": "~/Downloads",
        "rules": [
            {"name": "Documents", "extensions": [".pdf", ".docx", ".doc", ".txt", ".xlsx", ".pptx"], "target": f["docs"]},
            {"name": "Images", "extensions": [".png", ".jpg", ".jpeg", ".gif", ".webp"], "target": f["img"]},
            {"name": "Music", "extensions": [".mp3", ".wav", ".flac"], "target": f["music"]},
            {"name": "Video", "extensions": [".mp4", ".avi", ".mkv"], "target": f["video"]},
            {"name": "Archives", "extensions": [".zip", ".rar", ".7z"], "target": "Archives"},
            {"name": "Code", "extensions": [".py", ".js", ".html", ".css"], "target": "Code"},
        ],
    }


def normalize(config):
    #  получитс расширение в нуж формате
    for rule in config.get("rules", []):
        rule["extensions"] = [
            ("." + e.strip().lower().lstrip(".")) for e in rule.get("extensions", []) if e.strip()
        ]
    return config


def validate(config):
    #  гет список ошибок конфигов
    errors = []
    if not isinstance(config.get("rules"), list):
        return ["В rules.json нет списка 'rules'."]
    for i, rule in enumerate(config["rules"], 1):
        for key in ("name", "extensions", "target"):
            if not rule.get(key):
                errors.append(f"Правило #{i}: отсутствует поле '{key}'.")
        if rule.get("target"):
            for p in check_target(rule["target"]):
                errors.append(f"Правило #{i} ('{rule.get('name', '')}'): путь назначения — {p}")
    return errors



_INVALID_CHARS = set('<>"|?*')


def check_target(target):
    # проверка пути назначения гет список пустой ок
    t = str(target).strip()
    if not t:
        return ["путь не указан"]
    if "\x00" in t:
        return ["путь содержит недопустимый символ (NUL)"]
    
    # пути винды
    p = Path(t.replace("\\", "/"))
    if ".." in p.parts:
        return ["путь не должен содержать '..' (выход за пределы папки-источника)"]
    problems = []



    if p.parts and p.parts[0].startswith("~") and p.parts[0] != "~":
        problems.append(f"похоже на опечатку: '{p.parts[0]}' — домашняя папка пишется как '~/имя', например ~/Documents")


    # абсолютный путь 1 уровня ридонли корень
    # на маке и винде в него нельзя ~
    first = p.parts[0] if p.parts else ""
    windows_root = len(p.parts) == 2 and len(first) == 2 and first[0].isalpha() and first[1] == ":"
    if (p.is_absolute() and len(p.parts) <= 2) or windows_root:
        problems.append(f"цель — путь первого уровня от корня ({t}): системный корень только для чтения; если хотели домашнюю папку — напишите с '~' в начале, например ~/Documents")
    for i, part in enumerate(p.parts):
        bad = _INVALID_CHARS & set(part)

        # буквп диска на винду
        is_drive = i == 0 and len(part) == 2 and part[0].isalpha() and part.endswith(":")
        if ":" in part and not is_drive:
            bad |= {":"}
        if bad:
            problems.append(f"недопустимые символы {''.join(sorted(bad))} в части '{part}'")
        if not is_drive and (part.endswith(" ") or part.endswith(".")):
            problems.append(f"часть '{part}' не должна заканчиваться пробелом или точкой (сломается на Windows)")
    return problems


def load(path=RULES_FILE):
    path = Path(path)
    if not path.exists():
        cfg = default_config()
        save(cfg, path)
        return cfg
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
        
    except (json.JSONDecodeError, OSError):
        # повреждённый файл откатывает к шаблону ос
        cfg = default_config()
        save(cfg, path)
        return cfg
    return normalize(config)


def save(config, path=RULES_FILE):
    path = Path(path)
    path.write_text(json.dumps(normalize(config), ensure_ascii=False, indent=2), encoding="utf-8")


def clear_rules(config):
    config["rules"] = []
    return config


def add_rule(config, name, extensions, target):
    # доп правило расширения строкой через запятую /списком
    if isinstance(extensions, str):
        extensions = [e for e in extensions.replace(",", " ").split()]
    config.setdefault("rules", []).append(
        {"name": name, "extensions": extensions, "target": target}
    )
    return normalize(config)


def check_paths(config):
    warns = []
    src = Path(str(config.get("default_source", ""))).expanduser()
    if not src.is_dir():
        warns.append(f"папка по умолчанию не существует: {src}")
    for rule in config.get("rules", []):
        t = Path(str(rule.get("target", ""))).expanduser()
        if t.is_absolute() and not t.is_dir():
            warns.append(f"правило '{rule.get('name', '')}': папки нет и будет создана: {t}")
    return warns


def find_profiles():
    #  гесли есть кастомные свои 
    return sorted(RULES_FILE.parent.glob("rules-*.json"))
