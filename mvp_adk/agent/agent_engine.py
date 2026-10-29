"""What Agent Engine serves: the coordinator wrapped by ADK's AdkApp, which gives it session and streaming methods.

Agent Engine imports this module and uses `agent_engine`. The container has no database file, so one is seeded here.
"""

import os

from vertexai.agent_engines import AdkApp

from mvp_adk.agent.agents import make_coordinator
from mvp_common.tools.db import ensure_database

DATABASE = "/tmp/lumio.db"


os.environ["LUMIO_DB"] = DATABASE
ensure_database()
agent_engine = AdkApp(agent=make_coordinator())
