from app.errors import ApiError
from app.modules.competitions.ports import CompetitionPort
from app.modules.identity.adapter import identity_port
from app.modules.identity.ports import IdentityPort


class _CompetitionPortNotWired:
    """Заглушка, пока Б1 не подключил настоящую реализацию CompetitionPort.

    Как только появится `app/modules/competitions/adapter.py` с рабочим
    портом, замените возвращаемое значение `get_competition_port()` на него.
    До тех пор организаторские маршруты результатов отвечают 500, а не падают
    молча — это ожидаемо на этапе параллельной разработки (см.
    docs/architecture.md, «Параллельный старт»).
    """

    def _not_wired(self):
        raise ApiError(500, "NOT_IMPLEMENTED", "CompetitionPort ещё не подключён (ждёт реализации Б1).")

    def lock_for_result_publication(self, competition_id, db):
        self._not_wired()

    def get_registration(self, competition_id, registration_id, db):
        self._not_wired()

    def list_participants(self, competition_id, db):
        self._not_wired()

    def complete_competition(self, competition_id, db):
        self._not_wired()

    def get_competition_disciplines(self, competition_ids, db):
        self._not_wired()

    def get_competition_status(self, competition_id, db):
        self._not_wired()


_competition_port_stub = _CompetitionPortNotWired()


def get_competition_port() -> CompetitionPort:
    return _competition_port_stub


def get_identity_port() -> IdentityPort:
    return identity_port
