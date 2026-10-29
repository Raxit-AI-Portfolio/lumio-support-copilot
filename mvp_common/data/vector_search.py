"""Vertex AI Vector Search 2.0 for the KB chunks, over REST (request shapes proven in the M0.5 spike, HLD 9.7).

Run from the repo root:
  python -m mvp_common.data.vector_search load     create the collection and upload the chunks from kb_index.json
  python -m mvp_common.data.vector_search delete    delete all objects and the collection
"""

import json
import re
import sys
import time

import google.auth
from google.auth.transport.requests import AuthorizedSession

from mvp_common.core.config import INDEX_FILE, get_setting

API_ROOT = "https://vectorsearch.googleapis.com/v1"
COLLECTION_ID = "kb-chunks"
DIMENSIONS = 768
DATA_FIELDS = ["chunk_id", "doc_id", "title", "section", "text", "source_uri", "access_group"]
OBJECT_ID = re.compile(r"^[a-z](?:[-a-z0-9]{0,61}[a-z0-9])?$")


def object_id(chunk_id: str) -> str:
    """Make a valid object id from a chunk id."""
    name = chunk_id.replace("#", "-")
    if not OBJECT_ID.match(name):
        raise ValueError(f"{chunk_id}: not a valid object id")
    return name


def object_body(chunk: dict) -> dict:
    """Build one batchCreate request item."""
    if len(chunk["vector"]) != DIMENSIONS:
        raise ValueError(f"{chunk['chunk_id']}: expected {DIMENSIONS} numbers")
    data = {name: chunk.get(name, "") for name in DATA_FIELDS}
    data["source_uri"] = chunk["chunk_id"]
    return {
        "dataObjectId": object_id(chunk["chunk_id"]),
        "dataObject": {"data": data, "vectors": {"embedding": {"dense": {"values": chunk["vector"]}}}},
    }


def parse_results(reply: dict) -> list[dict]:
    """Turn a search reply into chunk dicts with a "score" (the service returns a similarity as `distance`)."""
    hits = []
    for item in reply.get("results", []):
        hit = dict(item.get("dataObject", {}).get("data", {}))
        hit["score"] = item.get("distance", 0.0)
        hits.append(hit)
    return hits


class VectorIndex:
    """The kb-chunks collection. One login session is reused for all calls."""

    def __init__(self):
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        self.session = AuthorizedSession(credentials)
        self.project = get_setting("GOOGLE_CLOUD_PROJECT")
        region = get_setting("VECTOR_REGION", "us-central1")
        self.parent = f"projects/{self.project}/locations/{region}"
        self.collection = f"{self.parent}/collections/{COLLECTION_ID}"

    def call(self, method: str, url: str, body: dict | None = None, allowed: tuple = ()) -> dict:
        """Call the API. Statuses in `allowed` return {"status": code} instead of raising."""
        headers = {"x-goog-user-project": self.project}
        reply = self.session.request(method, url, headers=headers, json=body, timeout=60)
        if reply.status_code in allowed:
            return {"status": reply.status_code}
        reply.raise_for_status()
        return reply.json() if reply.content else {}

    def wait_for(self, operation: dict) -> None:
        """Wait until a long-running operation is done."""
        if not operation.get("name"):
            return
        for _ in range(40):
            if self.call("GET", f"{API_ROOT}/{operation['name']}").get("done"):
                return
            time.sleep(3)
        raise TimeoutError("operation did not finish")

    def exists(self) -> bool:
        """Return True if the collection exists."""
        return self.call("GET", f"{API_ROOT}/{self.collection}", allowed=(404,)).get("status") != 404

    def ensure_collection(self) -> None:
        """Create the collection if it does not exist."""
        if self.exists():
            return
        body = {
            "dataSchema": {"type": "object", "properties": {name: {"type": "string"} for name in DATA_FIELDS}},
            "vectorSchema": {"embedding": {"denseVector": {"dimensions": DIMENSIONS}}},
        }
        self.wait_for(self.call("POST", f"{API_ROOT}/{self.parent}/collections?collectionId={COLLECTION_ID}", body))

    def object_names(self) -> list[str]:
        """Return the full names of the objects in the collection (one page of up to 1000)."""
        url = f"{API_ROOT}/{self.collection}/dataObjects:query"
        body = {"outputFields": {"dataFields": ["chunk_id"]}, "pageSize": 1000}
        return [item["name"] for item in self.call("POST", url, body, allowed=(404,)).get("dataObjects", [])]

    def delete_objects(self) -> None:
        """Delete every object in the collection."""
        for name in self.object_names():
            self.call("DELETE", f"{API_ROOT}/{name}", allowed=(404,))

    def load(self) -> int:
        """Upload every chunk in kb_index.json, replacing what is there. Returns the object count."""
        chunks = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        self.ensure_collection()
        self.delete_objects()
        requests = [object_body(chunk) for chunk in chunks]
        for start in range(0, len(requests), 500):
            body = {"requests": requests[start : start + 500]}
            self.call("POST", f"{API_ROOT}/{self.collection}/dataObjects:batchCreate", body)
        return len(requests)

    def delete(self) -> None:
        """Delete all objects, then the collection."""
        if not self.exists():
            print("no collection")
            return
        self.delete_objects()
        self.wait_for(self.call("DELETE", f"{API_ROOT}/{self.collection}"))
        print("deleted")

    def search(self, vector: list[float], groups: list[str], top_k: int) -> list[dict]:
        """Nearest chunks whose access_group is in `groups`, best first, each with a "score"."""
        if not groups:
            return []
        filters = [{"access_group": {"$eq": group}} for group in groups]
        search = {
            "searchField": "embedding",
            "vector": {"values": vector},
            "topK": top_k,
            "searchHint": {"knnHint": {}},
            "outputFields": {"dataFields": DATA_FIELDS},
            "filter": filters[0] if len(filters) == 1 else {"$or": filters},
        }
        reply = self.call("POST", f"{API_ROOT}/{self.collection}/dataObjects:search", {"vectorSearch": search})
        return parse_results(reply)


if __name__ == "__main__":
    if sys.argv[1:] == ["load"]:
        print(f"loaded {VectorIndex().load()} objects")
    elif sys.argv[1:] == ["delete"]:
        VectorIndex().delete()
    else:
        sys.exit("usage: python -m mvp_common.data.vector_search load|delete")
