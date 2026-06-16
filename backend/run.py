from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.app import create_app
from backend.config import Config

app = create_app()

if __name__ == "__main__":
    app.run(debug=Config.DEBUG, port=Config.PORT)
