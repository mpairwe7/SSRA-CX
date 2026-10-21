"""Keep agent-runtime tests in explicit synthetic/reference mode."""

import os

os.environ["SSRA_RUNTIME_MODE"] = "reference"
