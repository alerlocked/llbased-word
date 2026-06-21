# All-chapter empirical probe — regenerate material 1 every chapter via the real
# WritingAgent._do_template_fill pipeline, locate thin chapters + capture the
# G25a inspection/operation row baseline.
# Reuses diagnose_g25a.py patterns (conda env gywj, same sys.path inject,
# profile loads assembly.json, calls agent._do_template_fill directly).
# Run: conda run -n gywj --no-capture-output python backend/diagnose_all_chapters.py
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

# Chapters that are pure source-generated lists — do NOT inject upstream_chapters.
LIST_CHAPTERS = {"G4a", "G5a", "G10a", "B12a", "G12a", "G14a", "G19a"}

tpl = json.loads(
    open(os.path.join(_HERE, "app/templates/assembly_process_template.json"), encoding="utf-8").read()
)
chapters = tpl["chapters"]


def _template_slots(ch):
    # Flatten every structured definition a chapter exposes as template slots:
    # plain columns + sub_sections + dual_list sections + flow fields.
    slots = []
    slots.extend(ch.get("columns", []) or [])
    slots.extend(ch.get("sub_sections", []) or [])
    for sec_key in ("left_section", "right_section"):
        sec = ch.get(sec_key)
        if sec:
            slots.extend(sec.get("columns", []) or [])
    slots.extend(ch.get("shared_columns", []) or [])
    fields = ch.get("fields", [])
    if fields:
        slots.extend(fields)
    return slots


def _expected_data_cols(ch):
    # Count non-meta structured value keys (exclude seq-like positional keys).
    # Used as denominator for empty_rate. We include columns, sub_sections,
    # dual sections, shared columns and fields, but drop pure-meta keys.
    META = {"seq", "tool_seq", "gauge_seq", "step_no", "step_name", "workshop"}
    keys = []
    for c in _template_slots(ch):
        k = c.get("key")
        if k and k not in META:
            keys.append(k)
    return len(keys), keys


# Load domain profile (principles + triples) once, applied to every chapter
# (G25a is the strict consumer; others tolerate it).
from pathlib import Path
from app.config import settings
from app.models.profile import Profile

_profile_path = Path(settings.DATA_DIR) / "profiles" / "assembly.json"
_profile = Profile.from_json(_profile_path) if _profile_path.exists() else None

agent = WritingAgent()
if _profile is not None:
    agent.load_profile(_profile)
    print(
        f"[probe] profile loaded: principles={len(_profile.principles)} "
        f"triples={len(_profile.triples)}"
    )

# Pre-fetch G25a assembly data once (reused across the G25a task).
_asm_all = hc.extract_assembly_steps(DOC_DIR)
_skel_all = [ _asm_all[k].get("name", "") for k in sorted(_asm_all) ]
print(f"[probe] assembly_steps: {len(_asm_all)} 工序, names={_skel_all}")

# --- Source-length table (prove source completeness) ---
print("\n" + "=" * 78)
print("[1] 各章源文本长度 (get_chapter_content DOC_DIR=1)")
print("=" * 78)
src_lens = {}
for ch in chapters:
    title = ch["title"]
    try:
        txt = hc.get_chapter_content(DOC_DIR, title) or ""
    except Exception as e:
        txt = ""
        src_lens[title] = f"ERR:{e}"
    src_lens[title] = len(txt)
    flag = "" if len(txt) > 0 else "  <-- 无源/空"
    print(f"  {ch['code']:6s} {title:30s} source_chars={len(txt)}{flag}")


def _row_content_text(row, value_keys):
    # Pick the main long-text field for this chapter (content > step_desc >
    # material_desc > any long_text among value keys), fallback to concat.
    for k in ("content", "step_desc", "material_desc", "requirements", "tech_notes",
              "flow_step"):
        v = (row.get(k) or "").strip()
        if v:
            return v
    # field_values rows are single-key dicts; flow rows use flow_step.
    if isinstance(row, dict):
        vals = [str(v).strip() for v in row.values() if v]
        if vals:
            return vals[0]
    parts = [(row.get(k) or "").strip() for k in value_keys]
    return " ".join(p for p in parts if p)


stats = []  # list of dicts per chapter
failures = []  # (code, err)

print("\n" + "=" * 78)
print("[2] 逐章生成 (_do_template_fill, 串行真实 LLM)")
print("=" * 78)

for ch in chapters:
    code = ch["code"]
    title = ch["title"]
    ctype = ch.get("table_type", "fields")
    slots = _template_slots(ch)
    expected_cols, value_keys = _expected_data_cols(ch)

    task = {
        "chapter_code": code,
        "chapter_type": ctype,
        "chapter_title": title,
        "template_slots": slots,
        "ai_guidance": ch.get("ai_guidance", ""),
        # NOTE: _do_template_fill reads chapter_source_text from the TASK TOP
        # LEVEL (writing_agent.py:795), not params. Put it at top level so the
        # generic source actually reaches the generator.
        "chapter_source_text": hc.get_chapter_content(DOC_DIR, title) or "",
        "params": {},
    }
    upstream_note = ""
    if code in LIST_CHAPTERS:
        upstream_note = "未注入upstream(纯源生成)"
    else:
        upstream_note = "行级章节"

    # G25a extra injection (align orchestrator:2494-2526 + diagnose_g25a:40-44).
    # _do_template_fill reads assembly_steps/skeleton_steps/inherited_context
    # from both top-level and params — set both for safety.
    if code == "G25a":
        task["params"]["assembly_steps"] = _asm_all
        task["params"]["skeleton_steps"] = _skel_all
        task["params"]["inherited_context"] = {
            "step_names": _skel_all,
            "max_rows": len(_asm_all),
        }
        task["assembly_steps"] = _asm_all
        task["skeleton_steps"] = _skel_all
        task["inherited_context"] = task["params"]["inherited_context"]

    print(f"\n--- {code} {title} [{ctype}] {upstream_note} ---")
    try:
        result = asyncio.run(agent._do_template_fill(task, None, None))
    except Exception as e:
        print(f"  ❌ 生成异常: {type(e).__name__}: {e}")
        failures.append((code, f"{type(e).__name__}: {e}"))
        stats.append({
            "code": code, "title": title, "type": ctype,
            "rows_total": 0, "op_rows": 0, "insp_rows": 0,
            "non_empty_rows": 0, "empty_cells": 0, "expected_cols": expected_cols,
            "empty_rate": 1.0, "content_avg_chars": 0, "content_empty_rows": 0,
            "verdict": "生成异常", "err": str(e),
        })
        continue

    # Normalize output by table_type — _do_template_fill stores data in
    # type-specific keys, NOT always filled_data:
    #   single_row_list/process_card -> filled_data (list of rows)
    #   dual_list                    -> left_data + right_data
    #   flow_chart                   -> flow_steps (list[str])
    #   fields                       -> field_values (dict)
    rows = []
    if ctype == "dual_list":
        rows = list(result.get("left_data") or []) + list(result.get("right_data") or [])
    elif ctype == "flow_chart":
        rows = [{"flow_step": s} for s in (result.get("flow_steps") or [])]
    elif ctype in ("fields", None):
        fv = result.get("field_values") or {}
        rows = [{k: v} for k, v in fv.items()] if isinstance(fv, dict) else []
    else:
        rows = result.get("filled_data") or []
    rows_total = len(rows)

    op_rows = 0
    insp_rows = 0
    non_empty_rows = 0
    empty_cells = 0
    content_lens = []
    content_empty_rows = 0

    META_ROW = {"step_no", "step_name", "workshop", "seq", "tool_seq", "gauge_seq"}
    for r in rows:
        sname = (r.get("step_name") or "").strip()
        if sname == "检验":
            insp_rows += 1
        else:
            op_rows += 1

        # non-empty structured value cells
        filled_val = 0
        for k in value_keys:
            if k in META_ROW:
                continue
            if str(r.get(k) or "").strip():
                filled_val += 1
        empty_cells += max(0, len(value_keys) - filled_val)
        if filled_val > 0:
            non_empty_rows += 1

        ctext = _row_content_text(r, value_keys)
        clen = len(ctext.strip())
        content_lens.append(clen)
        if clen == 0:
            content_empty_rows += 1

    denom = rows_total * max(expected_cols, 1)
    empty_rate = (empty_cells / denom) if denom else 1.0
    content_avg = (sum(content_lens) / len(content_lens)) if content_lens else 0

    # --- Verdict ---
    verdicts = []
    # row-count expectations by chapter type
    row_expect = {
        "G19a": 10, "G1a": 8,
        "G4a": 8, "G5a": 5, "G10a": 6, "G12a": 8, "G14a": 6, "B12a": 4,
        "G18a": 8, "G22a": 10, "G25a": 40,
    }.get(code, 1)
    if rows_total < max(1, row_expect // 2):
        verdicts.append(f"行数不足(预期≈{row_expect})")
    # empty_rate only meaningful for structured column chapters (not flow/fields)
    if ctype not in ("flow_chart", "fields", None) and rows_total > 0 and empty_rate > 0.5:
        verdicts.append("字段大面积空")
    if content_avg < 20 and rows_total > 0:
        verdicts.append("content过短")
    verdict = ";".join(verdicts) if verdicts else "健康"

    stats.append({
        "code": code, "title": title, "type": ctype,
        "rows_total": rows_total, "op_rows": op_rows, "insp_rows": insp_rows,
        "non_empty_rows": non_empty_rows, "empty_cells": empty_cells,
        "expected_cols": expected_cols, "empty_rate": empty_rate,
        "content_avg_chars": content_avg, "content_empty_rows": content_empty_rows,
        "verdict": verdict, "content_lens": content_lens,
    })
    print(
        f"  rows={rows_total} op={op_rows} insp={insp_rows} "
        f"empty_rate={empty_rate:.2f} content_avg={content_avg:.0f}字 -> {verdict}"
    )
    # show first 3 rows content preview for sanity
    for r in rows[:3]:
        cprev = _row_content_text(r, value_keys).strip().replace("\n", " ")[:60]
        print(f"    row{r.get('step_no','?')} {str(r.get('step_name',''))[:6]:6s} | {cprev!r}")


# --- Per-chapter statistics table ---
print("\n" + "=" * 78)
print("[3] 各章统计表")
print("=" * 78)
hdr = f"{'code':6s}{'type':18s}{'rows':>5s}{'op':>5s}{'insp':>5s}{'empty%':>8s}{'cnt_avg':>9s}  判定"
print(hdr)
print("-" * 78)
for s in stats:
    print(
        f"{s['code']:6s}{s['type']:18s}{s['rows_total']:>5d}{s['op_rows']:>5d}"
        f"{s['insp_rows']:>5d}{s['empty_rate']*100:>7.1f}%{s['content_avg_chars']:>8.0f}字  {s['verdict']}"
    )

# --- Thinnest 3 chapters ---
print("\n" + "=" * 78)
print("[4] 最单薄 3 章 (empty_rate desc, content_avg_chars asc)")
print("=" * 78)
# Thinness score: only structured-table chapters pay empty_rate; flow/fields
# rank purely on content length + row shortfall. This avoids ranking a healthy
# flow_chart (10 steps) as "thinnest" purely because it has no columns.
def _thin_score(s):
    ctype = s.get("type")
    is_table = ctype not in ("flow_chart", "fields", None)
    er = s.get("empty_rate", 1.0) if is_table else 0.0
    # row shortfall penalty (1.0 if totally empty)
    row_pen = 1.0 if s.get("rows_total", 0) == 0 else 0.0
    return (-er - row_pen, s.get("content_avg_chars", 0))

ranked = sorted(
    [s for s in stats if s.get("rows_total", 0) > 0 or s.get("verdict") == "生成异常"],
    key=_thin_score,
)
for i, s in enumerate(ranked[:3], 1):
    cause = []
    if s["rows_total"] < 3:
        cause.append("行数少")
    ctype = s.get("type")
    if ctype not in ("flow_chart", "fields", None) and s["empty_rate"] > 0.5:
        cause.append(f"字段空{int(s['empty_rate']*100)}%")
    if s["content_avg_chars"] < 20:
        cause.append(f"content短({s['content_avg_chars']:.0f}字)")
    if s.get("verdict") == "生成异常":
        cause.append(f"异常:{s.get('err','')[:40]}")
    print(
        f"  #{i} {s['code']} {s['title']}: rows={s['rows_total']} "
        f"empty_rate={s['empty_rate']:.2f} content_avg={s['content_avg_chars']:.0f}字 "
        f"| 成因: {', '.join(cause) if cause else s['verdict']}"
    )

# --- G25a baseline ---
print("\n" + "=" * 78)
print("[5] G25a baseline (检验行 vs 工序行)")
print("=" * 78)
g = next((s for s in stats if s["code"] == "G25a"), None)
if g:
    print(f"  inspection_rows(检验) = {g['insp_rows']}   (现状应 ≈30)")
    print(f"  op_rows(工序)         = {g['op_rows']}   (现状应 ≈10)")
    print(f"  rows_total            = {g['rows_total']}")
    print(f"  content_avg           = {g['content_avg_chars']:.0f}字")
    print(f"  empty_rate            = {g['empty_rate']:.2f}")
else:
    print("  G25a 未生成")

# --- Failures ---
if failures:
    print("\n" + "=" * 78)
    print("[6] 生成失败/异常章节")
    print("=" * 78)
    for code, err in failures:
        print(f"  {code}: {err}")
else:
    print("\n[6] 无生成失败章节 ✅")

print("\n[probe] DONE")
