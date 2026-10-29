from mvp_common.core.config import KB_DIR
from mvp_common.data.chunking import make_chunks
from mvp_common.data.embeddings import normalize
from mvp_common.data.search import rank_chunks


def test_every_kb_file_makes_chunks_with_a_group():
    paths = list(KB_DIR.glob("*.md"))
    assert len(paths) == 20
    for path in paths:
        chunks = make_chunks(path.read_text(encoding="utf-8"))
        assert chunks
        assert chunks[0]["access_group"] in ("public", "customer", "internal")


def test_customer_never_sees_internal_chunks():
    chunks = [
        {"chunk_id": "a", "access_group": "public", "vector": [1.0, 0.0]},
        {"chunk_id": "b", "access_group": "internal", "vector": [1.0, 0.0]},
    ]
    customer_ids = [hit["chunk_id"] for hit in rank_chunks([1.0, 0.0], chunks, "customer")]
    agent_ids = [hit["chunk_id"] for hit in rank_chunks([1.0, 0.0], chunks, "agent")]
    assert customer_ids == ["a"]
    assert sorted(agent_ids) == ["a", "b"]


def test_normalized_vectors_have_length_one_so_dot_product_equals_cosine():
    vector = normalize([3.0, 4.0])
    assert vector == [0.6, 0.8]
    assert normalize([0.0, 0.0]) == [0.0, 0.0]


def test_best_match_ranks_first_and_unknown_role_sees_nothing():
    chunks = [
        {"chunk_id": "far", "access_group": "public", "vector": [0.0, 1.0]},
        {"chunk_id": "near", "access_group": "public", "vector": [1.0, 0.1]},
    ]
    assert rank_chunks([1.0, 0.0], chunks, "customer")[0]["chunk_id"] == "near"
    assert rank_chunks([1.0, 0.0], chunks, "stranger") == []


def test_config_paths_point_at_the_mvp_folder():
    from mvp_common.core.config import COMMON_DIR, SEED_DIR

    assert COMMON_DIR.name == "mvp_common"
    assert KB_DIR.is_dir()
    assert (SEED_DIR / "users.json").is_file()
