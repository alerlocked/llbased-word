#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
check_isolation.py - 验证 Writing Agent 和 Review Agent 的上下文隔离

检查：
1. Writing Agent 不导入 ReviewService
2. Review Agent 不导入 ContextService（除 load_profile 外）
"""
import sys
import json
import re
from pathlib import Path
from typing import Dict, Any, List


def check_file_imports(file_path: Path, forbidden_imports: List[str]) -> Dict[str, Any]:
    """
    检查文件是否包含禁止的导入
    
    Args:
        file_path: 文件路径
        forbidden_imports: 禁止的导入列表
        
    Returns:
        检查结果
    """
    violations = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查 import 语句
        for forbidden in forbidden_imports:
            # 检查 import xxx
            pattern1 = rf'^import\s+{re.escape(forbidden)}'
            # 检查 from xxx import
            pattern2 = rf'^from\s+{re.escape(forbidden)}'
            # 检查 from app.xxx import
            pattern3 = rf'^from\s+app\.{re.escape(forbidden)}'
            
            for pattern in [pattern1, pattern2, pattern3]:
                matches = re.findall(pattern, content, re.MULTILINE)
                if matches:
                    violations.append({
                        "file": str(file_path),
                        "forbidden_import": forbidden,
                        "match": matches[0] if matches else ""
                    })
    
    except Exception as e:
        return {
            "file": str(file_path),
            "error": str(e)
        }
    
    return {
        "file": str(file_path),
        "violations": violations,
        "clean": len(violations) == 0
    }


def main():
    """主函数"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent.parent
    
    # 定义检查规则
    checks = [
        {
            "name": "Writing Agent 隔离",
            "files": [
                project_root / "backend" / "app" / "agents" / "functional" / "writing_agent.py"
            ],
            "forbidden": [
                "review_service",
                "ReviewService"
            ]
        },
        {
            "name": "Review Agent 隔离",
            "files": [
                project_root / "backend" / "app" / "agents" / "functional" / "review_agent.py"
            ],
            "forbidden": [
                "context_service.ContextService",
                "ContextService.build_context",
                "ContextService.load_template"
                # 允许 load_profile
            ]
        }
    ]
    
    all_results = []
    all_clean = True
    
    for check in checks:
        check_result = {
            "name": check["name"],
            "files_checked": [],
            "passed": True
        }
        
        for file_path in check["files"]:
            if not file_path.exists():
                check_result["files_checked"].append({
                    "file": str(file_path),
                    "status": "not_found"
                })
                continue
            
            result = check_file_imports(file_path, check["forbidden"])
            check_result["files_checked"].append(result)
            
            if not result.get("clean", False):
                check_result["passed"] = False
                all_clean = False
        
        all_results.append(check_result)
    
    # 输出结果
    output = {
        "status": "PASS" if all_clean else "FAIL",
        "checks": all_results,
        "violations_count": sum(
            len([f for f in c["files_checked"] if not f.get("clean", True)])
            for c in all_results
        )
    }
    
    print(json.dumps(output, ensure_ascii=False, indent=2))
    sys.exit(0 if all_clean else 1)


if __name__ == "__main__":
    main()
