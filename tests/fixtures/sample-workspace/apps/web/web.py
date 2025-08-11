"""Web application."""

from shared import get_db

def render_page():
    """Render web page."""
    db = get_db()
    return "<html>Hello</html>"
