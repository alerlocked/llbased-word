"""
Task package (lightweight).

Why this exists:
- Some services (e.g. `NodeDocumentWriter`) expect `app.tasks.*` import paths.
- In the current repo, Celery is not wired (no Celery app instance / worker).
- We keep a tiny, dependency-free task shim to avoid runtime ImportError and
  keep the main workflow running deterministically.
"""

