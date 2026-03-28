# -*- coding: utf-8 -*-
"""
验证文档级 HTML 输出
"""
import sys
import json
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def validate_output():
    """验证输出目录中的文件"""
    output_dir = Path("data/exports_html")

    print("=" * 60)
    print("验证文档级 HTML 输出")
    print("=" * 60)
    print()

    errors = []
    warnings = []

    # 检查输出目录
    if not output_dir.exists():
        errors.append("❌ 输出目录不存在")
        print("\n".join(errors))
        return False

    # 查找所有文档目录
    doc_dirs = [d for d in output_dir.iterdir() if d.is_dir()]

    if not doc_dirs:
        errors.append("❌ 没有找到文档目录")
        print("\n".join(errors))
        return False

    print(f"📂 找到 {len(doc_dirs)} 个文档目录\n")

    for doc_dir in doc_dirs:
        print(f"📄 验证: {doc_dir.name}")

        # 检查 document.html
        html_file = doc_dir / "document.html"
        if not html_file.exists():
            errors.append(f"  ❌ 缺少 document.html")
        else:
            size_kb = html_file.stat().st_size / 1024
            print(f"  ✅ document.html ({size_kb:.1f} KB)")

            # 检查蓝白灰主题
            content = html_file.read_text(encoding='utf-8')
            if '--primary: #2563eb' in content:
                print(f"  ✅ 蓝白灰主题正确")
            else:
                warnings.append(f"  ⚠️ 蓝白灰主题可能不正确")

            # 检查表格锚点
            anchor_count = content.count('id="table-')
            print(f"  ✅ 表格锚点数: {anchor_count}")

            # 检查图片路径
            bad_paths = content.count('images/images/')
            if bad_paths > 0:
                errors.append(f"  ❌ 发现重复图片路径: {bad_paths} 处")
            else:
                print(f"  ✅ 图片路径正确")

        # 检查 index.json
        index_file = doc_dir / "index.json"
        if not index_file.exists():
            errors.append(f"  ❌ 缺少 index.json")
        else:
            with open(index_file, 'r', encoding='utf-8') as f:
                index_data = json.load(f)

            print(f"  ✅ index.json")
            print(f"     - 文档名: {index_data.get('name')}")
            print(f"     - 页数: {index_data.get('pages')}")
            print(f"     - 表格数: {len(index_data.get('tables', []))}")
            print(f"     - 工序数: {len(index_data.get('processes', []))}")
            print(f"     - 材料数: {len(index_data.get('materials', []))}")

            # 验证表格结构
            for table in index_data.get('tables', []):
                required_fields = ['id', 'type', 'page', 'summary']
                for field in required_fields:
                    if field not in table:
                        errors.append(f"  ❌ 表格缺少字段: {field}")

        # 检查 images 目录
        images_dir = doc_dir / "images"
        if not images_dir.exists():
            warnings.append(f"  ⚠️ 缺少 images 目录")
        else:
            image_count = len(list(images_dir.glob("*.jpg")))
            print(f"  ✅ images 目录 ({image_count} 张图片)")

        print()

    # 总结
    print("=" * 60)
    if errors:
        print("❌ 发现错误:")
        for e in errors:
            print(f"   {e}")

    if warnings:
        print("⚠️ 警告:")
        for w in warnings:
            print(f"   {w}")

    if not errors and not warnings:
        print("✅ 所有验证通过!")
        return True
    elif not errors:
        print("✅ 验证完成（有警告）")
        return True
    else:
        print("❌ 验证失败")
        return False

    print("=" * 60)


if __name__ == "__main__":
    import sys
    success = validate_output()
    sys.exit(0 if success else 1)
