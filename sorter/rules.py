"""Загрузка/сохранение правил сортировки (rules.json) + шаблон по умолчанию."""
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RULES_FILE = BASE_DIR / "rules.json"

# Системные папки «Документы/Картинки/Музыка/Видео» в каждой ОС свои.
# Цели — домашние папки пользователя: они уже существуют, поэтому при первом
# запуске не создаётся куча новых папок.
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
    """Свежая копия набора правил по умолчанию для ОС.

    os_name: None — для текущей ОС, либо "macOS" / "Windows" / "Linux".
    Папки «Archives» и «Code» в системах нет, поэтому они остаются
    относительными и создаются внутри папки-источника.
    """
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
    """Приводит расширения к виду с точкой, в нижнем регистре."""
    for rule in config.get("rules", []):
        rule["extensions"] = [
            ("." + e.strip().lower().lstrip(".")) for e in rule.get("extensions", []) if e.strip()
        ]
    return config


def validate(config):
    """Возвращает список ошибок конфигурации (пустой список = всё хорошо)."""
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


# символы, недопустимые в путях Windows (кроме 'C:' в начале) — проверяем для кроссплатформенности
_INVALID_CHARS = set('<>"|?*')


def check_target(target):
    """Проверка пути назначения. Возвращает список проблем (пустой = путь корректен)."""
    t = str(target).strip()
    if not t:
        return ["путь не указан"]
    if "\x00" in t:
        return ["путь содержит недопустимый символ (NUL)"]
    # Windows-пути ('C:\Users\Docs') проверяем в POSIX-виде
    p = Path(t.replace("\\", "/"))
    if ".." in p.parts:
        return ["путь не должен содержать '..' (выход за пределы папки-источника)"]
    problems = []
    # домашняя папка пишется как '~/Documents'; '~Documents' — опечатка, не раскроется
    if p.parts and p.parts[0].startswith("~") and p.parts[0] != "~":
        problems.append(f"похоже на опечатку: '{p.parts[0]}' — домашняя папка пишется как '~/имя', например ~/Documents")
    # абсолютный путь первого уровня ('/Documents', 'C:\Documents') — read-only корень
    # на macOS/Windows, в него нельзя писать; вероятна потерянная '~'
    first = p.parts[0] if p.parts else ""
    windows_root = len(p.parts) == 2 and len(first) == 2 and first[0].isalpha() and first[1] == ":"
    if (p.is_absolute() and len(p.parts) <= 2) or windows_root:
        problems.append(f"цель — путь первого уровня от корня ({t}): системный корень только для чтения; если хотели домашнюю папку — напишите с '~' в начале, например ~/Documents")
    for i, part in enumerate(p.parts):
        bad = _INVALID_CHARS & set(part)
        # 'C:' допустим только как первый компонент (буква диска на Windows)
        is_drive = i == 0 and len(part) == 2 and part[0].isalpha() and part.endswith(":")
        if ":" in part and not is_drive:
            bad |= {":"}
        if bad:
            problems.append(f"недопустимые символы {''.join(sorted(bad))} в части '{part}'")
        if not is_drive and (part.endswith(" ") or part.endswith(".")):
            problems.append(f"часть '{part}' не должна заканчиваться пробелом или точкой (сломается на Windows)")
    return problems


def load(path=RULES_FILE):
    """Загружает правила; если файла нет — создаёт набор по умолчанию для текущей ОС."""
    path = Path(path)
    if not path.exists():
        cfg = default_config()
        save(cfg, path)
        return cfg
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # повреждённый файл — откатываемся к шаблону для текущей ОС
        cfg = default_config()
        save(cfg, path)
        return cfg
    return normalize(config)


def save(config, path=RULES_FILE):
    path = Path(path)
    path.write_text(json.dumps(normalize(config), ensure_ascii=False, indent=2), encoding="utf-8")


def clear_rules(config):
    """Удаляет все правила (папка по умолчанию остаётся)."""
    config["rules"] = []
    return config


def add_rule(config, name, extensions, target):
    """Добавляет правило (расширения — строкой через запятую или списком)."""
    if isinstance(extensions, str):
        extensions = [e for e in extensions.replace(",", " ").split()]
    config.setdefault("rules", []).append(
        {"name": name, "extensions": extensions, "target": target}
    )
    return normalize(config)


def check_paths(config):
    """Предупреждения о папках, которых нет: они будут созданы при первой сортировке.

    Проверяются только абсолютные/домашние цели (~/...): относительные создаются
    внутри папки-источника по самой идее сортировки.
    """
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
    """Ищет файлы профилей rules-*.json рядом с rules.json."""
    return sorted(RULES_FILE.parent.glob("rules-*.json"))
