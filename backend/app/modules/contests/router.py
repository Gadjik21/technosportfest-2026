from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.competitions.ports import CompetitionPort
from app.modules.contests import service
from app.modules.contests.deps import get_competition_port
from app.modules.contests.models import Submission, Task
from app.modules.identity.security import Principal, require_permission, require_role

router = APIRouter(tags=["Contests"])


def iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def optional_principal(request: Request) -> Principal | None:
    return getattr(request.state, "principal", None)


class TaskCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=2, max_length=200)
    statement: str = Field(min_length=1, max_length=10000)
    maxScore: int = Field(ge=1, le=1000)
    judgingMode: Literal["manual", "code"] = "manual"
    testCases: list["TestCaseInput"] = Field(default_factory=list, max_length=50)
    timeLimitSeconds: int = Field(default=15, ge=1, le=60)
    memoryLimitMb: int = Field(default=128, ge=32, le=512)
    visibleTestCount: int = Field(default=2, ge=0, le=50)

    @model_validator(mode="after")
    def _check_cases(self) -> "TaskCreateRequest":
        if self.judgingMode == "code" and not self.testCases:
            raise ValueError("Для программной задачи добавьте хотя бы один тест.")
        if self.judgingMode == "manual" and self.testCases:
            raise ValueError("Тесты доступны только для программной задачи.")
        return self


class TestCaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: str = Field(max_length=8192)
    expectedOutput: str = Field(max_length=8192)


class TaskPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=2, max_length=200)
    statement: str | None = Field(default=None, min_length=1, max_length=10000)
    maxScore: int | None = Field(default=None, ge=1, le=1000)
    judgingMode: Literal["manual", "code"] | None = None
    testCases: list[TestCaseInput] | None = Field(default=None, max_length=50)
    timeLimitSeconds: int | None = Field(default=None, ge=1, le=60)
    memoryLimitMb: int | None = Field(default=None, ge=32, le=512)
    visibleTestCount: int | None = Field(default=None, ge=0, le=50)

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "TaskPatchRequest":
        if all(value is None for value in (self.title, self.statement, self.maxScore, self.judgingMode,
                                          self.testCases, self.timeLimitSeconds, self.memoryLimitMb, self.visibleTestCount)):
            raise ValueError("Нужно передать хотя бы одно поле.")
        return self


class TaskResponse(BaseModel):
    id: UUID
    competitionId: UUID
    title: str
    statement: str
    maxScore: int
    orderIndex: int
    judgingMode: str
    timeLimitSeconds: int
    memoryLimitMb: int
    visibleTestCount: int
    testCaseCount: int
    testCases: list[TestCaseInput]


class SubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["text", "link", "code"]
    content: str = Field(min_length=1, max_length=10000)
    language: Literal["python", "javascript", "go"] | None = None


class TestResultResponse(BaseModel):
    index: int
    verdict: str
    timeMs: int | None = None
    memoryKb: int | None = None
    actualOutput: str | None = None
    stderr: str | None = None


class SubmissionResponse(BaseModel):
    id: UUID
    taskId: UUID
    registrationId: UUID
    kind: str
    content: str
    submittedAt: str
    score: int | None
    gradedAt: str | None
    language: str | None
    verdict: str | None
    failedTestIndex: int | None
    timeMs: int | None
    memoryKb: int | None
    testResults: list[TestResultResponse]
    judgeMessage: str | None


class GradingSubmissionResponse(SubmissionResponse):
    taskTitle: str
    taskMaxScore: int
    athleteFullName: str


class GradeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: int = Field(ge=0)


class FinishContestResponse(BaseModel):
    competitionId: UUID
    status: str
    publishedCount: int
    publishedAt: str


class StandingsTaskResponse(BaseModel):
    id: UUID
    title: str
    maxScore: int


class StandingsRowResponse(BaseModel):
    registrationId: UUID
    fullName: str
    place: int
    totalScore: int
    taskScores: list[int | None]


class StandingsResponse(BaseModel):
    maxTotalScore: int
    tasks: list[StandingsTaskResponse]
    items: list[StandingsRowResponse]


def _task_response(task: Task, is_organizer: bool = False) -> TaskResponse:
    cases = task.test_cases if is_organizer else task.test_cases[:task.visible_test_count]
    return TaskResponse(
        id=task.id, competitionId=task.competition_id, title=task.title, statement=task.statement, maxScore=task.max_score,
        orderIndex=task.order_index, judgingMode=task.judging_mode, timeLimitSeconds=task.time_limit_seconds,
        memoryLimitMb=task.memory_limit_mb, visibleTestCount=task.visible_test_count,
        testCaseCount=len(task.test_cases),
        testCases=[TestCaseInput(input=case.input_data, expectedOutput=case.expected_output) for case in cases],
    )


def _submission_response(submission: Submission, task: Task, is_organizer: bool = False) -> SubmissionResponse:
    details = submission.judge_details or []
    return SubmissionResponse(
        id=submission.id,
        taskId=submission.task_id,
        registrationId=submission.registration_id,
        kind=submission.kind,
        content=submission.content,
        submittedAt=iso_z(submission.submitted_at),
        score=submission.score,
        gradedAt=iso_z(submission.graded_at) if submission.graded_at else None,
        language=submission.language, verdict=submission.verdict, failedTestIndex=submission.failed_test_index,
        timeMs=submission.time_ms, memoryKb=submission.memory_kb, judgeMessage=submission.judge_message,
        testResults=[TestResultResponse(**{
            "index": item["index"], "verdict": item["verdict"], "timeMs": item.get("timeMs"),
            "memoryKb": item.get("memoryKb"),
            "actualOutput": item.get("actualOutput") if is_organizer or item["index"] <= task.visible_test_count else None,
            "stderr": item.get("stderr") if is_organizer or item["index"] <= task.visible_test_count else None,
        }) for item in details],
    )


# ---------- Задания ----------


@router.get("/competitions/{competitionId}/tasks", response_model=list[TaskResponse])
def list_tasks(
    competitionId: UUID,
    request: Request,
    db: Session = Depends(get_db),
    competition_port: CompetitionPort = Depends(get_competition_port),
) -> list[TaskResponse]:
    principal = optional_principal(request)
    is_organizer = principal is not None and principal.has("contests.tasks")
    tasks = service.list_tasks(db, competition_port, competitionId, is_organizer)
    return [_task_response(t, is_organizer) for t in tasks]


@router.get("/competitions/{competitionId}/standings", response_model=StandingsResponse)
def get_standings(
    competitionId: UUID,
    request: Request,
    db: Session = Depends(get_db),
    competition_port: CompetitionPort = Depends(get_competition_port),
) -> StandingsResponse:
    principal = optional_principal(request)
    is_organizer = principal is not None and principal.role == "organizer"
    tasks, rows = service.contest_standings(db, competition_port, competitionId, is_organizer)
    max_total = sum(task.max_score for task in tasks)
    return StandingsResponse(
        maxTotalScore=max_total,
        tasks=[StandingsTaskResponse(id=t.id, title=t.title, maxScore=t.max_score) for t in tasks],
        items=[
            StandingsRowResponse(registrationId=r.registration_id, fullName=r.full_name, place=r.place, totalScore=r.total_score, taskScores=r.task_scores)
            for r in rows
        ],
    )


@router.post("/competitions/{competitionId}/tasks", response_model=TaskResponse, status_code=201)
def create_task(
    competitionId: UUID,
    body: TaskCreateRequest,
    _: Principal = Depends(require_permission("contests.tasks")),
    db: Session = Depends(get_db),
    competition_port: CompetitionPort = Depends(get_competition_port),
) -> TaskResponse:
    task = service.create_task(db, competition_port, competitionId, body.title, body.statement, body.maxScore,
                               body.judgingMode, [(case.input, case.expectedOutput) for case in body.testCases],
                               body.timeLimitSeconds, body.memoryLimitMb, body.visibleTestCount)
    return _task_response(task, True)


@router.patch("/competitions/{competitionId}/tasks/{taskId}", response_model=TaskResponse)
def update_task(
    competitionId: UUID,
    taskId: UUID,
    body: TaskPatchRequest,
    _: Principal = Depends(require_permission("contests.tasks")),
    db: Session = Depends(get_db),
    competition_port: CompetitionPort = Depends(get_competition_port),
) -> TaskResponse:
    task = service.update_task(db, competition_port, competitionId, taskId, body.title, body.statement, body.maxScore,
                               body.judgingMode, None if body.testCases is None else [(case.input, case.expectedOutput) for case in body.testCases],
                               body.timeLimitSeconds, body.memoryLimitMb, body.visibleTestCount)
    return _task_response(task, True)


@router.delete("/competitions/{competitionId}/tasks/{taskId}", status_code=204)
def delete_task(
    competitionId: UUID,
    taskId: UUID,
    _: Principal = Depends(require_permission("contests.tasks")),
    db: Session = Depends(get_db),
    competition_port: CompetitionPort = Depends(get_competition_port),
) -> None:
    service.delete_task(db, competition_port, competitionId, taskId)


# ---------- Решения спортсмена ----------


@router.put("/competitions/{competitionId}/tasks/{taskId}/submission", response_model=SubmissionResponse)
def submit_solution(
    competitionId: UUID,
    taskId: UUID,
    body: SubmissionRequest,
    principal: Principal = Depends(require_role("athlete")),
    db: Session = Depends(get_db),
    competition_port: CompetitionPort = Depends(get_competition_port),
) -> SubmissionResponse:
    submission = service.submit_solution(db, competition_port, competitionId, principal.user_id, taskId, body.kind, body.content, body.language)
    return _submission_response(submission, db.get(Task, taskId))


@router.get("/competitions/{competitionId}/my-submissions", response_model=list[SubmissionResponse])
def list_my_submissions(
    competitionId: UUID,
    principal: Principal = Depends(require_role("athlete")),
    db: Session = Depends(get_db),
    competition_port: CompetitionPort = Depends(get_competition_port),
) -> list[SubmissionResponse]:
    submissions = service.list_my_submissions(db, competition_port, competitionId, principal.user_id)
    return [_submission_response(s, db.get(Task, s.task_id)) for s in submissions]


# ---------- Проверка организатором ----------


@router.get("/competitions/{competitionId}/submissions", response_model=list[GradingSubmissionResponse])
def list_submissions_for_grading(
    competitionId: UUID,
    _: Principal = Depends(require_permission("contests.grade")),
    db: Session = Depends(get_db),
    competition_port: CompetitionPort = Depends(get_competition_port),
) -> list[GradingSubmissionResponse]:
    rows = service.list_submissions_for_grading(db, competition_port, competitionId)
    return [
        GradingSubmissionResponse(
            **_submission_response(row.submission, row.task, True).model_dump(),
            taskTitle=row.task.title,
            taskMaxScore=row.task.max_score,
            athleteFullName=row.athlete_full_name,
        )
        for row in rows
    ]


@router.patch("/competitions/{competitionId}/submissions/{submissionId}", response_model=SubmissionResponse)
def grade_submission(
    competitionId: UUID,
    submissionId: UUID,
    body: GradeRequest,
    _: Principal = Depends(require_permission("contests.grade")),
    db: Session = Depends(get_db),
    competition_port: CompetitionPort = Depends(get_competition_port),
) -> SubmissionResponse:
    submission = service.grade_submission(db, competition_port, competitionId, submissionId, body.score)
    return _submission_response(submission, db.get(Task, submission.task_id), True)


# ---------- Завершение контеста ----------


@router.post("/competitions/{competitionId}/finish-contest", response_model=FinishContestResponse)
def finish_contest(
    competitionId: UUID,
    _: Principal = Depends(require_permission("contests.grade")),
    db: Session = Depends(get_db),
    competition_port: CompetitionPort = Depends(get_competition_port),
) -> FinishContestResponse:
    published_count, published_at = service.finish_contest(db, competition_port, competitionId)
    return FinishContestResponse(competitionId=competitionId, status="completed", publishedCount=published_count, publishedAt=iso_z(published_at))
