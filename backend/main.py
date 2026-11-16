"""Entry point: `uvicorn main:app --app-dir backend`."""
from hl2.api import create_app

app = create_app()
