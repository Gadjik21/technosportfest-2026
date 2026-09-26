"""The API checks the separate worker before accepting code jobs."""

from urllib.error import URLError
from urllib.request import urlopen

from app.config import get_settings


def judge_ready() -> bool:
    settings = get_settings()
    if not settings.judge_enabled or not settings.judge_health_url:
        return False
    try:
        with urlopen(settings.judge_health_url, timeout=0.5) as response:
            return response.status == 200
    except (OSError, URLError, ValueError):
        return False
