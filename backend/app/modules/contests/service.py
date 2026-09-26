"""Кейс №2: задания, решения, проверка и завершение контеста.

Итоговый балл контеста публикуется через уже существующий механизм Results
(`upsert_draft` + `publish_results`) — так профиль спортсмена и рейтинг
получают результат контеста без единой новой строчки логики подсчёта очков.
Отдельного статуса «идёт» в БД нет: он вычисляется из `starts_at`/`ends_at`
поверх статуса `published`, чтобы не трогать общий контракт `competitions`.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.modules.competitions.ports import CompetitionPort
from app.modules.contests.models import Submission, Task
from app.modules.results import service as results_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _ensure_draft(status: str | None) -> None:
    if status is None:
        raise ApiError(404, "NOT_FOUND", "Соревнование не найдено.")
    if status != "draft":
        raise ApiError(409, "INVALID_STATE", "Задания можно менять только пока соревнование в статусе «черновик».")


def _get_task(db: Session, competition_id: UUID, task_id: UUID) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.competition_id != competition_id:
        raise ApiError(404, "NOT_FOUND", "Задание не найдено.")
    return task


# ---------- Задания (организатор) ----------


def create_task(
    db: Session, competition_port: CompetitionPort, competition_id: UUID, title: str, statement: str, max_score: int
) -> Task:
    _ensure_draft(competition_port.get_competition_status(competition_id, db))
    order_index = db.scalar(select(func.count()).select_from(Task).where(Task.competition_id == competition_id)) or 0
    task = Task(competition_id=competition_id, title=title, statement=statement, max_score=max_score, order_index=order_index)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(
    db: Session,
    competition_port: CompetitionPort,
    competition_id: UUID,
    task_id: UUID,
    title: str | None,
    statement: str | None,
    max_score: int | None,
) -> Task:
    _ensure_draft(competition_port.get_competition_status(competition_id, db))
    task = _get_task(db, competition_id, task_id)
    if title is not None:
        task.title = title
    if statement is not None:
        task.statement = statement
    if max_score is not None:
        task.max_score = max_score
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, competition_port: CompetitionPort, competition_id: UUID, task_id: UUID) -> None:
    _ensure_draft(competition_port.get_competition_status(competition_id, db))
    task = _get_task(db, competition_id, task_id)
    db.delete(task)
    db.commit()


def list_tasks(db: Session, competition_port: CompetitionPort, competition_id: UUID, is_organizer: bool) -> list[Task]:
    status = competition_port.get_competition_status(competition_id, db)
    if status is None or (status == "draft" and not is_organizer):
        raise ApiError(404, "NOT_FOUND", "Соревнование не найдено.")
    return list(db.scalars(select(Task).where(Task.competition_id == competition_id).order_by(Task.order_index, Task.id)).all())


# ---------- Решения (спортсмен) ----------


def submit_solution(
    db: Session,
    competition_port: CompetitionPort,
    competition_id: UUID,
    athlete_id: UUID,
    task_id: UUID,
    kind: str,
    content: str,
) -> Submission:
    timing = competition_port.get_competition_timing(competition_id, db)
    if timing is None:
        raise ApiError(404, "NOT_FOUND", "Соревнование не найдено.")
    task = _get_task(db, competition_id, task_id)
    if timing.status != "published":
        raise ApiError(409, "INVALID_STATE", "Приём решений закрыт: соревнование не опубликовано или уже завершено.")
    now = _now()
    if not (_as_utc(timing.starts_at) <= now < _as_utc(timing.ends_at)):
        raise ApiError(409, "INVALID_STATE", "Приём решений открыт только пока идёт соревнование.")
    participant = competition_port.get_registration_by_athlete(competition_id, athlete_id, db)
    if participant is None:
        raise ApiError(403, "FORBIDDEN", "Вы не зарегистрированы на это соревнование.")
    submission = db.scalar(
        select(Submission).where(Submission.task_id == task.id, Submission.registration_id == participant.registration_id)
    )
    if submission is None:
        submission = Submission(
            task_id=task.id, registration_id=participant.registration_id, kind=kind, content=content, submitted_at=now
        )
        db.add(submission)
    else:
        submission.kind = kind
        submission.content = content
        submission.submitted_at = now
        submission.score = None
        submission.graded_at = None
    db.commit()
    db.refresh(submission)
    return submission


def list_my_submissions(
    db: Session, competition_port: CompetitionPort, competition_id: UUID, athlete_id: UUID
) -> list[Submission]:
    participant = competition_port.get_registration_by_athlete(competition_id, athlete_id, db)
    if participant is None:
        return []
    task_ids = db.scalars(select(Task.id).where(Task.competition_id == competition_id)).all()
    if not task_ids:
        return []
    return list(
        db.scalars(
            select(Submission).where(Submission.registration_id == participant.registration_id, Submission.task_id.in_(task_ids))
        ).all()
    )


# ---------- Проверка (организатор) ----------


@dataclass(frozen=True)
class GradingRow:
    submission: Submission
    task: Task
    athlete_full_name: str


def list_submissions_for_grading(
    db: Session, competition_port: CompetitionPort, competition_id: UUID
) -> list[GradingRow]:
    if competition_port.get_competition_status(competition_id, db) is None:
        raise ApiError(404, "NOT_FOUND", "Соревнование не найдено.")
    tasks = {t.id: t for t in db.scalars(select(Task).where(Task.competition_id == competition_id)).all()}
    if not tasks:
        return []
    names = {p.registration_id: p.full_name for p in competition_port.list_participants(competition_id, db)}
    rows = db.scalars(select(Submission).where(Submission.task_id.in_(tasks.keys())).order_by(Submission.submitted_at)).all()
    return [GradingRow(submission=s, task=tasks[s.task_id], athlete_full_name=names.get(s.registration_id, "")) for s in rows]


def grade_submission(
    db: Session, competition_port: CompetitionPort, competition_id: UUID, submission_id: UUID, score: int
) -> Submission:
    if competition_port.get_competition_status(competition_id, db) is None:
        raise ApiError(404, "NOT_FOUND", "Соревнование не найдено.")
    row = db.execute(
        select(Submission, Task)
        .join(Task, Task.id == Submission.task_id)
        .where(Submission.id == submission_id, Task.competition_id == competition_id)
    ).first()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Решение не найдено.")
    submission, task = row
    if not (0 <= score <= task.max_score):
        raise ApiError(422, "VALIDATION_ERROR", f"Балл должен быть от 0 до {task.max_score}.")
    submission.score = score
    submission.graded_at = _now()
    db.commit()
    db.refresh(submission)
    return submission


# ---------- Таблица результатов (как в Codeforces: баллы по каждому заданию) ----------


@dataclass(frozen=True)
class StandingsRow:
    registration_id: UUID
    full_name: str
    place: int
    total_score: int
    task_scores: list[int | None]  # None = решение не отправлено; по порядку заданий


def contest_standings(
    db: Session, competition_port: CompetitionPort, competition_id: UUID, is_organizer: bool
) -> tuple[list[Task], list[StandingsRow]]:
    status = competition_port.get_competition_status(competition_id, db)
    if status is None or (status == "draft" and not is_organizer):
        raise ApiError(404, "NOT_FOUND", "Соревнование не найдено.")
    tasks = list(db.scalars(select(Task).where(Task.competition_id == competition_id).order_by(Task.order_index, Task.id)).all())
    if not tasks:
        return [], []
    participants = competition_port.list_participants(competition_id, db)
    task_ids = [t.id for t in tasks]
    score_map: dict[tuple[UUID, UUID], int] = {
        (registration_id, task_id): score
        for registration_id, task_id, score in db.execute(
            select(Submission.registration_id, Submission.task_id, Submission.score).where(
                Submission.task_id.in_(task_ids), Submission.score.is_not(None)
            )
        ).all()
    }
    totals: list[tuple] = []
    for participant in participants:
        task_scores = [score_map.get((participant.registration_id, task.id)) for task in tasks]
        total = sum(score for score in task_scores if score is not None)
        totals.append((participant, task_scores, total))
    totals.sort(key=lambda row: (-row[2], row[0].full_name, str(row[0].registration_id)))
    rows = [
        StandingsRow(
            registration_id=participant.registration_id,
            full_name=participant.full_name,
            place=sum(1 for _, _, other_total in totals if other_total > total) + 1,
            total_score=total,
            task_scores=task_scores,
        )
        for participant, task_scores, total in totals
    ]
    return tasks, rows


# ---------- Завершение контеста ----------


def finish_contest(db: Session, competition_port: CompetitionPort, competition_id: UUID) -> tuple[int, datetime]:
    status = competition_port.get_competition_status(competition_id, db)
    if status is None:
        raise ApiError(404, "NOT_FOUND", "Соревнование не найдено.")
    if status != "published":
        raise ApiError(409, "INVALID_STATE", "Завершить можно только опубликованное соревнование.")
    tasks = list(db.scalars(select(Task).where(Task.competition_id == competition_id)).all())
    if not tasks:
        raise ApiError(409, "NO_TASKS", "В соревновании нет заданий.")
    task_ids = [t.id for t in tasks]
    max_total = sum(t.max_score for t in tasks)
    ungraded = db.scalar(
        select(func.count()).select_from(Submission).where(Submission.task_id.in_(task_ids), Submission.score.is_(None))
    )
    if ungraded:
        raise ApiError(409, "UNGRADED_SUBMISSIONS", "Есть непроверенные решения — оцените их перед завершением.")
    participants = competition_port.list_participants(competition_id, db)
    totals: dict[UUID, int] = {p.registration_id: 0 for p in participants}
    rows = db.execute(select(Submission.registration_id, Submission.score).where(Submission.task_id.in_(task_ids))).all()
    for registration_id, score in rows:
        totals[registration_id] = totals.get(registration_id, 0) + (score or 0)
    ranked = sorted(participants, key=lambda p: (-totals.get(p.registration_id, 0), p.full_name, str(p.registration_id)))
    for participant in ranked:
        place = sum(1 for other in ranked if totals.get(other.registration_id, 0) > totals.get(participant.registration_id, 0)) + 1
        results_service.upsert_draft(
            db, competition_port, competition_id, participant.registration_id, place, f"{totals.get(participant.registration_id, 0)}/{max_total} баллов по заданиям"
        )
    return results_service.publish_results(db, competition_port, competition_id)
