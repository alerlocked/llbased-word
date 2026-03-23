# -*- coding: utf-8 -*-
"""
Markdown 工具函数
用于从 Markdown 中提取表格并转换为 HTML
"""
import re
from typing import List, Dict, Any, Optional


def markdown_table_to_html(table_lines: List[str]) -> str:
    """
    将 Markdown 表格行转换为 HTML 表格
    
    Args:
        table_lines: Markdown 表格行列表
        
    Returns:
        HTML 表格字符串
    """
    if not table_lines:
        return ""
    
    # 解析表头
    header_line = table_lines[0]
    headers = [cell.strip() for cell in header_line.split('|') if cell.strip()]
    
    # 跳过分隔行（如果有）
    start_idx = 1
    if start_idx < len(table_lines) and re.match(r'^[\|\-\s:]+$', table_lines[start_idx]):
        start_idx += 1
    
    # 解析数据行
    rows = []
    for i in range(start_idx, len(table_lines)):
        line = table_lines[i]
        if '|' in line:
            cells = [cell.strip() for cell in line.split('|') if cell.strip()]
            if cells:
                rows.append(cells)
    
    # 构建 HTML
    html_parts = ['<table>', '<thead><tr>']
    
    # 添加表头
    for header in headers:
        html_parts.append(f'<th>{header}</th>')
    
    html_parts.append('</tr></thead>')
    
    # 添加数据行
    if rows:
        html_parts.append('<tbody>')
        for row in rows:
            html_parts.append('<tr>')
            for cell in row:
                html_parts.append(f'<td>{cell}</td>')
            html_parts.append('</tr>')
        html_parts.append('</tbody>')
    
    html_parts.append('</table>')
    
    return '\n'.join(html_parts)


def extract_tables_from_markdown(markdown_text: str) -> List[str]:
    """
    从 Markdown 文本中提取所有表格并转换为 HTML
    
    Args:
        markdown_text: Markdown 文本
        
    Returns:
        HTML 表格列表
    """
    tables = []
    lines = markdown_text.split('\n')
    current_table = []
    in_table = False
    
    for line in lines:
        # 检测表格开始
        if '|' in line and not in_table:
            in_table = True
            current_table = [line]
        # 继续表格
        elif '|' in line and in_table:
            current_table.append(line)
        # 表格结束
        elif in_table:
            if current_table:
                html = markdown_table_to_html(current_table)
                if html:
                    tables.append(html)
            in_table = False
            current_table = []
    
    # 处理最后一个表格
    if current_table:
        html = markdown_table_to_html(current_table)
        if html:
            tables.append(html)
    
    return tables


def convert_vl_output_to_content_list(
    pages_data: Dict[int, Dict[str, Any]]
) -> List[List[Dict[str, Any]]]:
    """
    将 VL Service 的输出转换为 content_list_v2.json 格式
    
    Args:
        pages_data: 页面数据字典
            {
                1: {
                    "markdown": "...",
                    "figures": [{"type": "chart", "caption": "..."}],
                    "image_path": "pages/material_123_page_1.png"
                },
                ...
            }
            
    Returns:
        content_list_v2.json 格式的数据
        [
            [  # 第一页
                {
                    "type": "table",
                    "content": {
                        "image_source": {"path": "images/material_123_page_1.png"},
                        "table_caption": [{"type": "text", "content": "表格1"}],
                        "html": "<table>...</table>",
                        "table_type": "standard_table",
                        "table_nest_level": 0
                    },
                    "bbox": [0, 0, 0, 0]
                }
            ],
            ...
        ]
    """
    content_list = []
    
    # 按页码排序
    sorted_pages = sorted(pages_data.items(), key=lambda x: x[0])
    
    for page_num, page_data in sorted_pages:
        markdown = page_data.get("markdown", "")
        figures = page_data.get("figures", [])
        image_path = page_data.get("image_path", "")
        
        page_items = []
        
        # 提取表格
        tables_html = extract_tables_from_markdown(markdown)
        
        # 如果有表格，转换为 content_list_v2 格式
        for idx, table_html in enumerate(tables_html):
            # 尝试从 figures 中获取对应的 caption
            caption_text = ""
            if idx < len(figures):
                fig = figures[idx]
                caption_text = fig.get("caption", f"表格{idx + 1}")
            else:
                caption_text = f"表格{idx + 1}"
            
            # 构建图片路径（将 pages/ 转换为 images/）
            img_path = image_path.replace("pages/", "images/") if image_path else ""
            
            item = {
                "type": "table",
                "content": {
                    "image_source": {"path": img_path},
                    "table_caption": [{"type": "text", "content": caption_text}],
                    "html": table_html,
                    "table_type": "standard_table",
                    "table_nest_level": 0
                },
                "bbox": [0, 0, 0, 0]  # 简化处理，VL Service 不提供精确 bbox
            }
            page_items.append(item)
        
        content_list.append(page_items)
    
    return content_list


def estimate_table_id(markdown: str, table_idx: int) -> Optional[str]:
    """
    尝试从 Markdown 中提取表格 ID
    
    Args:
        markdown: Markdown 文本
        table_idx: 表格索引
        
    Returns:
        表格 ID（如 G4a）或 None
    """
    # 查找可能的表格标题模式
    patterns = [
        r'([A-Z]\d+[a-z]?)\s*[\：:\-]',  # G4a：
        r'表\s*([A-Z]\d+[a-z]?)',         # 表 G4a
        r'Table\s*([A-Z]\d+[a-z]?)',      # Table G4a
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, markdown)
        if matches and table_idx < len(matches):
            return matches[table_idx]
    
    return None
