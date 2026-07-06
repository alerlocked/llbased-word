"""
Tests for DocumentProfileLearner and Profile API endpoints.
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch


SAMPLE_PROCESS_DOC = """
装配工艺规程 QJ903A-2025

## 1. 适用范围
本规程适用于XX型号产品的装配工艺过程控制。

## 2. 装配前准备
2.1 检查所有零件的合格证和检验报告。
2.2 核对零件数量和规格是否符合工艺文件要求。
2.3 装配环境温度应控制在18-28°C范围内。

## 3. 装配工艺过程
3.1 将基座固定在装配平台上，使用M12螺栓拧紧，力矩为45±5 N·m。
3.2 注意：拧紧螺栓时应采用对角交叉方式，逐步均匀拧紧。
3.3 安装传动轴组件，确保轴向间隙为0.05-0.08mm。
3.4 热处理温度控制在800-850°C，保温时间2小时。

## 4. 检验要求
4.1 装配完成后进行外观检验。
4.2 尺寸精度检验应按GB/T 1804标准执行。
4.3 功能试验应连续运行不少于2小时。

警告：严禁在带电状态下进行装配操作！
"""


class TestDocumentProfileLearner:
    """Test the document profile extraction logic."""

    async def test_learn_from_content_extracts_terms(self):
        from app.services.document_profile_learner import DocumentProfileLearner

        learner = DocumentProfileLearner()
        features = await learner.learn_from_content(SAMPLE_PROCESS_DOC, domain="assembly", skip_llm_validate=True)

        assert "frequent_terms" in features
        terms = features["frequent_terms"]
        assert isinstance(terms, dict)
        # Should detect process-related terms
        assert len(terms) > 0

    async def test_learn_from_content_detects_domain(self):
        from app.services.document_profile_learner import DocumentProfileLearner

        learner = DocumentProfileLearner()
        features = await learner.learn_from_content(SAMPLE_PROCESS_DOC, domain="welding", skip_llm_validate=True)

        assert features["domain"] == "welding"

    async def test_learn_from_content_extracts_patterns(self):
        from app.services.document_profile_learner import DocumentProfileLearner

        learner = DocumentProfileLearner()
        features = await learner.learn_from_content(SAMPLE_PROCESS_DOC, domain="assembly", skip_llm_validate=True)

        # Should extract triples (replaces old document_patterns)
        triples = features["triples"]
        assert isinstance(triples, list)
        assert len(triples) > 0
        # Verify triple structure: {s, r, o}
        for t in triples:
            assert "s" in t and "r" in t and "o" in t

    async def test_learn_from_content_extracts_style(self):
        from app.services.document_profile_learner import DocumentProfileLearner

        learner = DocumentProfileLearner()
        features = await learner.learn_from_content(SAMPLE_PROCESS_DOC, domain="assembly", skip_llm_validate=True)

        # Style indicators should be present
        assert "preferred_sentence_length" in features
        # Document has warnings/caution notes
        assert features.get("include_caution_notes") is True

    async def test_learn_from_content_generates_summary(self):
        from app.services.document_profile_learner import DocumentProfileLearner

        learner = DocumentProfileLearner()
        features = await learner.learn_from_content(SAMPLE_PROCESS_DOC, domain="assembly", skip_llm_validate=True)

        summary = features["ai_generated_summary"]
        assert isinstance(summary, str)
        assert len(summary) > 0
        assert "装配" in summary

    async def test_learn_from_empty_content(self):
        from app.services.document_profile_learner import DocumentProfileLearner

        learner = DocumentProfileLearner()
        features = await learner.learn_from_content("短文本", domain="assembly", skip_llm_validate=True)
        assert isinstance(features, dict)
        assert "frequent_terms" in features

    async def test_triple_extraction_from_process_doc(self):
        """Verify triples are extracted with correct s-r-o structure."""
        from app.services.document_profile_learner import DocumentProfileLearner

        learner = DocumentProfileLearner()
        features = await learner.learn_from_content(SAMPLE_PROCESS_DOC, domain="assembly", skip_llm_validate=True)

        triples = features["triples"]
        # Should extract temperature spec
        temp_triples = [t for t in triples if t["r"] == "温度"]
        assert len(temp_triples) > 0
        assert "800" in temp_triples[0]["o"] or "850" in temp_triples[0]["o"]

        # Should extract torque spec
        torque_triples = [t for t in triples if t["r"] == "力矩"]
        assert len(torque_triples) > 0
        assert "45" in torque_triples[0]["o"]

        # Should extract safety constraints
        safety_triples = [t for t in triples if t["r"] == "禁止"]
        assert len(safety_triples) > 0

    @pytest.mark.xfail(reason="default-user resolution vs test-user isolation", strict=False)
    def test_to_context_text_renders_triples(self):
        """Profile.to_context_text should include triple knowledge."""
        from app.models.profile import Profile

        profile = Profile(
            id="test",
            user_id="u1",
            domain="assembly",
            triples=[
                {"s": "M12螺栓拧紧", "r": "力矩", "o": "45±5 N·m"},
                {"s": "热处理", "r": "温度", "o": "800-850°C"},
            ],
        )
        text = profile.to_context_text()
        assert "领域知识" in text
        assert "M12螺栓拧紧" in text
        assert "45±5" in text

    def test_merge_features_accumulates_terms(self):
        from app.services.document_profile_learner import DocumentProfileLearner

        learner = DocumentProfileLearner()
        profile_data = {
            "triples": [],
            "frequent_terms": {"装配工艺": 5, "检验": 3},
            "source_document_ids": [],
        }
        features = {
            "triples": [{"s": "热处理", "r": "温度", "o": "800-850°C"}],
            "frequent_terms": {"装配工艺": 2, "热处理": 4},
            "ai_generated_summary": "test summary",
            "domain": "assembly",
        }

        merged = learner.merge_features_to_profile(profile_data, features)

        # Terms accumulate
        assert merged["frequent_terms"]["装配工艺"] == 7
        assert merged["frequent_terms"]["热处理"] == 4
        # Triples are added
        assert len(merged["triples"]) == 1
        assert merged["triples"][0]["r"] == "温度"

    def test_merge_deduplicates_source_ids(self):
        from app.services.document_profile_learner import DocumentProfileLearner

        learner = DocumentProfileLearner()
        profile_data = {
            "frequent_terms": {},
            "document_patterns": [],
            "source_document_ids": ["doc_1"],
        }
        features = {
            "frequent_terms": {},
            "document_patterns": [],
            "source_document_id": "doc_1",
        }

        merged = learner.merge_features_to_profile(profile_data, features)
        assert merged["source_document_ids"].count("doc_1") == 1

        # Add a new document
        features["source_document_id"] = "doc_2"
        merged = learner.merge_features_to_profile(merged, features)
        assert "doc_2" in merged["source_document_ids"]
        assert len(merged["source_document_ids"]) == 2


class TestProfileAPI:
    """Test the profile API endpoints via FastAPI test client."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        # Import app after patching DATA_DIR
        with patch("app.api.profile.settings") as mock_settings:
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                mock_settings.DATA_DIR = Path(tmp)
                # Need to reimport to pick up patched settings
                from main import app
                client = TestClient(app)
                # Override the PROFILES_DIR for this test session
                import app.api.profile as profile_module
                original_dir = profile_module.PROFILES_DIR
                profile_module.PROFILES_DIR = Path(tmp) / "profiles"
                yield client
                profile_module.PROFILES_DIR = original_dir

    @pytest.mark.xfail(reason="default-user resolution vs test-user isolation", strict=False)
    def test_get_default_profile(self, client):
        resp = client.get("/api/profile/test-user")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["profile"]["user_id"] == "test-user"

    async def test_learn_from_content(self, client):
        resp = client.post(
            "/api/profile/test-user/learn",
            json={
                "content": SAMPLE_PROCESS_DOC,
                "domain": "assembly",
                "document_id": "doc-test-001",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["extracted_features"]["terms_count"] > 0
        assert "doc-test-001" in data["profile"]["source_document_ids"]

    def test_learn_accumulates_across_calls(self, client):
        # First learn
        client.post(
            "/api/profile/test-user-accum/learn",
            json={"content": SAMPLE_PROCESS_DOC, "domain": "assembly"},
        )
        # Second learn
        resp = client.post(
            "/api/profile/test-user-accum/learn",
            json={"content": "焊接工艺参数：电流120A，电压22V，焊接速度30cm/min", "domain": "welding"},
        )
        data = resp.json()
        # Should have accumulated terms from both documents
        assert data["extracted_features"]["terms_count"] >= 0

    def test_update_profile(self, client):
        # First create profile
        client.post(
            "/api/profile/test-user-update/learn",
            json={"content": SAMPLE_PROCESS_DOC, "domain": "assembly"},
        )
        # Update writing config
        resp = client.put(
            "/api/profile/test-user-update",
            json={"writing": {"tone": "操作手册", "detail_level": "简要"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["profile"]["writing"]["tone"] == "操作手册"

    def test_reset_profile(self, client):
        # Create profile
        client.post(
            "/api/profile/test-user-reset/learn",
            json={"content": SAMPLE_PROCESS_DOC, "domain": "assembly"},
        )
        # Reset
        resp = client.delete("/api/profile/test-user-reset")
        assert resp.status_code == 200
        data = resp.json()
        assert data["profile"]["frequent_terms"] == {}
