#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
validate_profiles.py - 验证画像 YAML 文件格式

遍历 .project-meta/profiles/*.yaml，验证格式和必需字段
"""
import sys
import json
from pathlib import Path
from typing import Dict, Any, List
import yaml


def validate_profile_file(yaml_path: Path) -> Dict[str, Any]:
    """
    验证单个画像文件
    
    Args:
        yaml_path: YAML 文件路径
        
    Returns:
        验证结果
    """
    result = {
        "file": str(yaml_path),
        "valid": True,
        "errors": [],
        "warnings": []
    }
    
    try:
        # 1. 尝试解析 YAML
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if data is None:
            result["valid"] = False
            result["errors"].append("文件内容为空")
            return result
        
        # 2. 检查必需字段
        required_fields = ["id", "user_id", "domain"]
        for field in required_fields:
            if field not in data:
                result["valid"] = False
                result["errors"].append(f"缺少必需字段: {field}")
        
        # 3. 检查 writing 配置
        writing = data.get("writing", {})
        if not isinstance(writing, dict):
            result["valid"] = False
            result["errors"].append("writing 字段必须是字典")
        else:
            writing_fields = ["tone", "terminology", "detail_level"]
            for field in writing_fields:
                if field not in writing:
                    result["warnings"].append(f"writing 缺少字段: {field}")
        
        # 4. 检查 review 配置
        review = data.get("review", {})
        if not isinstance(review, dict):
            result["valid"] = False
            result["errors"].append("review 字段必须是字典")
        else:
            review_fields = ["check_completeness", "check_accuracy", "allowed_deviation"]
            for field in review_fields:
                if field not in review:
                    result["warnings"].append(f"review 缺少字段: {field}")
            
            # 检查 allowed_deviation 范围
            if "allowed_deviation" in review:
                deviation = review["allowed_deviation"]
                if not isinstance(deviation, (int, float)):
                    result["valid"] = False
                    result["errors"].append("allowed_deviation 必须是数字")
                elif not 0 <= deviation <= 1:
                    result["valid"] = False
                    result["errors"].append("allowed_deviation 必须在 0-1 范围内")
        
    except yaml.YAMLError as e:
        result["valid"] = False
        result["errors"].append(f"YAML 解析错误: {str(e)}")
    except Exception as e:
        result["valid"] = False
        result["errors"].append(f"读取文件失败: {str(e)}")
    
    return result


def main():
    """主函数"""
    # 查找项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent.parent
    profiles_dir = project_root / ".project-meta" / "profiles"
    
    if not profiles_dir.exists():
        print(json.dumps({
            "status": "fail",
            "error": f"画像目录不存在: {profiles_dir}"
        }))
        sys.exit(1)
    
    # 遍历所有 YAML 文件
    results = []
    all_valid = True
    
    yaml_files = list(profiles_dir.glob("*.yaml"))
    
    if not yaml_files:
        print(json.dumps({
            "status": "fail",
            "error": "未找到画像文件",
            "profiles_dir": str(profiles_dir)
        }))
        sys.exit(1)
    
    for yaml_path in yaml_files:
        result = validate_profile_file(yaml_path)
        results.append(result)
        if not result["valid"]:
            all_valid = False
    
    # 输出结果
    output = {
        "status": "pass" if all_valid else "fail",
        "profiles_dir": str(profiles_dir),
        "profiles_count": len(results),
        "profiles": results
    }
    
    print(json.dumps(output, ensure_ascii=False, indent=2))
    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()
