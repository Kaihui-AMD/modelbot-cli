import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from modelbot_cli.precheck import check_local, patch_paths  # noqa: E402
from modelbot_cli.render import leaderboard_report, result_report, status_line  # noqa: E402

PATCHES = HERE / "fixtures"
ALLOWED = ["ggml/", "src/"]


def test_test_patches():
    assert check_local(PATCHES / "noop.patch", ALLOWED, 1 << 20).ok
    assert check_local(PATCHES / "hang.patch", ALLOWED, 1 << 20).files == ["src/llama.cpp"]
    bad = check_local(PATCHES / "forbidden-path.patch", ALLOWED, 1 << 20)
    assert not bad.ok and "tools/llama-bench/llama-bench.cpp" in bad.problems[0]
    assert not check_local(PATCHES / "noop.patch", ALLOWED, 10).ok


def test_rename_symlink_binary_headers():
    text = ("diff --git a/src/a.cpp b/tools/a.cpp\nsimilarity index 100%\nrename from src/a.cpp\nrename to tools/a.cpp\n"
            "diff --git a/ggml/l b/ggml/l\nnew file mode 120000\n"
            "diff --git a/src/b.bin b/src/b.bin\nGIT binary patch\n")
    paths, problems = patch_paths(text)
    assert "tools/a.cpp" in paths and "src/a.cpp" in paths
    assert any("symlinks" in p for p in problems) and any("binary" in p for p in problems)


def test_not_a_git_patch(tmp_path):
    p = tmp_path / "x.patch"
    p.write_text("--- a.c\n+++ a.c\n@@ -1 +1 @@\n-a\n+b\n")
    res = check_local(p, ALLOWED, 1 << 20)
    assert not res.ok and "git diff" in res.problems[0]


RESULT = {
    "id": 5, "problem": "llamacpp-navi3-p1", "version": "v1", "mode": "leaderboard", "status": "succeeded",
    "reason": "below_vulkan", "message": None,
    "result": {"outcome": "succeeded", "passed": True, "qualified": False, "message": "not faster on: a",
               "score": {"value": 0.8552},
               "environment": {"gpu_name": "AMD Radeon Pro W7900D", "gpu_arch": "gfx1100"},
               "gates": [{"name": "patch", "passed": True, "items": []},
                         {"name": "build", "passed": True, "duration_s": 3.9, "items": []},
                         {"name": "accuracy", "passed": True, "duration_s": 462.0, "items": [
                             {"name": "fa0_c32768", "value": 6.1282, "baseline": 6.1282, "ratio": 1.0, "passed": True}]},
                         {"name": "performance", "passed": False, "duration_s": 320.0, "items": [
                             {"name": "tg128-d2048-fa0", "value": 30.27, "baseline": 34.21, "ratio": 0.885,
                              "passed": False, "cv": 0.003}]}]}}


def test_result_report():
    text = result_report(RESULT)
    assert "accuracy     passed" in text and "fa0_c32768" in text and "x0.885  slower" in text
    assert "score 0.8552" in text and "ran on AMD Radeon Pro W7900D (gfx1100)" in text
    assert "not faster than Vulkan on every item" in text and "run:" not in text


def test_disqualified_marks():
    sub = {**RESULT, "disqualified_at": "2026-11-20T08:00:00+00:00", "disqualified_reason": "copied a patch"}
    assert "disqualified by the organizers: copied a patch (not on the leaderboard)" in result_report(sub)
    assert status_line(sub) == "submission 5 [leaderboard] evaluated (disqualified)"
    assert "disqualified" not in result_report(RESULT) and "disqualified" not in status_line(RESULT)


def test_leaderboard_report():
    board = {"problem": "p", "version": "v", "benchmarks": [{"name": "tg128-d2048-fa0"}],
             "qualified": [{"rank": 1, "user": "alice", "score": 1.1, "cv": 0.01,
                            "items": [{"name": "tg128-d2048-fa0", "value": 37.6}]}],
             "accuracy_passed": []}
    text = leaderboard_report(board)
    assert "alice" in text and "1.1000" in text and "37.60" in text and "(none)" in text
