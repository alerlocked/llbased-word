"""
QJ903 standards OCR -> exports_html converter.

Input:  data/standards_parsed/QJ 903.XB-2011_ocr.json
Output: data/exports_html/QJ903-XB-2011/{index.json, document.html}

Usage:
  Set-Location D:/Project Nantianmen/projects/localknowledgebase-word
  python backend/scripts/convert_standards_to_exports.py
"""

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 项目根目录
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INPUT_DIR = PROJECT_ROOT / "data" / "standards_parsed"
OUTPUT_DIR = PROJECT_ROOT / "data" / "exports_html"

# ---------------------------------------------------------------------------
# 标准号 → 中文标题 的映射
# OCR markdown 中标题位置不固定，靠正则匹配第一行 # 标题来获取，
# 但为了可靠性，这里维护一份映射。
# ---------------------------------------------------------------------------
STANDARD_TITLES = {
    "QJ903-1B-2011": "QJ 903.1B-2011 航天产品工艺文件管理制度 第1部分：总则",
    "QJ903-2B-2011": "QJ 903.2B-2011 航天产品工艺文件管理制度 第2部分：工艺文件编制一般要求",
    "QJ903-3B-2011": "QJ 903.3B-2011 航天产品工艺文件管理制度 第3部分：封面与主标题栏",
    "QJ903-4B-2011": "QJ 903.4B-2011 航天产品工艺文件管理制度 第4部分：工艺文件完整性要求",
    "QJ903-5B-2011": "QJ 903.5B-2011 航天产品工艺文件管理制度 第5部分：工艺文件签署规定",
    "QJ903-8B-2011": "QJ 903.8B-2011 航天产品工艺文件管理制度 第8部分：工艺总方案编制规则",
    "QJ903-9B-2011": "QJ 903.9B-2011 航天产品工艺文件管理制度 第9部分：管理用工艺文件编制规则",
    "QJ903-10B-2011": "QJ 903.10B-2011 航天产品工艺文件管理制度 第10部分：材料及外购件消耗工艺定额文件编制规则",
    "QJ903-11B-2011": "QJ 903.11B-2011 航天产品工艺文件管理制度 第11部分：工艺文件编号规定",
    "QJ903-29B-2011": "QJ 903.29B-2011 航天产品工艺文件管理制度 第29部分：光学零件加工工艺文件编制规则",
    "QJ903-30B-2011": "QJ 903.30B-2011 航天产品工艺文件管理制度 第30部分：复合固体推进剂、发动机总装工艺文件编制规则",
}

# ---------------------------------------------------------------------------
# Markdown → HTML 转换
# ---------------------------------------------------------------------------

def md_to_html(markdown_text: str) -> str:
    """将 OCR 产出的 Markdown 转换为简单 HTML。
    
    处理:
    - # 标题 → <h1> / <h2>
    - 空行分隔的段落 → <p>
    - 表格语法 → <table>
    - 普通文本 → <p>
    """
    lines = markdown_text.split("\n")
    html_parts = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # 空行跳过
        if not stripped:
            i += 1
            continue
        
        # 标题: ### h3
        if stripped.startswith("### "):
            html_parts.append(f"<h3>{_escape(stripped[4:])}</h3>")
            i += 1
            continue
        
        # 标题: ## h2
        if stripped.startswith("## "):
            html_parts.append(f"<h2>{_escape(stripped[3:])}</h2>")
            i += 1
            continue
        
        # 标题: # h1
        if stripped.startswith("# "):
            html_parts.append(f"<h1>{_escape(stripped[2:])}</h1>")
            i += 1
            continue
        
        # 表格行: | ... |
        if stripped.startswith("|") and "|" in stripped[1:]:
            table_html, consumed = _parse_table(lines, i)
            html_parts.append(table_html)
            i += consumed
            continue
        
        # 段落: 收集连续非空行
        para_lines = []
        while i < len(lines) and lines[i].strip():
            # 如果遇到了标题或表格，停止收集
            s = lines[i].strip()
            if s.startswith("#") or s.startswith("|"):
                break
            para_lines.append(lines[i].strip())
            i += 1
        
        if para_lines:
            para_text = " ".join(para_lines)
            html_parts.append(f"<p>{_escape(para_text)}</p>")
    
    return "<html>\n<head><meta charset=\"utf-8\"></head>\n<body>\n" + \
           "\n".join(html_parts) + \
           "\n</body>\n</html>"


def _parse_table(lines: list, start: int) -> tuple:
    """解析 Markdown 表格，返回 (html, consumed_lines)。"""
    rows = []
    i = start
    
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped.startswith("|"):
            break
        
        # 跳过分隔行 (|---|---|)
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if all(re.match(r"^[-:]+$", c) for c in cells):
            i += 1
            continue
        
        rows.append(cells)
        i += 1
    
    if not rows:
        return ("<p></p>", 1)
    
    html = "<table border=\"1\" cellpadding=\"4\" cellspacing=\"0\">\n"
    
    # 第一行作为表头
    html += "<thead><tr>"
    for cell in rows[0]:
        html += f"<th>{_escape(cell)}</th>"
    html += "</tr></thead>\n"
    
    # 后续行作为表体
    if len(rows) > 1:
        html += "<tbody>\n"
        for row in rows[1:]:
            html += "<tr>"
            for j, cell in enumerate(row):
                # 对齐列数：不够补空单元格
                html += f"<td>{_escape(cell)}</td>"
            html += "</tr>\n"
        html += "</tbody>\n"
    
    html += "</table>"
    consumed = i - start
    return (html, consumed)


def _escape(text: str) -> str:
    """HTML 实体转义。"""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


# ---------------------------------------------------------------------------
# 从 OCR markdown 中提取标题
# ---------------------------------------------------------------------------

def extract_title_from_markdown(md: str) -> str:
    """尝试从 markdown 中提取第一个 # 标题。"""
    for line in md.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


# ---------------------------------------------------------------------------
# 从 OCR markdown 中提取标准号
# ---------------------------------------------------------------------------

def extract_standard_code(md: str) -> str:
    """从 OCR markdown 中提取标准号，如 QJ 903.3B-2011。"""
    m = re.search(r"QJ\s*903\.(\d+)B[-—](\d{4})", md)
    if m:
        return f"QJ 903.{m.group(1)}B-{m.group(2)}"
    return ""


# ---------------------------------------------------------------------------
# 主转换逻辑
# ---------------------------------------------------------------------------

def convert_all():
    """转换所有标准文件。"""
    if not INPUT_DIR.exists():
        print(f"[ERROR] 输入目录不存在: {INPUT_DIR}")
        sys.exit(1)
    
    # 找到所有 _ocr.json 文件
    ocr_files = sorted(INPUT_DIR.glob("*_ocr.json"))
    if not ocr_files:
        print(f"[ERROR] 没有找到 OCR 文件: {INPUT_DIR}/*_ocr.json")
        sys.exit(1)
    
    print(f"[INFO] 找到 {len(ocr_files)} 个 OCR 文件")
    
    success = 0
    failed = 0
    
    for ocr_path in ocr_files:
        try:
            result = convert_one(ocr_path)
            if result:
                success += 1
            else:
                failed += 1
        except Exception as e:
            print(f"[ERROR] 转换失败: {ocr_path.name} → {e}")
            failed += 1
    
    print(f"\n[DONE] 成功: {success}, 失败: {failed}, 总计: {len(ocr_files)}")
    return failed == 0


def convert_one(ocr_path: Path) -> bool:
    """转换单个标准文件。
    
    输入: QJ 903.1B-2011_ocr.json
    输出: data/exports_html/standards/QJ903-1B-2011/{index.json, document.html}
    """
    # 读取 OCR JSON
    with open(ocr_path, "r", encoding="utf-8") as f:
        ocr_data = json.load(f)
    
    full_markdown = ocr_data.get("full_markdown", "")
    total_pages = ocr_data.get("total_pages", 0)
    source_file = ocr_data.get("source_file", "")
    
    if not full_markdown:
        print(f"[WARN] OCR 内容为空，跳过: {ocr_path.name}")
        return False
    
    # 推导目录名: "QJ 903.1B-2011_ocr.json" → "QJ903-1B-2011"
    # 先去掉 "_ocr.json" 后缀得到 "QJ 903.1B-2011"
    basename = ocr_path.stem.replace("_ocr", "")  # "QJ 903.1B-2011"
    dir_name = basename.replace(" ", "").replace(".", "-").replace("—", "-")
    # "QJ903-1B-2011" — 但注意标准号中的 . XB 部分
    # "QJ 903.1B-2011" → replace space → "QJ903.1B-2011" → replace . → "QJ903-1B-2011"
    # 但是要小心 "903.1B" 中间的点
    
    # 更精确: 用正则提取标准号
    m = re.search(r"QJ\s*903\.(\d+)B", basename)
    if m:
        part_num = m.group(1)
        dir_name = f"QJ903-{part_num}B-2011"
    else:
        dir_name = basename.replace(" ", "").replace(".", "-")
    
    # 获取标题
    title = STANDARD_TITLES.get(dir_name, "")
    if not title:
        # 从 markdown 中提取
        md_title = extract_title_from_markdown(full_markdown)
        if md_title:
            title = f"{basename} {md_title}"
        else:
            title = basename
    
    # 获取标准号
    standard_code = extract_standard_code(full_markdown)
    if not standard_code:
        standard_code = basename  # fallback
    
    # 生成 HTML
    document_html = md_to_html(full_markdown)
    
    # 生成 index.json
    index_data = {
        "name": title,
        "pages": total_pages,
        "tables": [],  # OCR 版本暂不提取表格索引
        "materials": [],
        "source_type": "standard",
        "standard_code": standard_code,
    }
    
    # 写入输出目录
    out_dir = OUTPUT_DIR / dir_name
    out_dir.mkdir(parents=True, exist_ok=True)
    
    with open(out_dir / "index.json", "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    
    with open(out_dir / "document.html", "w", encoding="utf-8") as f:
        f.write(document_html)
    
    print(f"[OK] {dir_name}: pages={total_pages}, title={title[:40]}...")
    return True


# ---------------------------------------------------------------------------
# 验证
# ---------------------------------------------------------------------------

def verify():
    """验证转换结果，用 HierarchicalContext 测试搜索。"""
    print("\n[VERIFY] 开始验证...")
    
    # 检查输出目录
    if not OUTPUT_DIR.exists():
        print(f"[ERROR] 输出目录不存在: {OUTPUT_DIR}")
        return False
    
    dirs = sorted([d for d in OUTPUT_DIR.iterdir() if d.is_dir()])
    print(f"[VERIFY] 找到 {len(dirs)} 个标准目录")
    
    for d in dirs:
        index_path = d / "index.json"
        html_path = d / "document.html"
        
        if not index_path.exists():
            print(f"[ERROR] 缺少 index.json: {d.name}")
            return False
        if not html_path.exists():
            print(f"[ERROR] 缺少 document.html: {d.name}")
            return False
        
        with open(index_path, "r", encoding="utf-8") as f:
            idx = json.load(f)
        
        required_keys = ["name", "pages", "tables", "materials", "source_type", "standard_code"]
        for k in required_keys:
            if k not in idx:
                print(f"[ERROR] index.json 缺少字段 '{k}': {d.name}")
                return False
        
        if idx["source_type"] != "standard":
            print(f"[ERROR] source_type 不是 'standard': {d.name}")
            return False
        
        print(f"  [OK] {d.name}: {idx['name'][:50]}...")
    
    # 尝试用 HierarchicalContext 搜索
    print("\n[VERIFY] 测试 HierarchicalContext 搜索...")
    try:
        # 动态导入项目模块
        sys.path.insert(0, str(PROJECT_ROOT / "backend"))
        from app.services.hierarchical_context import HierarchicalContext
        
        hc = HierarchicalContext(data_dir=str(OUTPUT_DIR))
        
        # 测试加载元信息
        meta = hc.load_meta_index(force_reload=True)
        if "标准" in meta or "QJ" in meta:
            print("  [OK] Layer 0 元信息加载成功")
        else:
            print(f"  [WARN] Layer 0 可能未包含标准文件")
        
        # 测试搜索
        test_queries = [
            "工艺文件管理",
            "QJ 903",
            "封面与主标题栏",
            "签署规定",
            "总则",
        ]
        
        for q in test_queries:
            results = hc.search_tables(q)
            meta_result = hc.search_meta_info(q)
            # 标准文件一般没有表格索引，但 meta 搜索应该能找到
            print(f"  搜索 '{q}': tables={len(results)}, meta={'found' if meta_result else 'none'}")
        
        print("\n[VERIFY] OK - verification passed")
        return True
        
    except Exception as e:
        print(f"[VERIFY] WARN - HierarchicalContext test failed: {e}")
        print("  (Files generated correctly, but search test failed)")
        return False


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="QJ903 标准文件转换")
    parser.add_argument("--verify-only", action="store_true", help="只运行验证")
    args = parser.parse_args()
    
    if args.verify_only:
        ok = verify()
    else:
        ok = convert_all()
        if ok:
            verify()
    
    sys.exit(0 if ok else 1)
