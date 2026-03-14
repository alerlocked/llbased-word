"""
合规检查 Tool

检查工艺文件是否符合企业标准和行业规范
"""
from typing import Dict, Any, Optional, List
from app.agents.core import ToolRegistry
from app.shared.logging import get_logger

logger = get_logger(__name__)


@ToolRegistry.register("compliance_checker")
class ComplianceTool:
    """
    合规检查工具

    检查工艺文件是否符合企业标准、行业规范和安全要求
    """

    name = "compliance_checker"
    description = "检查工艺文件的合规性，包括企业标准、行业规范、安全要求等"

    # 标准类型
    STANDARD_TYPES = {
        "enterprise": "企业标准",
        "industry": "行业标准",
        "safety": "安全标准",
        "quality": "质量标准"
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化合规检查工具

        Args:
            config: 配置参数
                - check_level: 检查级别（basic/detailed/strict）
                - strict_mode: 是否严格模式
                - auto_fix_enabled: 是否自动修复
        """
        self.config = config or {}
        self.check_level = self.config.get("check_level", "detailed")
        self.strict_mode = self.config.get("strict_mode", False)
        self.auto_fix_enabled = self.config.get("auto_fix_enabled", False)

        # 延迟加载 ComplianceChecker
        self._checker = None

        logger.info(
            "compliance_tool_initialized",
            check_level=self.check_level,
            strict_mode=self.strict_mode
        )

    @property
    def checker(self):
        """延迟加载 ComplianceChecker"""
        if self._checker is None:
            try:
                from app.tools.compliance_checker import ComplianceChecker
                self._checker = ComplianceChecker(self.config)
            except Exception as e:
                logger.error("compliance_checker_load_failed", error=str(e))
        return self._checker

    async def execute(
        self,
        input_data: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行合规检查

        Args:
            input_data: 输入数据
                - content: 待检查内容
                - standards: 标准类型列表
                - doc_type: 文档类型
            context: 执行上下文

        Returns:
            {
                "success": bool,
                "passed": bool,
                "results": {
                    "enterprise": {"passed": bool, "issues": []},
                    "industry": {"passed": bool, "issues": []},
                    ...
                },
                "summary": {
                    "total_issues": int,
                    "critical_issues": int,
                    "warnings": int
                },
                "suggestions": List[str]
            }
        """
        try:
            # 解析输入
            if isinstance(input_data, dict):
                content = input_data.get("content", "")
                standards = input_data.get("standards", ["enterprise"])
                doc_type = input_data.get("doc_type", "process_document")
            else:
                content = str(input_data)
                standards = ["enterprise"]
                doc_type = "process_document"

            if not content:
                return {
                    "success": False,
                    "error": "检查内容不能为空",
                    "error_code": "EMPTY_CONTENT"
                }

            # 执行检查
            if self.checker is None:
                return self._mock_check(content, standards)

            # 调用实际检查器
            check_result = await self._check_compliance(content, standards, doc_type)

            logger.info(
                "compliance_check_completed",
                passed=check_result.get("passed", False),
                standards=standards
            )

            return check_result

        except Exception as e:
            logger.error("compliance_check_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "error_code": "CHECK_FAILED"
            }

    async def _check_compliance(
        self,
        content: str,
        standards: List[str],
        doc_type: str
    ) -> Dict[str, Any]:
        """
        执行实际合规检查

        Args:
            content: 待检查内容
            standards: 标准类型列表
            doc_type: 文档类型

        Returns:
            检查结果
        """
        # 调用 ComplianceChecker
        check_result = await self.checker.check_document(
            document={"content": content, "type": doc_type},
            standards=standards,
            check_level=self.check_level,
            strict_mode=self.strict_mode
        )

        if not check_result or not check_result.get("success"):
            return {
                "success": False,
                "error": check_result.get("error", "合规检查失败"),
                "error_code": "CHECK_FAILED"
            }

        # 统计问题
        results = check_result.get("results", {})
        total_issues = 0
        critical_issues = 0
        warnings = 0

        for std_type, std_result in results.items():
            issues = std_result.get("issues", [])
            total_issues += len(issues)
            for issue in issues:
                if issue.get("severity") == "critical":
                    critical_issues += 1
                elif issue.get("severity") == "warning":
                    warnings += 1

        return {
            "success": True,
            "passed": critical_issues == 0,
            "results": results,
            "summary": {
                "total_issues": total_issues,
                "critical_issues": critical_issues,
                "warnings": warnings
            },
            "suggestions": check_result.get("suggestions", [])
        }

    def _mock_check(self, content: str, standards: List[str]) -> Dict[str, Any]:
        """
        模拟合规检查

        Args:
            content: 待检查内容
            standards: 标准类型列表

        Returns:
            模拟结果
        """
        results = {}
        total_issues = 0

        for std in standards:
            std_name = self.STANDARD_TYPES.get(std, std)
            # 简单的关键词检查
            issues = []

            if "安全" in std or std == "safety":
                safety_keywords = ["危险", "警告", "注意"]
                for kw in safety_keywords:
                    if kw in content:
                        issues.append({
                            "type": "safety_keyword",
                            "message": f"发现安全相关词汇: {kw}",
                            "severity": "warning",
                            "location": content.find(kw)
                        })

            results[std] = {
                "passed": len(issues) == 0,
                "issues": issues,
                "standard_name": std_name
            }
            total_issues += len(issues)

        return {
            "success": True,
            "passed": total_issues == 0,
            "results": results,
            "summary": {
                "total_issues": total_issues,
                "critical_issues": 0,
                "warnings": total_issues
            },
            "suggestions": ["建议检查安全相关词汇的使用"] if total_issues > 0 else [],
            "note": "ComplianceChecker 不可用，返回模拟结果"
        }
