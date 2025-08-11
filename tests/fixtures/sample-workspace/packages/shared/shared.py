"""Shared utilities."""

from database import Database

def get_db():
    """Get database connection."""
    return Database()
