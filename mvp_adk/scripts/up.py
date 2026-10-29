"""Create the cloud resources for mvp_adk: everything in mvp_common.scripts.up, plus the Agent Engine with --engine.

Run from the repo root (after `python -m mvp_common.data.ingest`):
  python -m mvp_adk.scripts.up            APIs, Model Armor template, Vector Search collection
  python -m mvp_adk.scripts.up --engine   the same, plus the Agent Engine deploy (bills by the hour)
"""

import sys

from mvp_adk.agent import engine
from mvp_common.scripts import up


def main() -> None:
    """Create the shared resources, then the engine if asked."""
    up.main()
    if "--engine" in sys.argv:
        engine.create()


if __name__ == "__main__":
    main()
