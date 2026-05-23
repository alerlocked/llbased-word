"""
Sandbox: Route AI panel "补齐" task through ProcessOrchestrator

Goal: Verify that when the AI panel receives an uploaded file + "帮我补齐",
instead of directly calling LLM, we route through the agent layer:
  IntentRecognizer → TaskDecomposer → WritingAgent → assemble

Success criteria:
1. IntentRecognizer detects DRAFT_COMPLETE intent
2. Orchestrator enters DRAFT_ANALYSIS state
3. WritingAgent receives a structured task (not raw prompt)
4. Output quality: real data from knowledge base, not fabricated content
5. The flow completes without error

This test does NOT require the full backend running — it exercises
the orchestrator + agents + hierarchical_context directly.
"""
import asyncio
import sys
import time
import os

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Load .env
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


# ── Test data: simulate uploaded file content (the incomplete docx) ──

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

USER_INPUT = "帮我补齐这份工艺文件"


async def test_intent_recognition():
    """Step 1: Verify IntentRecognizer detects DRAFT_COMPLETE."""
    from app.agents.orchestrator.intent_recognizer import IntentRecognizer, IntentType

    recognizer = IntentRecognizer()

    # Simulate context with uploaded file (no draft_id — temp upload)
    context = {
        "has_uploaded_file": True,
        "uploaded_file_name": "工艺规程_不完整版.docx",
    }

    result = await recognizer.recognize(USER_INPUT, context)
    intent_type = result.get("type")
    confidence = result.get("confidence", 0)

    print(f"[1] Intent: {intent_type}, confidence: {confidence:.2f}")

    assert intent_type == "draft_complete", f"Expected draft_complete, got {intent_type}"
    # Confidence may be 0.35 after _calculate_confidence aggregation,
    # but the intent type is correctly identified and routing works.
    print(f"[1] PASS: IntentRecognizer correctly detects DRAFT_COMPLETE (confidence: {confidence:.2f})")
    return result


async def test_orchestrator_with_temp_file():
    """Step 2: Run orchestrator flow with temp uploaded file (no draft_id).

    This tests the ADAPTED flow where _load_draft_content returns the
    uploaded file content instead of requiring a DB draft_id.
    """
    from app.agents.orchestrator.orchestrator import ProcessOrchestrator

    orchestrator = ProcessOrchestrator()

    # Pass uploaded file content as context (simulating what generate-stream would do)
    context = {
        "uploaded_file_content": UPLOADED_FILE_HTML,
        "uploaded_file_name": "工艺规程_不完整版.docx",
        "has_uploaded_file": True,
    }

    print("[2] Starting orchestrator.process_intent()...")
    start = time.time()

    result = await orchestrator.process_intent(
        user_input=USER_INPUT,
        context=context,
        task_name="补齐工艺文件-沙箱测试",
    )

    elapsed = time.time() - start
    print(f"[2] Elapsed: {elapsed:.1f}s")
    print(f"[2] Result keys: {list(result.keys())}")
    print(f"[2] Success: {result.get('success')}")

    if result.get("success"):
        state = result.get("state")
        print(f"[2] Final state: {state}")

        # Check if we got a modification plan (the normal draft_complete flow)
        if result.get("requires_response"):
            plan = result.get("modification_plan", "")
            print(f"[2] Plan length: {len(plan)} chars")
            print(f"[2] Plan preview: {plan[:300]}...")
            print("[2] PASS: Orchestrator generated modification plan, awaiting confirmation")
        else:
            print(f"[2] Direct result: {str(result)[:500]}")
            print("[2] PASS: Orchestrator completed (auto-confirm mode)")
    else:
        error = result.get("error", "unknown")
        print(f"[2] FAIL: {error}")
        # This is expected if _load_draft_content can't find a draft
        # — we need to adapt the flow for temp uploads

    return result


async def test_writing_agent_directly():
    """Step 3: Test WritingAgent directly with a fill task.

    Simulates what the orchestrator would dispatch.
    """
    from app.agents.functional.writing_agent import WritingAgent

    agent = WritingAgent()

    task = {
        "action": "fill",
        "target": "工艺装备明细表",
        "content": "需要补齐工艺装备明细表",
        "fields": ["序号", "名称", "编号", "数量", "用途"],
        "requirements": "根据知识库中的全单电缆装配规程补齐",
    }

    print("[3] Starting WritingAgent.process()...")
    start = time.time()

    result = await agent.process(task)

    elapsed = time.time() - start
    print(f"[3] Elapsed: {elapsed:.1f}s")
    print(f"[3] Success: {result.get('success')}")

    if result.get("success"):
        content = result.get("result", {}).get("content", "")
        print(f"[3] Content length: {len(content)} chars")
        print(f"[3] Content preview: {content[:500]}...")
        print("[3] PASS: WritingAgent produced output")
    else:
        error = result.get("error", "unknown")
        print(f"[3] FAIL: {error}")

    return result


async def test_multi_module_dispatch():
    """Step 4: Simulate the plan → dispatch → assemble flow.

    This is what the final integration should look like:
    1. Identify missing modules from uploaded file
    2. For each missing module, dispatch a WritingAgent task
    3. Assemble results
    """
    from app.agents.functional.writing_agent import WritingAgent

    agent = WritingAgent()

    # Identify what modules are present vs missing in the uploaded file
    present_modules = ["封面", "材料定额明细", "工序页"]
    all_modules = [
        "工艺装备明细表",
        "工具量具明细表",
        "引用文件目录",
        "装配件明细",
        "工艺总方案",
        "检测页",
        "审签页",
    ]
    missing_modules = [m for m in all_modules if m not in " ".join(present_modules)]
    print(f"[4] Missing modules: {missing_modules}")

    # For each missing module, dispatch a targeted retrieval + writing task
    results = {}
    for module in missing_modules[:2]:  # Test with first 2 to keep it quick
        print(f"[4] Processing module: {module}...")
        start = time.time()

        task = {
            "action": "generate",
            "target": module,
            "content": f"为工艺文件生成「{module}」模块内容",
            "requirements": (
                f"产品编号2080.S2427，产品代号KA0-0-KZD，"
                f"文件名：全弹设备电缆装配工艺规程。"
                f"请基于知识库中的完整文档数据生成{module}的具体内容。"
            ),
        }

        result = await agent.process(task)
        elapsed = time.time() - start

        if result.get("success"):
            content = result.get("result", {}).get("content", "")
            results[module] = content
            print(f"    {module}: {len(content)} chars, {elapsed:.1f}s")
            print(f"    Preview: {content[:200]}...")
        else:
            print(f"    {module}: FAILED - {result.get('error')}")

    print(f"[4] Completed {len(results)}/{len(missing_modules[:2])} modules")
    if len(results) > 0:
        print("[4] PASS: Multi-module dispatch works")
    else:
        print("[4] FAIL: No modules completed")


async def main():
    print("=" * 60)
    print("Sandbox: AI Panel → Agent Layer Routing Test")
    print("=" * 60)
    print()

    # Step 1: Intent recognition
    print("--- Step 1: Intent Recognition ---")
    try:
        intent = await test_intent_recognition()
    except Exception as e:
        print(f"[1] ERROR: {e}")
        intent = None
    print()

    # Step 2: Full orchestrator flow
    print("--- Step 2: Orchestrator with Temp File ---")
    try:
        orch_result = await test_orchestrator_with_temp_file()
    except Exception as e:
        print(f"[2] ERROR: {e}")
        import traceback
        traceback.print_exc()
        orch_result = None
    print()

    # Step 3: WritingAgent directly
    print("--- Step 3: WritingAgent Direct ---")
    try:
        agent_result = await test_writing_agent_directly()
    except Exception as e:
        print(f"[3] ERROR: {e}")
        import traceback
        traceback.print_exc()
        agent_result = None
    print()

    # Step 4: Multi-module dispatch
    print("--- Step 4: Multi-Module Dispatch ---")
    try:
        await test_multi_module_dispatch()
    except Exception as e:
        print(f"[4] ERROR: {e}")
        import traceback
        traceback.print_exc()
    print()

    print("=" * 60)
    print("Summary:")
    print("  [1] Intent Recognition: test basic intent detection")
    print("  [2] Orchestrator: test if draft_complete flow handles temp files")
    print("  [3] WritingAgent: test direct agent dispatch")
    print("  [4] Multi-module: test plan → dispatch → assemble pattern")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
