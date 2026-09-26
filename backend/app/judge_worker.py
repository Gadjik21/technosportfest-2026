"""Single-process database queue consumer for code submissions.

Run only as the dedicated judge service. The web API has no Docker access.
"""

import logging
import time

from sqlalchemy import select, update

from app.db import get_sessionmaker
from app.modules.contests.judge import JudgeUnavailable, judge_code
from app.modules.contests.models import Submission, Task
from app.modules.contests.service import _now


logger = logging.getLogger(__name__)


def process_one() -> bool:
    sessions = get_sessionmaker()
    with sessions() as db:
        submission = db.scalar(
            select(Submission).where(Submission.kind == "code", Submission.verdict == "queued")
            .order_by(Submission.submitted_at, Submission.id).with_for_update(skip_locked=True).limit(1)
        )
        if submission is None:
            return False
        task = db.get(Task, submission.task_id)
        if task is None or submission.language is None or submission.judge_token is None:
            submission.verdict = "judge_error"
            submission.judge_message = "Не удалось подготовить проверку."
            db.commit()
            return True
        token = submission.judge_token
        submission_id = submission.id
        source = submission.content
        language = submission.language
        cases = [(case.input_data, case.expected_output) for case in task.test_cases]
        seconds, memory_mb, max_score = task.time_limit_seconds, task.memory_limit_mb, task.max_score
        submission.verdict = "running"
        submission.judge_started_at = _now()
        db.commit()

    try:
        result = judge_code(language, source, cases, seconds, memory_mb)
    except JudgeUnavailable:
        logger.exception("Judge unavailable for submission %s", submission_id)
        result = None
    except Exception:
        logger.exception("Unexpected judge failure for submission %s", submission_id)
        result = None

    with sessions() as db:
        current = db.get(Submission, submission_id)
        if current is None or current.judge_token != token or current.verdict != "running":
            return True  # A newer submission replaced this job.
        if result is None:
            current.verdict = "judge_error"
            current.judge_message = "Проверка временно недоступна. Обратитесь к организатору."
        else:
            current.verdict = result.verdict
            current.failed_test_index = result.failed_test_index
            current.time_ms = result.time_ms
            current.memory_kb = result.memory_kb
            current.judge_details = result.details
            current.judge_message = result.message
            current.score = max_score if result.verdict == "accepted" else 0
            current.graded_at = _now()
        db.commit()
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    sessions = get_sessionmaker()
    # This service runs exactly one consumer. An interrupted job has no live
    # execution container after Docker service shutdown and can be retried.
    with sessions() as db:
        db.execute(update(Submission).where(Submission.kind == "code", Submission.verdict == "running")
                   .values(verdict="queued", judge_started_at=None))
        db.commit()
    while True:
        try:
            if not process_one():
                time.sleep(2)
        except Exception:
            logger.exception("Judge queue error")
            time.sleep(5)


if __name__ == "__main__":
    main()
