"""
测试 DraftDocument 和 DraftVersion 数据模型
Phase 1 - PIV: piv_20260411_draft_models_phase1
"""
import pytest
from datetime import datetime

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.models.database import Base, DraftDocument, DraftVersion


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine():
    """内存 SQLite 引擎，仅用于测试"""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()


# ---------------------------------------------------------------------------
# DraftDocument 测试
# ---------------------------------------------------------------------------

class TestDraftDocument:
    def test_table_exists(self, engine):
        """表 draft_documents 应被正确创建"""
        names = inspect(engine).get_table_names()
        assert "draft_documents" in names

    def test_create_instance(self, session):
        """能正常创建 DraftDocument 实例"""
        doc = DraftDocument(
            title="测试文件",
            file_path="/data/test.pdf",
            file_type="pdf",
            parsed_content={"pages": 5},
            content="<p>Hello</p>",
            status="draft",
            project_id=1,
        )
        session.add(doc)
        session.commit()

        assert doc.id is not None
        assert doc.title == "测试文件"
        assert doc.file_type == "pdf"
        assert doc.parsed_content == {"pages": 5}
        assert doc.content == "<p>Hello</p>"
        assert doc.status == "draft"
        assert doc.project_id == 1
        assert doc.created_at is not None

    def test_default_values(self, session):
        """默认值应正确设置"""
        doc = DraftDocument(title="minimal")
        session.add(doc)
        session.commit()

        assert doc.status is None or doc.status == "draft"
        assert doc.content == ""

    def test_all_columns(self, engine):
        """验证所有字段都存在"""
        cols = {c["name"] for c in inspect(engine).get_columns("draft_documents")}
        expected = {
            "id", "title", "file_path", "file_type",
            "parsed_content", "content", "status", "project_id",
            "created_at", "updated_at",
        }
        assert expected == cols


# ---------------------------------------------------------------------------
# DraftVersion 测试
# ---------------------------------------------------------------------------

class TestDraftVersion:
    def test_table_exists(self, engine):
        """表 draft_versions 应被正确创建"""
        names = inspect(engine).get_table_names()
        assert "draft_versions" in names

    def test_create_instance(self, session):
        """能正常创建 DraftVersion 实例"""
        # 先创建 DraftDocument
        doc = DraftDocument(title="parent doc")
        session.add(doc)
        session.flush()

        ver = DraftVersion(
            draft_id=doc.id,
            snapshot_content="<p>Version 1</p>",
            snapshot_source="user_edit",
        )
        session.add(ver)
        session.commit()

        assert ver.id is not None
        assert ver.draft_id == doc.id
        assert ver.snapshot_content == "<p>Version 1</p>"
        assert ver.snapshot_source == "user_edit"
        assert ver.created_at is not None

    def test_snapshot_sources(self, session):
        """验证三种合法 snapshot_source"""
        doc = DraftDocument(title="source test")
        session.add(doc)
        session.flush()

        for source in ("ai_complete", "user_edit", "rollback"):
            ver = DraftVersion(
                draft_id=doc.id,
                snapshot_content=f"<p>{source}</p>",
                snapshot_source=source,
            )
            session.add(ver)
        session.commit()

        versions = session.query(DraftVersion).all()
        assert len(versions) == 3
        assert {v.snapshot_source for v in versions} == {
            "ai_complete", "user_edit", "rollback"
        }

    def test_all_columns(self, engine):
        """验证所有字段都存在"""
        cols = {c["name"] for c in inspect(engine).get_columns("draft_versions")}
        expected = {
            "id", "draft_id", "snapshot_content",
            "snapshot_source", "created_at",
        }
        assert expected == cols


# ---------------------------------------------------------------------------
# 现有模型不受影响
# ---------------------------------------------------------------------------

class TestExistingModelsUnchanged:
    def test_existing_tables_still_exist(self, engine):
        """原有表不应受影响"""
        names = inspect(engine).get_table_names()
        required = [
            "articles", "projects", "knowledge_cards", "materials",
            "creation_projects", "editor_versions", "search_results",
            "figures", "annotations", "citations",
        ]
        for t in required:
            assert t in names, f"Missing existing table: {t}"
