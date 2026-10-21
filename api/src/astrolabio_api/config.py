"""Runtime settings, read once from environment variables.

Every knob the API reads from the environment lives here, so there is a single
place to see what can be configured.
"""

import os
from dataclasses import dataclass
from typing import Literal

Environment = Literal["production", "development"]


@dataclass(frozen=True)
class Settings:
    # "development" enables /docs and /openapi.json. Anything else is production.
    environment: Environment = "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ.get("ASTROLABIO_ENV", "production")
        return cls(environment="development" if env == "development" else "production")
