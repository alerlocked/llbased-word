"""
测试共享配置模块
"""
import pytest
from app.shared.config import UNRELIABLE_DOMAINS, DEBUG_CONFIG, API_CONFIG, SEARCH_CONFIG


class TestConfig:
    """配置测试类"""

    @pytest.mark.unit
    def test_unreliable_domains(self):
        """测试不可靠域名配置"""
        # 验证是不可变集合
        assert isinstance(UNRELIABLE_DOMAINS, set)

        # 验证包含预期的域名
        assert 'baidu.com' in UNRELIABLE_DOMAINS
        assert 'zhihu.com' in UNRELIABLE_DOMAINS
        assert 'github.com' in UNRELIABLE_DOMAINS

        # 验证域名数量合理
        assert len(UNRELIABLE_DOMAINS) > 20

    @pytest.mark.unit
    def test_debug_config(self):
        """测试调试配置"""
        # 验证配置结构
        assert 'log_file' in DEBUG_CONFIG
        assert 'log_level' in DEBUG_CONFIG
        assert 'max_log_size' in DEBUG_CONFIG
        assert 'log_rotation' in DEBUG_CONFIG

        # 验证日志文件配置
        assert DEBUG_CONFIG['log_file'] == 'debug_aliyun_search.log'
        assert DEBUG_CONFIG['log_level'] == 'INFO'
        assert DEBUG_CONFIG['max_log_size'] == 10 * 1024 * 1024  # 10MB
        assert DEBUG_CONFIG['log_rotation'] is True

    @pytest.mark.unit
    def test_api_config(self):
        """测试API配置"""
        # 验证配置结构
        assert 'timeout' in API_CONFIG
        assert 'retry_count' in API_CONFIG
        assert 'retry_delay' in API_CONFIG
        assert 'max_results' in API_CONFIG

        # 验证配置值合理
        assert API_CONFIG['timeout'] == 30
        assert API_CONFIG['retry_count'] == 3
        assert API_CONFIG['retry_delay'] == 1
        assert API_CONFIG['max_results'] == 20

    @pytest.mark.unit
    def test_search_config(self):
        """测试搜索配置"""
        # 验证配置结构
        assert 'safe_search' in SEARCH_CONFIG
        assert 'filter_unreliable' in SEARCH_CONFIG
        assert 'max_image_size' in SEARCH_CONFIG
        assert 'supported_formats' in SEARCH_CONFIG

        # 验证配置值
        assert SEARCH_CONFIG['safe_search'] is True
        assert SEARCH_CONFIG['filter_unreliable'] is True
        assert SEARCH_CONFIG['max_image_size'] == 5 * 1024 * 1024  # 5MB
        assert isinstance(SEARCH_CONFIG['supported_formats'], list)
        assert 'jpg' in SEARCH_CONFIG['supported_formats']