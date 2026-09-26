"""Run untrusted contest code in disposable, resource-limited Docker containers.

Only the dedicated judge process may access Docker. The API queues database rows
and never receives the daemon socket. A fresh container is used for every test,
so one test cannot leave files or processes for the next one.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import tempfile
import threading
import time
from uuid import uuid4


@dataclass(frozen=True)
class Language:
    filename: str
    image: str
    compile: tuple[str, ...] | None
    run: tuple[str, ...]


LANGUAGES: dict[str, Language] = {
    "python": Language("main.py", "python:3.12-slim", None, ("python", "/work/main.py")),
    "javascript": Language("main.js", "node:22-slim", None, ("node", "/work/main.js")),
    "go": Language("main.go", "golang:1.25-bookworm", ("go", "build", "-o", "/work/program", "/work/main.go"), ("/work/program",)),
    "java": Language("Main.java", "eclipse-temurin:21-jdk", ("javac", "-d", "/work", "/work/Main.java"), ("java", "-Xmx{heap}m", "-cp", "/work", "Main")),
    "kotlin": Language("Main.kt", "tsf-judge-kotlin:2.4.20", ("kotlinc", "/work/Main.kt", "-include-runtime", "-d", "/work/program.jar"), ("java", "-Xmx{heap}m", "-jar", "/work/program.jar")),
    "cpp": Language("main.cpp", "gcc:14", ("g++", "-O2", "-std=c++20", "-o", "/work/program", "/work/main.cpp"), ("/work/program",)),
    "rust": Language("main.rs", "rust:1.90-slim", ("rustc", "-O", "-o", "/work/program", "/work/main.rs"), ("/work/program",)),
}

OUTPUT_LIMIT = 64 * 1024
MESSAGE_LIMIT = 4000


class JudgeUnavailable(Exception):
    """The Docker daemon or a required language image is unavailable."""


@dataclass(frozen=True)
class RunResult:
    exit_code: int
    stdout: str
    stderr: str
    time_ms: int
    memory_kb: int | None
    timed_out: bool
    oom_killed: bool
    output_limit: bool


@dataclass(frozen=True)
class JudgeResult:
    verdict: str
    failed_test_index: int | None
    time_ms: int
    memory_kb: int | None
    details: list[dict]
    message: str | None = None


def _docker(*args: str, timeout: int = 10) -> str:
    try:
        result = subprocess.run(("docker", *args), capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise JudgeUnavailable("Docker недоступен для проверки решения.") from exc
    if result.returncode:
        raise JudgeUnavailable((result.stderr or result.stdout).strip()[:MESSAGE_LIMIT])
    return result.stdout.strip()


def _memory_kb(value: str) -> int | None:
    match = re.match(r"\s*([\d.]+)\s*([KMGT]?i?B|B)", value)
    if not match:
        return None
    number, unit = float(match.group(1)), match.group(2)
    factor = {"B": 1 / 1024, "kB": 1, "KB": 1, "KiB": 1, "MB": 1000, "MiB": 1024,
              "GB": 1000_000, "GiB": 1024_000, "TB": 1000_000_000, "TiB": 1024_000_000}.get(unit)
    return int(number * factor) if factor is not None else None


def _run_container(image: str, command: tuple[str, ...], work_dir: Path, *, writable: bool,
                   memory_mb: int, timeout_seconds: int, stdin: str = "") -> RunResult:
    name = f"tsf-judge-{uuid4().hex}"
    # The judge service sees /judge-work; the Docker daemon sees the host path.
    host_root = os.environ.get("JUDGE_HOST_WORKDIR")
    host_dir = (Path(host_root) / work_dir.name).resolve() if host_root else work_dir.resolve()
    opts = [
        "create", "--name", name, "--init", "-i", "--network", "none", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges=true", "--pids-limit", "64",
        "--memory", f"{memory_mb}m", "--memory-swap", f"{memory_mb}m", "--cpus", "1",
        "--user", "65534:65534", "--ulimit", "nofile=64:64",
        "--tmpfs", "/tmp:rw,nosuid,size=64m",
        "--mount", f"type=bind,source={host_dir},target=/work{'' if writable else ',readonly'}",
        "--workdir", "/work", "--env", "HOME=/tmp", "--env", "TMPDIR=/tmp",
        "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "GOCACHE=/tmp/go-cache",
        "--env", "GOMODCACHE=/tmp/go-mod", "--env", "GOTOOLCHAIN=local",
        # A second wall timer lives inside the container, so a judge process
        # crash cannot leave submitted code running indefinitely.
        image, "timeout", "--signal=KILL", str(timeout_seconds), *command,
    ]
    container_id = _docker(*opts)
    timed_out = output_limit = False
    peak_kb: int | None = None
    stop_stats = threading.Event()

    def sample_memory() -> None:
        nonlocal peak_kb
        while not stop_stats.is_set():
            try:
                usage = _docker("stats", "--no-stream", "--format", "{{.MemUsage}}", container_id, timeout=2)
                value = _memory_kb(usage)
                if value is not None:
                    peak_kb = max(peak_kb or 0, value)
            except JudgeUnavailable:
                pass
            stop_stats.wait(0.2)

    try:
        started = time.monotonic()
        try:
            process = subprocess.Popen(("docker", "start", "-a", "-i", container_id),
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError as exc:
            raise JudgeUnavailable("Docker недоступен для проверки решения.") from exc
        thread = threading.Thread(target=sample_memory, daemon=True)
        thread.start()
        assert process.stdin is not None and process.stdout is not None and process.stderr is not None
        try:
            process.stdin.write(stdin.encode())
            process.stdin.close()
        except BrokenPipeError:
            pass
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        output = {"stdout": bytearray(), "stderr": bytearray()}
        try:
            while selector.get_map():
                if time.monotonic() - started > timeout_seconds:
                    timed_out = True
                    break
                for key, _ in selector.select(timeout=0.1):
                    chunk = os.read(key.fileobj.fileno(), 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    output[key.data].extend(chunk[: max(0, OUTPUT_LIMIT - len(output[key.data]))])
                    if len(output[key.data]) >= OUTPUT_LIMIT:
                        output_limit = True
                        break
                if output_limit:
                    break
        finally:
            selector.close()
        if timed_out or output_limit:
            try:
                _docker("rm", "-f", container_id, timeout=5)
            except JudgeUnavailable:
                pass
            process.kill()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        elapsed = int((time.monotonic() - started) * 1000)
        try:
            state = _docker("inspect", "--format", "{{.State.ExitCode}} {{.State.OOMKilled}}", container_id)
            exit_text, oom_text = state.split()
            exit_code, oom_killed = int(exit_text), oom_text == "true"
        except (JudgeUnavailable, ValueError):
            exit_code, oom_killed = process.returncode or 1, False
        if process.returncode and exit_code == 0:
            exit_code = process.returncode
        timed_out = timed_out or (exit_code in (124, 137) and not oom_killed)
        return RunResult(exit_code, output["stdout"].decode(errors="replace"),
                         output["stderr"].decode(errors="replace"), elapsed, peak_kb,
                         timed_out, oom_killed, output_limit)
    finally:
        stop_stats.set()
        try:
            _docker("rm", "-f", container_id, timeout=5)
        except JudgeUnavailable:
            pass


def _normalized(output: str) -> str:
    return output.replace("\r\n", "\n").rstrip()


def judge_code(language: str, source: str, test_cases: list[tuple[str, str]],
               time_limit_seconds: int, memory_limit_mb: int) -> JudgeResult:
    if language not in LANGUAGES:
        raise ValueError("unsupported language")
    spec = LANGUAGES[language]
    base = Path(os.environ.get("JUDGE_WORKDIR", "/judge-work"))
    base.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix="job-", dir=base))
    work_dir.chmod(0o777)
    try:
        (work_dir / spec.filename).write_text(source, encoding="utf-8")
        (work_dir / spec.filename).chmod(0o644)
        if spec.compile:
            compiled = _run_container(spec.image, spec.compile, work_dir, writable=True,
                                      memory_mb=512, timeout_seconds=60)
            if compiled.timed_out or compiled.oom_killed:
                return JudgeResult("compile_error", None, compiled.time_ms, compiled.memory_kb, [],
                                   "Компиляция превысила лимит времени или памяти.")
            if compiled.exit_code or compiled.output_limit:
                return JudgeResult("compile_error", None, compiled.time_ms, compiled.memory_kb, [],
                                   (compiled.stderr or compiled.stdout)[:MESSAGE_LIMIT])
        details: list[dict] = []
        total_ms = 0
        peak_kb: int | None = None
        for index, (stdin, expected) in enumerate(test_cases, start=1):
            heap = max(32, int(memory_limit_mb * 0.55))
            command = tuple(part.format(heap=heap) for part in spec.run)
            result = _run_container(spec.image, command, work_dir, writable=False,
                                    memory_mb=memory_limit_mb, timeout_seconds=time_limit_seconds, stdin=stdin)
            total_ms += result.time_ms
            if result.memory_kb is not None:
                peak_kb = max(peak_kb or 0, result.memory_kb)
            verdict = ("time_limit" if result.timed_out else "memory_limit" if result.oom_killed else
                       "output_limit" if result.output_limit else "runtime_error" if result.exit_code else
                       "wrong_answer" if _normalized(result.stdout) != _normalized(expected) else "accepted")
            details.append({"index": index, "verdict": verdict, "timeMs": result.time_ms,
                            "memoryKb": result.memory_kb, "actualOutput": result.stdout[:MESSAGE_LIMIT],
                            "stderr": result.stderr[:MESSAGE_LIMIT]})
            if verdict != "accepted":
                return JudgeResult(verdict, index, total_ms, peak_kb, details)
        return JudgeResult("accepted", None, total_ms, peak_kb, details)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
