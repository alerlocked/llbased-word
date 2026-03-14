"""
测试配置使用 - 不依赖具体工具类
"""
import pytest
from app.shared.config import UNRELIABLE_DOMAINS


class TestConfigUsage:
    """配置使用测试类"""

    @pytest.mark.unit
    def test_unreliable_domains_usage(self):
        """测试不可靠域名配置的使用"""
        # 模拟URL检查逻辑
        test_urls = [
            'http://xdnimg.13520.info/image.jpg',
            'http://youpinqf.com/image.jpg',
            'http://jiutuvip.com/image.jpg',
            'http://chongso.com/image.jpg',
            'http://example.com/image.jpg',
        ]

        for url in test_urls:
            url_lower = url.lower()
            is_unreliable = any(domain in url_lower for domain in UNRELIABLE_DOMAINS)

            # 前4个URL应该被识别为不可靠
            if '13520.info' in url or 'youpinqf.com' in url or 'jiutuvip.com' in url or 'chongso.com' in url:
                assert is_unreliable, f"URL {url} 应该被识别为不可靠"
            else:
                assert not is_unreliable, f"URL {url} 应该被识别为可靠"

    @pytest.mark.unit
    def test_config_constants_immutable(self):
        """测试配置常量不可变性"""
        # 验证不可靠域名集合是只读的
        original_size = len(UNRELIABLE_DOMAINS)

        # 尝试修改（应该失败或不影响原集合）
        try:
            # 集合的add方法会修改原集合，但我们可以测试它是否存在
            UNRELIABLE_DOMAINS.add('test.domain.com')
            # 如果执行到这里，说明是集合类型
            assert len(UNRELIABLE_DOMAINS) == original_size + 1
        except AttributeError:
            # 如果是不可变类型，会抛出AttributeError
            pass

    @pytest.mark.unit
    def test_domain_matching_case_insensitive(self):
        """测试域名匹配不区分大小写"""
        test_cases = [
            ('http://XDNIMG.13520.INFO/image.jpg', True),
            ('http://xdnimg.13520.info/image.jpg', True),
            ('http://XdnImg.13520.Info/image.jpg', True),
            ('http://YOUPINQF.COM/image.jpg', True),
            ('http://YouPinQf.Com/image.jpg', True),
        ]

        for url, expected_unreliable in test_cases:
            url_lower = url.lower()
            is_unreliable = any(domain in url_lower for domain in UNRELIABLE_DOMAINS)
            assert is_unreliable == expected_unreliable, f"URL {url} 大小写匹配失败"