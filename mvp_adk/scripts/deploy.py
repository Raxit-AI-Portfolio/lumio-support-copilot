"""Deploy the ADK web app and agent to Cloud Run, reachable only with IAM. You run this one: it uses Cloud Build.

Run from the repo root: python -m mvp_adk.scripts.deploy
Then open the service through a local proxy (needs your login): the proxy command for the lumio-mvp service,
region us-central1, port 8080.
"""

from mvp_adk.agent.engine import ADK_DIR
from mvp_common.scripts import cloud, cloud_run

if __name__ == "__main__":
    cloud_run.deploy(cloud.SERVICE, ADK_DIR)
