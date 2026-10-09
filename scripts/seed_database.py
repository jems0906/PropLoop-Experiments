import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.main import init_db

init_db()
print("Database schema is ready and demo data is seeded when the database was empty.")
