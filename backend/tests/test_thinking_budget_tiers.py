"""T1: per-tier thinking budget — simple tier off, complex tier tunable."""
from app.services.llm_service import llm_service
from app.config import settings


class TestThinkingExtraBody:
    def test_simple_tier_thinking_off_by_default(self):
        body = llm_service._thinking_extra_body("simple")
        assert body == {"enable_thinking": False, "thinking_budget": 0}

    def test_complex_tier_thinking_on_with_budget(self):
        body = llm_service._thinking_extra_body("complex")
        assert body["enable_thinking"] is True
        assert body["thinking_budget"] > 0

    def test_env_override_takes_effect(self, monkeypatch):
        monkeypatch.setattr(settings, "THINKING_BUDGET_COMPLEX", 512)
        body = llm_service._thinking_extra_body("complex")
        assert body["thinking_budget"] == 512

    def test_types_coerced(self, monkeypatch):
        # .env values arrive as strings when injected via env — coerce safely
        monkeypatch.setattr(settings, "THINKING_ENABLED_COMPLEX", "true")
        monkeypatch.setattr(settings, "THINKING_BUDGET_COMPLEX", "256")
        body = llm_service._thinking_extra_body("complex")
        assert body == {"enable_thinking": True, "thinking_budget": 256}


class TestCollectStreamUsesTierBody:
    async def test_collect_stream_passes_tier_extra_body(self, monkeypatch):
        """The create() call must receive the per-tier body (not the old hardcoded 1024)."""
        captured = {}

        class FakeStream:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

        async def fake_create(**kwargs):
            captured.update(kwargs)
            return FakeStream()

        class FakeClient:
            chat = type("Chat", (), {"completions": type("Completions", (), {"create": staticmethod(fake_create)})})()

        monkeypatch.setattr(llm_service, "_simple_client", FakeClient())
        await llm_service._collect_stream_content(
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.1,
            max_tokens=100,
            tier="simple",
        )
        assert captured["extra_body"] == {"enable_thinking": False, "thinking_budget": 0}
