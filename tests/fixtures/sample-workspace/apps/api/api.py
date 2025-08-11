"""API application."""

from auth import authenticate
from database import Database
from shared import get_db

def handle_request():
    """Handle API request."""
    db = get_db()
    return {"status": "ok"}
