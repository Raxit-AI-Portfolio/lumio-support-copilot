"""Read-only leftover check for the lab project. Exit 0 clean, 1 leftovers, 2 could not check."""

import argparse
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass

TOKEN_COMMAND = ["gcloud", "auth", "print-access-token"]


class AuditError(Exception):
    pass


@dataclass
class Check:
    name: str
    command: list
    url: str
    list_key: str
    name_field: str
    ignore_exact: list
    ignore_suffixes: list


def command_check(name, command, name_field, ignore_exact=None, ignore_suffixes=None):
    return Check(name, command, "", "", name_field, ignore_exact or [], ignore_suffixes or [])


def http_check(name, url, list_key):
    return Check(name, [], url, list_key, "name", [], [])


CHECKS = [
    command_check(
        "cloud run services",
        ["gcloud", "run", "services", "list", "--project", "{project}", "--format", "json"],
        "metadata.name",
    ),
    command_check(
        "cloud run jobs",
        ["gcloud", "run", "jobs", "list", "--project", "{project}", "--format", "json"],
        "metadata.name",
    ),
    command_check(
        "bigquery datasets",
        ["bq", "ls", "--project_id", "{project}", "--format", "json"],
        "datasetReference.datasetId",
    ),
    command_check(
        "firestore databases",
        ["gcloud", "firestore", "databases", "list", "--project", "{project}", "--format", "json"],
        "name",
    ),
    command_check("secrets", ["gcloud", "secrets", "list", "--project", "{project}", "--format", "json"], "name"),
    command_check(
        "artifact registry repositories",
        ["gcloud", "artifacts", "repositories", "list", "--project", "{project}", "--format", "json"],
        "name",
    ),
    command_check(
        "storage buckets",
        ["gcloud", "storage", "buckets", "list", "--project", "{project}", "--format", "json"],
        "name",
        ignore_exact=["{project}-tfstate"],
    ),
    command_check(
        "compute forwarding rules",
        ["gcloud", "compute", "forwarding-rules", "list", "--project", "{project}", "--format", "json"],
        "name",
    ),
    command_check(
        "service accounts",
        ["gcloud", "iam", "service-accounts", "list", "--project", "{project}", "--format", "json"],
        "email",
        ignore_suffixes=["-compute@developer.gserviceaccount.com", "@appspot.gserviceaccount.com"],
    ),
    http_check(
        "agent engine reasoning engines",
        "https://{region}-aiplatform.googleapis.com/v1/projects/{project}/locations/{region}/reasoningEngines",
        "reasoningEngines",
    ),
    http_check(
        "model armor templates",
        "https://modelarmor.{region}.rep.googleapis.com/v1/projects/{project}/locations/{region}/templates",
        "templates",
    ),
    http_check(
        "vector search collections",
        "https://vectorsearch.googleapis.com/v1/projects/{project}/locations/{region}/collections",
        "collections",
    ),
]


def fill(text, project, region):
    return text.replace("{project}", project).replace("{region}", region)


def get_path(item, path):
    value = item
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    if value is None:
        return None
    return str(value)


def parse_items(text, list_key):
    if text is None or text.strip() == "":
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise AuditError("output is not JSON")
    if data is None:
        return []
    if list_key:
        if not isinstance(data, dict):
            raise AuditError("expected a JSON object")
        data = data.get(list_key) or []
    if not isinstance(data, list):
        raise AuditError("expected a JSON list")
    return data


def names_found(check, text, project, region):
    ignore_exact = [fill(name, project, region) for name in check.ignore_exact]
    names = []
    for item in parse_items(text, check.list_key):
        name = get_path(item, check.name_field)
        if name is None:
            name = "(unnamed)"
        short_name = name.split("/")[-1] if "/" in name else name
        if name in ignore_exact or short_name in ignore_exact:
            continue
        if name.endswith(tuple(check.ignore_suffixes)):
            continue
        names.append(short_name)
    return names


def run_one_check(check, project, region, run_command, http_get, token):
    if check.url:
        if token is None:
            raise AuditError("no access token")
        status, body = http_get(fill(check.url, project, region), token)
        if status != 200:
            raise AuditError(f"http status {status}")
        return names_found(check, body, project, region)
    args = [fill(part, project, region) for part in check.command]
    exit_code, output = run_command(args)
    if exit_code != 0:
        raise AuditError(f"command exit code {exit_code}")
    return names_found(check, output, project, region)


def get_token(run_command):
    exit_code, output = run_command(TOKEN_COMMAND)
    if exit_code != 0 or not output.strip():
        return None
    return output.strip()


def run_audit(project, region, run_command, http_get):
    lines = []
    found_count = 0
    unchecked_count = 0
    token = None
    if any(check.url for check in CHECKS):
        token = get_token(run_command)
    for check in CHECKS:
        try:
            names = run_one_check(check, project, region, run_command, http_get, token)
        except AuditError as error:
            lines.append(f"COULD NOT CHECK: {check.name} ({error})")
            unchecked_count += 1
            continue
        if not names:
            lines.append(f"ok: {check.name}")
        for name in names:
            lines.append(f"FOUND: {check.name} {name}")
            found_count += 1
    lines.append(f"summary: {found_count} found, {unchecked_count} could not be checked")
    if unchecked_count > 0:
        return 2, lines
    if found_count > 0:
        return 1, lines
    return 0, lines


def real_run_command(args):
    program = shutil.which(args[0])
    if program is None:
        return 1, ""
    try:
        result = subprocess.run([program] + args[1:], capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return 1, ""
    return result.returncode, result.stdout


def real_http_get(url, token):
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, ""
    except urllib.error.URLError:
        return 0, ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", default="us-central1")
    options = parser.parse_args()
    exit_code, lines = run_audit(options.project, options.region, real_run_command, real_http_get)
    for line in lines:
        print(line)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
