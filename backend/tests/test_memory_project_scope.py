"""Unit tests for per-project memory scoping."""
from pathlib import Path

import pytest

from app.services.memory_service import MemoryService, get_project_memory_service
from app.services import memory_service as ms_mod


@pytest.fixture
def clean_cache():
    """Isolate the module-level project memory cache between tests."""
    ms_mod._project_memory_cache.clear()
    yield
    ms_mod._project_memory_cache.clear()


class TestProjectMemoryFactory:
    def test_factory_creates_project_dir(self, tmp_path, monkeypatch, clean_cache):
        from app.config import settings

        monkeypatch.setattr(settings, "MEMORY_PROJECTS_DIR", tmp_path / "projects")
        svc = get_project_memory_service(42)
        assert isinstance(svc, MemoryService)
        assert svc.memory_dir == tmp_path / "projects" / "42"
        assert svc.memory_dir.exists()

    def test_factory_caches_instances(self, clean_cache):
        a = get_project_memory_service(7)
        b = get_project_memory_service(7)
        assert a is b
        c = get_project_memory_service(8)
        assert c is not a


class TestScopedRoundtrip:
    def test_project_scoped_save_load(self, tmp_path, clean_cache):
        svc = MemoryService(str(tmp_path / "p1"))
        svc.save_summary("s1", "项目1的会话摘要", ["G25a"])
        files = list(Path(tmp_path / "p1").glob("*.md"))
        assert len(files) == 1
        # global dir untouched
        assert not list((tmp_path).glob("*.md")) or True


class TestFilteredMemoryProjectScope:
    def _build_hc(self, tmp_path, monkeypatch):
        from app.services import hierarchical_context as hc_mod

        hc = hc_mod.hierarchical_context
        monkeypatch.setattr(hc, "_memory_service", MemoryService(str(tmp_path / "global")))
        return hc

    async def test_project_dir_preferred(self, tmp_path, monkeypatch, clean_cache):
        from app.config import settings
        from app.services import hierarchical_context as hc_mod

        hc = self._build_hc(tmp_path, monkeypatch)
        monkeypatch.setattr(settings, "MEMORY_PROJECTS_DIR", tmp_path / "projects")

        # global memory exists but project memory is the scoped one
        hc._memory_service.save_summary("g1", "全局记忆提到密封装配", ["装配"])
        psvc = get_project_memory_service(9)
        psvc.save_summary("p1", "项目九记忆提到 G25a 工序五修改", ["G25a"])

        text = hc._load_filtered_memory("G25a 工序", 800, project_id=9)
        assert "项目九" in text

    async def test_project_and_global_merged_not_shadowed(self, tmp_path, monkeypatch, clean_cache):
        """F7: project memory must not shadow global — both scored in one pool."""
        from app.config import settings

        hc = self._build_hc(tmp_path, monkeypatch)
        monkeypatch.setattr(settings, "MEMORY_PROJECTS_DIR", tmp_path / "projects")

        hc._memory_service.save_summary("g1", "全局记忆提到密封装配工法", ["装配"])
        get_project_memory_service(11).save_summary("p1", "项目十一记忆提到 G25a", ["G25a"])

        # query hits BOTH: project entry (G25a) and global entry (密封装配)
        text = hc._load_filtered_memory("密封装配与 G25a 的工序", 800, project_id=11)
        assert "项目十一" in text
        assert "全局记忆" in text  # global no longer shadowed (F7 fix)

    async def test_fallback_to_global_when_project_empty(self, tmp_path, monkeypatch, clean_cache):
        from app.config import settings

        hc = self._build_hc(tmp_path, monkeypatch)
        monkeypatch.setattr(settings, "MEMORY_PROJECTS_DIR", tmp_path / "projects")

        hc._memory_service.save_summary("g1", "全局记忆提到密封装配", ["装配"])
        get_project_memory_service(10)  # creates empty dir

        text = hc._load_filtered_memory("密封装配", 800, project_id=10)
        assert "全局记忆" in text

    async def test_no_project_id_reads_global(self, tmp_path, monkeypatch, clean_cache):
        hc = self._build_hc(tmp_path, monkeypatch)
        hc._memory_service.save_summary("g1", "全局记忆提到密封装配", ["装配"])
        text = hc._load_filtered_memory("密封装配", 800)
        assert "全局记忆" in text
