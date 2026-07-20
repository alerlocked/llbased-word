"""
撰写 Agent

负责工艺内容的编辑、表格填充、格式调整

集成 Search Agent 进行统一检索
支持用户反馈和多轮修改
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from app.agents.base_agent import BaseAgent
from app.agents.core import AgentRegistry
from app.shared.logging import get_logger

logger = get_logger(__name__)


class FeedbackType(str, Enum):
    """用户反馈类型"""
    ACCEPT = "accept"
    MODIFY = "modify"
    REJECT = "reject"


@dataclass
class UserFeedback:
    """用户反馈"""
    type: FeedbackType
    content: str = ""
    suggestions: List[str] = field(default_factory=list)


@dataclass
class VersionHistory:
    """版本历史"""
    version: int
    content: str
    timestamp: float
    feedback: Optional[UserFeedback] = None


@AgentRegistry.register("writing")
class WritingAgent(BaseAgent):
    """
    撰写 Agent

    职责：
    - 工艺内容编辑
    - 表格填充
    - 格式调整
    - 多轮修改支持

    使用 Search Agent 进行统一检索
    """

    name = "writing"
    description = "负责工艺内容的编辑、表格填充、格式调整"
    tools = []  # document_generator 已清理（被 _do_template_fill 取代）；rag_retriever 用 Search Agent

    # 支持的动作类型
    ACTION_TYPES = ["edit", "fill", "format", "generate"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化撰写 Agent

        Args:
            config: 配置参数
        """
        super().__init__(config)

        # 撰写相关配置
        self.default_format = self.config.get("default_format", "html")
        self.max_retrieval_results = self.config.get("max_retrieval_results", 5)

        # Dynamic writing preferences (loaded per session)
        self._writing_preferences: Optional["WritingPreferences"] = None
        # Full domain profile (强约束 principles + 参考值 triples), loaded per
        # session for chapter prompts that need standards / reference values.
        self._profile: Optional["Profile"] = None

        # 版本历史（用于多轮修改）
        self._version_history: List[VersionHistory] = []
        self._current_version = 0

    async def process(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理撰写任务

        Args:
            task: 任务描述
                - action: 动作类型 (edit/fill/format/generate)
                - target: 目标对象（表格/段落标识）
                - content: 编辑内容
                - requirements: 要求描述
            context: 执行上下文

        Returns:
            {
                "success": bool,
                "result": Any,
                "document": Dict,
                "suggestions": List[str]
            }
        """
        try:
            action = task.get("action", "edit")

            if action not in self.ACTION_TYPES:
                return {
                    "success": False,
                    "error": f"不支持的动作类型: {action}",
                    "error_code": "INVALID_ACTION"
                }

            # 1. Use pre-loaded context if available (skip re-search)
            knowledge = None
            preloaded_content = task.get("retrieved_context") or task.get("chapter_source_text")
            if task.get("skip_planning") and preloaded_content:
                # Context already provided by orchestrator
                knowledge = {
                    "success": True,
                    "results": [{"content": preloaded_content, "source": "orchestrator", "score": 1.0}],
                    "total": 1,
                }
            elif task.get("requirements"):
                knowledge = await self._search_knowledge(
                    task["requirements"],
                    task.get("search_mode", "comprehensive")
                )

            # 2. 根据动作类型执行
            if action == "edit":
                result = await self._do_edit(task, knowledge, context)
            elif action == "fill":
                result = await self._do_fill(task, knowledge, context)
            elif action == "format":
                result = await self._do_format(task, context)
            elif action == "generate":
                result = await self._do_generate(task, knowledge, context)
            else:
                result = {"success": False, "error": f"未知动作: {action}"}

            if not result.get("success"):
                return result

            logger.info(
                "writing_task_completed",
                action=action,
                target=task.get("target", ""),
            )

            return {
                "success": True,
                "result": result,
                "suggestions": result.get("suggestions", [])
            }

        except Exception as e:
            logger.error("writing_task_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "error_code": "WRITING_FAILED"
            }

    async def _do_edit(
        self,
        task: Dict[str, Any],
        knowledge: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        执行编辑操作

        Args:
            task: 任务描述
            knowledge: 检索到的知识
            context: 执行上下文

        Returns:
            编辑结果
        """
        target = task.get("target", "")
        content = task.get("content", "")
        requirements = task.get("requirements", "")

        # Build knowledge context from search results
        knowledge_context = ""
        if knowledge and knowledge.get("success"):
            results = knowledge.get("results", [])
            knowledge_context = "\n".join([
                r.get("content", "") for r in results[:3]
            ])

        # Inject knowledge catalog (materials/tools/standards)
        catalog_context = self._get_knowledge_catalog_context(requirements or content)

        # Call LLM for actual editing
        from app.services.llm_service import llm_service

        system_msg = (
            "你是一位专业的工艺文件编辑助手。请根据用户要求编辑以下工艺内容，"
            "保持工艺术语的准确性和规范性。直接输出编辑后的内容，不要包含解释。"
        )
        if self._writing_preferences:
            system_msg += self._get_preference_prompt_fragment()

        user_parts = [f"请编辑以下内容"]
        if requirements:
            user_parts.append(f"编辑要求：{requirements}")
        user_parts.append(f"原文：\n{content}")
        if knowledge_context:
            user_parts.append(f"参考依据：\n{knowledge_context[:800]}")
        if catalog_context:
            user_parts.append(f"物料与标准参考：\n{catalog_context[:1000]}")

        result = await llm_service.generate_with_messages(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": "\n\n".join(user_parts)},
            ],
            temperature=0.5,
            max_tokens=3000,
            tier="complex",
        )

        if result["status"] == "error":
            return {"success": False, "error": result.get("error", "LLM调用失败")}

        edited_content = result["content"]

        # Post-generation guardrail: run universal checks on output
        guardrail_warnings = self._quick_check_output(edited_content)

        self._save_version(edited_content)

        return {
            "success": True,
            "content": edited_content,
            "target": target,
            "suggestions": ["建议检查术语一致性", "建议添加工艺参数"],
            "guardrail_warnings": guardrail_warnings,
        }

    async def _do_fill(
        self,
        task: Dict[str, Any],
        knowledge: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        执行表格填充

        Args:
            task: 任务描述
            knowledge: 检索到的知识
            context: 执行上下文

        Returns:
            填充结果
        """
        target = task.get("target", "")
        fields = task.get("fields", [])

        # Collect knowledge snippets for LLM context
        knowledge_context = ""
        if knowledge and knowledge.get("success"):
            results = knowledge.get("results", [])
            knowledge_context = "\n".join([
                r.get("content", "") for r in results[:3]
            ])

        from app.services.llm_service import llm_service

        system_msg = (
            "你是一位专业的工艺文件编写助手。请根据提供的参考知识，"
            "为工艺表格中的字段填写准确的工艺参数。"
            "直接输出 JSON 格式：{\"field1\": \"value1\", \"field2\": \"value2\"}"
        )

        user_parts = [f"请为以下表格字段填写内容：{', '.join(fields)}"]
        if target:
            user_parts.append(f"表格名称：{target}")
        if knowledge_context:
            user_parts.append(f"参考知识：\n{knowledge_context[:800]}")

        result = await llm_service.generate_with_messages(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": "\n\n".join(user_parts)},
            ],
            temperature=0.3,
            max_tokens=1500,
            tier="complex",
        )

        filled_data = {}
        if result["status"] == "success":
            import json
            try:
                text = result["content"].strip()
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                filled_data = json.loads(text.strip())
            except (json.JSONDecodeError, IndexError):
                # LLM didn't return valid JSON, return empty
                logger.warning("fill_json_parse_failed", raw=result["content"][:200])

        unfilled = [f for f in fields if f not in filled_data]

        return {
            "success": True,
            "content": f"表格 {target} 填充完成",
            "filled_data": filled_data,
            "unfilled_fields": unfilled,
        }

    async def _do_format(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        执行格式调整

        Args:
            task: 任务描述
            context: 执行上下文

        Returns:
            格式调整结果
        """
        content = task.get("content", "")
        format_rules = task.get("format_rules", [])

        if not content:
            return {"success": False, "error": "格式化内容不能为空"}

        from app.services.llm_service import llm_service

        rules_text = "\n".join(f"- {r}" for r in format_rules) if format_rules else "- 统一为标准工艺文件格式"

        system_msg = (
            "你是一位工艺文件格式化专家。请按照指定的格式规则调整工艺文档内容。"
            "保持内容不变，只调整格式、标点、编号、缩进等。直接输出格式化后的内容。"
        )
        if self._writing_preferences:
            system_msg += self._get_preference_prompt_fragment()

        result = await llm_service.generate_with_messages(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"格式规则：\n{rules_text}\n\n原文：\n{content}"},
            ],
            temperature=0.3,
            max_tokens=3000,
            tier="complex",
        )

        if result["status"] == "error":
            return {"success": False, "error": result.get("error", "LLM调用失败")}

        return {
            "success": True,
            "content": result["content"],
            "applied_rules": format_rules,
        }

    async def _do_generate(
        self,
        task: Dict[str, Any],
        knowledge: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        生成新内容 with Planning/CoT decomposition.

        For complex generation tasks, first asks LLM to produce a writing
        plan, then uses that plan to guide content generation.

        When task contains `skip_planning=True` and pre-loaded context
        (from orchestrator), skips the planning phase and uses the
        provided context directly.

        When task contains `template_slots`, routes to _do_template_fill
        for structured JSON output instead of free Markdown.

        Args:
            task: 任务描述
            knowledge: 检索到的知识
            context: 执行上下文

        Returns:
            生成结果
        """
        # Template-driven fill route: structured JSON output
        if task.get("template_slots"):
            return await self._do_template_fill(task, knowledge, context)

        requirements = task.get("requirements", "")
        template = task.get("template", "standard")

        knowledge_context = ""
        if knowledge and knowledge.get("success"):
            results = knowledge.get("results", [])
            if results:
                knowledge_context = "\n".join([
                    r.get("content", "") for r in results[:3]
                ])

        from app.services.llm_service import llm_service

        template_guides = {
            "standard": "使用标准工艺文件格式：标题、适用范围、引用标准、工艺流程、检验要求",
            "assembly": "使用装配工艺规程格式：标题、范围、引用标准、装配流程表、检验要求",
            "welding": "使用焊接工艺规程格式：标题、母材信息、焊接参数表、质量检验、安全要求",
            "inspection": "使用检验工艺规程格式：标题、检验项目表、判定标准、检验设备清单",
        }

        # Structure rules per template type (condition-based, not hardcoded into every prompt)
        structure_rules_map = {
            "assembly": (
                "\n\n## 结构规范（必须遵守）\n"
                "### 编号体系\n"
                "- 工序号: 1, 2, 3...（对应工艺流程图顺序，不可跳号或混编）\n"
                "- 工步号: 工序号.子序号（如 1.1, 1.2, 2.1, 2.2）\n"
                "- 子项: 工步号.子序号（如 1.2.1, 1.2.2）\n"
                "- 检验项: 1) 2) 3)...（紧跟在工序全部工步之后）\n"
                "- 用户未指定编号时，默认按流程顺序编号\n\n"
                "### 装配工艺卡片每个工序的结构\n"
                "工序号N → N.1工步(辅助材料|仪器装备) → N.2工步 → ... → 检验(1)2)3))\n\n"
                "### 关键规则\n"
                "1. 辅料和工具归属到具体工步右侧，不是独立段落\n"
                "2. 检验紧跟在工序全部工步之后，不在其他位置散落\n"
                "3. 工序间不交叉：工序1全部内容(含检验)完毕后才开始工序2\n"
                "4. 工艺流程图中每个工序在装配工艺卡片中都要有对应展开\n"
                "5. 工序必须连续输出：1→2→3→...→N，禁止跳过任何工序号\n"
                "6. 如果知识库原文只包含部分工序，仍按工艺流程图的顺序列出所有工序，"
                "有原文的工序列出详细内容，无原文的工序列出工序号+名称+简要说明\n"
            ),
            # "welding": "焊接结构规范...",   # TODO: add when needed
            # "inspection": "检验结构规范...",
        }
        structure_rules = structure_rules_map.get(template, "")

        format_guide = template_guides.get(template, template_guides["standard"])

        # Check for pre-loaded context from orchestrator (skip planning)
        chapter_source_text = task.get("chapter_source_text", "")
        has_preloaded = task.get("skip_planning") and (
            task.get("retrieved_context") or chapter_source_text
        )

        if has_preloaded:
            # Direct generation with orchestrator-provided context
            retrieved_ctx = task.get("retrieved_context", "")
            draft_ctx = task.get("draft_content", "")
            mod_plan = task.get("modification_plan", "")
            material_instr = task.get("material_instruction", "")
            module_name = task.get("module_name", "")
            module_instruction = task.get("module_instruction", "")
            section_schema = task.get("section_schema")  # SectionSchema dataclass or None
            retry_context = task.get("retry_context", "")

            # Single-module focus mode: only output content for this one module
            if module_name:
                # Use chapter source text when available, fallback to retrieved_context
                source_text = chapter_source_text or retrieved_ctx
                source_label = "知识库参考文档" if chapter_source_text else "知识库完整文档"
                has_source = bool(source_text and source_text.strip())

                # Build schema constraint if available
                schema_instruction = ""
                if section_schema:
                    from app.services.section_schemas import build_schema_prompt
                    schema_instruction = build_schema_prompt(section_schema)

                system_msg = (
                    f"你是一位专业的工艺文件编写助手。任务：生成「{module_name}」模块的完整内容。\n\n"
                    "工作方法：\n"
                )
                if has_source:
                    system_msg += (
                        "这是生成系统，不是摘抄系统。参考文档仅用于格式和术语。\n\n"
                        f"1. 参考「{source_label}」的格式和术语体系，根据工艺要求生成内容\n"
                        "2. 关键参数（代号、材料牌号、公差等）必须准确，参考文档中有的直接使用\n"
                        "3. 描述性文字用自己的语言组织，不要直接复制原文段落\n"
                        "4. 必须排除噪声内容：签名栏（及人名）、日期戳、页码、更改单号、续表标记\n"
                        "5. 不要把 PDF 表头文字（产品工号、车间、准结等）当作数据输出\n\n"
                    )
                else:
                    system_msg += (
                        "1. 根据工艺文件的标准结构生成该章节内容\n"
                        "2. 参考已有章节的格式、术语和参数风格，保持全文一致\n"
                        "3. 如果能从上下文推断出相关参数，直接使用；不确定的用 [待确认] 标注\n"
                        "4. 内容要详实具体，不要写空泛的描述\n\n"
                    )

                system_msg += (
                    "输出规则（必须遵守）：\n"
                    f"- 只输出「{module_name}」模块的内容\n"
                    "- 不要输出章节大标题（如「{module_name}」），外部已经提供\n"
                    "- 直接从内容开始输出（如表格、工步描述等）\n"
                    "- 不要输出分析过程、推理说明、依据标注、来源说明\n"
                    "- 不要输出页码引用（如「第19页起」）\n"
                    "- 不要对原文内容进行点评（如「疑似笔误」「原文中存在异常」等）\n"
                    "- 不要使用 ✅ ❌ ⚠️ 🔹 等标记符号\n"
                    "- 表格数据使用标准 Markdown 表格格式：表头行 | 分隔行(|---|---|) | 数据行，每列用 | 分隔，不要用空格对齐\n"
                    "- 非表格的工步/工序内容使用清晰的分条格式\n"
                    "- 工序必须严格按编号顺序输出：1, 2, 3... 不允许跳跃或乱序\n"
                    "- 跳过签名栏、日期栏（编制/校对/审核/标检/批准），这些在导出时由模板填充\n"
                    "- 跳过空白行、空行占位符\n"
                    "- 不要添加[待确认]标记（除非确实无法确定具体参数）\n"
                    "- 输出就是该模块的最终内容，不是内部草稿"
                    + structure_rules
                    + schema_instruction
                )
                if self._writing_preferences:
                    system_msg += self._get_preference_prompt_fragment()

                user_parts = [f"## 生成指令\n{module_instruction}"]
                if material_instr:
                    user_parts.append(material_instr)
                if source_text:
                    user_parts.append(
                        f"## {source_label}（仅供参考，作为格式和术语参考，不要照抄原文）\n{source_text}"
                    )

                # Retry: include previous output as assistant message + correction as new user message
                if retry_context:
                    messages = [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": "\n\n".join(user_parts)},
                        {"role": "assistant", "content": retry_context},
                        {"role": "user", "content": module_instruction},
                    ]
                else:
                    messages = [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": "\n\n".join(user_parts)},
                    ]

                result = await llm_service.generate_with_messages(
                    messages=messages,
                    temperature=0.3,
                    max_tokens=8000,
                    tier="complex",
                )

                if result["status"] == "error":
                    return {"success": False, "error": result.get("error", "LLM调用失败")}

                content = result["content"]
                guardrail_warnings = self._quick_check_output(content)
                self._save_version(content)

                return {
                    "success": True,
                    "content": content,
                    "template": template,
                    "guardrail_warnings": guardrail_warnings,
                }

            # Full-document generation mode (original logic)
            system_msg = (
                "你是一位专业的工艺文件编写助手。任务：根据知识库中的完整文档，补齐用户上传的不完整工艺文件。\n\n"
                "工作方法：\n"
                "1. 以「用户初稿」为基础框架，保留所有已有内容\n"
                "2. 对比「知识库完整文档」，逐模块补充缺失内容\n"
                "3. 如果知识库有对应内容，直接引用或改编（不要自己编造参数）\n"
                "4. 严格基于知识库原文输出，不要遗漏已有的参数和数据\n\n"
                "输出规则（必须遵守）：\n"
                "- 直接输出完整工艺文件内容，不要输出分析过程、推理说明、依据标注\n"
                "- 不要使用 ✅ ❌ ⚠️ 🔹 等标记符号\n"
                "- 不要写「依据来源」「缺失说明」「本次修订严格遵循」等元描述\n"
                "- 不要对原文内容进行点评（如「疑似笔误」「原文中存在异常」等）\n"
                "- 不要输出页码引用（如「第19页起」）\n"
                "- 不要添加[待确认]标记，所有内容直接基于原文输出\n"
                "- 保持原文档的章节结构和编号体系\n"
                "- 工序必须严格按编号顺序输出：1, 2, 3... 不允许跳跃或乱序\n"
                "- 不要重复用户初稿中已有的章节标题，只补充缺失的章节内容\n"
                "- 跳过签名栏、日期栏（编制/校对/审核/标检/批准及日期），这些在导出时由模板填充\n"
                "- 使用标准 Markdown 表格格式：表头行 | 分隔行(|---|---|) | 数据行，每列用 | 分隔\n"
                "- 输出就是最终给用户看的完整文件，不是内部草稿"
                + structure_rules
            )
            if self._writing_preferences:
                system_msg += self._get_preference_prompt_fragment()

            user_parts = []
            if mod_plan:
                user_parts.append(f"## 修改方案\n{mod_plan}")
            user_parts.append(f"## 任务要求\n{requirements}")
            if material_instr:
                user_parts.append(material_instr)
            if retrieved_ctx:
                user_parts.append(f"## 知识库完整文档（优先参考此内容补充）\n{retrieved_ctx}")
            if draft_ctx:
                user_parts.append(f"## 用户初稿（在此基础上补充，保留已有内容）\n{draft_ctx}")

            # Multi-pass generation for long documents
            # A 53-page process doc (~30000 chars) exceeds single-call output limits.
            # Generate in passes, each continuing from where the previous left off.
            all_content = ""
            max_passes = 5
            user_msg = "\n\n".join(user_parts)

            for pass_num in range(max_passes):
                if pass_num > 0:
                    # Continuation pass: show the tail of previous output
                    tail = all_content[-1500:] if len(all_content) > 1500 else all_content
                    user_msg = (
                        f"以下是之前已生成的内容尾部：\n\n---\n{tail}\n---\n\n"
                        "请从上面的断点处继续生成，不要重复已有内容。"
                    )

                result = await llm_service.generate_with_messages(
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.3,
                    max_tokens=8000,
                    tier="complex",
                )

                if result["status"] == "error":
                    # If we already have some content from previous passes, return it
                    if all_content:
                        break
                    return {"success": False, "error": result.get("error", "LLM调用失败")}

                chunk = result["content"]
                if pass_num == 0:
                    all_content = chunk
                else:
                    all_content += "\n" + chunk

                logger.info(
                    "multi_pass_generation",
                    pass_num=pass_num + 1,
                    chunk_len=len(chunk),
                    total_len=len(all_content),
                )

                # Check if generation looks complete
                if self._looks_complete(all_content):
                    break

                # If chunk is short (< 2000 chars), model likely finished
                if len(chunk) < 2000:
                    break

            guardrail_warnings = self._quick_check_output(all_content)
            self._save_version(all_content)

            return {
                "success": True,
                "content": all_content,
                "template": template,
                "guardrail_warnings": guardrail_warnings,
            }

        # Standard flow: planning then generation
        # Phase 1: Planning — generate a structured writing plan via CoT
        plan = await self._generate_writing_plan(
            requirements=requirements,
            format_guide=format_guide,
            knowledge_context=knowledge_context,
            context=context,
        )

        # Phase 2: Execution — generate content guided by the plan
        system_msg = (
            "你是一位专业的工艺文件编写助手。请严格按照给定的写作计划，"
            "逐步生成工艺文件的每个章节内容。\n\n"
            f"格式要求：{format_guide}\n\n"
            "输出规则（必须遵守）：\n"
            "- 直接输出工艺文件内容，不要输出任何分析过程、推理说明、依据标注\n"
            "- 不要使用 ✅ ❌ ⚠️ 🔹 等标记符号\n"
            "- 不要写「依据来源」「缺失说明」「本次修订严格遵循」等元描述\n"
            "- 不要添加[待确认]标记，严格基于原文输出\n"
            "- 输出就是最终给用户看的文件，不是内部草稿"
        )
        if self._writing_preferences:
            system_msg += self._get_preference_prompt_fragment()

        user_parts = [f"## 写作计划\n{plan}\n\n## 用户要求\n{requirements}"]
        if knowledge_context:
            user_parts.append(f"参考知识：\n{knowledge_context[:3000]}")
        if context:
            doc_context = context.get("document_context", "")
            if doc_context:
                user_parts.append(f"当前文档上下文：\n{doc_context[:500]}")

        result = await llm_service.generate_with_messages(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": "\n\n".join(user_parts)},
            ],
            temperature=0.5,
            max_tokens=4000,
            tier="complex",
        )

        if result["status"] == "error":
            return {"success": False, "error": result.get("error", "LLM调用失败")}

        generated_content = result["content"]
        guardrail_warnings = self._quick_check_output(generated_content)
        self._save_version(generated_content)

        return {
            "success": True,
            "content": generated_content,
            "template": template,
            "plan": plan,
            "guardrail_warnings": guardrail_warnings,
        }

    async def _do_template_fill(
        self,
        task: Dict[str, Any],
        knowledge: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Fill template slots with slot-based structured + unstructured output.

        Flow:
          1. Group columns by fill_type (structured / unstructured)
          2. Extract structured fields from source text (no LLM)
          3. Send only unstructured slots to LLM
          4. Merge structured + unstructured into final rows

        Args:
            task: Must contain template_slots, chapter_code, chapter_type.
            knowledge: Pre-loaded knowledge context.
            context: Execution context.

        Returns:
            {"success": True, "filled_data": [...], "chapter_code": "...",
             "fill_sources": {...}}
        """
        import json as _json

        from app.services.template_types import TemplateColumn, ChapterData
        from app.services.template_loader import get_columns_by_fill_type
        from app.services.structured_extractor import (
            extract_structured_fields,
            merge_structured_with_unstructured,
            _filter_noise_rows,
        )

        chapter_code = task.get("chapter_code", "")
        chapter_type = task.get("chapter_type", "single_row_list")
        template_slots = task.get("template_slots", [])
        chapter_source_text = task.get("chapter_source_text", "")
        ai_guidance = task.get("ai_guidance", "")

        # Build knowledge context
        knowledge_context = ""
        if knowledge and knowledge.get("success"):
            results = knowledge.get("results", [])
            knowledge_context = "\n".join(r.get("content", "") for r in results[:3])

        # Also accept pre-loaded context
        if chapter_source_text:
            knowledge_context = chapter_source_text

        # --- Step 1: Classify columns by fill_type ---
        slot_cols = [TemplateColumn.from_dict(s) for s in template_slots]
        grouped = _group_slots_by_fill_type(slot_cols)
        structured_cols: List[TemplateColumn] = grouped["structured"]
        unstructured_cols: List[TemplateColumn] = grouped["unstructured"]

        fill_sources = {
            "structured": [c.key for c in structured_cols],
            "unstructured": [c.key for c in unstructured_cols],
        }

        # --- Step 2: Extract structured fields from source ---
        structured_values: Dict[str, List[str]] = {}
        if structured_cols and knowledge_context:
            structured_values = extract_structured_fields(
                chapter_code=chapter_code,
                structured_cols=structured_cols,
                source_text=knowledge_context,
            )

        # Determine row count from structured extraction
        struct_row_count = 0
        if structured_values:
            struct_row_count = max(
                (len(v) for v in structured_values.values()), default=0
            )

        # --- Step 3: Generate unstructured fields via LLM ---
        from app.services.llm_service import llm_service

        unstructured_slots: List[Dict[str, Any]] = []
        llm_row_count = 0
        parsed = None

        # Extract inherited context early for prompt injection
        inherited = task.get("inherited_context") or task.get("params", {}).get("inherited_context")

        # G22a 工艺过程卡: step_name (工序名称) is the work-type category
        # (钳/机/etc) — structured-extracted from source, default "钳". Do NOT
        # override it with G19a flow-step names; those belong in step_desc
        # (工序内容简述), which the LLM fills below using inherited step_names.
        # G22a row count is still driven by max_rows (工序数, one row per step).

        # --- G25a: source-driven generation (real substeps, no fabrication) ---
        # The orchestrator injects assembly_steps (per-step substeps extracted
        # from the source G25a chapter) + skeleton_steps (G19a step names).
        # We direct-fill structured columns from source and feed the substep
        # text to the LLM as the single source of truth for content.
        _assembly = task.get("assembly_steps") or task.get("params", {}).get("assembly_steps")
        _skeleton = (task.get("skeleton_steps") or task.get("params", {}).get("skeleton_steps")
                     or (inherited or {}).get("step_names", []))
        # G25a 装配卡适用范围说明 (章节级背景, 来自源文档说明区, 非臆造).
        # 仅注入 system_msg 作为背景前缀, 不写入任何工序 content.
        _assembly_overview = task.get("assembly_overview") or task.get("params", {}).get("assembly_overview")
        is_g25a_sourced = chapter_code == "G25a" and bool(_assembly)
        g25a_source_block = ""
        g25a_skeleton_block = ""
        if is_g25a_sourced:
            asm: Dict[int, Dict[str, Any]] = {}
            for _k, _v in _assembly.items():
                try:
                    asm[int(_k)] = _v
                except (ValueError, TypeError):
                    continue
            skel = list(_skeleton) if _skeleton else [asm[k]["name"] for k in sorted(asm)]
            n = len(skel)
            # Direct-fill structured columns from source (zero fabrication)
            structured_values["step_no"] = [str(i + 1) for i in range(n)]
            # step_name (工序名称) is the work-type category (钳/机), NOT the
            # G19a flow step name. extract_assembly_steps already captured it
            # per step (asm[k]["name"]); use that instead of skeleton so the
            # 工序名称 column shows 钳, while skeleton only drives row count
            # and the 工序内容 prompt below.
            structured_values["step_name"] = [asm.get(k, {}).get("name", "钳") for k in sorted(asm)]
            _aux: List[str] = []
            _instr: List[str] = []
            _src_lines: List[str] = []
            for i in range(1, n + 1):
                name = skel[i - 1] if i - 1 < len(skel) else ""
                step = asm.get(i)
                subs = step.get("substeps", []) if step else []
                mats = sorted({s.get("material", "") for s in subs if s.get("material")})
                _aux.append("、".join(mats) if mats else "")
                instrs = sorted({s.get("instruments", "") for s in subs if s.get("instruments")})
                _instr.append("、".join(instrs) if instrs else "")
                sub_text = "\n".join(
                    f"  {s.get('content', '')}" + (f" | 辅材:{s.get('material')}" if s.get("material") else "")
                    for s in subs
                )
                _src_lines.append(f"工序{i}（{name}）：\n{sub_text if sub_text else '  （原文未提供）'}")
            structured_values["aux_materials"] = _aux
            structured_values["instruments"] = _instr
            struct_row_count = n
            g25a_source_block = "\n".join(_src_lines)
            g25a_skeleton_block = "\n".join(f"{i + 1}. {nm}" for i, nm in enumerate(skel))

        # --- G22a: source-driven 工序名称 + 工序内容简述 (extract 直填, 不交 LLM) ---
        _card_steps = task.get("process_card_steps") or task.get("params", {}).get("process_card_steps")
        if chapter_code == "G22a" and _card_steps:
            cs: Dict[int, Dict[str, str]] = {}
            for _k, _v in _card_steps.items():
                try:
                    cs[int(_k)] = _v
                except (ValueError, TypeError):
                    continue
            if cs:
                ordered = sorted(cs)
                structured_values["step_no"] = [str(i) for i in ordered]
                structured_values["step_name"] = [cs[k].get("step_name", "钳") for k in ordered]
                structured_values["step_desc"] = [cs[k].get("step_desc", "") for k in ordered]
                struct_row_count = len(ordered)
                # step_desc is direct-filled from source; drop it from
                # unstructured so the LLM doesn't fabricate 工业话术.
                unstructured_cols = [c for c in unstructured_cols if c.key != "step_desc"]

        # --- G5a: source-driven 引(借)用文件目录 (extract 直填, 不交 LLM) ---
        _file_refs = task.get("file_references") or task.get("params", {}).get("file_references")
        if chapter_code == "G5a" and _file_refs:
            structured_values["seq"] = [str(r.get("seq", "")) for r in _file_refs]
            structured_values["ref_code"] = [r.get("ref_code", "") for r in _file_refs]
            structured_values["ref_name"] = [r.get("ref_name", "") for r in _file_refs]
            structured_values["pages"] = [str(r.get("pages", "")) for r in _file_refs]
            structured_values["remarks"] = [r.get("remarks", "") for r in _file_refs]
            struct_row_count = len(_file_refs)
            # ref_name direct-filled from source; drop it from unstructured so
            # the LLM doesn't fabricate part names into the 文件名称 column.
            unstructured_cols = [c for c in unstructured_cols if c.key != "ref_name"]

        # --- G4a: source-driven 工艺文件目录 (extract 直填, 不交 LLM) ---
        _doc_catalog = task.get("doc_catalog") or task.get("params", {}).get("doc_catalog")
        if chapter_code == "G4a" and _doc_catalog:
            structured_values["seq"] = [str(r.get("seq", "")) for r in _doc_catalog]
            structured_values["doc_name"] = [r.get("doc_name", "") for r in _doc_catalog]
            structured_values["doc_number"] = [r.get("doc_number", "") for r in _doc_catalog]
            structured_values["component_code"] = [r.get("component_code", "") for r in _doc_catalog]
            structured_values["component_name"] = [r.get("component_name", "") for r in _doc_catalog]
            structured_values["pages"] = [str(r.get("pages", "")) for r in _doc_catalog]
            structured_values["volume"] = [r.get("volume", "") for r in _doc_catalog]
            structured_values["remarks"] = [r.get("remarks", "") for r in _doc_catalog]
            struct_row_count = len(_doc_catalog)
            # doc_name direct-filled from source; drop it from unstructured so
            # the LLM doesn't fabricate chapter names into the 文件名称 column.
            unstructured_cols = [c for c in unstructured_cols if c.key != "doc_name"]

        if unstructured_cols:
            slot_desc = ", ".join(
                f'"{c.key}"({c.label})' for c in unstructured_cols
            )

            # Build full table schema context so LLM sees the whole picture
            schema_lines = []
            for c in slot_cols:
                if c.fill_type == "structured":
                    status = "✅ 系统已提取"
                else:
                    status = "📝 你需要生成"
                schema_lines.append(f"  {c.key} | {c.label} | {c.col_type} | {status}")
            schema_block = (
                f"## 表格完整结构\n"
                f"章节：{task.get('chapter_title', '')} ({chapter_code})\n"
                f"表格类型：{chapter_type}\n\n"
                f"| 列key | 列标题 | 类型 | 状态 |\n"
                f"|-------|--------|------|------|\n"
                + "\n".join(schema_lines) + "\n\n"
                f"你只需要生成标记为「📝 你需要生成」的列。不要生成标记为「✅ 系统已提取」的列。\n"
            )

            # Build inherited context block (process flow steps from Phase 1)
            inherited_block = ""
            if inherited:
                step_names = inherited.get("step_names", [])
                max_rows = inherited.get("max_rows")
                if step_names:
                    step_list = "\n".join(
                        f"  {i+1}. {name}" for i, name in enumerate(step_names)
                    )
                    inherited_block = (
                        f"\n## 工艺流程步骤（必须严格对应）\n"
                        f"Phase 1 已确定以下 {len(step_names)} 道工序步骤，"
                        f"你的生成必须按此顺序逐行对应：\n{step_list}\n"
                        f"每行的工序号和工序名称必须与上述列表一致，不要自行编造或更改。\n"
                    )
                if max_rows:
                    inherited_block += (
                        f"\n行数约束：必须恰好生成 {max_rows} 行，与工艺流程步骤一一对应。\n"
                    )

            row_hint = ""
            if struct_row_count > 0:
                row_hint = f"参考文档中共有 {struct_row_count} 道工序/条目，请为每道工序/条目都生成内容。\n"

            if chapter_type == "process_card":
                fill_instruction = (
                    f"输出格式：JSON 数组，每个元素包含 row（行号，从1开始）、slot（列key）、value（值）三个字段。\n"
                    f"需要生成内容的列：{slot_desc}\n"
                    f"{row_hint}"
                    f"示例：[{{\"row\": 1, \"slot\": \"content\", \"value\": \"详细工序描述...\"}}, "
                    f"{{\"row\": 1, \"slot\": \"inspection\", \"value\": \"检查要点...\"}}]\n"
                )
            elif chapter_type == "single_row_list":
                fill_instruction = (
                    f"输出格式：JSON 数组，每个元素包含 row、slot、value。\n"
                    f"需要生成内容的列：{slot_desc}\n"
                    f"{row_hint}"
                )
            else:
                fill_instruction = (
                    f"输出格式：JSON 数组，每个元素包含 row、slot、value。\n"
                    f"字段：{slot_desc}\n"
                )

            system_msg = (
                "你是一位专业的航天工艺文件编写助手。你的任务是为指定的表格位置生成内容。\n"
                "这是生成系统，不是摘抄系统——参考文档仅用于了解格式和术语，不要照搬原文。\n\n"
                f"{schema_block}\n"
                f"章节代码：{chapter_code}\n"
                f"章节标题：{task.get('chapter_title', '')}\n"
                f"表格类型：{chapter_type}\n"
                f"{fill_instruction}\n"
                f"{inherited_block}\n"
                "硬约束：\n"
                "- 只输出 JSON 数组\n"
                "- 不要使用 ```json``` 代码块包裹\n"
                "- 每一行/每一个条目都必须是完整的\n"
                "- 关键参数（代号、材料牌号等）必须准确，参考文档中有的直接使用\n"
                "- 描述性内容用自己的语言组织\n"
                "- 必须排除以下噪声（它们是文档元数据，不是工艺数据）：\n"
                "  · 签名栏及人名（编制/校对/审核/标检/批准，以及具体人名）\n"
                "  · 日期戳（如 20240828）\n"
                "  · 页码、页数、更改单号\n"
                "  · 续表标记（如'XX(续)'、'XX序'）\n"
                "  · 表头文字（如'产品工号'、'车间'、'准结'出现在数据字段中）\n"
                "  · 产品型号/图号作为占位符出现在非对应字段中\n"
                "  · 其他章节的标题（如'工艺过程卡'不应出现在目录中）\n"
            )
            # G25a: override the generic "don't copy source" prompt — this
            # chapter must stay faithful to the extracted substep text.
            # Profile two layers: principles (强约束) + triples (参考值兜底).
            # 全章节注入（profile-expand-and-relations 节点4：移出 G25a-only gate，
            # 因 principles/triples 是章节无关的行文约束 + 参考值）.
            if self._profile:
                _enabled = [
                    p for p in (getattr(self._profile, "principles", []) or [])
                    if p.get("enabled", True)
                ]
                if _enabled:
                    _ptxt = "\n".join(
                        f"- {p.get('name', '')}: {p.get('description', '')}"
                        for p in _enabled
                    )
                    system_msg += f"\n## 画像强约束（必须遵守）\n{_ptxt}\n"
                _triples = getattr(self._profile, "triples", []) or []
                if _triples:
                    _ttxt = "\n".join(
                        f"- {t.get('s', '')} → {t.get('r', '')}: {t.get('o', '')}"
                        for t in _triples
                    )
                    system_msg += (
                        "\n## 参数参考值（工步原文优先；原文缺失才参考下列值；"
                        "两者都无则留空，绝不臆造）\n"
                        f"{_ttxt}\n"
                    )
            if is_g25a_sourced:
                # G25a 严格原文约束保留 gate 内（G25a-specific）
                system_msg += (
                    "\n\n## G25a 严格原文约束（覆盖以上任何相反指示）\n"
                    "本装配卡每个工序的内容来自下方【工步原文】。你必须：\n"
                    "- 工序内容(content)：基于【工步原文】组织工艺方法描述，操作语言可整理通顺，"
                    "但工具名称、材料牌号、参数数值、公差必须严格来自原文，禁止新增/臆造/替换\n"
                    "- 车间/工序号/工序名称/辅助材料 已由系统从原文结构化提取，你不要生成这些列\n"
                    "- 工序行必须与【工序骨架】逐行对应，不得增删\n"
                    "- 上方关于「不要照搬原文」「用自己的语言组织」的指示对本章不适用——本章必须忠实于工步原文\n\n"
                    f"## 工序骨架（逐行对应）\n{g25a_skeleton_block}\n\n"
                    f"## 工步原文（content 的唯一事实来源）\n{g25a_source_block}\n"
                )
                # G25a 装配卡适用范围说明: chapter-level background so the LLM
                # understands what this card applies to (extracted from the
                # source 说明 cell). This is scope context, NOT step content —
                # it lives in the system_msg only and must never appear in any
                # 工序 row's content slot.
                if _assembly_overview:
                    system_msg += (
                        "\n\n## 本卡适用范围（章节背景，仅供理解，不得写入任何工序行）\n"
                        f"{_assembly_overview}\n"
                    )
            # G19a 工艺流程图: list only operation steps, never countersign/audit nodes.
            # Keep LLM generation (generic across docs); just constrain what counts as a step.
            if chapter_type == "flow_chart":
                system_msg += (
                    "\n\n## 工艺流程图严格约束\n"
                    "工艺流程图只列装配/加工的**操作工序**（如「装前准备」「安装密封圈」），按工序先后顺序。\n"
                    "禁止列出：会签、审核、批准、校对、标检、签名、更改单号等**文件管理/审批环节**"
                    "——它们是文件审批流程，不是工艺工序，绝不属于流程图。\n"
                    "只输出参考文档流程图中出现的工序；参考文档没有的环节一律不要添加。\n"
                )
            if ai_guidance:
                system_msg += f"\n指导：{ai_guidance}\n"

            if self._writing_preferences:
                system_msg += self._get_preference_prompt_fragment()

            user_parts = []
            if knowledge_context:
                user_parts.append(
                    f"## 参考文档（仅供格式和术语参考，过滤噪声后生成内容）\n{knowledge_context[:8000]}"
                )
                user_parts.append(
                    "请基于参考文档的格式和术语，结合工艺要求生成指定列的内容。"
                    "排除签名栏、日期、页码、更改单号、续表标记等文档元数据。"
                )
            else:
                user_parts.append(
                    f"请填写章节 {chapter_code}（{task.get('chapter_title', '')}）的指定列内容。"
                )

            if task.get("requirements"):
                user_parts.append(f"## 用户要求\n{task['requirements']}")

            # process_card / G25a carry many long_text columns across N rows
            # (content/inspection/references/tech_notes/requirements) — the
            # default 6000 cap truncates mid-JSON → _parse_llm_json returns
            # None → content silently empty. Give these a larger budget.
            if is_g25a_sourced and unstructured_cols:
                # G25a per-step parallel: each process step gets its own LLM
                # call (Semaphore(4) concurrent). Avoids max_tokens truncation
                # (critical for local qwen3-30b-a3b, maxIterTimes=2048) and
                # improves quality — each call focuses on one step's content.
                unstructured_slots, llm_row_count = await self._generate_g25a_per_row_parallel(
                    base_system_msg=system_msg,
                    user_parts=user_parts,
                    unstructured_cols=unstructured_cols,
                    asm=asm, skel=skel,
                    chapter_code=chapter_code,
                )
            else:
                gen_max_tokens = 8192 if (chapter_type == "process_card" or is_g25a_sourced) else 6000
                result = await llm_service.generate_with_messages(
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": "\n\n".join(user_parts)},
                    ],
                    temperature=0.2,
                    max_tokens=gen_max_tokens,
                    tier="complex",
                )

                if result["status"] == "error":
                    return {
                        "success": False,
                        "error": result.get("error", "LLM调用失败"),
                        "chapter_code": chapter_code,
                    }

                raw = result["content"].strip()
                # Detect max_tokens truncation — if hit, JSON is likely incomplete
                # → parse fails → content empty. Log so we know to switch to batched
                # generation if the cap still isn't enough.
                if result.get("finish_reason") == "length":
                    logger.warning(
                        "llm_output_truncated",
                        chapter_code=chapter_code,
                        max_tokens=gen_max_tokens,
                    )
                parsed = _parse_llm_json(raw)

                if parsed is not None and isinstance(parsed, list):
                    if parsed and "slot" in parsed[0] and "row" in parsed[0]:
                        # Normalize slot names: LLM may return label instead of key
                        label_to_key = {c.label: c.key for c in unstructured_cols}
                        for slot_item in parsed:
                            s = slot_item.get("slot", "")
                            if s in label_to_key:
                                slot_item["slot"] = label_to_key[s]
                        unstructured_slots = parsed
                    else:
                        unstructured_slots = _legacy_to_slots(parsed, unstructured_cols)

                    if unstructured_slots:
                        llm_row_count = max(
                            s.get("row", 0) for s in unstructured_slots
                        )

        # --- Step 3b: Derivation fallback REMOVED (节点3) ---
        # List chapter derivation moved to orchestrator's derive strong node
        # (_derive_strong_node, post-Phase-3 pre-Review): unconditional, with
        # provenance filter + original-first merge + 待补 marker. The weak
        # 三空 fallback here was too narrow — it was skipped whenever structured
        # extraction returned partial data, leaving list tables incomplete.

        # --- Step 4: Merge structured + unstructured ---
        total_rows = max(struct_row_count, llm_row_count, 1)

        # Cap rows by inherited process flow step count (phased generation)
        # inherited already extracted above for prompt injection
        if inherited and inherited.get("max_rows"):
            total_rows = min(total_rows, inherited["max_rows"])

        merged_rows: List[Dict[str, Any]] = []
        if chapter_type in ("single_row_list", "process_card"):
            if structured_values or unstructured_slots:
                # key_map: label→key so LLM-returned slot names (which may
                # be column labels like "工序号") are matched to template
                # column keys — fills by header name (excel logic), not by
                # position. Fixes G18a/清单 off-by-one column shifts.
                _key_map = {c.label: c.key for c in slot_cols}
                merged_rows = merge_structured_with_unstructured(
                    structured_values, unstructured_slots, total_rows,
                    key_map=_key_map,
                )
            if not structured_values and not unstructured_slots and parsed is not None:
                merged_rows = parsed if isinstance(parsed, list) else [parsed]
                # Apply noise filter to LLM direct output (fallback path)
                merged_rows = _filter_noise_rows(merged_rows)

        # G25a: expand inspection values into '检验' process rows (after each op row)
        if chapter_code == "G25a" and merged_rows:
            merged_rows = _expand_inspection_rows(merged_rows)

        # --- Step 5: Build output ---
        chapter_data = ChapterData(
            chapter_code=chapter_code,
            chapter_title=task.get("chapter_title", ""),
            table_type=chapter_type,
        )

        if chapter_type == "dual_list":
            if parsed is not None:
                chapter_data.left_data = parsed.get("left", []) if isinstance(parsed, dict) else []
                chapter_data.right_data = parsed.get("right", []) if isinstance(parsed, dict) else []
            else:
                chapter_data.left_data = []
                chapter_data.right_data = []
        elif chapter_type == "flow_chart":
            if parsed is not None:
                if isinstance(parsed, list):
                    if parsed and isinstance(parsed[0], str):
                        chapter_data.flow_steps = parsed
                    elif parsed and "slot" in parsed[0]:
                        chapter_data.flow_steps = [s.get("value", "") for s in parsed]
                    else:
                        chapter_data.flow_steps = []
                elif isinstance(parsed, dict):
                    chapter_data.flow_steps = (
                        parsed.get("data")
                        or parsed.get("steps")
                        or parsed.get("flow_steps")
                        or []
                    )
                else:
                    chapter_data.flow_steps = []
            else:
                chapter_data.flow_steps = []
        elif chapter_type in ("fields",):
            if parsed is not None and isinstance(parsed, dict):
                chapter_data.field_values = parsed
            else:
                chapter_data.field_values = {}
        else:
            chapter_data.filled_data = merged_rows

        self._save_version(_json.dumps(merged_rows or parsed or {}, ensure_ascii=False))

        # Retry once if output is suspiciously sparse
        item_count = (
            len(chapter_data.filled_data)
            or len(chapter_data.left_data or [])
            or len(chapter_data.flow_steps or [])
        )
        if item_count == 0 and knowledge_context and len(knowledge_context) > 100:
            logger.warning("template_fill_retry_sparse", chapter_code=chapter_code)
            if unstructured_cols:
                retry_result = await llm_service.generate_with_messages(
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": (
                            "上一次输出为空，请重新提取。参考文档中有大量数据，"
                            "请确保每一条都提取为完整的 JSON 条目。\n\n"
                            + "\n\n".join(user_parts)
                        )},
                    ],
                    temperature=0.1,
                    max_tokens=6000,
                    tier="complex",
                )
                if retry_result["status"] != "error":
                    retry_filled = _parse_llm_json(retry_result["content"].strip())
                    if retry_filled is not None:
                        if chapter_type in ("single_row_list", "process_card"):
                            if isinstance(retry_filled, list):
                                chapter_data.filled_data = _filter_noise_rows(retry_filled)
                            else:
                                chapter_data.filled_data = _filter_noise_rows([retry_filled])
                        elif chapter_type == "flow_chart":
                            chapter_data.flow_steps = retry_filled if isinstance(retry_filled, list) else []
                        elif chapter_type == "dual_list":
                            chapter_data.left_data = retry_filled.get("left", [])
                            chapter_data.right_data = retry_filled.get("right", [])

        return {
            "success": True,
            "chapter_code": chapter_code,
            "chapter_title": task.get("chapter_title", ""),
            "filled_data": chapter_data.filled_data,
            "left_data": chapter_data.left_data,
            "right_data": chapter_data.right_data,
            "flow_steps": chapter_data.flow_steps,
            "field_values": chapter_data.field_values,
            "table_type": chapter_type,
            "fill_sources": fill_sources,
        }

    async def _derive_list_from_upstream(
        self,
        chapter_code: str,
        chapter_type: str,
        chapter_title: str,
        slot_cols: List["TemplateColumn"],
        ai_guidance: str,
        upstream: Dict[str, Any],
    ) -> Any:
        """Derive list rows for a structured-only chapter from upstream chapters.

        Used when a list chapter (G4a/G5a/G10a/G12a/G14a/B12a) has no
        unstructured columns and structured extraction yielded nothing.
        Feeds already-generated chapters (G19a/G22a/G25a) as source so the
        LLM can reverse-derive the list (parts <- assembly content, tooling
        <- equipment column, materials <- aux_materials column).

        Returns:
            For single_row_list/process_card: list of {row, slot, value}.
            For dual_list: dict {"left": [...], "right": [...]}.
            None if derivation yields nothing.
        """
        from app.services.llm_service import llm_service

        # Build upstream context text from already-generated chapters
        upstream_parts = []
        for code, info in upstream.items():
            if not isinstance(info, dict):
                continue
            title = info.get("title", code)
            text = info.get("text", "")
            if text:
                upstream_parts.append(f"### {title}（{code}）\n{text}")
        upstream_text = "\n\n".join(upstream_parts)[:8000]
        if not upstream_text:
            return None

        # Columns to fill (all ai_filled slots)
        fill_cols = [c for c in slot_cols if c.ai_filled]
        if not fill_cols:
            return None
        slot_desc = ", ".join(f'"{c.key}"({c.label})' for c in fill_cols)

        if chapter_type == "dual_list":
            system_msg = (
                f"你是航天工艺文件编写助手。任务：根据已生成的工艺内容，"
                f"反推填写「{chapter_title}」（{chapter_code}）的左右双栏清单。\n"
                f"左栏=专用工具，右栏=专用量具。从上游工序内容里提到的工具与量具"
                f"中归纳：工具归入 left，量具归入 right。\n"
                f"需要填的列：{slot_desc}\n"
                f"指导：{ai_guidance}\n\n"
                f"输出格式：JSON 对象 {{\"left\": [{{...}}], \"right\": [{{...}}]}}，"
                f"对象键为列 key。只输出 JSON，不要解释、不要 markdown 代码块。"
            )
        else:
            first_key = fill_cols[0].key
            system_msg = (
                f"你是航天工艺文件编写助手。任务：根据已生成的工艺内容，"
                f"反推填写「{chapter_title}」（{chapter_code}）清单。\n"
                f"从上游工序内容中归纳出本清单所需条目（零件、设备、材料等），"
                f"每一条目生成一行，填入指定列。\n"
                f"需要填的列：{slot_desc}\n"
                f"指导：{ai_guidance}\n\n"
                f"输出格式：JSON 数组，每个元素含 row（行号从1开始）、slot（列key）、"
                f"value（值）。示例：[{{\"row\":1,\"slot\":\"{first_key}\",\"value\":\"...\"}}]。\n"
                f"只输出 JSON 数组，不要 ```json``` 包裹、不要解释。"
            )

        if self._writing_preferences:
            system_msg += self._get_preference_prompt_fragment()

        user_parts = [
            f"## 已生成的工艺内容（据此反推本清单）\n{upstream_text}",
            "从上面的工艺内容归纳出本清单的所有条目。"
            "关键参数（代号、数量、牌号）必须来自上游内容，不要编造。"
            "排除签名、日期、页码、更改单号等噪声。"
            "上游确实没有的信息宁可少填，也不要凭空编造。",
        ]

        result = await llm_service.generate_with_messages(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": "\n\n".join(user_parts)},
            ],
            temperature=0.2,
            max_tokens=4000,
            tier="complex",
        )

        if result["status"] == "error":
            logger.warning(
                "derive_list_failed",
                chapter_code=chapter_code,
                error=result.get("error"),
            )
            return None

        parsed = _parse_llm_json(result["content"].strip())

        if chapter_type == "dual_list":
            if isinstance(parsed, dict):
                parsed = self._provenance_filter(parsed, upstream_text, chapter_type)
            return parsed if isinstance(parsed, dict) else None

        # single_row_list / process_card: expect [{row, slot, value}]
        if isinstance(parsed, list):
            if parsed and isinstance(parsed[0], dict) and "slot" in parsed[0] and "row" in parsed[0]:
                label_to_key = {c.label: c.key for c in fill_cols}
                for item in parsed:
                    s = item.get("slot", "")
                    if s in label_to_key:
                        item["slot"] = label_to_key[s]
                parsed = self._provenance_filter(parsed, upstream_text, chapter_type)
                return parsed
            return _legacy_to_slots(parsed, fill_cols)
        return None

    def _provenance_filter(
        self, parsed: Any, upstream_text: str, chapter_type: str,
    ) -> Any:
        """Drop derived items whose value cannot be traced in upstream text.

        Anti-fabrication guard for _derive_list_from_upstream: every derived
        value must appear (whole or as a len>=2 token) in the already-generated
        upstream chapters (mainly G25a). Items without provenance are dropped
        to honor "宁可少不可假" (better fewer than fabricated).
        """
        if not upstream_text:
            return parsed  # nothing to check against — keep (safety)

        def _keep(value: Any) -> bool:
            v = str(value).strip()
            if not v or v == "待补":
                return True  # empty / already-marked-missing — keep
            if v in upstream_text:
                return True
            return any(len(t) >= 2 and t in upstream_text for t in v.split())

        if chapter_type == "dual_list":
            if not isinstance(parsed, dict):
                return parsed

            def _filter_side(side: Any) -> Any:
                if not isinstance(side, list):
                    return side
                return [
                    item for item in side
                    if isinstance(item, dict) and all(_keep(v) for v in item.values())
                ]

            return {
                "left": _filter_side(parsed.get("left", [])),
                "right": _filter_side(parsed.get("right", [])),
            }

        if isinstance(parsed, list):
            return [
                item for item in parsed
                if isinstance(item, dict) and _keep(item.get("value", ""))
            ]

        return parsed

    async def derive_list_strong(
        self, task: Dict[str, Any], upstream: Dict[str, Any]
    ) -> Any:
        """Strong-node entry for orchestrator: parse slot_cols from task and call
        _derive_list_from_upstream (which includes provenance filtering).

        Called by orchestrator's derive strong node (unconditional, post-Phase-3,
        pre-Review). Returns derived shape:
          - single_row_list / process_card: list[{row, slot, value}]
          - dual_list: {"left": [...], "right": [...]}
          - None if nothing derived.
        """
        from app.services.template_types import TemplateColumn

        template_slots = task.get("template_slots", [])
        slot_cols = [TemplateColumn.from_dict(s) for s in template_slots]
        if not slot_cols:
            return None
        return await self._derive_list_from_upstream(
            chapter_code=task.get("chapter_code", ""),
            chapter_type=task.get("chapter_type", ""),
            chapter_title=task.get("chapter_title", ""),
            slot_cols=slot_cols,
            ai_guidance=task.get("ai_guidance", ""),
            upstream=upstream,
        )

    def _looks_complete(self, content: str) -> bool:
        """Check if the generated document looks complete (has closing sections)."""
        tail = content[-800:] if len(content) > 800 else content
        completion_markers = ["审签页", "批准", "签名", "检验要求", "质量检验"]
        return any(m in tail for m in completion_markers)

    async def _generate_writing_plan(
        self,
        requirements: str,
        format_guide: str,
        knowledge_context: str,
        context: Optional[Dict[str, Any]],
    ) -> str:
        """Use LLM to create a structured writing plan (CoT step).

        The plan includes: sections to write, key parameters to include,
        standards to reference, and safety notes needed.

        Returns:
            Structured plan text to be injected into the generation prompt.
        """
        from app.services.llm_service import llm_service

        planning_msg = (
            "你是工艺文件架构师。请根据用户要求和可用知识，制定一个详细的写作计划。\n"
            "计划格式：\n"
            "1. 章节结构（列出所有需要的章节及其主要内容）\n"
            "2. 关键参数（需要写入的数值、单位、公差范围）\n"
            "3. 引用标准（需要引用的标准文档编号）\n"
            "4. 安全注意事项（需要标注的高风险操作）\n"
            f"\n格式要求：{format_guide}"
        )

        plan_parts = [f"用户要求：{requirements}"]
        if knowledge_context:
            plan_parts.append(f"可用知识：\n{knowledge_context[:1500]}")

        plan_result = await llm_service.generate_with_messages(
            messages=[
                {"role": "system", "content": planning_msg},
                {"role": "user", "content": "\n\n".join(plan_parts)},
            ],
            temperature=0.3,
            max_tokens=1500,
            tier="fast",
        )

        if plan_result["status"] == "success":
            return plan_result["content"]

        # Planning failed — return a minimal default plan
        return f"按标准格式生成，重点覆盖用户要求：{requirements[:200]}"

    def load_preferences(self, preferences: "WritingPreferences") -> None:
        """
        Load dynamic writing preferences for this session.

        Args:
            preferences: WritingPreferences instance
        """
        from app.models.profile import WritingPreferences
        self._writing_preferences = preferences
        logger.info("writing_preferences_loaded", confidence=preferences.confidence)

    def load_profile(self, profile: "Profile") -> None:
        """Load the full domain profile (principles强约束 + triples参考值).

        Used by chapter prompts (e.g. G25a) to inject standards and
        reference values alongside the per-step source text.
        """
        self._profile = profile
        logger.info(
            "writing_profile_loaded",
            principles=len(getattr(profile, "principles", []) or []),
            triples=len(getattr(profile, "triples", []) or []),
        )

    async def _generate_g25a_per_row_parallel(
        self,
        base_system_msg: str,
        user_parts: List[str],
        unstructured_cols: List["TemplateColumn"],
        asm: Dict[int, Dict[str, Any]],
        skel: List[str],
        chapter_code: str,
    ) -> tuple:
        """G25a per-step parallel generation.

        Each process step → one LLM call (Semaphore(4) concurrent). Avoids
        max_tokens truncation (local qwen3-30b-a3b maxIterTimes=2048) and
        focuses each call on one step's content/inspection for better quality.
        Returns (unstructured_slots, llm_row_count).
        """
        import asyncio
        from app.services.llm_service import llm_service

        n = len(skel)
        slot_keys = [c.key for c in unstructured_cols]
        slot_desc = ", ".join(f'"{c.key}"({c.label})' for c in unstructured_cols)
        label_to_key = {c.label: c.key for c in unstructured_cols}
        # G25a inspection column removed from template (now expanded into '检验'
        # process rows), but the LLM still needs to generate this slot so the
        # post-processor can split it into inspection rows.
        if chapter_code == "G25a" and "inspection" not in slot_keys:
            slot_keys.append("inspection")
            slot_desc += ', "inspection"(检验)'
        semaphore = asyncio.Semaphore(4)
        user_msg = "\n\n".join(user_parts) if user_parts else "请生成。"

        async def gen_one(i: int):
            name = skel[i - 1] if i - 1 < len(skel) else ""
            step = asm.get(i)
            subs = step.get("substeps", []) if step else []
            sub_text = "\n".join(
                f"  {s.get('content', '')}"
                + (f" | 辅材:{s.get('material')}" if s.get("material") else "")
                for s in subs
            ) or "  （原文未提供）"
            step_msg = base_system_msg + (
                f"\n\n## 当前任务：只生成第 {i} 道工序（{name}）的内容\n"
                f"只输出 row={i} 的列：{slot_desc}\n"
                f"输出格式：JSON 数组，每个元素 {{\"row\": {i}, \"slot\": 列key, \"value\": 值}}\n"
                f"不要输出其他工序，不要输出已由系统提取的列（车间/工序号/工序名称/辅助材料）。\n"
                f"## 工序内容(content) 写法：基于「工序{i}（{name}）工步原文」逐工步详实展开，保留 1.1/1.2/1.3 等工步编号与层次结构。\n"
                f"每个工步写清：操作动作 + 关键参数（力矩/尺寸/规格/数量）+ 使用的辅材/仪器。多个工步用换行分段，结构：「工步号」操作描述；关键参数；辅材/仪器。\n"
                f"约束（强制）：\n"
                f"  1. 只用工步原文里出现的信息，不得新增原文没有的参数、数值、步骤；原文不足则如实写已有的，不要补全。\n"
                f"  2. 不要带「钳：」「机：」前缀（工序名称已单独提取到 step_name 列）。\n"
                f"  3. 目标长度：本工序有多少工步就写多少段，每工步 1-3 句（约 30-60 字/工步），整道工序通常 100-200 字；工步多的可更长。宁详勿简，但绝不超过工步原文提供的信息量。\n"
                f"  4. 若该工序工步原文为「（原文未提供）」，content 留空字符串，不要臆造。\n\n"
                f"## 检验(inspection) 写法：仅对【关键质检工序】生成检验点——"
                f"即涉及力矩/密封性/电气性能/位置度/关键尺寸测量，且原文工步中出现检验或测量要求的工序，生成 1-2 个检验点。"
                f"普通装配动作（装密封圈、拧螺钉、搬运、清洗、涂胶、普通装配）一律不生成检验点，该 slot 留空字符串。"
                f"全表检验点总数不得超过工序数，宁缺毋滥。\n"
                f"每个检验点独占一行（用换行分隔）。不要写操作步骤（操作步骤归 content）。\n\n"
                f"## 工序{i}（{name}）工步原文（content 的依据，按上述工步结构详实展开，保留全部工步信息）\n{sub_text}\n"
            )
            async with semaphore:
                result = await llm_service.generate_with_messages(
                    messages=[
                        {"role": "system", "content": step_msg},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.2,
                    max_tokens=3000,
                    tier="complex",
                )
            if result["status"] == "error":
                logger.warning("g25a_per_step_failed", step=i, error=result.get("error"))
                return []
            raw = result["content"].strip()
            if result.get("finish_reason") == "length":
                logger.warning("g25a_per_step_truncated", step=i, max_tokens=3000)
            parsed = _parse_llm_json(raw)
            if not parsed or not isinstance(parsed, list):
                logger.warning("g25a_per_step_parse_failed", step=i)
                return []
            slots = []
            for item in parsed:
                s = item.get("slot", "")
                s = label_to_key.get(s, s)
                if s in slot_keys:
                    slots.append({"row": i, "slot": s, "value": item.get("value", "")})
            return slots

        tasks = [gen_one(i) for i in range(1, n + 1)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_slots: List[Dict[str, Any]] = []
        for idx, r in enumerate(results, start=1):
            if isinstance(r, Exception):
                logger.error("g25a_per_step_exception", step=idx, error=str(r))
            else:
                all_slots.extend(r)
        logger.info("g25a_per_step_parallel_done", steps=n, slots=len(all_slots))
        return all_slots, n

    def _get_preference_prompt_fragment(self) -> str:
        """Generate a prompt fragment from loaded preferences."""
        if not self._writing_preferences:
            return ""

        prefs = self._writing_preferences
        lines = []

        if prefs.confidence > 0.3:
            lines.append(f"- 语气: {prefs.tone}")
            lines.append(f"- 详细程度: {prefs.detail_level}")
            lines.append(f"- 句式长度偏好: {prefs.preferred_sentence_length}")

            if not prefs.use_passive_voice:
                lines.append("- 尽量使用主动语态")
            if not prefs.include_examples:
                lines.append("- 不需要举例说明")
            if not prefs.include_caution_notes:
                lines.append("- 不需要额外注意事项")

            if prefs.avoid_phrases:
                lines.append(f"- 避免使用: {', '.join(prefs.avoid_phrases[:5])}")
            if prefs.custom_vocabulary:
                for cn, en in list(prefs.custom_vocabulary.items())[:5]:
                    lines.append(f"- 术语 {cn} 对应 {en}")

        if lines:
            return "\n## 用户写作偏好 (基于历史交互学习)\n" + "\n".join(lines)
        return ""

    def _get_knowledge_catalog_context(self, query: str) -> str:
        """Query the knowledge catalog for materials/tools/standards relevant to the query.

        Returns formatted text for LLM injection, or empty string if nothing found.
        """
        if not query:
            return ""
        try:
            from app.database import SessionLocal
            from app.services.knowledge_search import KnowledgeSearchService
            db = SessionLocal()
            try:
                svc = KnowledgeSearchService()
                return svc.build_knowledge_context_text(db, query, max_items=5)
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"knowledge_catalog_query_failed: {e}")
            return ""

    async def _search_knowledge(
        self,
        query: str,
        mode: str = "comprehensive"
    ) -> Dict[str, Any]:
        """
        检索知识 via hierarchical_context keyword search.

        Args:
            query: 查询字符串
            mode: 检索模式 (保留参数兼容旧调用，统一走 hierarchical_context)

        Returns:
            检索结果
        """
        results = []

        try:
            from app.services.hierarchical_context import hierarchical_context

            hc_results = hierarchical_context.global_keyword_search(
                query=query, top_k=5
            )
            for r in hc_results:
                if r.get("score", 0) >= 2:
                    results.append({
                        "content": r.get("snippet", ""),
                        "source": r.get("doc_name", ""),
                        "score": float(r.get("score", 0)),
                        "metadata": {"page": r.get("page"), "retriever": "hierarchical_context"},
                    })

            logger.info("search_hier", query=query[:50], results=len(results))
        except Exception as e:
            logger.warning("hier_context_search_failed", error=str(e))

        return {
            "success": len(results) > 0,
            "results": results,
            "total": len(results)
        }

    async def handle_feedback(
        self,
        feedback: UserFeedback,
        task: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        处理用户反馈（多轮修改支持）

        Args:
            feedback: 用户反馈
            task: 原始任务（可选）

        Returns:
            处理结果
        """
        if feedback.type == FeedbackType.ACCEPT:
            # 用户接受，标记完成
            logger.info("user_accepted", version=self._current_version)
            return {
                "success": True,
                "status": "accepted",
                "version": self._current_version,
                "message": "内容已确认"
            }

        elif feedback.type == FeedbackType.REJECT:
            # 用户拒绝，回滚或中止
            logger.info("user_rejected", version=self._current_version)
            return {
                "success": True,
                "status": "rejected",
                "version": self._current_version,
                "message": "内容已拒绝"
            }

        elif feedback.type == FeedbackType.MODIFY:
            # 用户要求修改
            if len(self._version_history) >= 3:
                return {
                    "success": False,
                    "status": "max_iterations_reached",
                    "message": "已达到最大修改次数（3次）"
                }

            # 基于反馈进行增量修改
            last_version = self._version_history[-1] if self._version_history else None
            if last_version is None:
                return {
                    "success": False,
                    "status": "no_content_to_modify",
                    "message": "没有可修改的内容"
                }

            # 执行增量修改
            modified_content = await self._incremental_modify(
                last_version.content,
                feedback
            )

            # 保存新版本
            self._current_version += 1
            new_version = VersionHistory(
                version=self._current_version,
                content=modified_content.get("content", ""),
                timestamp=__import__("time").time(),
                feedback=feedback
            )
            self._version_history.append(new_version)

            logger.info(
                "content_modified",
                version=self._current_version,
                feedback_type=feedback.type
            )

            return {
                "success": True,
                "status": "modified",
                "version": self._current_version,
                "content": modified_content.get("content"),
                "suggestions": modified_content.get("suggestions", [])
            }

        return {
            "success": False,
            "status": "unknown_feedback_type",
            "message": f"未知的反馈类型: {feedback.type}"
        }

    async def _incremental_modify(
        self,
        original_content: str,
        feedback: UserFeedback
    ) -> Dict[str, Any]:
        """
        增量修改内容

        Args:
            original_content: 原始内容
            feedback: 用户反馈

        Returns:
            修改后的内容
        """
        suggestions = []

        # Search for additional knowledge if suggestions provided
        knowledge_context = ""
        if feedback.suggestions:
            additional_knowledge = await self._search_knowledge(
                " ".join(feedback.suggestions),
                mode="comprehensive"
            )

            if additional_knowledge.get("success"):
                results = additional_knowledge.get("results", [])
                knowledge_context = "\n".join([
                    r.get("content", "") for r in results[:2]
                ])
                for result in results[:2]:
                    suggestions.append(f"参考: {result.get('content', '')[:200]}")

        from app.services.llm_service import llm_service

        system_msg = (
            "你是一位专业的工艺文件编辑助手。请根据用户的反馈意见，对原始内容进行增量修改。"
            "只修改反馈中提到的部分，保持其余内容不变。直接输出修改后的完整内容。"
        )
        if self._writing_preferences:
            system_msg += self._get_preference_prompt_fragment()

        user_parts = [f"原始内容：\n{original_content}"]
        user_parts.append(f"修改意见：{feedback.content}")
        if feedback.suggestions:
            user_parts.append(f"具体建议：{', '.join(feedback.suggestions)}")
        if knowledge_context:
            user_parts.append(f"参考知识：\n{knowledge_context[:500]}")

        result = await llm_service.generate_with_messages(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": "\n\n".join(user_parts)},
            ],
            temperature=0.5,
            max_tokens=3000,
            tier="complex",
        )

        if result["status"] == "error":
            return {"content": original_content, "suggestions": suggestions}

        return {
            "content": result["content"],
            "suggestions": suggestions,
        }

    def get_version_history(self) -> List[Dict[str, Any]]:
        """
        获取版本历史

        Returns:
            版本历史列表
        """
        return [
            {
                "version": v.version,
                "content": v.content[:500] + "..." if len(v.content) > 500 else v.content,
                "timestamp": v.timestamp,
                "feedback_type": v.feedback.type if v.feedback else None
            }
            for v in self._version_history
        ]

    def rollback(self, version: int) -> Dict[str, Any]:
        """
        回滚到指定版本

        Args:
            version: 目标版本号

        Returns:
            回滚结果
        """
        for v in self._version_history:
            if v.version == version:
                self._current_version = version
                logger.info("version_rollback", version=version)
                return {
                    "success": True,
                    "version": version,
                    "content": v.content
                }

        return {
            "success": False,
            "error": f"版本 {version} 不存在"
        }

    def _save_version(self, content: str, feedback: Optional[UserFeedback] = None):
        """
        保存版本到历史

        Args:
            content: 内容
            feedback: 关联的反馈
        """
        import time
        self._current_version += 1
        version = VersionHistory(
            version=self._current_version,
            content=content,
            timestamp=time.time(),
            feedback=feedback
        )
        self._version_history.append(version)

    def _quick_check_output(self, content: str) -> List[str]:
        """Run lightweight guardrail checks on generated content.

        These are fast, rule-based checks that catch common LLM output
        problems without requiring a full ReviewAgent call.
        Format/structure checks (duplication, meta-commentary, ordering)
        are handled by ReviewAgent._check_output_quality() instead.

        Returns:
            List of warning messages (empty if all checks pass).
        """
        import re as _re
        warnings: List[str] = []

        # Check 1: LLM left placeholder markers
        placeholders = _re.findall(r"\[(?:待补充|此处填写|请填写|TODO|FIXME|XXX)\]", content)
        if placeholders:
            warnings.append(f"输出包含占位符标记: {placeholders[:3]}，可能需要人工补充")

        # Check 2: Numeric values without units (common LLM mistake in process docs)
        bare_numbers = _re.findall(
            r"(?<![a-zA-Z\d])(\d+(?:\.\d+)?(?:±\d+(?:\.\d+)?)?)(?!\s*(?:°C|MPa|mm|min|N·m|Nm|HRC|rpm|kg|m|cm|s|小时|分钟|秒|度|%))",
            content,
        )
        # Filter obvious non-parameter numbers (line numbers, section numbers)
        suspicious = [n for n in bare_numbers if "." in n or "±" in n]
        if len(suspicious) >= 3:
            warnings.append(f"输出包含 {len(suspicious)} 个疑似无单位的数值参数，请确认单位标注完整")

        # Check 3: Fuzzy/vague language in process instructions
        vague_patterns = ["适当", "酌情", "视情况", "根据实际情况", "相关要求"]
        found_vague = [v for v in vague_patterns if v in content]
        if found_vague:
            warnings.append(f"输出包含模糊表述: {found_vague}，工艺文件应使用确定性描述")

        if warnings:
            logger.warning("output_guardrail_triggered", warnings=warnings)

        return warnings


def _parse_llm_json(raw: str) -> Any:
    """Parse JSON from LLM output, handling common formatting issues.

    Strips markdown code blocks, leading/trailing whitespace, and
    attempts multiple parse strategies.
    """
    import json as _json

    text = raw.strip()

    # Strip markdown code block wrapper
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # Direct parse
    try:
        return _json.loads(text)
    except _json.JSONDecodeError:
        pass

    # Try to find JSON array or object boundaries
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end > start:
            try:
                return _json.loads(text[start : end + 1])
            except _json.JSONDecodeError:
                continue

    return None


def _group_slots_by_fill_type(
    cols: List["TemplateColumn"],
) -> Dict[str, List["TemplateColumn"]]:
    """Group TemplateColumn list by fill_type field."""
    structured: List["TemplateColumn"] = []
    unstructured: List["TemplateColumn"] = []
    for col in cols:
        if col.fill_type == "unstructured":
            unstructured.append(col)
        else:
            structured.append(col)
    return {"structured": structured, "unstructured": unstructured}


def _expand_inspection_rows(
    merged_rows: List[Dict[str, Any]],
    inspection_key: str = "inspection",
) -> List[Dict[str, Any]]:
    """G25a: split each row's inspection value into inspection process rows.

    Each operating row keeps its fields (inspection removed); after it we insert
    one '检验' row per non-empty inspection point (points split on newlines).
    Inspection rows carry only step_name='检验' + content=point; other columns
    empty so they match the frontend G25a dataColumns keys exactly.

    Global cap: total inspection rows must not exceed the number of operating
    rows (step_name != '检验'). When over budget, rows are ranked by point
    count (desc) so multi-point key-QC steps are preserved and weak single-point
    steps are dropped first.
    """
    import re

    # Operating rows = cap (inspection rows must not exceed operating rows)
    cap = sum(1 for r in merged_rows if (r.get("step_name") or "") != "检验")
    # Pre-split inspection points per row
    row_points = []  # list of [idx, [points]]
    for idx, row in enumerate(merged_rows):
        insp = (row.get(inspection_key) or "").strip()
        pts = [p.strip() for p in re.split(r"[\n\r]+", insp) if p.strip()]
        if pts:
            row_points.append([idx, pts])
    # Global cap: when over budget keep rows with most points (key QC), drop weak single-points
    if cap > 0:
        total = sum(len(p) for _, p in row_points)
        if total > cap:
            ranked = sorted(range(len(row_points)), key=lambda i: -len(row_points[i][1]))
            kept, budget = set(), cap
            for i in ranked:
                if budget <= 0:
                    break
                n = len(row_points[i][1])
                take = min(n, budget)
                if take < n:
                    row_points[i][1] = row_points[i][1][:take]
                kept.add(i)
                budget -= take
            row_points = [row_points[i] for i in range(len(row_points)) if i in kept]
    keep_by_row = {idx: pts for idx, pts in row_points}

    out: List[Dict[str, Any]] = []
    for idx, row in enumerate(merged_rows):
        out.append({k: v for k, v in row.items() if k != inspection_key})
        for point in keep_by_row.get(idx, []):
            out.append({
                "workshop": "",
                "step_no": "",
                "step_name": "检验",
                "content": point,
                "aux_materials": "",
                "instruments": "",
                "time_setup": "",
                "time_per_piece": "",
                "time_total": "",
            })
    return out


def _legacy_to_slots(
    rows: List[Dict[str, Any]],
    cols: List["TemplateColumn"],
) -> List[Dict[str, Any]]:
    """Convert legacy full-row format [{key: value}] to slot-based [{row, slot, value}]."""
    slots: List[Dict[str, Any]] = []
    for row_idx, row in enumerate(rows, start=1):
        for col in cols:
            if col.key in row:
                slots.append({
                    "row": row_idx,
                    "slot": col.key,
                    "value": row[col.key],
                })
    return slots
