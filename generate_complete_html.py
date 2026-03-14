# -*- coding: utf-8 -*-
"""
生成完整HTML报告 - 一个PDF对应一个HTML文件
包含所有表格和图片
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# 完整CSS样式
COMPLETE_HTML_CSS = """
* { box-sizing: border-box; }
body {
    font-family: "Microsoft YaHei", "SimSun", Arial, sans-serif;
    margin: 0;
    padding: 20px;
    background: #f5f5f5;
    line-height: 1.6;
}
.container {
    max-width: 1200px;
    margin: 0 auto;
    background: white;
    padding: 30px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}
h1 {
    color: #333;
    border-bottom: 3px solid #4CAF50;
    padding-bottom: 15px;
    margin-bottom: 10px;
}
.meta {
    color: #666;
    font-size: 14px;
    margin-bottom: 30px;
}
nav {
    background: #333;
    color: white;
    padding: 10px 15px;
    border-radius: 5px;
    margin-bottom: 20px;
    position: sticky;
    top: 0;
    z-index: 100;
}
nav span {
    font-weight: bold;
    margin-right: 10px;
}
nav a {
    color: #ddd;
    text-decoration: none;
    margin: 0 3px;
    padding: 3px 8px;
    border-radius: 3px;
    font-size: 12px;
}
nav a:hover { background: #555; color: white; }
.page-section {
    margin-bottom: 40px;
    padding-bottom: 30px;
    border-bottom: 2px dashed #e0e0e0;
}
.page-section:last-child { border-bottom: none; }
.page-header {
    background: linear-gradient(135deg, #4CAF50, #45a049);
    color: white;
    padding: 10px 20px;
    border-radius: 5px;
    margin-bottom: 15px;
}
.page-header h2 { margin: 0; font-size: 18px; }
.table-container {
    overflow-x: auto;
    margin: 15px 0;
    border: 1px solid #e0e0e0;
    border-radius: 5px;
}
table {
    border-collapse: collapse;
    width: 100%;
    background: white;
}
td, th {
    border: 1px solid #ddd;
    padding: 8px 12px;
    text-align: left;
    vertical-align: middle;
    font-size: 13px;
}
th { background-color: #f5f5f5; font-weight: bold; }
tr:nth-child(even) { background-color: #fafafa; }
tr:hover { background-color: #f0f7f0; }
.image-container {
    margin: 20px 0;
    padding: 15px;
    background: #f9f9f9;
    border-radius: 5px;
    border-left: 4px solid #4CAF50;
}
.image-container h4 {
    margin: 0 0 10px 0;
    color: #333;
}
.image-container img {
    max-width: 100%;
    border: 1px solid #ddd;
    border-radius: 3px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}
.footer {
    margin-top: 30px;
    padding-top: 20px;
    border-top: 1px solid #ddd;
    text-align: center;
    color: #999;
    font-size: 12px;
}
@media print {
    nav { display: none; }
    .page-section { page-break-after: always; }
    .page-section:last-child { page-break-after: auto; }
}
"""


def generate_complete_html(content_list_path: str,
                           output_path: str,
                           pdf_name: str = "全单电缆装配规程"):
    """
    生成完整的HTML报告

    Args:
        content_list_path: content_list.json路径
        output_path: 输出HTML路径
        pdf_name: PDF文件名（用于标题）
    """
    # 读取数据
    with open(content_list_path, 'r', encoding='utf-8') as f:
        content_list = json.load(f)

    # 建立页面索引
    tables_by_page = {}
    for item in content_list:
        if item.get('type') == 'table':
            page_idx = item.get('page_idx', -1)
            tables_by_page[page_idx] = item

    # 计算总页数
    total_pages = max(t.get('page_idx', 0) for t in content_list if t.get('type') == 'table') + 1

    # 生成HTML
    html_parts = [
        '<!DOCTYPE html>',
        '<html lang="zh-CN">',
        '<head>',
        '<meta charset="utf-8">',
        f'<title>{pdf_name} - 完整解析报告</title>',
        '<style>',
        COMPLETE_HTML_CSS,
        '</style>',
        '</head>',
        '<body>',
        '<div class="container">',
        f'<h1>{pdf_name}</h1>',
        f'<div class="meta">共 {total_pages} 页 | 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>',
        '',
        # 导航栏
        '<nav>',
        '<span>快速跳转:</span>',
    ]

    # 添加页面导航链接
    for p in range(1, total_pages + 1):
        html_parts.append(f'<a href="#page-{p}">{p}</a>')

    html_parts.extend([
        '</nav>',
        '',
    ])

    # 生成每页内容
    images_dir = f"{pdf_name}/vlm/images"

    for page_idx in range(total_pages):
        page_num = page_idx + 1

        # 获取表格数据
        table_data = tables_by_page.get(page_idx, {})

        html_parts.extend([
            f'<!-- 第{page_num}页 -->',
            f'<section id="page-{page_num}" class="page-section">',
            f'<div class="page-header">',
            f'<h2>第 {page_num} 页</h2>',
            f'</div>',
            '',
        ])

        # 添加表格HTML
        table_body = table_data.get('table_body', '')
        caption = table_data.get('table_caption', [])
        img_path = table_data.get('img_path', '')

        if caption:
            html_parts.append(f'<p class="caption">{" ".join(caption)}</p>')

        if table_body:
            html_parts.extend([
                '<div class="table-container">',
                f'<table>{table_body}</table>',
                '</div>',
                '',
            ])

        # 添加图片
        if img_path:
            html_parts.extend([
                '<div class="image-container">',
                '<h4>表格截图</h4>',
                f'<img src="{img_path}" alt="第{page_num}页表格截图">',
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
        f'<p>由 MinerU VLM 自动生成</p>',
        f'<p>项目: 智能工艺文件辅助编辑系统</p>',
        '</div>',
        '',
        '</div>',  # container
        '</body>',
        '</html>'
    ])

    # 保存HTML
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html_parts))

    print(f"HTML生成完成: {output_path}")
    print(f"  总页数: {total_pages}")
    print(f"  文件大小: {os.path.getsize(output_path) / 1024:.1f} KB")


def main():
    """主函数"""
    print("=" * 60)
    print("生成完整HTML报告")
    print("=" * 60)

    base_dir = Path("data/exports_vlm_full")
    pdf_name = "全单电缆装配规程"

    content_list_path = base_dir / pdf_name / "vlm" / f"{pdf_name}_content_list.json"
    output_path = base_dir / f"{pdf_name}_complete.html"

    generate_complete_html(
        str(content_list_path),
        str(output_path),
        pdf_name
    )

    print("\n用浏览器打开查看:")
    print(f"  {output_path}")


if __name__ == "__main__":
    main()
