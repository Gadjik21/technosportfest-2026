from app.modules.contests import judge


def test_judge_stops_at_first_failed_case_and_tracks_limits(tmp_path, monkeypatch):
    monkeypatch.setenv("JUDGE_WORKDIR", str(tmp_path))
    calls = []
    results = iter([
        judge.RunResult(0, "3\r\n", "", 12, 900, False, False, False),
        judge.RunResult(0, "wrong\n", "", 15, 1100, False, False, False),
    ])

    def fake_run(image, command, work_dir, *, writable, memory_mb, timeout_seconds, stdin=""):
        calls.append((image, command, writable, memory_mb, timeout_seconds, stdin))
        return next(results)

    monkeypatch.setattr(judge, "_run_container", fake_run)
    result = judge.judge_code("python", "print(3)", [("1 2\n", "3\n"), ("4 5\n", "9\n"), ("6 7\n", "13\n")], 15, 128)
    assert result.verdict == "wrong_answer"
    assert result.failed_test_index == 2
    assert result.time_ms == 27
    assert result.memory_kb == 1100
    assert len(calls) == 2  # The third hidden case was never executed.
    assert all(not call[2] and call[3:5] == (128, 15) for call in calls)
    assert [call[5] for call in calls] == ["1 2\n", "4 5\n"]
    assert list(tmp_path.iterdir()) == []


def test_judge_compiles_with_separate_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("JUDGE_WORKDIR", str(tmp_path))
    calls = []

    def fake_run(image, command, work_dir, *, writable, memory_mb, timeout_seconds, stdin=""):
        calls.append((writable, memory_mb, timeout_seconds))
        return judge.RunResult(0, "", "", 10, 500, False, False, False)

    monkeypatch.setattr(judge, "_run_container", fake_run)
    result = judge.judge_code("go", "package main\nfunc main() {}", [("", "")], 15, 128)
    assert result.verdict == "accepted"
    assert calls == [(True, 512, 60), (False, 128, 15)]
