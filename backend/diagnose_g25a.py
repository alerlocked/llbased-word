# Direct G25a generation probe — verify content fills after max_tokens fix.
# Calls WritingAgent._do_template_fill with real assembly_steps (material 1),
# bypassing orchestrator/frontend. One LLM call, focused on the content-empty
# root cause (max_tokens truncation).
# Run: conda run -n gywj --no-capture-output python diagnose_g25a.py
import os
import sys
import json
import asyncio

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from app.services.hierarchical_context import hierarchical_context as hc
from app.agents.functional.writing_agent import WritingAgent

DOC_DIR = "1"
asm = hc.extract_assembly_steps(DOC_DIR)
ordered = sorted(asm)
step_names = [asm[k].get("name", "") for k in ordered]
print(f"[probe] assembly_steps: {len(asm)} 工序, names={step_names}")

tpl = json.loads(
    open(os.path.join(_HERE, "app/templates/assembly_process_template.json"), encoding="utf-8").read()
)
g25a = next(c for c in tpl["chapters"] if c["code"] == "G25a")
slots = list(g25a.get("columns", [])) + list(g25a.get("sub_sections", []))

task = {
    "chapter_code": "G25a",
    "chapter_type": g25a["table_type"],  # process_card
    "chapter_title": g25a["title"],
    "template_slots": slots,
    "ai_guidance": g25a.get("ai_guidance", ""),
    "chapter_source_text": "",
    "params": {
        "assembly_steps": asm,
        "skeleton_steps": step_names,
        "inherited_context": {"step_names": step_names, "max_rows": len(asm)},
    },
}

# Load domain profile so principles (强约束) + triples (参考值) get injected
from pathlib import Path
from app.config import settings
from app.models.profile import Profile

_profile_path = Path(settings.DATA_DIR) / "profiles" / "assembly.json"
_profile = Profile.from_json(_profile_path) if _profile_path.exists() else None

agent = WritingAgent()
if _profile is not None:
    agent.load_profile(_profile)
    print(f"[probe] profile loaded: principles={len(_profile.principles)} triples={len(_profile.triples)}")
result = asyncio.run(agent._do_template_fill(task, None, None))

rows = result.get("filled_data") or []
print(f"\n[probe] filled_data: {len(rows)} rows")
for r in rows:
    c = (r.get("content") or "").strip()
    print(f"  row{r.get('step_no')} {r.get('step_name')!r} content[{len(c)}]: {c[:140]!r}")
nonempty = sum(1 for r in rows if (r.get("content") or "").strip())
print(f"\n[probe] 非空content行: {nonempty}/{len(rows)}")
inspection_rows = sum(1 for r in rows if (r.get("step_name") or "") == "检验")
op_rows = sum(1 for r in rows if (r.get("step_name") or "") != "检验")
ratio = (inspection_rows / op_rows) if op_rows else 0.0
print(f"[probe] inspection_rows={inspection_rows} op_rows={op_rows} 比值={ratio:.2f}")
flag = "✅" if inspection_rows <= op_rows else "❌"
print(f"[probe] 检验≤工序? {flag} (目标 inspection_rows ≤ {op_rows}, baseline=38)")
if nonempty > 0:
    print("[probe] RESULT ✅ content 出来了（max_tokens 修复有效）")
else:
    print("[probe] RESULT ❌ content 仍空（需查 LLM 截断/分批）")
