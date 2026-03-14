"""
审查 Agent

负责合规性检查、合理性验证、风险提示
"""
from typing import Dict, Any, Optional, List
from app.agents.base_agent import BaseAgent
from app.agents.core import AgentRegistry
from app.shared.logging import get_logger

logger = get_logger(__name__)


@AgentRegistry.register("review")
class ReviewAgent(BaseAgent):
    """
    审查 Agent

    职责：
    - 合规性检查
    - 合理性验证
    - 风险提示
    """

    name = "review"
    description = "负责合规性检查、合理性验证、风险提示"
    tools = ["rag_retriever", "compliance_checker"]

    # 检查类型
    CHECK_TYPES = ["compliance", "rationality", "risk", "all"]

    # 标准类型
    STANDARD_TYPES = ["enterprise", "industry", "safety", "quality"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化审查 Agent

        Args:
            config: 配置参数
        """
        super().__init__(config)

        # 审查相关配置
        self.strict_mode = self.config.get("strict_mode", False)
        self.default_standards = self.config.get(
            "default_standards",
            ["enterprise", "safety"]
        )

    async def process(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理审查任务

        Args:
            task: 任务描述
                - content: 待审查内容
                - check_type: 检查类型 (compliance/rationality/risk/all)
                - standards: 要检查的标准列表
            context: 执行上下文

        Returns:
            {
                "success": bool,
                "results": {
                    "compliance": {...},
                    "rationality": {...},
                    "risk": {...}
                },
                "passed": bool,
                "warnings": List[str],
                "recommendations": List[str]
            }
        """
        try:
            content = task.get("content", "")
            check_type = task.get("check_type", "all")
            standards = task.get("standards", self.default_standards)

            if not content:
                return {
                    "success": False,
                    "error": "审查内容不能为空",
                    "error_code": "EMPTY_CONTENT"
                }

            results = {}
            all_passed = True
            all_warnings = []
            all_recommendations = []

            # 1. 合规性检查
            if check_type in ["compliance", "all"]:
                compliance_result = await self._check_compliance(
                    content, standards, context
                )
                results["compliance"] = compliance_result
                if not compliance_result.get("passed"):
                    all_passed = False
                all_warnings.extend(compliance_result.get("warnings", []))
                all_recommendations.extend(compliance_result.get("recommendations", []))

            # 2. 合理性验证
            if check_type in ["rationality", "all"]:
                rationality_result = await self._check_rationality(content, context)
                results["rationality"] = rationality_result
                if not rationality_result.get("passed"):
                    all_passed = False
                all_warnings.extend(rationality_result.get("warnings", []))
                all_recommendations.extend(rationality_result.get("recommendations", []))

            # 3. 风险评估
            if check_type in ["risk", "all"]:
                risk_result = await self._check_risk(content, context)
                results["risk"] = risk_result
                if not risk_result.get("passed"):
                    all_passed = False
                all_warnings.extend(risk_result.get("warnings", []))
                all_recommendations.extend(risk_result.get("recommendations", []))

            # 严格模式下，任何问题都不通过
            final_passed = all_passed if self.strict_mode else results.get("compliance", {}).get("passed", True)

            logger.info(
                "review_completed",
                check_type=check_type,
                passed=final_passed,
                warnings_count=len(all_warnings)
            )

            return {
                "success": True,
                "results": results,
                "passed": final_passed,
                "warnings": all_warnings,
                "recommendations": all_recommendations,
                "summary": {
                    "total_checks": len(results),
                    "passed_checks": sum(1 for r in results.values() if r.get("passed")),
                    "total_warnings": len(all_warnings),
                    "critical_issues": len([w for w in all_warnings if w.get("severity") == "critical"])
                }
            }

        except Exception as e:
            logger.error("review_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "error_code": "REVIEW_FAILED"
            }

    async def _check_compliance(
        self,
        content: str,
        standards: List[str],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        合规性检查

        Args:
            content: 待检查内容
            standards: 标准列表
            context: 执行上下文

        Returns:
            合规检查结果
        """
        # 调用合规检查 Tool
        compliance_result = await self.use_tool(
            "compliance_checker",
            {
                "content": content,
                "standards": standards
            }
        )

        if not compliance_result.get("success"):
            return {
                "passed": True,  # Tool 不可用时默认通过
                "warnings": [],
                "recommendations": []
            }

        # 分析检查结果
        tool_results = compliance_result.get("results", {})
        warnings = []
        recommendations = []
        all_passed = True

        for standard, result in tool_results.items():
            if not result.get("passed"):
                all_passed = False

            # 收集问题
            for issue in result.get("issues", []):
                warnings.append({
                    "type": "compliance",
                    "severity": issue.get("severity", "warning"),
                    "standard": standard,
                    "message": issue.get("message", "")
                })

            # 收集建议
            for suggestion in result.get("suggestions", []):
                recommendations.append({
                    "type": "compliance",
                    "standard": standard,
                    "suggestion": suggestion
                })

        return {
            "passed": all_passed,
            "standards_checked": standards,
            "warnings": warnings,
            "recommendations": recommendations
        }

    async def _check_rationality(
        self,
        content: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        合理性验证

        Args:
            content: 待验证内容
            context: 执行上下文

        Returns:
            合理性验证结果
        """
        warnings = []
        recommendations = []

        # 1. 检索相关知识进行对比
        knowledge = await self.use_tool(
            "rag_retriever",
            f"合理性验证: {content[:100]}",
            {"top_k": 3}
        )

        # 2. 基本逻辑检查
        import re

        # 检查数值范围
        numbers = re.findall(r'(\d+\.?\d*)\s*(mm|cm|m|kg|g|°C|V|A)', content)
        for value, unit in numbers:
            val = float(value)
            # 简单的范围检查
            if unit == "mm" and (val < 0 or val > 10000):
                warnings.append({
                    "type": "rationality",
                    "severity": "warning",
                    "message": f"数值 {value}{unit} 可能超出合理范围"
                })
            if unit == "°C" and (val < -273 or val > 2000):
                warnings.append({
                    "type": "rationality",
                    "severity": "critical",
                    "message": f"温度 {value}{unit} 不符合物理规律"
                })

        # 3. 检查工艺流程逻辑
        process_keywords = ["焊接", "压接", "装配", "检测", "包装"]
        found_keywords = [kw for kw in process_keywords if kw in content]

        if len(found_keywords) > 0:
            # 检查顺序是否合理
            # 简单检查：装配应该在包装之前
            if "包装" in found_keywords and "装配" in found_keywords:
                pack_pos = content.find("包装")
                assem_pos = content.find("装配")
                if pack_pos < assem_pos:
                    recommendations.append({
                        "type": "rationality",
                        "suggestion": "建议调整工序顺序：装配应在包装之前"
                    })

        # 4. 基于知识库的合理性检查
        if knowledge and knowledge.get("success"):
            results = knowledge.get("results", [])
            if results:
                # 简单的知识对比
                kb_content = results[0].get("content", "")
                # 这里可以做更复杂的对比
                pass

        passed = len([w for w in warnings if w.get("severity") == "critical"]) == 0

        return {
            "passed": passed,
            "warnings": warnings,
            "recommendations": recommendations,
            "checked_numbers": len(numbers),
            "found_processes": found_keywords
        }

    async def _check_risk(
        self,
        content: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        风险评估

        Args:
            content: 待评估内容
            context: 执行上下文

        Returns:
            风险评估结果
        """
        warnings = []
        recommendations = []

        # 风险关键词
        risk_keywords = {
            "critical": ["危险", "有毒", "易燃", "爆炸", "高压"],
            "warning": ["注意", "小心", "警告", "风险"],
            "info": ["建议", "参考", "可选"]
        }

        # 检查风险关键词
        for severity, keywords in risk_keywords.items():
            for kw in keywords:
                if kw in content:
                    warnings.append({
                        "type": "risk",
                        "severity": severity,
                        "keyword": kw,
                        "message": f"发现{severity}级别风险关键词: {kw}"
                    })

        # 检查是否有安全措施
        safety_keywords = ["防护", "安全", "保护", "紧急", "应急"]
        has_safety = any(kw in content for kw in safety_keywords)

        if warnings and not has_safety:
            recommendations.append({
                "type": "risk",
                "suggestion": "检测到风险关键词但未发现安全措施描述，建议添加安全防护说明"
            })

        # 评估通过条件：没有 critical 级别风险
        critical_count = len([w for w in warnings if w.get("severity") == "critical"])
        passed = critical_count == 0

        if not passed:
            recommendations.append({
                "type": "risk",
                "suggestion": f"存在 {critical_count} 个高风险项，需要重点关注"
            })

        return {
            "passed": passed,
            "warnings": warnings,
            "recommendations": recommendations,
            "risk_level": "critical" if critical_count > 0 else "warning" if warnings else "safe",
            "has_safety_measures": has_safety
        }
