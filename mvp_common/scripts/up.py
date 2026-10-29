"""Create the MVP's cloud resources. Safe to run twice.

Run from the repo root (after `python -m mvp_common.data.ingest`):
  python -m mvp_common.scripts.up            APIs, Model Armor template, Vector Search collection
  (mvp_adk has its own wrapper with --engine: the same, plus the Agent Engine deploy)
"""

from mvp_common.data.vector_search import VectorIndex
from mvp_common.scripts import cloud


def main() -> None:
    """Create everything, then print the settings to put in mvp_common/.env."""
    session = cloud.make_session()
    cloud.enable_apis(session)
    print("apis: enabled")
    print(f"model armor template: {cloud.create_template(session)}")
    print(f"vector search: loaded {VectorIndex().load()} objects")
    template = f"projects/{cloud.project()}/locations/{cloud.REGION}/templates/{cloud.TEMPLATE_ID}"
    print("put in mvp_common/.env:")
    print(f"  MODEL_ARMOR_TEMPLATE={template}")
    print("  USE_VECTOR_SEARCH=1")


if __name__ == "__main__":
    main()
