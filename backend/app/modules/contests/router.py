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


class TaskPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=2, max_length=200)
    statement: str | None = Field(default=None, min_length=1, max_length=10000)
    maxScore: int | None = Field(default=None, ge=1, le=1000)

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "TaskPatchRequest":
        if self.title is None and self.statement is None and self.maxScore is None:
            raise ValueError("Нужно передать хотя бы одно поле.")
        return self


class TaskResponse(BaseModel):
    id: UUID
    competitionId: UUID
    title: str
    statement: str
    maxScore: int
    orderIndex: int


class SubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["text", "link"]
    content: str = Field(min_length=1, max_length=10000)


class SubmissionResponse(BaseModel):
    id: UUID
    taskId: UUID
    registrationId: UUID
    kind: str
    content: str
    submittedAt: str
    score: int | None
    gradedAt: str | None


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


def _task_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id, competitionId=task.competition_id, title=task.title, statement=task.statement, maxScore=task.max_score, orderIndex=task.order_index
    )


def _submission_response(submission: Submission) -> SubmissionResponse:
    return SubmissionResponse(
        id=submission.id,
        taskId=submission.task_id,
        registrationId=submission.registration_id,
        kind=submission.kind,
        content=submission.content,
        submittedAt=iso_z(submission.submitted_at),
        score=submission.score,
        gradedAt=iso_z(submission.graded_at) if submission.graded_at else None,
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
    return [_task_response(t) for t in tasks]


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
    task = service.create_task(db, competition_port, competitionId, body.title, body.statement, body.maxScore)
    return _task_response(task)


@router.patch("/competitions/{competitionId}/tasks/{taskId}", response_model=TaskResponse)
def update_task(
    competitionId: UUID,
    taskId: UUID,
    body: TaskPatchRequest,
    _: Principal = Depends(require_permission("contests.tasks")),
    db: Session = Depends(get_db),
    competition_port: CompetitionPort = Depends(get_competition_port),
) -> TaskResponse:
    task = service.update_task(db, competition_port, competitionId, taskId, body.title, body.statement, body.maxScore)
    return _task_response(task)


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
    submission = service.submit_solution(db, competition_port, competitionId, principal.user_id, taskId, body.kind, body.content)
    return _submission_response(submission)


@router.get("/competitions/{competitionId}/my-submissions", response_model=list[SubmissionResponse])
def list_my_submissions(
    competitionId: UUID,
    principal: Principal = Depends(require_role("athlete")),
    db: Session = Depends(get_db),
    competition_port: CompetitionPort = Depends(get_competition_port),
) -> list[SubmissionResponse]:
    submissions = service.list_my_submissions(db, competition_port, competitionId, principal.user_id)
    return [_submission_response(s) for s in submissions]


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
            **_submission_response(row.submission).model_dump(),
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
    return _submission_response(submission)


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
