from datetime import datetime, timezone


class RelojSistema:
    def ahora(self) -> datetime:
        return datetime.now(timezone.utc)
