"""Handles reading and loading of the bough config."""

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class BoughConfig:
    """A configuration for bough."""

    buildable: list[str]
    ignore: list[str]


def load_config(config_path: Path) -> BoughConfig:
    """Read and load the config."""
    defaults = BoughConfig(buildable=["apps/*"], ignore=["*.md"])

    if not config_path.exists():
        logger.info(f"Config file not found at {config_path}, using defaults")
        return defaults

    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)

        if data is None:
            data = {}

        return BoughConfig(
            buildable=data.get("buildable", defaults.buildable),
            ignore=data.get("ignore", defaults.ignore),
        )
    except yaml.YAMLError:
        logger.exception(f"Invalid YAML in {config_path}. Using defaults.")
        return defaults
    except Exception:
        logger.exception(f"Failed to parse config {config_path}. Using defaults.")
        return defaults
