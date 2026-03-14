# -*- coding: utf-8 -*-
"""通过API完成完整流程"""
import requests
import os

BASE_URL = "http://localhost:8000"
PDF_FILE = r"D:\ai_idea\localknowledgebase-word\data\process_docs\全单电缆装配规程.pdf"

# 1. 创建项目
print("Step 1: 创建项目...")
resp = requests.post(f"{BASE_URL}/api/creation/projects", json={"name": "电缆装配风险分析"})
print(f"  Response: {resp.status_code} - {resp.text}")
project = resp.json()
project_id = project.get("id")
print(f"  Project ID: {project_id}")

# 2. 上传PDF
print("\nStep 2: 上传PDF...")
if project_id and os.path.exists(PDF_FILE):
    with open(PDF_FILE, 'rb') as f:
        files = {'file': ('全单电缆装配规程.pdf', f, 'application/pdf')}
        resp = requests.post(f"{BASE_URL}/api/creation/projects/{project_id}/upload", files=files)
        print(f"  Response: {resp.status_code} - {resp.text[:500]}")
else:
    print("  Skip: No project or file not found")

# 3. 查询项目素材
print("\nStep 3: 查询项目素材...")
if project_id:
    resp = requests.get(f"{BASE_URL}/api/creation/projects/{project_id}/materials")
    print(f"  Response: {resp.status_code} - {resp.text[:500]}")

# 4. 调用Agent分析
print("\nStep 4: 调用Agent分析...")
task_prompt = """请分析《全单电缆装配规程》这份工艺文档，找出电缆装配过程中潜在的风险点。

要求：
1. 识别工艺流程中的风险点（至少5个）
2. 对每个风险点说明：
   - 风险描述
   - 可能导致的后果
   - 初步修改建议

请以结构化的方式输出结果。"""

if project_id:
    # 使用chat endpoint
    resp = requests.post(f"{BASE_URL}/api/agent/chat", json={
        "message": task_prompt,
        "project_id": project_id,
        "session_id": "test-session-001"
    }, stream=True)

    print(f"  Response status: {resp.status_code}")
    print("\n  AI Response:")
    print("-" * 60)

    full_response = ""
    for line in resp.iter_lines():
        if line:
            try:
                text = line.decode('utf-8')
                if text.startswith('data: '):
                    data = text[6:]
                    if data == '[DONE]':
                        break
                    import json
                    chunk = json.loads(data)
                    if 'content' in chunk:
                        content = chunk['content']
                        full_response += content
                        print(content, end='', flush=True)
            except:
                pass

    print("\n" + "-" * 60)

    # 保存结果
    if full_response:
        result_file = "D:/ai_idea/localknowledgebase-word/validation_results/ai_analysis.txt"
        with open(result_file, 'w', encoding='utf-8') as f:
            f.write("="*60 + "\n")
            f.write("电缆装配风险点分析结果\n")
            f.write("="*60 + "\n\n")
            f.write(full_response)
        print(f"\n结果已保存到: {result_file}")

print("\n完成!")
