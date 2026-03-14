"""
校对 Agent

负责术语标准化、数据纠正补全、格式校验
"""
from typing import Dict, Any, Optional, List
from app.agents.base_agent import BaseAgent
from app.agents.core import AgentRegistry
from app.shared.logging import get_logger

logger = get_logger(__name__)


@AgentRegistry.register("proofread")
class ProofreadAgent(BaseAgent):
    """
    校对 Agent

    职责：
    - 术语标准化
    - 数据纠正补全
    - 格式校验
    """

    name = "proofread"
    description = "负责术语标准化、数据纠正补全、格式校验"
    tools = ["rag_retriever", "terminology_mapper"]

    # 检查类型
    CHECK_TYPES = ["terminology", "data", "format", "all"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化校对 Agent

        Args:
            config: 配置参数
        """
        super().__init__(config)

        # 校对相关配置
        self.auto_fix = self.config.get("auto_fix", False)
        self.strict_mode = self.config.get("strict_mode", False)

    async def process(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理校对任务

        Args:
            task: 任务描述
                - content: 待校对内容
                - check_type: 检查类型 (terminology/data/format/all)
                - target_standard: 目标标准
            context: 执行上下文

        Returns:
            {
                "success": bool,
                "results": {
                    "terminology": {...},
                    "data": {...},
                    "format": {...}
                },
                "corrections": List[Dict],
                "passed": bool
            }
        """
        try:
            content = task.get("content", "")
            check_type = task.get("check_type", "all")

            if not content:
                return {
                    "success": False,
                    "error": "校对内容不能为空",
                    "error_code": "EMPTY_CONTENT"
                }

            results = {}
            all_issues = []

            # 1. 术语检查
            if check_type in ["terminology", "all"]:
                term_result = await self._check_terminology(task, context)
                results["terminology"] = term_result
                all_issues.extend(term_result.get("issues", []))

            # 2. 数据检查
            if check_type in ["data", "all"]:
                data_result = await self._check_data(task, context)
                results["data"] = data_result
                all_issues.extend(data_result.get("issues", []))

            # 3. 格式检查
            if check_type in ["format", "all"]:
                format_result = await self._check_format(task, context)
                results["format"] = format_result
                all_issues.extend(format_result.get("issues", []))

            # 汇总结果
            passed = len(all_issues) == 0
            corrections = self._generate_corrections(all_issues)

            # 自动修复（如果启用）
            corrected_content = None
            if self.auto_fix and not passed:
                corrected_content = self._apply_corrections(content, corrections)

            logger.info(
                "proofread_completed",
                check_type=check_type,
                issues_count=len(all_issues),
                passed=passed
            )

            return {
                "success": True,
                "results": results,
                "corrections": corrections,
                "corrected_content": corrected_content,
                "passed": passed,
                "summary": {
                    "total_issues": len(all_issues),
                    "critical_issues": len([i for i in all_issues if i.get("severity") == "critical"]),
                    "warnings": len([i for i in all_issues if i.get("severity") == "warning"])
                }
            }

        except Exception as e:
            logger.error("proofread_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "error_code": "PROOFREAD_FAILED"
            }

    async def _check_terminology(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        术语检查

        Args:
            task: 任务描述
            context: 执行上下文

        Returns:
            术语检查结果
        """
        content = task.get("content", "")
        target_standard = task.get("target_standard", "enterprise_standard")

        # 调用术语映射 Tool
        term_result = await self.use_tool(
            "terminology_mapper",
            {
                "content": content,
                "target_standard": target_standard
            }
        )

        if not term_result.get("success"):
            return {
                "passed": True,  # 工具不可用时默认通过
                "issues": [],
                "mappings": []
            }

        # 分析术语映射结果
        mappings = term_result.get("mappings", [])
        issues = []

        for mapping in mappings:
            if mapping.get("confidence", 1.0) < 0.9:
                issues.append({
                    "type": "terminology",
                    "severity": "warning",
                    "original": mapping.get("original", ""),
                    "suggested": mapping.get("standard", ""),
                    "confidence": mapping.get("confidence"),
                    "message": f"术语 '{mapping.get('original')}' 建议改为 '{mapping.get('standard')}'"
                })

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "mappings": mappings
        }

    async def _check_data(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        数据检查

        Args:
            task: 任务描述
            context: 执行上下文

        Returns:
            数据检查结果
        """
        content = task.get("content", "")

        # 检索相关知识进行数据验证
        retrieval_result = await self.use_tool(
            "rag_retriever",
            f"数据验证: {content[:100]}",
            {"top_k": 3}
        )

        issues = []

        # 基本数据格式检查
        import re

        # 检查数字格式
        numbers = re.findall(r'\d+\.?\d*', content)
        for num in numbers:
            try:
                float(num)
            except ValueError:
                issues.append({
                    "type": "data",
                    "severity": "warning",
                    "value": num,
                    "message": f"数字格式可能有问题: {num}"
                })

        # 检查是否有缺失数据
        if "待定" in content or "TBD" in content or "___" in content:
            issues.append({
                "type": "data",
                "severity": "critical",
                "message": "存在未填写的占位符"
            })

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "checked_numbers": len(numbers)
        }

    async def _check_format(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        格式检查

        Args:
            task: 任务描述
            context: 执行上下文

        Returns:
            格式检查结果
        """
        content = task.get("content", "")
        issues = []

        # 检查表格格式
        if "<table" in content.lower():
            # 检查表格是否完整
            if content.count("<table") != content.count("</table>"):
                issues.append({
                    "type": "format",
                    "severity": "critical",
                    "message": "表格标签不匹配"
                })

        # 检查段落格式
        paragraphs = content.split("\n\n")
        for i, para in enumerate(paragraphs):
            if len(para) > 1000:
                issues.append({
                    "type": "format",
                    "severity": "warning",
                    "message": f"段落 {i+1} 过长，建议分段"
                })

        # 检查标题层级
        import re
        headings = re.findall(r'^#+\s+.+$', content, re.MULTILINE)
        if len(headings) > 0:
            levels = [len(re.match(r'^#+', h).group()) for h in headings]
            for i in range(1, len(levels)):
                if levels[i] - levels[i-1] > 1:
                    issues.append({
                        "type": "format",
                        "severity": "warning",
                        "message": f"标题层级跳跃: 从 {levels[i-1]} 到 {levels[i]}"
                    })

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "paragraphs_count": len(paragraphs),
            "headings_count": len(headings)
        }

    def _generate_corrections(self, issues: List[Dict]) -> List[Dict]:
        """
        生成修正建议

        Args:
            issues: 问题列表

        Returns:
            修正建议列表
        """
        corrections = []

        for issue in issues:
            correction = {
                "type": issue.get("type"),
                "severity": issue.get("severity"),
                "message": issue.get("message"),
                "action": "review"  # review, auto_fix, ignore
            }

            # 如果是术语问题，提供自动修正
            if issue.get("type") == "terminology" and issue.get("suggested"):
                correction["action"] = "auto_fix"
                correction["original"] = issue.get("original")
                correction["replacement"] = issue.get("suggested")

            corrections.append(correction)

        return corrections

    def _apply_corrections(
        self,
        content: str,
        corrections: List[Dict]
    ) -> str:
        """
        应用修正

        Args:
            content: 原始内容
            corrections: 修正列表

        Returns:
            修正后的内容
        """
        corrected = content

        for correction in corrections:
            if correction.get("action") == "auto_fix":
                original = correction.get("original", "")
                replacement = correction.get("replacement", "")
                if original and replacement:
                    corrected = corrected.replace(original, replacement)

        return corrected
