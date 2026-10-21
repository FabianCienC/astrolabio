"""Runtime settings, read once from environment variables.

Every knob the API reads from the environment lives here, so there is a single
place to see what can be configured.
"""

import os
import re
from dataclasses import dataclass
from typing import Literal

Environment = Literal["production", "development"]
Source = Literal["cluster", "example"]

PUBLIC_ORIGIN = "https://astrolabio.fabiancienfuegos.com"
_LOCAL_ORIGIN = re.compile(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$")


@dataclass(frozen=True)
class Settings:
    # "development" enables /docs and /openapi.json. Anything else is production.
    environment: Environment = "production"
    # "cluster" watches the cluster (in-cluster token, or kubeconfig outside a pod);
    # "example" serves the example galaxy without touching any cluster.
    source: Source = "cluster"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    def allows_origin(self, origin: str | None) -> bool:
        """Browsers send Origin on WebSockets: only the site itself may open `/ws`
        (plus local dev servers in development)."""
        if origin == PUBLIC_ORIGIN:
            return True
        return self.is_development and bool(origin) and _LOCAL_ORIGIN.match(origin) is not None

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ.get("ASTROLABIO_ENV", "production")
        source = os.environ.get("ASTROLABIO_SOURCE", "cluster")
        return cls(
            environment="development" if env == "development" else "production",
            source="example" if source == "example" else "cluster",
        )
