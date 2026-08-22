"""Unit tests for N4 workspace material management APIs.

Covers:
- DELETE /projects/{id}/materials/{mid}: remove / idempotent / 404 unknown
  project / material row preserved (only the reference is dropped)
- GET /materials: folder_id / model / specialty fields present
- GET /projects/{id}/materials: selected_material_ids mirrors project.material_ids

In-memory SQLite + TestClient with get_db overridden (never touches craftdoc.db).
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.models.database import Base, Material, CreationProject, MaterialFolder
from app.api.creation import router as creation_router


@pytest.fixture
def harness(monkeypatch):
    """(TestClient, sessionmaker) wired to an in-memory SQLite DB."""
    # StaticPool: single shared connection so the in-memory DB is visible
    # across TestClient's worker thread and the test thread.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    app = FastAPI()
    app.include_router(creation_router, prefix="/api/creation")

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), factory


def _seed(db_factory):
    """One folder, two materials, one project selecting material 1."""
    with db_factory() as db:
        db.add(MaterialFolder(id=7, name="装配", sort_order=0))
        db.add(Material(id=1, name="a.pdf", material_type="pdf",
                        folder_id=7, model="XX-1", specialty="assembly"))
        db.add(Material(id=2, name="b.pdf", material_type="pdf"))
        db.add(CreationProject(id=100, name="p", material_ids=[1]))
        db.commit()


class TestRemoveMaterial:
    def test_remove_drops_reference_only(self, harness):
        client, factory = harness
        _seed(factory)

        resp = client.delete("/api/creation/projects/100/materials/1")
        assert resp.status_code == 200
        assert resp.json()["removed"] is True

        with factory() as db:
            project = db.get(CreationProject, 100)
            assert project.material_ids == []
            # Material body preserved
            assert db.get(Material, 1) is not None

    def test_remove_idempotent_when_not_selected(self, harness):
        client, factory = harness
        _seed(factory)

        resp = client.delete("/api/creation/projects/100/materials/2")
        assert resp.status_code == 200
        assert resp.json()["removed"] is False

        with factory() as db:
            assert db.get(CreationProject, 100).material_ids == [1]

    def test_remove_unknown_project_404(self, harness):
        client, _ = harness
        resp = client.delete("/api/creation/projects/999/materials/1")
        assert resp.status_code == 404


class TestMaterialsListFields:
    def test_folder_model_specialty_present(self, harness):
        client, factory = harness
        _seed(factory)

        resp = client.get("/api/creation/materials")
        assert resp.status_code == 200
        items = {i["id"]: i for i in resp.json()["items"]}
        assert items[1]["folder_id"] == 7
        assert items[1]["model"] == "XX-1"
        assert items[1]["specialty"] == "assembly"
        # None fields are still present (explicit keys)
        assert items[2]["folder_id"] is None
        assert items[2]["model"] is None


class TestProjectMaterialsSelected:
    def test_selected_material_ids_reflects_project(self, harness):
        client, factory = harness
        _seed(factory)

        data = client.get("/api/creation/projects/100/materials").json()
        assert data["selected_material_ids"] == [1]

    def test_documents_carry_specialty_for_profile_learning(self, harness):
        """domain fix: list must expose specialty so the frontend learns
        the profile into the right domain library (not always assembly)."""
        client, factory = harness
        _seed(factory)

        docs = {d["id"]: d for d in client.get("/api/creation/projects/100/materials").json()["documents"]}
        assert docs[1]["specialty"] == "assembly"
        assert docs[2]["specialty"] is None  # explicit key, frontend falls back

    def test_unknown_project_returns_empty_selection(self, harness):
        client, _ = harness
        data = client.get("/api/creation/projects/0/materials").json()
        assert data["selected_material_ids"] == []


class TestProjectDeleteKeepsMaterials:
    """2026-08-22 incident: deleting a project silently shredded the shared
    materials checked into its working area. Materials are global library
    assets — project delete must only unbind, never delete."""

    def test_delete_project_preserves_selected_materials(self, harness, tmp_path, monkeypatch):
        client, factory = harness
        _seed(factory)
        # material 1 is checked into project 100's working area
        from app.config import settings
        monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))

        resp = client.delete("/api/creation/projects/100")
        assert resp.status_code == 200

        with factory() as db:
            assert db.get(Material, 1) is not None, "material must survive project deletion"
            assert db.get(Material, 2) is not None
