from ..blackboard import BlackboardExtended


class DownloadJob:
    def __init__(self, session: BlackboardExtended):
        self._session = session
        self._cancelled = False

    @property
    def session(self) -> BlackboardExtended:
        return self._session

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        self._cancelled = True
