# -*- coding: utf-8 -*-
"""
表格截图元数据提取脚本
从MinerU输出的content_list.json提取表格截图信息
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


def extract_table_image_metadata(content_list_path: str) -> dict:
    """
    从content_list.json提取表格截图元数据

    Args:
        content_list_path: content_list.json文件路径

    Returns:
        包含所有表格截图信息的字典
    """
    with open(content_list_path, 'r', encoding='utf-8') as f:
        content_list = json.load(f)

    # 统计元素类型
    type_count = {}
    for item in content_list:
        t = item.get('type', 'unknown')
        type_count[t] = type_count.get(t, 0) + 1

    print("content_list.json元素类型统计:")
    for t, c in type_count.items():
        print(f"  {t}: {c}")

    # 提取表格及其截图
    tables = []
    for idx, item in enumerate(content_list):
        if item.get('type') == 'table':
            page_idx = item.get('page_idx', -1)
            img_path = item.get('img_path', '')

            table_info = {
                "index": idx,
                "page": page_idx + 1,  # 转换为1-based页码
                "type": "table",
                "table_caption": item.get('table_caption', []),
                "table_img_path": img_path,
                "table_img_filename": Path(img_path).name if img_path else "",
                "bbox": item.get('bbox', []),
                "rows": item.get('table_body', '').count('<tr>'),
                "has_html": bool(item.get('table_body', '')),
                # 待后续VLM分析填充
                "content_type": "unknown",  # pure_table, flowchart, diagram, mixed
                "has_inner_image": False,
                "inner_image_type": None,
                "description": ""
            }
            tables.append(table_info)

    return {
        "total_tables": len(tables),
        "extracted_at": datetime.now().isoformat(),
        "source_file": str(content_list_path),
        "type_statistics": type_count,
        "tables": tables
    }


def main():
    """主函数"""
    print("=" * 60)
    print("表格截图元数据提取")
    print("=" * 60)

    # 输入输出路径
    content_list_path = Path("data/exports_vlm_full/全单电缆装配规程/vlm/全单电缆装配规程_content_list.json")
    output_path = Path("data/exports_vlm_full/table_images_info.json")

    if not content_list_path.exists():
        print(f"[错误] 文件不存在: {content_list_path}")
        return

    # 提取元数据
    print(f"\n输入: {content_list_path}")
    result = extract_table_image_metadata(str(content_list_path))

    # 保存结果
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n输出: {output_path}")
    print(f"  表格数量: {result['total_tables']}")

    # 显示部分表格信息
    print("\n前5个表格:")
    for t in result['tables'][:5]:
        print(f"  页{t['page']}: {t['rows']}行, 图片={t['table_img_filename'][:30]}...")

    # 检查图片目录
    images_dir = Path("data/exports_vlm_full/全单电缆装配规程/vlm/images")
    if images_dir.exists():
        image_files = list(images_dir.glob("*.jpg"))
        print(f"\n图片目录: {images_dir}")
        print(f"  图片文件数: {len(image_files)}")

    print("\n" + "=" * 60)
    print("提取完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
