"""Delete everything up.py created, then run the leftover check. Safe to run twice.

Run from the repo root: python -m mvp_common.scripts.down
"""

import subprocess
import sys

from mvp_common.data.vector_search import VectorIndex
from mvp_common.scripts import cloud


def main() -> None:
    """Delete the Vector Search collection and the Model Armor template, then audit."""
    VectorIndex().delete()
    session = cloud.make_session()
    print(f"model armor template: {cloud.delete_template(session)}")
    print(f"cloud run service: {cloud.delete_cloud_run(session)}")
    print(f"artifact registry repo: {cloud.delete_registry_repo(session)}")
    print(f"source buckets deleted: {cloud.delete_source_buckets(session)}")
    print("audit:")
    subprocess.run([sys.executable, "-m", "mvp_common.scripts.audit", "--project", cloud.project()], check=False)


if __name__ == "__main__":
    main()
