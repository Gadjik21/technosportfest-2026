from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.modules.competitions.ports import CompetitionPort
from app.modules.identity.ports import AthleteSummary, IdentityPort
from app.modules.results.models import Result


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _paginate(items: list, page: int, page_size: int) -> tuple[list, int]:
    total = len(items)
    start = (page - 1) * page_size
    return items[start : start + page_size], total


def _competition_is_completed(db: Session, competition_id: UUID) -> bool:
    """Соревнование считается завершённым, если у него есть опубликованный результат.

    Публикация переводит все черновики в published и competitions.status в
    completed одной транзакцией (см. publish_results), поэтому наличие хотя бы
    одного published-результата равносильно completed для целей Results.
    """
    return (
        db.scalar(select(Result.id).where(Result.competition_id == competition_id, Result.status == "published").limit(1))
        is not None
    )


def _full_name(names: dict[UUID, AthleteSummary], athlete_id: UUID) -> str:
    summary = names.get(athlete_id)
    return summary.full_name if summary else ""


def upsert_draft(
    db: Session,
    competition_port: CompetitionPort,
    competition_id: UUID,
    registration_id: UUID,
    place: int,
    score_text: str | None,
) -> Result:
    participant = competition_port.get_registration(competition_id, registration_id, db)
    if _competition_is_completed(db, competition_id):
        raise ApiError(409, "INVALID_STATE", "Результаты соревнования уже опубликованы, черновики недоступны.")
    result = db.scalar(select(Result).where(Result.registration_id == registration_id))
    if result is None:
        result = Result(
            registration_id=registration_id,
            competition_id=competition_id,
            athlete_id=participant.athlete_id,
            place=place,
            score_text=score_text,
            status="draft",
        )
        db.add(result)
    else:
        result.place = place
        result.score_text = score_text
        result.athlete_id = participant.athlete_id
        result.updated_at = _now()
    db.commit()
    db.refresh(result)
    return result


def list_drafts(
    db: Session, identity_port: IdentityPort, competition_id: UUID, page: int, page_size: int
) -> tuple[list[tuple[Result, str]], int]:
    rows = db.scalars(select(Result).where(Result.competition_id == competition_id, Result.status == "draft")).all()
    names = identity_port.get_athlete_summaries([r.athlete_id for r in rows], db)
    enriched = [(r, _full_name(names, r.athlete_id)) for r in rows]
    enriched.sort(key=lambda pair: (pair[0].place, pair[1], str(pair[0].id)))
    return _paginate(enriched, page, page_size)


def publish_results(db: Session, competition_port: CompetitionPort, competition_id: UUID) -> tuple[int, datetime]:
    if _competition_is_completed(db, competition_id):
        raise ApiError(409, "ALREADY_COMPLETED", "Результаты этого соревнования уже опубликованы.")
    competition_port.lock_for_result_publication(competition_id, db)
    drafts = db.scalars(select(Result).where(Result.competition_id == competition_id, Result.status == "draft")).all()
    if not drafts:
        raise ApiError(409, "NO_RESULTS", "Нет черновиков для публикации.")
    published_at = _now()
    for draft in drafts:
        draft.status = "published"
        draft.published_at = published_at
        draft.updated_at = published_at
    competition_port.complete_competition(competition_id, db)
    db.commit()
    return len(drafts), published_at


def list_public_results(
    db: Session, identity_port: IdentityPort, competition_id: UUID, page: int, page_size: int
) -> tuple[list[tuple[Result, str]], int]:
    rows = db.scalars(select(Result).where(Result.competition_id == competition_id, Result.status == "published")).all()
    names = identity_port.get_athlete_summaries([r.athlete_id for r in rows], db)
    enriched = [(r, _full_name(names, r.athlete_id)) for r in rows]
    enriched.sort(key=lambda pair: (pair[0].place, pair[1], str(pair[0].id)))
    return _paginate(enriched, page, page_size)


def list_my_results(
    db: Session, identity_port: IdentityPort, athlete_id: UUID, page: int, page_size: int
) -> tuple[list[tuple[Result, str]], int]:
    rows = db.scalars(select(Result).where(Result.athlete_id == athlete_id, Result.status == "published")).all()
    names = identity_port.get_athlete_summaries([athlete_id], db)
    full_name = _full_name(names, athlete_id)
    enriched = [(r, full_name) for r in rows]
    enriched.sort(key=lambda pair: (pair[0].place, pair[1], str(pair[0].id)))
    return _paginate(enriched, page, page_size)


@dataclass(frozen=True)
class RatingRow:
    athlete_id: UUID
    full_name: str
    points: int
    results_count: int


def _aggregate_ratings(
    db: Session, competition_port: CompetitionPort, identity_port: IdentityPort, discipline_id: UUID | None
) -> list[RatingRow]:
    rows = db.scalars(select(Result).where(Result.status == "published")).all()
    if discipline_id is not None:
        competition_ids = list({r.competition_id for r in rows})
        disciplines = competition_port.get_competition_disciplines(competition_ids, db)
        rows = [r for r in rows if disciplines.get(r.competition_id) == discipline_id]
    totals: dict[UUID, list[int]] = {}
    for r in rows:
        bucket = totals.setdefault(r.athlete_id, [0, 0])
        bucket[0] += r.points()
        bucket[1] += 1
    names = identity_port.get_athlete_summaries(list(totals.keys()), db)
    ratings = [
        RatingRow(athlete_id=aid, full_name=_full_name(names, aid), points=points, results_count=count)
        for aid, (points, count) in totals.items()
    ]
    ratings.sort(key=lambda row: (-row.points, row.full_name, str(row.athlete_id)))
    return ratings


def _rank_of(ratings: list[RatingRow], row: RatingRow) -> int:
    return sum(1 for other in ratings if other.points > row.points) + 1


def list_ratings(
    db: Session,
    competition_port: CompetitionPort,
    identity_port: IdentityPort,
    discipline_id: UUID | None,
    page: int,
    page_size: int,
) -> tuple[list[tuple[RatingRow, int]], int]:
    ratings = _aggregate_ratings(db, competition_port, identity_port, discipline_id)
    ranked = [(row, _rank_of(ratings, row)) for row in ratings]
    return _paginate(ranked, page, page_size)


def my_rating(
    db: Session,
    competition_port: CompetitionPort,
    identity_port: IdentityPort,
    athlete_id: UUID,
    discipline_id: UUID | None,
) -> tuple[int, int | None, int]:
    ratings = _aggregate_ratings(db, competition_port, identity_port, discipline_id)
    for row in ratings:
        if row.athlete_id == athlete_id:
            return row.points, _rank_of(ratings, row), row.results_count
    return 0, None, 0
