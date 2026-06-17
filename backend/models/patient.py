from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone

PRIORITY_LABELS = {5:"Critical", 4:"Serious", 3:"Moderate", 2:"Mild", 1:"Minor"}
LONG_WAIT_MINUTES = 180

@dataclass
class Patient:
    id                   : str
    name                 : str
    age                  : int
    gender               : str
    condition            : str
    priority             : int
    priority_label       : str
    ai_suggested_priority: int   = 0
    ai_reasoning         : str   = ""
    arrival_time         : str   = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status               : str   = "waiting"
    admitted_at          : Optional[str] = None

    def to_dict(self) -> dict:
        """Return JSON-serializable dict representation of this patient."""
        arrival_dt = self.arrival_datetime()
        wait_minutes = max(0, int((datetime.now(timezone.utc) - arrival_dt).total_seconds() // 60))
        return {
            "id"                   : self.id,
            "name"                 : self.name,
            "age"                  : self.age,
            "gender"               : self.gender,
            "condition"            : self.condition,
            "priority"             : self.priority,
            "priority_label"       : self.priority_label,
            "ai_suggested_priority": self.ai_suggested_priority,
            "ai_reasoning"         : self.ai_reasoning,
            "arrival_time"         : self.arrival_time if isinstance(self.arrival_time, str)
                                     else self.arrival_time.isoformat(),
            "wait_minutes"         : wait_minutes,
            "needs_attention"      : wait_minutes >= LONG_WAIT_MINUTES,
            "status"               : self.status,
            "admitted_at"          : self.admitted_at if isinstance(self.admitted_at, str)
                                     else (self.admitted_at.isoformat() if self.admitted_at else None)
        }

    def arrival_datetime(self) -> datetime:
        if isinstance(self.arrival_time, datetime):
            return self.arrival_time.astimezone(timezone.utc) if self.arrival_time.tzinfo else self.arrival_time.replace(tzinfo=timezone.utc)
        if isinstance(self.arrival_time, str):
            return datetime.fromisoformat(self.arrival_time.replace("Z", "+00:00"))
        raise TypeError("Unsupported arrival_time value")

    @classmethod
    def from_row(cls, row: dict) -> "Patient":
        """Construct a Patient from a psycopg2 RealDictCursor row."""
        return cls(
            id                    = str(row["id"]),
            name                  = row["name"],
            age                   = row["age"],
            gender                = row["gender"],
            condition             = row["condition"],
            priority              = row["priority"],
            priority_label        = row["priority_label"],
            ai_suggested_priority = row.get("ai_suggested_priority", 0),
            ai_reasoning          = row.get("ai_reasoning", ""),
            arrival_time          = row["arrival_time"].isoformat()
                                    if hasattr(row["arrival_time"], "isoformat")
                                    else str(row["arrival_time"]),
            status                = row.get("status", "waiting"),
            admitted_at           = row["admitted_at"].isoformat()
                                    if row.get("admitted_at") and
                                       hasattr(row["admitted_at"], "isoformat")
                                    else row.get("admitted_at")
        )
