# -*- coding: utf-8 -*-
"""
批量生成文档级 HTML + 语义索引
"""
import sys
from pathlib import Path

# 导入单文档处理脚本
sys.path.insert(0, str(Path(__file__).parent))
from generate_document_html import process_document

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


def main():
    """批量处理所有文档"""
    print("=" * 60)
    print("批量生成文档级 HTML + 语义索引")
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
    for idx, doc_dir in enumerate(doc_dirs, 1):
        print(f"[{idx}/{len(doc_dirs)}] 📄 处理: {doc_dir.name}")
        if process_document(doc_dir, output_dir):
            success_count += 1
        print()
    
    print("=" * 60)
    print(f"✅ 完成! 成功处理 {success_count}/{len(doc_dirs)} 个文档")
    print(f"📂 输出目录: {output_dir.absolute()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
