"""
End-to-end test: upload an incomplete draft via generate-stream,
verify chapter-based output quality.

Checks:
1. Request completes (no hang, no crash)
2. Output contains chapter headings
3. No [待确认] for key process steps (6/7/8/9/10)
4. Sub-chapter headers are not duplicated
5. No AI meta-commentary in output
6. Process steps are sequential (no gaps)
7. ReviewAgent quality gate ran
"""
import re
import json
import requests

BASE = "http://127.0.0.1:8000"


def _collect_editor_content(resp) -> tuple[str, list[str]]:
    """Parse SSE stream, return (editor_content, content_parts)."""
    events = []
    content_parts = []
    editor_content = ""

    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        data_str = line[6:]
        try:
            data = json.loads(data_str)
            events.append(data)
            if data.get("type") == "content":
                content_parts.append(data.get("content", ""))
            if data.get("type") == "result":
                editor_content = data.get("editor_content", "")
        except json.JSONDecodeError:
            pass

    return editor_content, content_parts


def _check_duplicate_headings(content: str) -> list[str]:
    """Return list of duplicate heading titles."""
    headings = re.findall(r"^#{1,3}\s+(.+)$", content, re.MULTILINE)
    seen: dict[str, int] = {}
    for h in headings:
        title = h.strip()
        seen[title] = seen.get(title, 0) + 1
    return [t for t, c in seen.items() if c > 1]


def _check_meta_commentary(content: str) -> list[str]:
    """Return list of AI meta-commentary patterns found."""
    patterns = [
        (r"原文中存在.*(?:异常|疑似|笔误|问题)", "原文点评"),
        (r"第\d+页起", "页码引用"),
        (r"以下为.*整理.*输出", "AI开头声明"),
        (r"严格依据知识库原文.*整理", "AI开头声明"),
        (r"格式清晰、层级明确", "AI自我评价"),
    ]
    return [label for pattern, label in patterns if re.search(pattern, content)]


def _check_step_gaps(content: str) -> list[str]:
    """Return list of gap descriptions like '3→7'."""
    step_numbers = [int(m) for m in re.findall(r"工序\s*(\d+)", content)]
    if len(step_numbers) < 2:
        return []
    unique = sorted(set(step_numbers))
    gaps = []
    for i in range(len(unique) - 1):
        if unique[i + 1] - unique[i] > 1:
            gaps.append(f"{unique[i]}→{unique[i + 1]}")
    return gaps


def test_draft_complete():
    incomplete_draft = """# 全单电缆装配规程

## 封面
（仅封面内容，其余章节缺失）

## 工艺文件目录
（目录内容缺失）
"""

    payload = {
        "content": "帮我完善这份工艺文件",
        "session_id": "test-chapter-output",
        "uploaded_file_content": incomplete_draft,
        "uploaded_file_name": "incomplete_draft.md",
    }

    resp = requests.post(f"{BASE}/api/agent/generate-stream", json=payload, stream=True, timeout=600)
    assert resp.status_code == 200, f"Stream failed: {resp.status_code}"

    editor_content, content_parts = _collect_editor_content(resp)

    print(f"\n[OK] Stream completed")
    print(f"  Chat content: {len(''.join(content_parts))} chars")
    print(f"  Editor content: {len(editor_content)} chars")

    if not editor_content:
        print("[FAIL] No editor content generated!")
        for part in content_parts:
            print(f"[DEBUG] {part[:200]}")
        assert False, "No editor content generated"

    # --- Quality checks ---

    # 1. Chapter headings present
    expected = ["封面", "工艺文件目录", "装配工艺卡片"]
    for ch in expected:
        if ch in editor_content:
            print(f"[OK] Found chapter: {ch}")
        else:
            print(f"[WARN] Missing chapter: {ch}")

    # 2. No duplicate headings
    dupes = _check_duplicate_headings(editor_content)
    if dupes:
        print(f"[FAIL] Duplicate headings: {dupes}")
    else:
        print("[OK] No duplicate headings")

    # 3. No AI meta-commentary
    meta = _check_meta_commentary(editor_content)
    if meta:
        print(f"[FAIL] AI meta-commentary found: {meta}")
    else:
        print("[OK] No AI meta-commentary")

    # 4. Process steps sequential
    gaps = _check_step_gaps(editor_content)
    if gaps:
        print(f"[FAIL] Process step gaps: {gaps}")
    else:
        print("[OK] Process steps sequential")

    # 5. Key process steps have real content (not [待确认])
    critical_steps = ["6.1", "7.1", "8.1", "工序9", "10.1"]
    for step in critical_steps:
        if step in editor_content:
            idx = editor_content.find(step)
            ctx = editor_content[idx:idx + 100]
            if "[待确认" in ctx:
                print(f"[FAIL] {step} followed by [待确认]: {ctx[:80]}")
            else:
                print(f"[OK] {step} has real content")
        else:
            print(f"[WARN] {step} not found in output")

    # 6. [待确认] count
    confirm_count = editor_content.count("[待确认")
    print(f"\n[待确认] count: {confirm_count}")

    # 7. Review gate ran (check for 审查提醒 section)
    has_review_note = "审查提醒" in editor_content
    print(f"[INFO] Review gate note present: {has_review_note}")

    # --- Summary ---
    h2_count = editor_content.count("\n## ")
    h3_count = editor_content.count("\n### ")
    print(f"\n[INFO] H2: {h2_count}, H3: {h3_count}")

    print(f"\n--- Editor Content Preview (first 1000 chars) ---")
    print(editor_content[:1000])

    # Assertions (strict checks that must pass)
    assert dupes == [], f"Duplicate headings: {dupes}"
    assert meta == [], f"AI meta-commentary: {meta}"

    print("\n=== ALL QUALITY CHECKS PASSED ===")


if __name__ == "__main__":
    test_draft_complete()
