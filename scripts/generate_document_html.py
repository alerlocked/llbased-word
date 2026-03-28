# -*- coding: utf-8 -*-
"""
文档级 HTML 生成 + 语义索引
一个 PDF → 一个 HTML + index.json
"""
import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# 蓝白灰主题 CSS
BLUE_WHITE_GRAY_THEME = """
:root {
    --primary: #2563eb;
    --primary-dark: #1d4ed8;
    --bg-light: #f8fafc;
    --bg-white: #ffffff;
    --text-dark: #1e293b;
    --text-gray: #64748b;
    --border: #e2e8f0;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: "Microsoft YaHei", "SimSun", Arial, sans-serif;
    background: var(--bg-light);
    color: var(--text-dark);
    line-height: 1.6;
    padding: 20px;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    background: var(--bg-white);
    padding: 30px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    border-radius: 8px;
}

h1 {
    color: var(--primary);
    border-bottom: 3px solid var(--primary);
    padding-bottom: 15px;
    margin-bottom: 10px;
    font-size: 28px;
}

.meta {
    color: var(--text-gray);
    font-size: 14px;
    margin-bottom: 30px;
    padding: 10px;
    background: var(--bg-light);
    border-radius: 5px;
}

nav {
    background: var(--primary);
    color: white;
    padding: 15px 20px;
    border-radius: 5px;
    margin-bottom: 30px;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3);
}

nav .nav-title {
    font-weight: bold;
    font-size: 16px;
    margin-bottom: 10px;
}

nav .nav-links {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
}

nav a {
    color: white;
    text-decoration: none;
    padding: 5px 12px;
    border-radius: 4px;
    font-size: 13px;
    background: rgba(255,255,255,0.1);
    transition: background 0.2s;
}

nav a:hover { 
    background: rgba(255,255,255,0.2); 
}

.page-section {
    margin-bottom: 50px;
    padding-bottom: 30px;
    border-bottom: 2px solid var(--border);
}

.page-section:last-child { 
    border-bottom: none; 
}

.page-header {
    background: linear-gradient(135deg, var(--primary), var(--primary-dark));
    color: white;
    padding: 12px 20px;
    border-radius: 5px;
    margin-bottom: 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.page-header h2 { 
    margin: 0; 
    font-size: 18px;
}

.page-header .page-num {
    background: rgba(255,255,255,0.2);
    padding: 5px 15px;
    border-radius: 20px;
    font-size: 14px;
}

.table-anchor {
    margin-bottom: 20px;
    padding: 15px;
    background: var(--bg-light);
    border-radius: 5px;
    border-left: 4px solid var(--primary);
}

.table-anchor .table-id {
    font-weight: bold;
    color: var(--primary);
    font-size: 16px;
    margin-bottom: 5px;
}

.table-anchor .table-type {
    color: var(--text-gray);
    font-size: 13px;
}

.table-container {
    overflow-x: auto;
    margin: 15px 0;
    border: 1px solid var(--border);
    border-radius: 5px;
    background: var(--bg-white);
}

table {
    border-collapse: collapse;
    width: 100%;
    font-size: 13px;
}

td, th {
    border: 1px solid var(--border);
    padding: 8px 12px;
    text-align: left;
    vertical-align: middle;
}

th { 
    background-color: var(--bg-light); 
    font-weight: bold;
}

tr:nth-child(even) { 
    background-color: #fafafa; 
}

tr:hover { 
    background-color: #f1f5f9; 
}

.image-container {
    margin: 20px 0;
    padding: 15px;
    background: var(--bg-light);
    border-radius: 5px;
    border: 1px solid var(--border);
}

.image-container h4 {
    margin: 0 0 10px 0;
    color: var(--text-dark);
    font-size: 14px;
}

.image-container img {
    max-width: 100%;
    border: 1px solid var(--border);
    border-radius: 3px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.05);
}

.footer {
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px solid var(--border);
    text-align: center;
    color: var(--text-gray);
    font-size: 12px;
}

@media print {
    nav { display: none; }
    .page-section { page-break-after: always; }
    .page-section:last-child { page-break-after: auto; }
}
"""


def extract_table_id(table_caption: List[Dict]) -> Optional[str]:
    """从 table_caption 提取表格 ID"""
    if not table_caption:
        return None
    
    for item in table_caption:
        if item.get('type') == 'text':
            content = item.get('content', '').strip()
            # 匹配类似 G1a, G4a, G18b 等格式
            match = re.match(r'^([A-Z]\d+[a-z]?)', content)
            if match:
                return match.group(1)
    
    return None


def infer_table_type(table_id: str, html_content: str) -> str:
    """推断表格类型"""
    if not table_id:
        return "未分类"
    
    html_lower = html_content.lower()
    
    # 基于 ID 前缀判断
    if table_id.startswith('G1'):
        return "封面"
    elif table_id.startswith('G4'):
        if "目录" in html_content:
            return "工艺文件目录"
        return "配套表"
    elif table_id.startswith('G5'):
        return "设计文件目录"
    elif table_id.startswith('G18'):
        return "配套明细表"
    elif table_id.startswith('G21'):
        return "工序卡片"
    elif table_id.startswith('G22'):
        return "检验卡片"
    elif table_id.startswith('G31'):
        return "工艺简图"
    
    # 基于内容判断
    if "目录" in html_content:
        return "目录表"
    elif "配套" in html_content:
        return "配套表"
    elif "明细" in html_content:
        return "明细表"
    elif "工序" in html_content:
        return "工序卡片"
    elif "检验" in html_content:
        return "检验卡片"
    
    return "工艺表格"


def infer_table_summary(table_id: str, html_content: str) -> str:
    """生成表格摘要"""
    table_type = infer_table_type(table_id, html_content)
    
    if table_type == "封面":
        return "工艺文件封面"
    elif table_type == "工艺文件目录":
        return "工艺文件目录、产品工号信息"
    elif table_type == "配套表":
        return "工艺装备、零部件配套信息"
    elif table_type == "配套明细表":
        return "装配件配套明细"
    elif table_type == "工序卡片":
        # 尝试提取工序名称
        if "装前准备" in html_content:
            return "装前准备工序"
        elif "对接" in html_content:
            return "舱段对接工序"
        elif "安装" in html_content:
            return "安装工序"
        return "工艺工序卡片"
    
    return f"{table_id} 工艺表格"


def extract_processes_and_materials(pages_data: List[List[Dict]]) -> tuple:
    """提取工序和材料信息"""
    processes = set()
    materials = set()
    
    # 常见材料列表
    material_keywords = ['无水乙醇', '乐泰', 'GD414', '密封胶', '润滑脂', '清洗剂', '胶粘剂']
    
    for page in pages_data:
        for item in page:
            if item.get('type') == 'table':
                html = item.get('content', {}).get('html', '')
                
                # 提取工序
                if '工序' in html or '步骤' in html:
                    # 简单提取（可优化）
                    matches = re.findall(r'工序[名称：]*([^\s<>{]+)/', html)
                    processes.update(matches)
                
                # 提取材料
                for material in material_keywords:
                    if material in html:
                        materials.add(material)
    
    return list(processes), list(materials)


def generate_document_html(
    doc_name: str,
    pages_data: List[List[Dict]],
    images_base_path: str
) -> str:
    """生成文档级 HTML"""
    
    total_pages = len(pages_data)
    
    html_parts = [
        '<!DOCTYPE html>',
        '<html lang="zh-CN">',
        '<head>',
        '<meta charset="utf-8">',
        f'<title>{doc_name} - 完整解析报告</title>',
        '<style>',
        BLUE_WHITE_GRAY_THEME,
        '</style>',
        '</head>',
        '<body>',
        '<div class="container">',
        f'<h1>{doc_name}</h1>',
        f'<div class="meta">共 {total_pages} 页 | 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>',
        '',
        # 导航栏
        '<nav>',
        '<div class="nav-title">快速导航</div>',
        '<div class="nav-links">',
    ]
    
    # 添加表格导航链接
    table_count = 0
    for page_idx, page in enumerate(pages_data):
        for item in page:
            if item.get('type') == 'table':
                caption = item.get('content', {}).get('table_caption', [])
                table_id = extract_table_id(caption)
                if table_id:
                    table_count += 1
                    html_parts.append(
                        f'<a href="#table-{table_id}">{table_id}</a>'
                    )
    
    html_parts.extend([
        '</div>',
        '</nav>',
        '',
    ])
    
    # 生成每页内容
    for page_idx, page in enumerate(pages_data):
        page_num = page_idx + 1
        
        html_parts.extend([
            f'<!-- 第 {page_num} 页 -->',
            f'<section id="page-{page_num}" class="page-section">',
            f'<div class="page-header">',
            f'<h2>第 {page_num} 页</h2>',
            f'<span class="page-num">Page {page_num}/{total_pages}</span>',
            f'</div>',
            '',
        ])
        
        # 添加该页的表格
        for item in page:
            if item.get('type') == 'table':
                content = item.get('content', {})
                caption = content.get('table_caption', [])
                table_html = content.get('html', '')
                img_path = content.get('image_source', {}).get('path', '')
                
                table_id = extract_table_id(caption)
                table_type = infer_table_type(table_id, table_html)
                
                # 添加表格锚点
                if table_id:
                    html_parts.extend([
                        f'<div id="table-{table_id}" class="table-anchor">',
                        f'<div class="table-id">{table_id}</div>',
                        f'<div class="table-type">类型: {table_type}</div>',
                        f'</div>',
                        '',
                    ])
                
                # 添加表格
                if table_html:
                    html_parts.extend([
                        '<div class="table-container">',
                        table_html,
                        '</div>',
                        '',
                    ])
                
                # 添加图片
                if img_path:
                    # img_path 已经包含 images/ 前缀，直接使用
                    html_parts.extend([
                        '<div class="image-container">',
                        '<h4>📋 表格原图</h4>',
                        f'<img src="{img_path}" alt="第 {page_num} 页表格截图">',
                        '</div>',
                        '',
                    ])
        
        html_parts.extend([
            '</section>',
            '',
        ])
    
    # 添加页脚
    html_parts.extend([
        '<div class="footer">',
        f'<p>📄 文档: {doc_name}</p>',
        f'<p>🤖 由智能工艺文件系统生成 | {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>',
        '</div>',
        '',
        '</div>',  # container
        '</body>',
        '</html>'
    ])
    
    return '\n'.join(html_parts)


def generate_index_json(
    doc_name: str,
    file_name: str,
    pages_data: List[List[Dict]]
) -> Dict[str, Any]:
    """生成语义索引 JSON"""
    
    tables = []
    all_processes = set()
    all_materials = set()
    
    for page_idx, page in enumerate(pages_data):
        for item in page:
            if item.get('type') == 'table':
                content = item.get('content', {})
                caption = content.get('table_caption', [])
                html = content.get('html', '')
                
                table_id = extract_table_id(caption)
                if table_id:
                    table_type = infer_table_type(table_id, html)
                    summary = infer_table_summary(table_id, html)
                    
                    tables.append({
                        "id": table_id,
                        "type": table_type,
                        "page": page_idx + 1,
                        "summary": summary
                    })
    
    # 提取工序和材料
    processes, materials = extract_processes_and_materials(pages_data)
    
    index = {
        "name": doc_name,
        "file_name": file_name,
        "pages": len(pages_data),
        "tables": tables,
        "processes": processes,
        "materials": materials,
        "generated_at": datetime.now().isoformat(),
        "html_file": "document.html"
    }
    
    return index


def process_document(doc_dir: Path, output_dir: Path) -> bool:
    """处理单个文档"""
    
    # 查找 content_list_v2.json
    vlm_dir = doc_dir / "vlm"
    content_list_path = vlm_dir / f"{doc_dir.name}_content_list_v2.json"
    
    if not content_list_path.exists():
        print(f"  ⚠️  未找到 content_list_v2.json: {content_list_path}")
        return False
    
    print(f"  📖 读取: {content_list_path.name}")
    
    # 读取数据
    with open(content_list_path, 'r', encoding='utf-8') as f:
        pages_data = json.load(f)
    
    # 准备输出目录
    doc_output_dir = output_dir / doc_dir.name
    doc_output_dir.mkdir(parents=True, exist_ok=True)
    
    # 复制图片目录
    src_images = vlm_dir / "images"
    dst_images = doc_output_dir / "images"
    if src_images.exists() and not dst_images.exists():
        import shutil
        shutil.copytree(src_images, dst_images)
        print(f"  📁 复制图片: {len(list(dst_images.glob("*")))} 个文件")
    
    # 生成 HTML
    images_base_path = "images"
    html_content = generate_document_html(
        doc_name=doc_dir.name,
        pages_data=pages_data,
        images_base_path=images_base_path
    )
    
    html_path = doc_output_dir / "document.html"
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"  ✅ 生成 HTML: {html_path.name} ({html_path.stat().st_size / 1024:.1f} KB)")
    
    # 生成索引
    index_data = generate_index_json(
        doc_name=doc_dir.name,
        file_name=f"{doc_dir.name}.pdf",
        pages_data=pages_data
    )
    
    index_path = doc_output_dir / "index.json"
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    
    print(f"  ✅ 生成索引: {index_path.name}")
    print(f"     - 表格数: {len(index_data['tables'])}")
    print(f"     - 工序数: {len(index_data['processes'])}")
    print(f"     - 材料数: {len(index_data['materials'])}")
    
    return True


def main():
    """主函数"""
    print("=" * 60)
    print("文档级 HTML 生成 + 语义索引")
    print("=" * 60)
    print()
    
    base_dir = Path("data/exports_vlm_full")
    output_dir = Path("data/exports_html")
    
    if not base_dir.exists():
        print(f"❌ 输入目录不存在: {base_dir}")
        return
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 查找所有文档目录
    doc_dirs = [d for d in base_dir.iterdir() if d.is_dir() and (d / "vlm").exists()]
    
    if not doc_dirs:
        print(f"❌ 未找到有效的文档目录")
        return
    
    print(f"📂 找到 {len(doc_dirs)} 个文档")
    print()
    
    success_count = 0
    for doc_dir in doc_dirs:
        print(f"📄 处理: {doc_dir.name}")
        if process_document(doc_dir, output_dir):
            success_count += 1
        print()
    
    print("=" * 60)
    print(f"✅ 完成! 成功处理 {success_count}/{len(doc_dirs)} 个文档")
    print(f"📂 输出目录: {output_dir.absolute()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
