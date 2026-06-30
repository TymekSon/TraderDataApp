"""Entry point – run the Trader Data App."""

import argparse
import logging
import sys

import yaml


def setup_logging(config_path: str = "config.yaml"):
    """Configure logging from config.yaml or sensible defaults."""
    try:
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        log_cfg = cfg.get("logging", {})
        level = getattr(logging, log_cfg.get("level", "INFO").upper(), logging.INFO)
        log_file = log_cfg.get("file", "app.log")
    except Exception:
        level = logging.INFO
        log_file = "app.log"

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main():
    parser = argparse.ArgumentParser(description="Trader Data App — Fundamental Analysis for ES Futures")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    parser.add_argument("--port", type=int, default=8050, help="Port to serve on (default: 8050)")
    args = parser.parse_args()

    setup_logging(args.config)

    from app.dashboard import run_server
    run_server(config_path=args.config, debug=args.debug, port=args.port)


if __name__ == "__main__":
    main()
