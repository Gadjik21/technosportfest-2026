from app.modules.competitions.adapter import competition_port
from app.modules.competitions.ports import CompetitionPort


def get_competition_port() -> CompetitionPort:
    return competition_port
