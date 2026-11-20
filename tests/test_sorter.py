import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sorter import engine, history, log, rules, scanner  # noqa: E402


def make_config():
    return {
        "default_source": "~/Downloads",
        "rules": [{"name": "Docs", "extensions": [".pdf"], "target": "Docs"}],
    }


# --- rules.py ---

def test_load_creates_default(tmp_path):
    cfg = rules.load(tmp_path / "rules.json")
    assert cfg["rules"]  # шаблон по умолчанию создан
    assert (tmp_path / "rules.json").exists()


def test_normalize_extensions(tmp_path):
    cfg = {"rules": [{"name": "A", "extensions": ["PDF", " .txt "], "target": "T"}]}
    rules.save(cfg, tmp_path / "rules.json")
    saved = rules.load(tmp_path / "rules.json")
    assert saved["rules"][0]["extensions"] == [".pdf", ".txt"]


def test_validate_missing_fields(tmp_path):
    assert rules.validate({"rules": [{"name": "A", "extensions": [".pdf"], "target": "T"}]}) == []
    assert rules.validate({"rules": [{"name": "", "extensions": [], "target": ""}]}) != []


def test_add_rule(tmp_path):
    cfg = make_config()
    cfg = rules.add_rule(cfg, "Pics", "png, jpg", "Images")
    assert {"name": "Pics", "extensions": [".png", ".jpg"], "target": "Images"} in cfg["rules"]


def test_clear_and_default(tmp_path):
    cfg = rules.add_rule(make_config(), "X", "zip", "Z")
    rules.clear_rules(cfg)
    assert cfg["rules"] == []
    d1, d2 = rules.default_config(), rules.default_config()
    assert d1 == d2 and d1 is not d2  # свежая копия, а не ссылка
    assert rules.validate(d1) == []


def test_default_config_os_specific():
    mac = rules.default_config("macOS")
    win = rules.default_config("Windows")
    lin = rules.default_config("Linux")
    targets = lambda c: {r["name"]: r["target"] for r in c["rules"]}
    assert targets(mac)["Video"] == "~/Movies"
    assert targets(win)["Video"] == "~/Videos"
    assert targets(lin)["Video"] == "~/Videos"
    assert targets(mac)["Images"] == "~/Pictures"
    assert rules.current_os() in {"macOS", "Windows", "Linux"}


def test_check_paths_warns_on_missing(tmp_path):
    cfg = make_config()
    cfg["default_source"] = str(tmp_path)  # цель "Docs" относительная — не проверяется
    assert rules.check_paths(cfg) == []
    cfg2 = {"default_source": str(tmp_path), "rules": [{"name": "A", "extensions": [".pdf"], "target": str(tmp_path / "missing")}]}
    warns = rules.check_paths(cfg2)
    assert any("missing" in w for w in warns)
    (tmp_path / "missing").mkdir()
    assert rules.check_paths(cfg2) == []


def test_check_target_valid():
    assert rules.check_target("Documents") == []
    assert rules.check_target("Docs/Sub") == []
    assert rules.check_target("/Users/x/Docs") == []
    assert rules.check_target("C:\\Users\\Docs") == []


def test_check_target_invalid():
    assert rules.check_target("") == ["путь не указан"]
    assert rules.check_target("../outside")
    assert rules.check_target("Docs/../..")
    assert rules.check_target("a|b")
    assert rules.check_target("Docs: extra")
    assert rules.check_target("my doc.")


def test_validate_checks_target():
    cfg = {"rules": [{"name": "A", "extensions": [".pdf"], "target": "../up"}]}
    assert any(".." in e for e in rules.validate(cfg))


def test_check_target_root_path_rejected():
    #'/Documents' и 'C:\Documents' — read-only корень, вероятна потерянная '~'
    assert rules.check_target("/Documents")
    assert rules.check_target("C:\\Documents")
    assert rules.check_target("~/Documents") == []          # правильный вид — ок
    assert rules.check_target("/Users/elena/Documents") == []


def test_check_target_tilde_typo():
    assert rules.check_target("~Documents")                  # опечатка без '/'


def test_execute_refuses_root_target(tmp_path):
    src = tmp_path / "a.pptx"
    src.write_text("x")
    ops = [{"src": src, "dst_dir": "/Documents", "rule": "Documents"}]
    moved, errors = engine.execute(ops)
    assert not moved and errors
    assert src.exists()  # файл остался на месте


# --- engine.py ---

def test_match_rule_case_insensitive(tmp_path):
    cfg = make_config()
    f = tmp_path / "doc.PDF"
    f.touch()
    assert engine.match_rule(f, cfg)["name"] == "Docs"
    assert engine.match_rule(tmp_path / "x.zip", cfg) is None


def test_execute_moves_and_creates_dirs(tmp_path):
    src = tmp_path / "a.pdf"
    src.write_text("x")
    ops = [{"src": src, "dst_dir": tmp_path / "Docs", "rule": "Docs"}]
    moved, errors = engine.execute(ops)
    assert not errors
    assert (tmp_path / "Docs" / "a.pdf").exists()
    assert moved[0]["from"].endswith("a.pdf")


def test_conflict_suffix_no_overwrite(tmp_path):
    d = tmp_path / "Docs"
    d.mkdir()
    (d / "a.pdf").write_text("old")
    ops = [{"src": tmp_path / "a.pdf", "dst_dir": d, "rule": "Docs"}]
    tmp_path.joinpath("a.pdf").write_text("new")
    moved, errors = engine.execute(ops)
    assert not errors
    assert (d / "a (1).pdf").read_text() == "new"
    assert (d / "a.pdf").read_text() == "old"


# --- scanner.py ---

def test_scan_missing_dir_reported(tmp_path):
    errors = []
    files = scanner.scan([tmp_path / "nope"], errors=errors)
    assert files == []
    assert errors and "не найдена" in errors[0]


def test_scan_excludes_targets_and_service_files(tmp_path):
    base = tmp_path / "src"
    (base / "Docs").mkdir(parents=True)
    (base / "Docs" / "old.pdf").touch()      # уже в целевой папке — не сканируем
    (base / "new.pdf").touch()
    (base / "history.json").touch()          # служебный файл
    (base / ".hidden" / "h.pdf").mkdir(parents=True, exist_ok=True)
    (base / ".hidden" / "h.pdf").touch()
    cfg = make_config()
    files = scanner.scan([base], cfg)
    names = [p.name for p in files]
    assert names == ["new.pdf"]


# --- history.py ---

def test_record_and_undo(tmp_path):
    hist = tmp_path / "history.json"
    src = tmp_path / "a.pdf"
    src.write_text("x")
    dst = tmp_path / "Docs" / "a.pdf"
    dst.parent.mkdir()
    src.rename(dst)
    history.record_session([{"from": str(src), "to": str(dst), "rule": "Docs"}], hist)
    result = history.undo_last(hist)
    assert src.exists() and not dst.exists()
    assert result["restored"] == [str(src)]


def test_undo_conflict_renames(tmp_path):
    hist = tmp_path / "history.json"
    src = tmp_path / "a.pdf"
    dst = tmp_path / "Docs" / "a.pdf"
    dst.parent.mkdir()
    src.write_text("old")
    src.rename(dst)
    src.write_text("new")  # на старом месте появился другой файл с тем же именем
    history.record_session([{"from": str(src), "to": str(dst), "rule": "Docs"}], hist)
    result = history.undo_last(hist)
    assert (tmp_path / "a (1).pdf").exists() and (tmp_path / "a (1).pdf").read_text() == "old"


def test_undo_skips_missing(tmp_path):
    hist = tmp_path / "history.json"
    history.record_session([{"from": str(tmp_path / "a.pdf"), "to": str(tmp_path / "Docs" / "a.pdf"), "rule": "Docs"}], hist)
    result = history.undo_last(hist)
    assert result["skipped"]


def test_undo_empty_history(tmp_path):
    assert history.undo_last(tmp_path / "no.json") is None


def test_history_rotation(tmp_path):
    hist = tmp_path / "history.json"
    op = [{"from": str(tmp_path / "a"), "to": str(tmp_path / "b"), "rule": "R"}]
    for i in range(25):
        history.record_session(op, hist)
    sessions = history.load_history(hist)
    assert len(sessions) == history.MAX_SESSIONS  # старые сессии вытесняются
    assert history.undo_last(hist) is not None    # последняя — доступна для отката


def test_history_clear(tmp_path):
    hist = tmp_path / "history.json"
    history.record_session([], hist)
    history.clear(hist)
    assert history.load_history(hist) == []
    assert history.undo_last(hist) is None


# --- log.py ---

def test_log_moves_written(tmp_path):
    lf = tmp_path / "log.txt"
    log.log_move("a.pdf", "Docs/a.pdf", lf)
    log.log_error("файл занят", lf)
    text = lf.read_text(encoding="utf-8")
    assert "MOVE: a.pdf -> Docs/a.pdf" in text
    assert "ERROR: файл занят" in text


def test_log_rotation(tmp_path):
    lf = tmp_path / "log.txt"
    for i in range(1100):
        log.log_info(f"строка {i}", lf)
    lines = lf.read_text(encoding="utf-8").splitlines()
    assert log.KEEP_LINES < len(lines) <= log.MAX_LINES  # обрезка сработала на >1000
    assert lines[-1].endswith("строка 1099")             # самая свежая на месте


def test_log_clear(tmp_path):
    lf = tmp_path / "log.txt"
    log.log_info("x", lf)
    log.clear(lf)
    assert not lf.exists()
