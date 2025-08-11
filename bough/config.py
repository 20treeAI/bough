"""Configuration handling for bough."""

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class BoughConfig:
    """Configuration for bough analysis."""

    buildable: List[str]
    ignore: List[str]


def load_config(config_path: Path) -> BoughConfig:
    """Load configuration from .bough.yml file."""
    # Stub implementation
    return BoughConfig(buildable=["apps/*"], ignore=["*.md"])
