# -*- coding: utf-8 -*-
"""测试PDF解析功能"""
import asyncio
import sys
import io

# 设置UTF-8编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, 'backend')

from app.tools.pdf_parser import PDFParser

async def test():
    parser = PDFParser({
        'extract_tables': True,
        'extract_text': True,
        'preferred_parser': 'auto'
    })

    pdf_path = r'D:\ai_idea\localknowledgebase-word\data\process_docs\全单电缆装配规程.pdf'

    print("="*50)
    print("开始解析PDF...")
    print("="*50)

    result = await parser.parse(pdf_path, extract_tables=True, extract_text=True)

    pages = result.get('pages', [])
    tables = result.get('tables', [])

    print(f"\n解析结果:")
    print(f"  总页数: {len(pages)}")
    print(f"  表格数: {len(tables)}")

    # 检查第一页的文本
    if pages:
        first_page_text = pages[0].get('full_text', '')[:300]
        print(f"\n第一页文本预览:\n{first_page_text}...")

    # 检查表格
    if tables:
        print(f"\n第一个表格信息:")
        first_table = tables[0]
        print(f"  ID: {first_table.get('table_id', 'N/A')}")
        print(f"  页码: {first_table.get('page_number', 'N/A')}")
        print(f"  行数: {first_table.get('rows', 0)}")
        print(f"  列数: {first_table.get('columns', 0)}")

    print("\n"+"="*50)
    print("测试完成!")
    print("="*50)

    return result

if __name__ == "__main__":
    asyncio.run(test())
