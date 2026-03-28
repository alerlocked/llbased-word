"""
生成 summary.json - 页级索引
"""
import json
from pathlib import Path
from datetime import datetime

def generate_summary():
    """为素材生成页级索引"""
    
    # 读取 manifest.json
    materials_dir = Path(__file__).parent.parent / "data" / "materials"
    material_dirs = [d for d in materials_dir.iterdir() if d.is_dir() and d.name != "index.json"]
    
    if not material_dirs:
        print("没有找到素材目录")
        return
    
    material_dir = material_dirs[0]  # 取第一个
    manifest_path = material_dir / "manifest.json"
    
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    
    page_count = manifest['page_count']
    material_id = manifest['id']
    
    # 生成 pages 数组
    pages = []
    keyword_index = {}
    
    for i in range(1, page_count + 1):
        page_info = {
            "page": i,
            "type": "text",
            "title": f"第{i}页",
            "summary": f"第{i}页内容",
            "keywords": [],
            "tables": [],
            "figures": [],
            "tokens_estimate": 100
        }
        pages.append(page_info)
    
    # 基础关键词（从文件名推断）
    base_keywords = ["电缆", "装配", "规程", "全单"]
    for keyword in base_keywords:
        keyword_index[keyword] = list(range(1, min(page_count + 1, 10)))  # 前10页
    
    # 生成 summary.json
    summary = {
        "version": "1.0",
        "total_pages": page_count,
        "total_tokens_estimate": page_count * 100,
        "generated_at": datetime.now().isoformat(),
        "toc": [
            {
                "title": "全文",
                "page_range": [1, page_count],
                "summary": manifest['name']
            }
        ],
        "pages": pages,
        "keyword_index": keyword_index
    }
    
    # 保存
    output_path = material_dir / "summary.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"[OK] 生成 summary.json: {output_path}")
    print(f"   总页数: {page_count}")
    print(f"   关键词数: {len(keyword_index)}")
    
    return summary

if __name__ == "__main__":
    generate_summary()
