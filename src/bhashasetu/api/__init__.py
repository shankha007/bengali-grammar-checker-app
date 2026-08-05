"""HTTP surface.

Spec §4 puts FastAPI in the backend and §6.2 asks for a public REST API with
per-device rate limits and OpenAPI docs. This is the subset the Phase 1 UI needs,
built so the Phase 3/4 additions are new routes rather than a rewrite.
"""

from bhashasetu.api.app import create_app

__all__ = ["create_app"]
