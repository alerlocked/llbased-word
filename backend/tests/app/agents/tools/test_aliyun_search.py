"""
测试阿里云搜索工具
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.agents.tools.aliyun_search import AliyunSearchTool
from app.shared.config import UNRELIABLE_DOMAINS


class TestAliyunSearchTool:
    """阿里云搜索工具测试类"""

    @pytest.mark.unit
    def test_init_without_credentials(self):
        """测试无凭证初始化"""
        mock_config = Mock()
        mock_config.ALIYUN_ACCESS_KEY_ID = None
        mock_config.ALIYUN_ACCESS_KEY_SECRET = None
        mock_config.ALIYUN_IQS_ENDPOINT = 'test-endpoint'

        tool = AliyunSearchTool(mock_config)
        assert tool.client is None

    @pytest.mark.unit
    def test_simplify_query_empty(self):
        """测试空查询简化"""
        mock_config = Mock()
        tool = AliyunSearchTool(mock_config)

        result = tool._simplify_query("")
        assert result == ""

    @pytest.mark.unit
    def test_simplify_query_normalization(self):
        """测试查询标准化"""
        mock_config = Mock()
        tool = AliyunSearchTool(mock_config)

        # 测试换行符替换
        result = tool._simplify_query("line1\nline2\nline3")
        assert result == "line1 line2 line3"

        # 测试首尾空格去除
        result = tool._simplify_query("  test query  ")
        assert result == "test query"

    @pytest.mark.unit
    def test_extract_images_with_unreliable_domains(self):
        """测试提取图片时过滤不可靠域名"""
        mock_config = Mock()
        tool = AliyunSearchTool(mock_config)

        # 测试不可靠域名
        test_cases = [
            ('http://example.com/image.jpg', False),
            ('http://xdnimg.13520.info/image.jpg', True),
            ('http://youpinqf.com/image.jpg', True),
            ('http://jiutuvip.com/image.jpg', True),
            ('http://chongso.com/image.jpg', True),
            ('http://baidu.com/image.jpg', True),  # 应在不可靠域名列表中
        ]

        for url, should_be_unreliable in test_cases:
            # 这里我们测试配置是否被正确导入
            url_lower = url.lower()
            is_unreliable = any(domain in url_lower for domain in UNRELIABLE_DOMAINS)
            assert is_unreliable == should_be_unreliable, f"URL {url} 可靠性判断错误"

    @pytest.mark.unit
    def test_is_reliable_source(self):
        """测试源可靠性判断"""
        mock_config = Mock()
        tool = AliyunSearchTool(mock_config)

        # 测试可靠来源
        reliable_url = "http://sinaimg.cn/news/image.jpg"
        assert tool._is_reliable_source(reliable_url) is True

        # 测试不可靠来源
        unreliable_url = "http://xdnimg.13520.info/test.jpg"
        assert tool._is_reliable_source(unreliable_url) is False

        # 测试默认情况
        unknown_url = "http://unknown-domain.com/test.jpg"
        assert tool._is_reliable_source(unknown_url) is True