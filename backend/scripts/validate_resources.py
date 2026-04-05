#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
validate_resources.py - 验证资源文件完整性

检查：
1. 必需的画像文件存在
2. 必需的模板文件存在
3. YAML 格式正确
4. 必需字段齐全
"""
import sys
import json
import yaml
from pathlib import Path
from typing import Dict, Any, List


# 必需的资源文件
REQUIRED_RESOURCES = {
    "profiles": [
        "default_assembly.yaml",
        "default_welding.yaml"
    ],
    "templates": [
        "assembly_work_instruction.yaml",
        "welding_procedure.yaml"
    ]
}


def validate_yaml_file(file_path: Path, required_fields: List[str] = None) -> Dict[str, Any]:
    """
    验证 YAML 文件
    
    Args:
        file_path: 文件路径
        required_fields: 必需字段列表
        
    Returns:
        验证结果
    """
    result = {
        "file": str(file_path),
        "exists": False,
        "valid": False,
        "errors": []
    }
    
    if not file_path.exists():
        result["errors"].append("文件不存在")
        return result
    
    result["exists"] = True
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if data is None:
            result["errors"].append("文件内容为空")
            return result
        
        # 检查必需字段
        if required_fields:
            for field in required_fields:
                if field not in data:
                    result["errors"].append(f"缺少必需字段: {field}")
        
        if not result["errors"]:
            result["valid"] = True
    
    except yaml.YAMLError as e:
        result["errors"].append(f"YAML 解析错误: {str(e)}")
    except Exception as e:
        result["errors"].append(f"读取文件失败: {str(e)}")
    
    return result


def main():
    """主函数"""
    script_dir = Path(__file__).parent
    # script_dir = backend/scripts
    # script_dir.parent.parent = project root
    project_root = script_dir.parent.parent
    meta_dir = project_root / ".project-meta"
    
    all_results = []
    all_valid = True
    missing_files = []
    
    # 检查 profiles
    profiles_dir = meta_dir / "profiles"
    for filename in REQUIRED_RESOURCES["profiles"]:
        file_path = profiles_dir / filename
        result = validate_yaml_file(
            file_path,
            required_fields=["id", "user_id", "domain"]
        )
        result["type"] = "profile"
        all_results.append(result)
        
        if not result["exists"]:
            missing_files.append(str(file_path))
            all_valid = False
        elif not result["valid"]:
            all_valid = False
    
    # 检查 templates
    templates_dir = meta_dir / "templates"
    for filename in REQUIRED_RESOURCES["templates"]:
        file_path = templates_dir / filename
        result = validate_yaml_file(
            file_path,
            required_fields=["id", "domain", "structure"]
        )
        result["type"] = "template"
        all_results.append(result)
        
        if not result["exists"]:
            missing_files.append(str(file_path))
            all_valid = False
        elif not result["valid"]:
            all_valid = False
    
    # 输出结果
    output = {
        "status": "pass" if all_valid else "fail",
        "meta_dir": str(meta_dir),
        "files_checked": len(all_results),
        "files_valid": sum(1 for r in all_results if r["valid"]),
        "files_invalid": sum(1 for r in all_results if not r["valid"]),
        "missing_files": missing_files,
        "files": all_results
    }
    
    print(json.dumps(output, ensure_ascii=False, indent=2))
    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()
