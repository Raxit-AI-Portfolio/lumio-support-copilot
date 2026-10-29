"""Cloud helpers shared by up.py and down.py: enable APIs, create and delete the Model Armor template."""

import time
from urllib.parse import quote

import google.auth
from google.auth.transport.requests import AuthorizedSession

from mvp_common.core.config import get_setting

REGION = "us-central1"
TEMPLATE_ID = "lumio-mvp"
APIS = [
    "aiplatform.googleapis.com",
    "vectorsearch.googleapis.com",
    "modelarmor.googleapis.com",
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
]
SERVICE = "lumio-mvp"  # Cloud Run service of mvp_adk
LC_SERVICE = "lumio-lc"  # Cloud Run service of mvp_lc
SOURCE_BUCKET_PREFIX = "run-sources-"


def project() -> str:
    """Return the project id from settings."""
    return get_setting("GOOGLE_CLOUD_PROJECT")


def template_url() -> str:
    """Return the Model Armor API address of the lumio-mvp template."""
    return f"https://modelarmor.{REGION}.rep.googleapis.com/v1/projects/{project()}/locations/{REGION}/templates"


def make_session() -> AuthorizedSession:
    """A session that signs calls with the ADC login."""
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    session = AuthorizedSession(credentials)
    session.headers["x-goog-user-project"] = project()
    return session


def enable_apis(session: AuthorizedSession) -> None:
    """Turn on the APIs the MVP uses. Enabling an API that is already on does nothing."""
    url = f"https://serviceusage.googleapis.com/v1/projects/{project()}/services:batchEnable"
    reply = session.post(url, json={"serviceIds": APIS}, timeout=60)
    reply.raise_for_status()
    operation = reply.json().get("name", "")
    for _ in range(30):
        if not operation or session.get(f"https://serviceusage.googleapis.com/v1/{operation}", timeout=60).json().get(
            "done"
        ):
            return
        time.sleep(3)


def create_template(session: AuthorizedSession) -> str:
    """Create the Model Armor template (prompt injection and jailbreak filter). Returns "created" or "exists"."""
    body = {
        "filterConfig": {
            "piAndJailbreakFilterSettings": {"filterEnforcement": "ENABLED", "confidenceLevel": "MEDIUM_AND_ABOVE"}
        }
    }
    reply = session.post(f"{template_url()}?templateId={TEMPLATE_ID}", json=body, timeout=60)
    if reply.status_code == 409:
        return "exists"
    reply.raise_for_status()
    return "created"


def delete_template(session: AuthorizedSession) -> str:
    """Delete the Model Armor template. Returns "deleted" or "none"."""
    return delete_and_report(session, f"{template_url()}/{TEMPLATE_ID}")


def delete_and_report(session: AuthorizedSession, url: str) -> str:
    """Send a DELETE. Returns "deleted", or "none" if the resource was not there."""
    reply = session.delete(url, timeout=60)
    if reply.status_code == 404:
        return "none"
    reply.raise_for_status()
    return "deleted"


def delete_cloud_run(session: AuthorizedSession) -> str:
    """Delete the Cloud Run services of both frameworks."""
    base = f"https://run.googleapis.com/v2/projects/{project()}/locations/{REGION}/services"
    return ", ".join(f"{name}: {delete_and_report(session, f'{base}/{name}')}" for name in (SERVICE, LC_SERVICE))


def delete_registry_repo(session: AuthorizedSession) -> str:
    """Delete the Artifact Registry repo that deploying from source creates."""
    base = f"https://artifactregistry.googleapis.com/v1/projects/{project()}/locations/{REGION}"
    return delete_and_report(session, f"{base}/repositories/cloud-run-source-deploy")


def delete_source_buckets(session: AuthorizedSession) -> list[str]:
    """Empty and delete the upload buckets of deploying from source (names start with run-sources-<project>-)."""
    api = "https://storage.googleapis.com/storage/v1/b"
    prefix = f"{SOURCE_BUCKET_PREFIX}{project()}-"
    listing = session.get(api, params={"project": project()}, timeout=60)
    listing.raise_for_status()
    deleted = []
    for bucket in listing.json().get("items", []):
        if not bucket["name"].startswith(prefix):
            continue
        objects = session.get(f"{api}/{bucket['name']}/o", timeout=60).json()
        for item in objects.get("items", []):
            delete_and_report(session, f"{api}/{bucket['name']}/o/{quote(item['name'], safe='')}")
        delete_and_report(session, f"{api}/{bucket['name']}")
        deleted.append(bucket["name"])
    return deleted
