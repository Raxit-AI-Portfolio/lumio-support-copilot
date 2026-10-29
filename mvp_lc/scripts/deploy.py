"""Deploy the LangGraph web app and agent to Cloud Run, reachable only with IAM. You run this one: it uses Cloud Build.

Run from the repo root: python -m mvp_lc.scripts.deploy
Then open the service through a local proxy (needs your login): the proxy command for the lumio-lc service,
region us-central1, port 8081.
"""

from pathlib import Path

from mvp_common.scripts import cloud, cloud_run

if __name__ == "__main__":
    cloud_run.deploy(cloud.LC_SERVICE, Path(__file__).parent.parent)
