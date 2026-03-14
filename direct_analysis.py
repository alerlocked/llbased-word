# -*- coding: utf-8 -*-
"""直接分析PDF文档，找出电缆装配风险点"""
import sys
import os
import asyncio
import io

# 设置UTF-8编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, r"D:\ai_idea\localknowledgebase-word\backend")

PDF_FILE = r"D:\ai_idea\localknowledgebase-word\data\process_docs\全单电缆装配规程.pdf"
RESULT_FILE = r"D:\ai_idea\localknowledgebase-word\validation_results\risk_analysis.txt"

async def main():
    from app.tools.pdf_parser import PDFParser
    from app.services.llm_service import get_llm

    print("=" * 60)
    print("电缆装配风险点分析")
    print("=" * 60)

    # 1. 解析PDF
    print("\n[Step 1] 解析PDF文档...")
    parser = PDFParser({
        "extract_tables": True,
        "extract_text": True,
        "preferred_parser": "auto"
    })

    result = await parser.parse(PDF_FILE, extract_tables=True, extract_text=True)

    # 提取文本内容
    text_content = ""
    tables_content = ""

    if isinstance(result, dict):
        text_content = result.get('text', '')
        tables = result.get('tables', [])
        for i, table in enumerate(tables):
            tables_content += f"\n表格 {i+1}:\n"
            if isinstance(table, dict) and 'data' in table:
                for row in table['data']:
                    tables_content += " | ".join(str(cell) if cell else "" for cell in row) + "\n"

    full_content = f"{text_content}\n\n{tables_content}"
    print(f"  文档内容长度: {len(full_content)} 字符")

    # 2. 调用LLM分析风险点
    print("\n[Step 2] 调用LLM分析风险点...")

    prompt = f"""你是一个专业的工艺文件审核专家。请分析以下电缆装配工艺文档，找出其中潜在的风险点。

文档内容:
{full_content[:6000]}

请识别至少5个潜在风险点，对每个风险点提供：
1. 风险描述
2. 可能导致的后果
3. 初步修改建议

请以清晰的格式输出结果。
"""

    try:
        # 获取LLM实例
        llm = get_llm()

        # 调用LLM
        response = await llm.ainvoke(prompt)
        analysis_result = response.content if hasattr(response, 'content') else str(response)

        print("\n[Step 3] 分析结果:")
        print("-" * 60)
        print(analysis_result)
        print("-" * 60)

        # 保存结果
        os.makedirs(os.path.dirname(RESULT_FILE), exist_ok=True)
        with open(RESULT_FILE, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("电缆装配风险点分析结果\n")
            f.write("=" * 60 + "\n\n")
            f.write(analysis_result)
        print(f"\n结果已保存到: {RESULT_FILE}")

    except Exception as e:
        print(f"\n[ERROR] LLM调用失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n完成!")

if __name__ == "__main__":
    asyncio.run(main())
