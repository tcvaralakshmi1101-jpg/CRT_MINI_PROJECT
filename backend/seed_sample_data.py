from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.database.connection import init_pool, execute_schema
from backend.database.seed import seed_sample_data
from backend.services.patient_service import rebuild_heap


def main() -> None:
    init_pool()
    execute_schema()
    seed_sample_data()
    rebuild_heap()
    print("Loaded 10 sample patients and rebuilt the queue.")


if __name__ == "__main__":
    main()
