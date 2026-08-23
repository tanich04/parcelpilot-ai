from pathlib import Path
import os

# Project root (one level above src/)
BASE_DIR = Path(__file__).resolve().parent.parent

DB_PATH = os.getenv(
    "DB_PATH",
    str(BASE_DIR / "parcelpilot.db")
)

CHROMA_PATH = os.getenv(
    "CHROMA_PATH",
    str(BASE_DIR / "chroma_db")
)
