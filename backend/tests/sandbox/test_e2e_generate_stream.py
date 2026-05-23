"""
End-to-end test: simulate the full AI panel → generate_stream flow

Mimics what the frontend does:
1. Upload a temp file (parse to HTML)
2. Send "帮我完善这份工艺文件" via generate-stream logic
3. Verify: intent recognized, plan generated, auto-confirm executed, content returned

This test exercises the SAME code path as the real frontend,
just without the HTTP/SSE layer.
"""
import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


UPLOADED_FILE_HTML = """
<h2>1. 封面</h2>
<table>
<tr><td>文件编号</td><td>2080.S2427</td></tr>
<tr><td>产品代号</td><td>KA0-0-KZD</td></tr>
<tr><td>产品名称</td><td>某型导弹</td></tr>
<tr><td>文件名称</td><td>全弹设备电缆装配工艺规程</td></tr>
</table>

<h2>4. 材料定额明细</h2>
<table>
<tr><td>1</td><td>电缆组件 KA6-0-KZD</td><td>—</td><td>件</td><td>1</td></tr>
<tr><td>2</td><td>固定卡箍</td><td>Φ3~Φ8</td><td>件</td><td>16</td></tr>
</table>

<h2>8. 工序页</h2>
<h3>工序 1：装配前准备</h3>
<p>核对零部件数量，确认与装配件明细一致</p>
<h3>工序 2：电缆敷设与连接</h3>
<p>按电气走向图将电缆组件依次敷设至各设备接口</p>
"""

USER_INPUT = "帮我完善这份不完整的工艺文件，从结构和内容两个方面完善"


async def test_e2e():
    """Full end-to-end: context → orchestrator → auto-confirm → result"""
    from app.api.agent import _build_orchestrator_context, _save_memory
    from app.agents.orchestrator.orchestrator import ProcessOrchestrator
    from app.agents.orchestrator.interaction_models import UserResponse, InputType

    print("=" * 60)
    print("E2E Test: AI Panel → generate_stream full flow")
    print("=" * 60)

    # ── Step 1: Build context (same as generate_stream does) ──
    print("\n[Step 1] Build orchestrator context...")
    from pydantic import BaseModel, Field
    from typing import Optional, List

    class FakeRequest(BaseModel):
        session_id: Optional[str] = None
        content: Optional[str] = None
        user_input: Optional[str] = None
        user_id: Optional[int] = None
        project_id: Optional[int] = None
        domain: Optional[str] = None
        reference_materials: Optional[List[dict]] = None
        chat_history: Optional[List[dict]] = None
        uploaded_file_content: Optional[str] = None
        uploaded_file_name: Optional[str] = None

    req = FakeRequest(
        session_id="test-e2e-session",
        content=USER_INPUT,
        user_id=1,
        project_id=1,
        uploaded_file_content=UPLOADED_FILE_HTML,
        uploaded_file_name="工艺规程_不完整版.docx",
    )

    orch_context = _build_orchestrator_context(req, USER_INPUT, "write")

    assert orch_context.get("has_uploaded_file"), "FAIL: has_uploaded_file not set"
    assert orch_context.get("uploaded_file_content"), "FAIL: uploaded_file_content missing"
    assert orch_context.get("doc_context"), "FAIL: doc_context missing (knowledge base not loaded)"
    print(f"  doc_context: {len(orch_context['doc_context'])} chars")
    print(f"  material_status.has_documents: {orch_context.get('material_status', {}).get('has_documents')}")
    print("  PASS")

    # ── Step 2: Orchestrator process_intent ──
    print("\n[Step 2] Call orchestrator.process_intent()...")
    orchestrator = ProcessOrchestrator()

    orch_result = await orchestrator.process_intent(
        user_input=USER_INPUT,
        context=orch_context,
        task_name="E2E-test-完善工艺文件",
    )

    assert orch_result.get("success"), f"FAIL: process_intent failed: {orch_result.get('error')}"
    intent_type = orch_result.get("intent", {}).get("type", "unknown")
    print(f"  intent: {intent_type}")

    if not orch_result.get("requires_response"):
        print("  FAIL: expected requires_response=True (draft_complete plan)")
        print(f"  Got: {list(orch_result.keys())}")
        return False

    plan = orch_result.get("modification_plan", "")
    print(f"  plan length: {len(plan)} chars")
    print(f"  plan preview: {plan[:200]}")
    print("  PASS")

    # ── Step 3: Auto-confirm (same as generate_stream does) ──
    print("\n[Step 3] Auto-confirm and execute...")
    confirm_response = UserResponse(
        session_id="test-e2e-session",
        response_type=InputType.TEXT,
        content="确认执行",
        selected_option="confirm",
    )

    exec_result = await orchestrator.continue_conversation(
        user_response=confirm_response,
    )

    if not exec_result.get("success"):
        error = exec_result.get("error", "unknown")
        print(f"  FAIL: continue_conversation error: {error}")
        return False

    print("  Execution succeeded")

    # ── Step 4: Verify result has content ──
    print("\n[Step 4] Verify output content...")
    # Structure: exec_result.result.agent_result.result = {success, result: {content: "..."}}
    result_wrapper = exec_result.get("result", {})
    agent_result = result_wrapper.get("agent_result", {})
    new_content = ""
    if isinstance(agent_result, dict):
        inner = agent_result.get("result", {})
        if isinstance(inner, dict):
            new_content = inner.get("content") or inner.get("result", {}).get("content", "")

    if not new_content:
        print(f"  FAIL: no content in result.")
        print(f"  exec_result keys: {list(exec_result.keys())}")
        print(f"  result_wrapper keys: {list(result_wrapper.keys()) if isinstance(result_wrapper, dict) else 'not a dict'}")
        print(f"  content_updated: {result_wrapper.get('content_updated')}")
        if isinstance(agent_result, dict):
            print(f"  agent_result keys: {list(agent_result.keys())}")
            print(f"  agent_result status: {agent_result.get('status')}")
            print(f"  agent_result type: {agent_result.get('type')}")
            inner = agent_result.get("result", {})
            print(f"  inner type: {type(inner)}, len: {len(str(inner))}")
            if isinstance(inner, dict):
                print(f"  inner keys: {list(inner.keys())}")
                for k in inner:
                    v = inner[k]
                    print(f"    {k}: type={type(v).__name__}, len={len(str(v))}")
        return False

    print(f"  content length: {len(new_content)} chars")
    safe_preview = new_content[:300].encode('ascii', errors='replace').decode('ascii')
    print(f"  content preview: {safe_preview}")
    print("  PASS")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("E2E Test Result: ALL PASSED")
    print("=" * 60)
    return True


if __name__ == "__main__":
    result = asyncio.run(test_e2e())
    sys.exit(0 if result else 1)
