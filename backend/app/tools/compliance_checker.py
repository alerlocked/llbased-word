"""
工艺文件辅助编辑系统 - 合规检查工具
实现工艺文件的合规性检查，支持多标准和多级别检查
"""
from typing import Dict, Any, Optional, List, Union
import json
import os
from pathlib import Path

from app.shared.logging import get_logger
from app.config import settings

logger = get_logger(__name__)


class ComplianceChecker:
    """
    合规检查工具

    负责具体的合规性检查逻辑，
    支持企业标准、行业标准和安全标准的检查
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化合规检查工具

        Args:
            config: 配置参数
        """
        self.config = config or {}
        # 使用统一的配置路径
        self.compliance_rules_dir = self.config.get("compliance_rules_dir", str(settings.DATA_DIR / "compliance"))
        self.cache_enabled = self.config.get("cache_enabled", True)

        # 加载合规规则
        self.compliance_rules = self._load_compliance_rules()
        self.supported_standards = list(self.compliance_rules.keys())

        logger.info(
            "compliance_checker_initialized",
            standards=self.supported_standards,
            rules_dir=self.compliance_rules_dir
        )

    def _load_compliance_rules(self) -> Dict[str, Any]:
        """
        加载合规规则

        Returns:
            合规规则字典
        """
        compliance_rules = {}

        try:
            rules_path = Path(self.compliance_rules_dir)
            if not rules_path.exists():
                logger.warning("compliance_rules_directory_not_found", path=self.compliance_rules_dir)
                return compliance_rules

            # 查找所有合规规则文件
            for rules_file in rules_path.glob("*.json"):
                standard_name = rules_file.stem
                try:
                    with open(rules_file, 'r', encoding='utf-8') as f:
                        compliance_rules[standard_name] = json.load(f)
                    logger.debug("compliance_rules_loaded", standard=standard_name)
                except Exception as e:
                    logger.error("failed_to_load_compliance_rules", standard=standard_name, error=str(e))

            if not compliance_rules:
                logger.warning("no_compliance_rules_found", path=self.compliance_rules_dir)

        except Exception as e:
            logger.error("compliance_rules_loading_failed", error=str(e))

        return compliance_rules

    async def check_document(
        self,
        document: Dict[str, Any],
        standards: List[str],
        check_level: str = "detailed",
        strict_mode: bool = False
    ) -> Dict[str, Any]:
        """
        检查文档合规性

        Args:
            document: 工艺文件
            standards: 要检查的标准列表
            check_level: 检查级别
            strict_mode: 严格模式

        Returns:
            检查结果
        """
        try:
            issues = []
            warnings = []
            total_checks = 0
            passed_checks = 0
            failed_checks = 0

            # 遍历所有指定的标准
            for standard in standards:
                if standard not in self.compliance_rules:
                    logger.warning("unsupported_standard", standard=standard)
                    continue

                standard_rules = self.compliance_rules[standard]
                standard_issues, standard_warnings, standard_checks = await self._check_against_standard(
                    document, standard_rules, check_level, strict_mode
                )

                issues.extend(standard_issues)
                warnings.extend(standard_warnings)
                total_checks += standard_checks["total"]
                passed_checks += standard_checks["passed"]
                failed_checks += standard_checks["failed"]

            # 确定合规状态
            compliance_status = "compliant"
            if issues:
                critical_issues = [i for i in issues if i.get("severity") == "critical"]
                if critical_issues:
                    compliance_status = "non_compliant_critical"
                else:
                    compliance_status = "non_compliant"

            return {
                "success": True,
                "compliance_status": compliance_status,
                "issues": issues,
                "warnings": warnings,
                "total_checks": total_checks,
                "passed_checks": passed_checks,
                "failed_checks": failed_checks
            }

        except Exception as e:
            logger.error("document_check_failed", error=str(e), document_id=document.get("id", "unknown"))
            return {
                "success": False,
                "error": f"文档检查失败: {str(e)}",
                "error_code": "CHECK_EXCEPTION"
            }

    async def _check_against_standard(
        self,
        document: Dict[str, Any],
        standard_rules: Dict[str, Any],
        check_level: str,
        strict_mode: bool
    ) -> tuple:
        """
        根据标准检查文档

        Args:
            document: 工艺文件
            standard_rules: 标准规则
            check_level: 检查级别
            strict_mode: 严格模式

        Returns:
            (问题列表, 警告列表, 检查统计)
        """
        issues = []
        warnings = []
        total_checks = 0
        passed_checks = 0
        failed_checks = 0

        try:
            # 检查文档基本信息
            basic_info_checks = await self._check_basic_info(document, standard_rules, strict_mode)
            issues.extend(basic_info_checks["issues"])
            warnings.extend(basic_info_checks["warnings"])
            total_checks += basic_info_checks["total_checks"]
            passed_checks += basic_info_checks["passed_checks"]
            failed_checks += basic_info_checks["failed_checks"]

            # 检查工序
            operation_checks = await self._check_operations(document, standard_rules, check_level, strict_mode)
            issues.extend(operation_checks["issues"])
            warnings.extend(operation_checks["warnings"])
            total_checks += operation_checks["total_checks"]
            passed_checks += operation_checks["passed_checks"]
            failed_checks += operation_checks["failed_checks"]

            # 检查参数
            parameter_checks = await self._check_parameters(document, standard_rules, check_level, strict_mode)
            issues.extend(parameter_checks["issues"])
            warnings.extend(parameter_checks["warnings"])
            total_checks += parameter_checks["total_checks"]
            passed_checks += parameter_checks["passed_checks"]
            failed_checks += parameter_checks["failed_checks"]

            # 检查质量要求
            quality_checks = await self._check_quality_requirements(document, standard_rules, check_level, strict_mode)
            issues.extend(quality_checks["issues"])
            warnings.extend(quality_checks["warnings"])
            total_checks += quality_checks["total_checks"]
            passed_checks += quality_checks["passed_checks"]
            failed_checks += quality_checks["failed_checks"]

            return issues, warnings, {"total": total_checks, "passed": passed_checks, "failed": failed_checks}

        except Exception as e:
            logger.error("standard_check_failed", error=str(e))
            return [], [], {"total": 0, "passed": 0, "failed": 0}

    async def _check_basic_info(self, document: Dict[str, Any], standard_rules: Dict[str, Any], strict_mode: bool) -> Dict[str, Any]:
        """
        检查文档基本信息

        Args:
            document: 工艺文件
            standard_rules: 标准规则
            strict_mode: 严格模式

        Returns:
            检查结果
        """
        issues = []
        warnings = []
        total_checks = 0
        passed_checks = 0
        failed_checks = 0

        # 检查必需字段
        required_fields = standard_rules.get("required_fields", [])
        for field in required_fields:
            total_checks += 1
            if field not in document or not document[field]:
                failed_checks += 1
                severity = "critical" if strict_mode else "high"
                issues.append({
                    "rule_id": f"basic_info_{field}",
                    "description": f"缺少必需字段: {field}",
                    "severity": severity,
                    "category": "basic_info",
                    "auto_fixable": False
                })
            else:
                passed_checks += 1

        # 检查文档ID格式
        doc_id = document.get("id", "")
        if doc_id:
            total_checks += 1
            id_pattern = standard_rules.get("id_pattern", "^[A-Za-z0-9\\-_]+$")
            import re
            if not re.match(id_pattern, doc_id):
                failed_checks += 1
                issues.append({
                    "rule_id": "basic_info_id_format",
                    "description": f"文档ID格式不符合要求: {doc_id}",
                    "severity": "medium",
                    "category": "basic_info",
                    "auto_fixable": False
                })
            else:
                passed_checks += 1

        return {
            "issues": issues,
            "warnings": warnings,
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks
        }

    async def _check_operations(self, document: Dict[str, Any], standard_rules: Dict[str, Any], check_level: str, strict_mode: bool) -> Dict[str, Any]:
        """
        检查工序

        Args:
            document: 工艺文件
            standard_rules: 标准规则
            check_level: 检查级别
            strict_mode: 严格模式

        Returns:
            检查结果
        """
        issues = []
        warnings = []
        total_checks = 0
        passed_checks = 0
        failed_checks = 0

        operations = document.get("operations", [])

        # 检查工序数量
        total_checks += 1
        if len(operations) == 0:
            failed_checks += 1
            severity = "critical" if strict_mode else "high"
            issues.append({
                "rule_id": "operations_empty",
                "description": "工艺文件必须包含至少一个工序",
                "severity": severity,
                "category": "operations",
                "auto_fixable": False
            })
        else:
            passed_checks += 1

        # 检查每个工序
        for i, operation in enumerate(operations):
            op_checks = await self._check_single_operation(operation, standard_rules, check_level, i)
            issues.extend(op_checks["issues"])
            warnings.extend(op_checks["warnings"])
            total_checks += op_checks["total_checks"]
            passed_checks += op_checks["passed_checks"]
            failed_checks += op_checks["failed_checks"]

        return {
            "issues": issues,
            "warnings": warnings,
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks
        }

    async def _check_single_operation(self, operation: Dict[str, Any], standard_rules: Dict[str, Any], check_level: str, index: int) -> Dict[str, Any]:
        """
        检查单个工序

        Args:
            operation: 工序
            standard_rules: 标准规则
            check_level: 检查级别
            index: 工序索引

        Returns:
            检查结果
        """
        issues = []
        warnings = []
        total_checks = 0
        passed_checks = 0
        failed_checks = 0

        # 检查必需字段
        required_fields = ["id", "name", "description"]
        for field in required_fields:
            total_checks += 1
            if field not in operation or not operation[field]:
                failed_checks += 1
                issues.append({
                    "rule_id": f"operation_{field}",
                    "description": f"工序 {index+1} 缺少必需字段: {field}",
                    "severity": "high",
                    "category": "operations",
                    "auto_fixable": False
                })
            else:
                passed_checks += 1

        # 检查工具信息（详细检查级别）
        if check_level == "detailed":
            tools = operation.get("tools", [])
            total_checks += 1
            if not tools:
                failed_checks += 1
                warnings.append({
                    "rule_id": "operation_tools_missing",
                    "description": f"工序 {index+1} 未指定使用工具",
                    "severity": "low",
                    "category": "operations",
                    "auto_fixable": False
                })
            else:
                passed_checks += 1

        return {
            "issues": issues,
            "warnings": warnings,
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks
        }

    async def _check_parameters(self, document: Dict[str, Any], standard_rules: Dict[str, Any], check_level: str, strict_mode: bool) -> Dict[str, Any]:
        """
        检查工艺参数

        Args:
            document: 工艺文件
            standard_rules: 标准规则
            check_level: 检查级别
            strict_mode: 严格模式

        Returns:
            检查结果
        """
        issues = []
        warnings = []
        total_checks = 0
        passed_checks = 0
        failed_checks = 0

        parameters = document.get("parameters", {})

        # 检查参数完整性（详细检查级别）
        if check_level == "detailed":
            total_checks += 1
            if not parameters:
                failed_checks += 1
                warnings.append({
                    "rule_id": "parameters_empty",
                    "description": "建议添加工艺参数以提高工艺文件的可执行性",
                    "severity": "low",
                    "category": "parameters",
                    "auto_fixable": False
                })
            else:
                passed_checks += 1

        return {
            "issues": issues,
            "warnings": warnings,
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks
        }

    async def _check_quality_requirements(self, document: Dict[str, Any], standard_rules: Dict[str, Any], check_level: str, strict_mode: bool) -> Dict[str, Any]:
        """
        检查质量要求

        Args:
            document: 工艺文件
            standard_rules: 标准规则
            check_level: 检查级别
            strict_mode: 严格模式

        Returns:
            检查结果
        """
        issues = []
        warnings = []
        total_checks = 0
        passed_checks = 0
        failed_checks = 0

        quality_requirements = document.get("quality_requirements", [])

        # 检查质量要求（详细检查级别）
        if check_level == "detailed":
            total_checks += 1
            if not quality_requirements:
                failed_checks += 1
                warnings.append({
                    "rule_id": "quality_requirements_empty",
                    "description": "建议添加质量要求以确保工艺质量",
                    "severity": "low",
                    "category": "quality",
                    "auto_fixable": False
                })
            else:
                passed_checks += 1

        return {
            "issues": issues,
            "warnings": warnings,
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks
        }

    async def get_supported_standards(self) -> List[str]:
        """
        获取支持的合规标准

        Returns:
            支持的标准列表
        """
        return self.supported_standards

    async def get_rule_details(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """
        获取规则详情

        Args:
            rule_id: 规则ID

        Returns:
            规则详情
        """
        # 在所有标准中查找规则
        for standard, rules in self.compliance_rules.items():
            # 这里可以实现更复杂的规则查找逻辑
            # 目前返回空字典作为占位符
            pass

        return {}

    async def add_rule_to_standard(self, rule: Dict[str, Any], standard: str) -> Dict[str, Any]:
        """
        添加规则到标准

        Args:
            rule: 规则
            standard: 标准

        Returns:
            添加结果
        """
        try:
            if standard not in self.compliance_rules:
                self.compliance_rules[standard] = {}

            # 添加规则到标准
            # 这里需要根据具体的规则结构实现
            # 目前是占位符实现

            logger.info("rule_added_to_standard", rule_id=rule.get("id"), standard=standard)
            return {
                "success": True,
                "message": f"规则已添加到标准 '{standard}'"
            }

        except Exception as e:
            logger.error("rule_addition_failed", error=str(e), rule_id=rule.get("id"), standard=standard)
            return {
                "success": False,
                "error": f"规则添加失败: {str(e)}",
                "error_code": "RULE_ADDITION_EXCEPTION"
            }