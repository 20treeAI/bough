"""Configuration handling for bough."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

import yaml


@dataclass
class BoughConfig:
    """Configuration for bough analysis."""

    buildable: List[str]
    ignore: List[str]


def load_config(config_path: Path) -> BoughConfig:
    """Load configuration from .bough.yml file."""
    defaults = BoughConfig(buildable=["apps/*"], ignore=["*.md"])
    
    if not config_path.exists():
        logging.info(f"Config file not found at {config_path}, using defaults")
        return defaults
    
    try:
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
        
        if data is None:
            data = {}
        
        return BoughConfig(
            buildable=data.get('buildable', defaults.buildable),
            ignore=data.get('ignore', defaults.ignore)
        )
    except yaml.YAMLError as e:
        logging.warning(f"Invalid YAML in {config_path}: {e}. Using defaults.")
        return defaults
    except Exception as e:
        logging.warning(f"Failed to parse config {config_path}: {e}. Using defaults.")
        return defaults
