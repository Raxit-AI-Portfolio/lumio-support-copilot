"""Deploy a framework web app to Cloud Run, reachable only with IAM. The owner runs it (gcloud and Cloud Build)."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from mvp_common.core.config import COMMON_DIR, get_setting
from mvp_common.scripts import cloud

EXCLUDE = ["__pycache__", ".env", "*.db", "tests", "evals", ".pytest_cache", "engine_resource.txt", "*.md"]


def stage(framework_dir: Path) -> Path:
    """Copy the framework folder and mvp_common to a temp folder without secrets, databases or tests."""
    staged = Path(tempfile.mkdtemp())
    for folder in (framework_dir, COMMON_DIR):
        shutil.copytree(folder, staged / folder.name, ignore=shutil.ignore_patterns(*EXCLUDE))
    return staged


def env_vars() -> str:
    """Environment for the service: the project, plus Model Armor and Vector Search if they are set locally."""
    pairs = {"GOOGLE_CLOUD_PROJECT": cloud.project()}
    for name in ["MODEL_ARMOR_TEMPLATE", "USE_VECTOR_SEARCH", "MODEL", "MODEL_LOCATION", "EMBED_LOCATION"]:
        if get_setting(name):
            pairs[name] = get_setting(name)
    return ",".join(f"{name}={value}" for name, value in pairs.items())


def deploy(service: str, framework_dir: Path) -> None:
    """Stage a clean copy with the framework's Dockerfile and hand it to gcloud."""
    staged = stage(framework_dir)
    shutil.copy(framework_dir / "Dockerfile", staged / "Dockerfile")
    gcloud = shutil.which("gcloud")
    if gcloud is None:
        sys.exit("gcloud was not found on PATH. Install the Google Cloud CLI first.")
    command = [
        gcloud,
        "run",
        "deploy",
        service,
        "--source",
        str(staged),
        "--project",
        cloud.project(),
        "--region",
        cloud.REGION,
        "--no-allow-unauthenticated",
        "--max-instances",
        "1",
        "--memory",
        "1Gi",
        "--set-env-vars",
        env_vars(),
        "--quiet",
    ]
    print("running:", " ".join(command))
    sys.exit(subprocess.run(command, check=False).returncode)
