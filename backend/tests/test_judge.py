from app.modules.contests import judge
from app.modules.contests import availability
import pytest
from types import SimpleNamespace
from urllib.error import URLError


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


def test_worker_refuses_rootful_or_unlimited_docker(tmp_path, monkeypatch):
    monkeypatch.setenv("JUDGE_WORKDIR", str(tmp_path))
    monkeypatch.setenv("JUDGE_HOST_WORKDIR", str(tmp_path))

    def rootful(*args):
        if args[:2] == ("info", "--format"):
            return '["name=seccomp,profile=builtin"]'
        return ""

    monkeypatch.setattr(judge, "_docker", rootful)
    with pytest.raises(judge.JudgeUnavailable, match="rootless"):
        judge.check_runtime()

    def unlimited(*args):
        if args[:2] == ("info", "--format"):
            return '["name=rootless"]' if "SecurityOptions" in args[2] else "2 none"
        return ""

    monkeypatch.setattr(judge, "_docker", unlimited)
    with pytest.raises(judge.JudgeUnavailable, match="cgroup"):
        judge.check_runtime()


def test_worker_preflight_checks_every_language_image(tmp_path, monkeypatch):
    monkeypatch.setenv("JUDGE_WORKDIR", str(tmp_path))
    monkeypatch.setenv("JUDGE_HOST_WORKDIR", str(tmp_path))
    images = []

    def healthy(*args):
        if args[:2] == ("info", "--format"):
            return '["name=rootless"]' if "SecurityOptions" in args[2] else "2 systemd"
        if args[:2] == ("image", "inspect"):
            images.append(args[2])
        return ""

    monkeypatch.setattr(judge, "_docker", healthy)
    judge.check_runtime()
    assert set(images) == {spec.image for spec in judge.LANGUAGES.values()}


def test_worker_only_cleans_its_own_disposable_containers(monkeypatch):
    calls = []

    def fake_docker(*args):
        calls.append(args)
        return "own-1\nown-2" if args[0] == "ps" else ""

    monkeypatch.setattr(judge, "_docker", fake_docker)
    judge.cleanup_stale_containers()
    assert calls == [
        ("ps", "-aq", "--filter", "label=technosportfest.judge=1"),
        ("rm", "-f", "own-1"),
        ("rm", "-f", "own-2"),
    ]


def test_api_rejects_code_when_worker_health_is_unavailable(monkeypatch):
    monkeypatch.setattr(availability, "get_settings", lambda: SimpleNamespace(
        judge_enabled=True, judge_health_url="http://judge:9000/health"
    ))

    def unavailable(*args, **kwargs):
        raise URLError("offline")

    monkeypatch.setattr(availability, "urlopen", unavailable)
    assert not availability.judge_ready()
