"""Main Dash application – server initialisation and layout wiring."""

import logging

import dash
import yaml

from data.db_init import init_db
from app.callbacks import register_callbacks

logger = logging.getLogger(__name__)


def create_app(config_path: str = "config.yaml") -> dash.Dash:
    """Build and return a fully configured Dash application."""

    # ── Load configuration ──────────────────────────────────────────
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # ── Initialise database ─────────────────────────────────────────
    db_path = config.get("database", {}).get("path", "data/analytics.db")
    db = init_db(db_path)

    # ── Create Dash instance ────────────────────────────────────────
    app = dash.Dash(
        __name__,
        title="Trader Data App",
        assets_folder="assets",
    )

    # ── Layout ──────────────────────────────────────────────────────
    from app.layout import layout
    app.layout = layout

    # ── Callbacks ───────────────────────────────────────────────────
    register_callbacks(app, db, config)

    return app


def run_server(config_path: str = "config.yaml", debug: bool = False, port: int = 8050):
    """Start the Dash development server."""
    app = create_app(config_path)
    logger.info("Starting Dash server on http://127.0.0.1:%d", port)
    app.run(debug=debug, port=port)
