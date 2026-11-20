"""Интерактивный консольный диалог (фаза 1). GUI позже вызывает те же модули ядра."""
import time
from pathlib import Path

from . import rules as rules_mod
from . import history as history_mod
from . import log as log_mod
from .engine import execute, plan_sort
from .history import record_session, undo_last
from .log import log_error, log_info, log_move
from .scanner import scan


def choose_profile():
    """Выбор профиля правил rules-*.json при старте (если есть)."""
    profiles = rules_mod.find_profiles()
    if not profiles:
        return rules_mod.RULES_FILE
    print("\nНайдены профили правил:")
    print("  0 — rules.json (по умолчанию)")
    for i, p in enumerate(profiles, 1):
        print(f"  {i} — {p.name}")
    choice = input("Выберите профиль [0]: ").strip()
    if choice.isdigit() and 0 < int(choice) <= len(profiles):
        return profiles[int(choice) - 1]
    return rules_mod.RULES_FILE


def show_rules(config):
    print("\nТекущие правила (расширение -> папка):")
    for rule in config.get("rules", []):
        exts = ", ".join(rule["extensions"])
        print(f"  {rule['name']}: {exts} -> {rule['target']}")


def edit_rules(config, rules_path):
    """Редактор правил: цикл до Enter, удаление по номеру, сброс и набор по умолчанию."""
    while True:
        show_rules(config)
        if not config.get("rules"):
            print("\nПравил нет: файлы без подходящего расширения будут пропускаться.")
        print("\nПравила: 1 — добавить | 2 — удалить (по номеру) | 3 — удалить ВСЕ | 4 — загрузить набор по умолчанию | Enter — назад")
        act = input("> ").strip()
        if act == "":
            break
        elif act == "1":
            name = input("Название правила (например Documents): ").strip() or "Rule"
            exts = input("Расширения через запятую (например pdf, docx): ").strip()
            target = input("Папка назначения (например Documents или /полный/путь): ").strip()
            if not exts:
                print("Расширения не указаны — правило не добавлено.")
                continue
            problems = rules_mod.check_target(target)
            if problems:
                print("Путь назначения не принят:", *problems, sep="\n  ")
                continue
            config = rules_mod.add_rule(config, name, exts, target)
            rules_mod.save(config, rules_path)
            print("Правило добавлено и сохранено.")
        elif act == "2":
            rules_list = config.get("rules", [])
            if not rules_list:
                print("Удалять нечего — правил нет.")
                continue
            for i, r in enumerate(rules_list, 1):
                print(f"  {i} — {r['name']}: {', '.join(r['extensions'])} -> {r['target']}")
            n = input("Номер правила для удаления [Enter — отмена]: ").strip()
            if n.isdigit() and 1 <= int(n) <= len(rules_list):
                removed = rules_list.pop(int(n) - 1)
                rules_mod.save(config, rules_path)
                print(f"Удалено: {removed['name']}.")
            elif n:
                print("Такого номера нет.")
        elif act == "3":
            if not config.get("rules"):
                print("Удалять нечего — правил нет.")
                continue
            ans = input("Удалить ВСЕ правила? [y/N]: ").strip().lower()
            if ans == "y":
                config = rules_mod.clear_rules(config)
                rules_mod.save(config, rules_path)
                print("Все правила удалены. Набор по умолчанию можно вернуть пунктом 4.")
        elif act == "4":
            cur = rules_mod.current_os()
            print(f"Набор по умолчанию для какой ОС? 1 — {cur} (текущая), 2 — macOS, 3 — Windows, 4 — Linux [1]")
            c = input("> ").strip() or "1"
            if c not in {"1", "2", "3", "4"}:
                print("Не понял выбор — отмена.")
                continue
            pick = {"1": None, "2": "macOS", "3": "Windows", "4": "Linux"}[c]
            ans = input("Заменить текущие правила на набор по умолчанию? [y/N]: ").strip().lower()
            if ans == "y":
                config = rules_mod.default_config(pick)
                rules_mod.save(config, rules_path)
                print(f"Загружены и сохранены правила по умолчанию для {pick or cur}.")
                for w in rules_mod.check_paths(config):
                    print(f"  Предупреждение: {w}")
    return config


def ask_sources(config):
    """Папки-источники; пустой ввод -> папка по умолчанию из правил."""
    raw = input("\nПапки для сортировки через запятую (Enter — по умолчанию): ").strip()
    if raw:
        sources = [s.strip() for s in raw.split(",") if s.strip()]
    else:
        sources = [config.get("default_source", "~/Downloads")]
    return [s for s in sources if Path(s).expanduser().is_dir()]


def preview(ops, skipped):
    """Показывает план до реального перемещения."""
    print(f"\nПлан: будет перемещено {len(ops)} файл(ов).")
    by_dir = {}
    for op in ops:
        by_dir.setdefault(str(op["dst_dir"]), 0)
        by_dir[str(op["dst_dir"])] += 1
    for d, n in sorted(by_dir.items()):
        print(f"  {n} -> {d}")
    if skipped:
        print(f"Без правила (будут пропущены): {len(skipped)}: " +
              ", ".join(p.name for p in skipped[:5]) +
              (" ..." if len(skipped) > 5 else ""))


def report_scan_errors(errors):
    """Диагностика: macOS может закрыть папку (Загрузки/Документы) для терминала."""
    if errors:
        print("\nПроблемы доступа:")
        for e in errors:
            print(f"  {e}")
        print("  Подсказка (macOS): Системные настройки → Конфиденциальность и безопасность →")
        print("  Файлы и папки (или «Полный доступ к диску») → разрешите доступ к папке")
        print("  программе Terminal / iTerm / своей IDE и запустите сортировщик заново.")


def sort_once(config, sources, auto=False):
    """Одна сессия сортировки: план -> подтверждение -> перемещение -> журнал."""
    errors = []
    files = scan(sources, config, errors=errors)
    report_scan_errors(errors)
    if not files:
        print("Файлов для сортировки не найдено.")
        return
    ops, skipped = plan_sort(files, sources, config)
    preview(ops, skipped)
    if not ops:
        return
    if not auto:
        answer = input("Переместить? [y/N]: ").strip().lower()
        if answer != "y":
            print("Отменено.")
            return
    moved, errors = execute(ops)
    for op in moved:
        log_move(op["from"], op["to"])
    for err in errors:
        log_error(f"{err['file']}: {err['error']}")
    log_info(f"Сессия: перемещено {len(moved)}, ошибок {len(errors)}, пропущено {len(skipped)}")
    if moved:
        record_session(moved)
    print(f"\nИтог: перемещено {len(moved)}, ошибок {len(errors)}, пропущено без правила {len(skipped)}.")
    for err in errors:
        print(f"  Ошибка: {err['file']} — {err['error']}")


def run_session(files, sources, config, label=""):
    """Перемещение готового списка файлов без подтверждения (для режима наблюдения)."""
    ops, skipped = plan_sort(files, sources, config)
    moved, errors = execute(ops)
    for op in moved:
        log_move(op["from"], op["to"])
    for err in errors:
        log_error(f"{err['file']}: {err['error']}")
    if moved:
        record_session(moved)
    if moved or errors or label:
        print(f"{label}перемещено {len(moved)}, ошибок {len(errors)}, пропущено без правила {len(skipped)}.")
    return moved, skipped


def watch_mode(config):
    """Режим наблюдения: новые файлы сортируются автоматически. Остановка — Ctrl+C."""
    sources = ask_sources(config)
    if not sources:
        print("Папка не найдена.")
        return
    errors = []
    existing = scan(sources, config, errors=errors)
    report_scan_errors(errors)
    watched = ", ".join(str(Path(s).expanduser()) for s in sources)
    print(f"\nНаблюдение за {watched}. Ctrl+C — остановка.")
    if existing:
        print(f"Сейчас в папке {len(existing)} файл(ов).")
        ans = input("1 — отсортировать их сейчас, 2 — следить только за новыми [1]: ").strip() or "1"
        if ans == "1":
            run_session(existing, sources, config, label="Существующие файлы: ")
    else:
        print("Ожидаю новые файлы...")
    seen = set(scan(sources, config))
    try:
        while True:
            time.sleep(3)
            try:
                fresh = [f for f in scan(sources, config) if f not in seen]
                seen.update(fresh)
                if fresh:
                    run_session(fresh, sources, config, label=f"Новых файлов: {len(fresh)}. ")
            except Exception as e:
                # сбой не останавливает наблюдение
                log_error(f"цикл наблюдения: {e}")
                print(f"Ошибка цикла (наблюдение продолжается): {e}")
    except KeyboardInterrupt:
        print("\nРежим наблюдения остановлен.")


def undo():
    result = undo_last()
    if result is None:
        print("Откатывать нечего — история пуста.")
        return
    print(f"\nОткат последней сортировки: возвращено {len(result['restored'])}.")
    for r in result["renamed"]:
        print(f"  Конфликт имени на старом месте: {r}")
    for s in result["skipped"]:
        print(f"  Пропущено (файла нет на месте): {s}")


def cleanup():
    """Ручная очистка журнала log.txt и/или истории отката history.json."""
    log_path, hist_path = log_mod.LOG_FILE, history_mod.HISTORY_FILE
    log_size = log_path.stat().st_size if log_path.exists() else 0
    sessions = len(history_mod.load_history(hist_path))
    print(f"\nСейчас: log.txt — {log_size} байт, history.json — {sessions} сессий.")
    print("1 — очистить журнал log.txt | 2 — очистить историю отката | 3 — оба | Enter — отмена")
    act = input("> ").strip() or ""
    if act not in {"1", "2", "3"}:
        print("Отменено.")
        return
    if act in {"1", "3"}:
        log_mod.clear()
        print("log.txt удалён (начнёт заполняться заново).")
    if act in {"2", "3"}:
        history_mod.clear()
        print("history.json очищена: откат недоступен, пока не пройдёт новая сортировка.")


def main():
    print("=" * 40)
    print("File Sorter — сортировщик файлов")
    print("=" * 40)
    rules_path = choose_profile()
    config = rules_mod.load(rules_path)
    errors = rules_mod.validate(config)
    if errors:
        print("Внимание, проблемы с правилами:", *errors, sep="\n  ")
    warns = rules_mod.check_paths(config)
    if warns:
        print("Предупреждения (эти папки будут созданы при сортировке):", *("  " + w for w in warns), sep="\n")
    while True:
        print("\nМеню: 1 — правила | 2 — сортировать | 3 — наблюдать | 4 — откатить | 5 — очистить лог/историю | 0 — выход")
        choice = input("> ").strip()
        if choice == "1":
            config = edit_rules(config, rules_path)
        elif choice == "2":
            sources = ask_sources(config)
            if sources:
                sort_once(config, sources)
        elif choice == "3":
            watch_mode(config)
        elif choice == "4":
            undo()
        elif choice == "5":
            cleanup()
        elif choice == "0":
            print("Выход.")
            break


if __name__ == "__main__":
    main()
