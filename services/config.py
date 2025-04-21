import json
import os
from typing import Dict, Any

class ConfigManager:
    def __init__(self, config_file="settings.json"):
        self.config_file = config_file
        self.defaults = {
            "people": True,
            "helmets": True,
            "vests": True,
            "threshold": 5
        }

    def load(self) -> Dict[str, Any]:
        """Load settings from JSON file or return defaults"""
        if os.path.exists(self.config_file):
            with open(self.config_file, "r") as f:
                return {**self.defaults, **json.load(f)}
        return self.defaults

    def save(self, settings: Dict[str, Any]):
        """Save settings to JSON file (only non-default values)"""
        with open(self.config_file, "w") as f:
            json.dump(
                {k: v for k, v in settings.items() if v != self.defaults.get(k)},
                f,
                indent=2
            )