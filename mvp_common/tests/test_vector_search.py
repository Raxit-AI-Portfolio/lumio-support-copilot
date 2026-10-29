import pytest

from mvp_common.data import vector_search


def test_object_body_checks_dimensions_and_makes_a_valid_id():
    chunk = {"chunk_id": "kb-pub-02-plan-tiers#2", "doc_id": "d", "access_group": "public", "vector": [0.1] * 768}
    body = vector_search.object_body(chunk)
    assert body["dataObjectId"] == "kb-pub-02-plan-tiers-2"
    assert len(body["dataObject"]["vectors"]["embedding"]["dense"]["values"]) == 768
    with pytest.raises(ValueError):
        vector_search.object_body({**chunk, "vector": [0.1] * 10})


def test_search_sends_the_role_filter_and_maps_distance_to_score(monkeypatch):
    sent = {}

    def fake_call(self, method, url, body=None, allowed=()):
        sent["body"] = body
        return {"results": [{"distance": 0.8, "dataObject": {"data": {"chunk_id": "a#1", "title": "A"}}}]}

    monkeypatch.setattr(vector_search.VectorIndex, "__init__", lambda self: setattr(self, "collection", "c"))
    monkeypatch.setattr(vector_search.VectorIndex, "call", fake_call)
    index = vector_search.VectorIndex()
    hits = index.search([0.0] * 768, ["public", "customer"], 3)
    assert hits == [{"chunk_id": "a#1", "title": "A", "score": 0.8}]
    assert sent["body"]["vectorSearch"]["filter"] == {
        "$or": [{"access_group": {"$eq": "public"}}, {"access_group": {"$eq": "customer"}}]
    }
    assert index.search([0.0] * 768, [], 3) == []
