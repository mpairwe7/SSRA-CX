"""Keep API tests in explicit synthetic/reference mode."""

import os

os.environ["SSRA_RUNTIME_MODE"] = "reference"
