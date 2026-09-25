from app.modules.competitions.adapter import competition_port
from app.modules.competitions.ports import CompetitionPort
from app.modules.identity.adapter import identity_port
from app.modules.identity.ports import IdentityPort


def get_competition_port() -> CompetitionPort:
    return competition_port


def get_identity_port() -> IdentityPort:
    return identity_port
