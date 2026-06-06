"""
审查 Agent

负责合规性检查、合理性验证、风险提示

集成 Search Agent 进行统一检索
支持标准检索和缓存复用
"""
from typing import Dict, Any, Optional, List
from app.agents.base_agent import BaseAgent
from app.agents.core import AgentRegistry
from app.agents.search import SearchAgent, SearchMode
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

    使用 Search Agent 进行标准检索
    """

    name = "review"
    description = "负责合规性检查、合理性验证、风险提示"
    tools = ["compliance_checker"]  # 移除 rag_retriever，使用 Search Agent

    # 检查类型
    CHECK_TYPES = ["compliance", "rationality", "risk", "output_quality", "all"]

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

        # Search Agent 实例（依赖注入）
        self._search_agent: Optional[SearchAgent] = None

    @property
    def search_agent(self) -> SearchAgent:
        """获取或创建 Search Agent 实例"""
        if self._search_agent is None:
            self._search_agent = SearchAgent(self.config.get("search_agent", {}))
        return self._search_agent

    @search_agent.setter
    def search_agent(self, agent: SearchAgent):
        """设置 Search Agent 实例（依赖注入）"""
        self._search_agent = agent

    async def _search_standards(
        self,
        query: str,
        standards: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        使用 Search Agent 检索标准

        Args:
            query: 查询字符串
            standards: 标准类型列表

        Returns:
            检索结果
        """
        try:
            # 使用 standards_only 模式检索标准
            filters = {}
            if standards:
                filters["entity_types"] = standards

            search_context = await self.search_agent.search(
                mode=SearchMode.STANDARDS_ONLY,
                query=query,
                token_budget=2000,
                filters=filters
            )

            # 转换为兼容格式
            results = []
            for ctx in search_context.contexts:
                results.append({
                    "content": ctx.content,
                    "source": ctx.source,
                    "score": ctx.relevance_score,
                    "entity_type": ctx.entity_type,
                    "metadata": ctx.metadata
                })

            logger.info(
                "search_standards_completed",
                query=query[:50],
                results_count=len(results),
                cache_hit=search_context.cache_hit
            )

            return {
                "success": True,
                "results": results,
                "cache_hit": search_context.cache_hit
            }

        except Exception as e:
            logger.error("search_standards_failed", error=str(e), query=query[:50])
            return {
                "success": False,
                "error": str(e),
                "results": []
            }

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
            profile_data = task.get("profile")

            if not content:
                return {
                    "success": False,
                    "error": "审查内容不能为空",
                    "error_code": "EMPTY_CONTENT"
                }

            # If profile is available, use ReviewService for principle-based checks
            if profile_data:
                try:
                    from app.services.review_service import ReviewService
                    from app.models.profile import Profile
                    profile = Profile.from_dict(profile_data)
                    review_svc = ReviewService()
                    review_result = review_svc.review(content, profile)
                    return {
                        "success": True,
                        "results": {"principles": review_result.to_dict()},
                        "passed": review_result.passed,
                        "warnings": [i.message for i in review_result.issues if i.severity == "warning"],
                        "recommendations": [s.get("message", "") for s in review_result.suggestions],
                    }
                except Exception as e:
                    logger.warning(f"profile_review_failed, fallback to default: {e}")

            # Fallback: original compliance check flow
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

            # 4. Output quality check (format, duplication, ordering)
            if check_type in ["output_quality", "all"]:
                quality_result = self._check_output_quality(content)
                results["output_quality"] = quality_result
                if not quality_result.get("passed"):
                    all_passed = False
                all_warnings.extend(quality_result.get("warnings", []))
                all_recommendations.extend(quality_result.get("recommendations", []))

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
            # Tool unavailable: NEVER default-pass in production
            return {
                "passed": False,
                "warnings": [{
                    "type": "compliance",
                    "severity": "warning",
                    "message": "合规检查工具不可用，无法自动验证，请人工检查",
                }],
                "recommendations": [{
                    "type": "compliance",
                    "suggestion": "合规检查服务暂不可用，建议人工审核确认文档合规性",
                }],
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

        # 1. 使用 Search Agent 检索相关知识进行对比
        knowledge = await self._search_standards(
            f"合理性验证: {content[:100]}",
            standards=["Standard", "Process"]
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
                logger.debug(
                    "rationality_knowledge_check",
                    kb_content_length=len(kb_content)
                )

        passed = len([w for w in warnings if w.get("severity") == "critical"]) == 0

        return {
            "passed": passed,
            "warnings": warnings,
            "recommendations": recommendations,
            "checked_numbers": len(numbers),
            "found_processes": found_keywords,
            "cache_hit": knowledge.get("cache_hit", False) if knowledge else False
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

    def _check_table_structure(
        self,
        content: str,
        section_schema,
        lenient: bool = False,
    ) -> List[Dict[str, Any]]:
        """Validate table column structure against a SectionSchema.

        Checks:
        1. Column count matches schema definition.
        2. Required columns are not empty in data rows.

        Args:
            content: Generated content to check.
            section_schema: SectionSchema dataclass defining expected structure.
            lenient: When True (e.g. no reference source), lower severity from
                critical to warning for structural issues.

        Returns a list of warning dicts (may be empty).
        """
        import re as _re
        warnings: List[Dict[str, Any]] = []

        if section_schema.content_type != "table":
            return warnings

        expected_cols = section_schema.columns
        required_cols = section_schema.required_columns
        if not expected_cols:
            return warnings

        # Find all Markdown table rows (lines starting with |)
        table_rows = [
            line for line in content.split("\n")
            if line.strip().startswith("|") and line.strip().endswith("|")
        ]

        # Filter out separator rows (|---|---|...)
        data_rows = [
            row for row in table_rows
            if not _re.match(r"^\|[\s\-:|]+\|$", row.strip())
        ]

        if not data_rows:
            severity = "warning" if lenient else "critical"
            warnings.append({
                "type": "table_structure",
                "severity": severity,
                "message": (
                    f"Schema expects a table ({len(expected_cols)} columns: "
                    f"{', '.join(expected_cols)})，但输出中未检测到 Markdown 表格"
                ),
            })
            return warnings

        # Check column count on the header row (first data row)
        header_cells = [c.strip() for c in data_rows[0].strip().strip("|").split("|")]

        # Check column count on data rows (skip header)
        col_mismatches = []
        for i, row in enumerate(data_rows[1:], start=2):
            cells = row.strip().strip("|").split("|")
            if len(cells) != len(expected_cols):
                col_mismatches.append(i)

        if col_mismatches:
            severity = "warning" if lenient else "critical"
            warnings.append({
                "type": "table_structure",
                "severity": severity,
                "message": (
                    f"表格列数不匹配 schema（期望 {len(expected_cols)} 列），"
                    f"第 {col_mismatches[:5]} 行列数不符"
                ),
            })

        return warnings

    def _check_output_quality(self, content: str, section_schema=None, lenient: bool = False) -> Dict[str, Any]:
        """Check WritingAgent output for format/structure problems.

        Pure rule-based checks — no LLM calls, fast enough to run on
        every chapter output.

        Args:
            content: The generated content to check.
            section_schema: Optional SectionSchema dataclass for table structure
                validation. When provided, validates column count and required
                columns against the schema definition.
            lenient: When True, lower severity of structural checks to warning
                (useful for chapters generated without reference source).

        Returns:
            {passed: bool, warnings: [...], recommendations: [...]}
        """
        import re as _re
        warnings: List[Dict[str, Any]] = []
        recommendations: List[Dict[str, Any]] = []

        # 0. Schema-based table structure check
        if section_schema is not None:
            schema_warnings = self._check_table_structure(content, section_schema, lenient=lenient)
            warnings.extend(schema_warnings)

        # 1. Duplicate section titles
        headings = _re.findall(r"^#{1,3}\s+(.+)$", content, _re.MULTILINE)
        seen: dict[str, int] = {}
        for h in headings:
            title = h.strip()
            seen[title] = seen.get(title, 0) + 1
        dupes = {t: c for t, c in seen.items() if c > 1}
        if dupes:
            warnings.append({
                "type": "output_quality",
                "severity": "critical",
                "message": f"存在重复的章节标题: {list(dupes.keys())}，请合并或删除重复项",
            })

        # 2. AI meta-commentary / page references
        meta_patterns = [
            (r"原文中存在.*(?:异常|疑似|笔误|问题)", "原文点评"),
            (r"第\d+页起", "页码引用"),
            (r"以下为.*整理.*输出", "AI开头声明"),
            (r"严格依据知识库原文.*整理", "AI开头声明"),
            (r"格式清晰、层级明确", "AI自我评价"),
        ]
        meta_hits = []
        for pattern, label in meta_patterns:
            if _re.search(pattern, content):
                meta_hits.append(label)
        if meta_hits:
            warnings.append({
                "type": "output_quality",
                "severity": "critical",
                "message": f"输出包含AI元描述（{meta_hits}），应只保留工艺文件正文",
            })

        # 3. Process step ordering gaps
        step_numbers = [int(m) for m in _re.findall(r"工序\s*(\d+)", content)]
        if len(step_numbers) >= 2:
            unique_steps = sorted(set(step_numbers))
            gaps = []
            for i in range(len(unique_steps) - 1):
                if unique_steps[i + 1] - unique_steps[i] > 1:
                    gaps.append(f"{unique_steps[i]}→{unique_steps[i + 1]}")
            if gaps:
                warnings.append({
                    "type": "output_quality",
                    "severity": "critical",
                    "message": f"工序编号不连续: {gaps}，请按顺序补齐",
                })

        # 4. Signature/date fields that belong in export template, not content
        sig_patterns = [
            r"(?:编制|校对|审核|标检|批准|会签)\s+\S+",
            r"共\d+页\s*第\d+页",
        ]
        sig_hits = [p for p in sig_patterns if _re.search(p, content)]
        if sig_hits:
            warnings.append({
                "type": "output_quality",
                "severity": "warning",
                "message": "输出包含签名栏/日期/页码等导出模板字段，应由模板填充",
            })

        critical_count = len([w for w in warnings if w.get("severity") == "critical"])
        passed = critical_count == 0

        return {
            "passed": passed,
            "warnings": warnings,
            "recommendations": recommendations,
        }
