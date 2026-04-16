"""
Tests for should_compress integration and message preservation.
Covers fix #5: compression threshold check and short message handling.
"""
import pytest


class TestShouldCompressIntegration:
    """should_compress must gate actual compression in ProgressiveContextLoader."""

    def test_should_compress_below_threshold_returns_false(self):
        """Below 85% token usage, should_compress returns False."""
        from app.services.context_engineering import ContextCompressor

        compressor = ContextCompressor()
        # 1000 / 32000 = 0.03, well below 0.85
        assert compressor.should_compress(
            current_tokens=1000,
            max_tokens=32000,
            history_turns=20,
        ) is False

    def test_should_compress_above_threshold_but_few_turns(self):
        """Above 85% tokens but < 16 turns should not compress."""
        from app.services.context_engineering import ContextCompressor

        compressor = ContextCompressor()
        # 28000 / 32000 = 0.875 > 0.85, but only 10 turns
        assert compressor.should_compress(
            current_tokens=28000,
            max_tokens=32000,
            history_turns=10,
        ) is False

    def test_should_compress_triggered(self):
        """Both conditions met: 85%+ tokens AND 16+ turns."""
        from app.services.context_engineering import ContextCompressor

        compressor = ContextCompressor()
        assert compressor.should_compress(
            current_tokens=28000,
            max_tokens=32000,
            history_turns=20,
        ) is True

    def test_should_compress_zero_max_tokens(self):
        """Zero max_tokens should not crash."""
        from app.services.context_engineering import ContextCompressor

        compressor = ContextCompressor()
        assert compressor.should_compress(100, 0, 20) is False


class TestCompressKeyInfoPreservesShortMessages:
    """Short messages (confirmations) must not be truncated."""

    def test_short_confirmation_preserved(self):
        """Messages <= 100 chars should be kept intact."""
        from app.services.context_engineering import ContextCompressor

        compressor = ContextCompressor()
        history = [
            {"role": "user", "content": "好的"},
            {"role": "assistant", "content": "已确认，继续执行"},
            {"role": "user", "content": "确认方案A"},
        ]

        result = compressor._compress_key_info(history)
        assert result[0]["content"] == "好的"
        assert result[1]["content"] == "已确认，继续执行"
        assert result[2]["content"] == "确认方案A"

    def test_long_message_with_keywords_compressed(self):
        """Long messages with keywords get key sentence extraction."""
        from app.services.context_engineering import ContextCompressor

        compressor = ContextCompressor()
        history = [
            {
                "role": "assistant",
                "content": (
                    "经过分析，我们决定采用方案B进行热处理。"
                    "该方案的温度控制在800-850度范围内。"
                    "保温时间为2小时。"
                    "冷却方式为随炉冷却至室温。"
                    "出炉后需进行硬度检测。"
                    "其他参数详见附表。"
                    "后续还需要进行金相组织分析。"
                    "最终确认方案需要用户签字。"
                    "以上为热处理工艺的详细说明。"
                ),
            }
        ]

        result = compressor._compress_key_info(history)
        # Should contain key sentences with keywords
        content = result[0]["content"]
        assert "决定" in content or "确认" in content or "方案" in content

    def test_long_message_without_keywords_truncated(self):
        """Long messages without keywords get truncated to 50 chars."""
        from app.services.context_engineering import ContextCompressor

        compressor = ContextCompressor()
        long_content = "这是一段很长的描述文字" * 20  # 180+ chars
        history = [{"role": "assistant", "content": long_content}]

        result = compressor._compress_key_info(history)
        assert result[0]["content"].endswith("...")
        assert len(result[0]["content"]) <= 60  # 50 chars + "..."

    def test_empty_history_returns_empty(self):
        """Empty history should return empty list."""
        from app.services.context_engineering import ContextCompressor

        compressor = ContextCompressor()
        result = compressor._compress_key_info([])
        assert result == []
