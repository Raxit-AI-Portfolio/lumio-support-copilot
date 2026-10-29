"""Delete everything up.py created for mvp_adk, including the Agent Engine, then run the leftover check.

Run from the repo root: python -m mvp_adk.scripts.down
"""

from mvp_adk.agent import engine
from mvp_common.scripts import down


def main() -> None:
    """Delete the engine, then the shared resources and the audit."""
    engine.delete()
    down.main()


if __name__ == "__main__":
    main()
