"""
工艺文件辅助编辑系统 - 意图识别器
识别用户输入的工艺意图，将其分类为具体的工艺操作类型
"""
import json
import re
from typing import Dict, Any, Optional, List
from enum import Enum

from app.shared.logging import get_logger

logger = get_logger(__name__)


class IntentType(Enum):
    """意图类型枚举"""
    CREATE_DOCUMENT = "create_document"  # 创建新工艺文件
    EDIT_DOCUMENT = "edit_document"      # 编辑现有工艺文件
    REVIEW_DOCUMENT = "review_document"  # 审核工艺文件
    GENERATE_DOCUMENT = "generate_document"  # 生成工艺文件
    PARSE_PDF = "parse_pdf"              # 解析PDF工艺文件
    SEARCH_KNOWLEDGE = "search_knowledge"  # 搜索工艺知识
    ALIGN_TERMINOLOGY = "align_terminology"  # 对齐工艺术语
    CHECK_COMPLIANCE = "check_compliance"  # 检查合规性
    EXPORT_TO_PDM = "export_to_pdm"      # 导出到PDM系统
    DRAFT_COMPLETE = "draft_complete"    # 工艺文件补全（基于初稿生成修改方案）
    UNKNOWN = "unknown"                  # 未知意图


class IntentRecognizer:
    """
    意图识别器

    分析用户输入的工艺描述，识别具体的工艺操作意图，
    支持自然语言理解和关键词匹配
    """

    # 意图关键词映射
    INTENT_KEYWORDS = {
        IntentType.CREATE_DOCUMENT: [
            "创建", "新建", "制作", "编写", "起草", "建立",
            "create", "new", "make", "write", "draft"
        ],
        IntentType.EDIT_DOCUMENT: [
            "编辑", "修改", "更新", "调整", "改动", "修订",
            "edit", "modify", "update", "change", "revise"
        ],
        IntentType.REVIEW_DOCUMENT: [
            "审核", "检查", "评审", "验证", "确认", "审批",
            "review", "check", "verify", "validate", "approve"
        ],
        IntentType.GENERATE_DOCUMENT: [
            "生成", "导出", "输出", "打印", "产生",
            "generate", "export", "output", "print", "produce"
        ],
        IntentType.PARSE_PDF: [
            "解析", "提取", "读取", "分析", "识别", "PDF",
            "parse", "extract", "read", "analyze", "recognize"
        ],
        IntentType.SEARCH_KNOWLEDGE: [
            "搜索", "查找", "查询", "检索", "寻找", "知识",
            "search", "find", "query", "retrieve", "lookup"
        ],
        IntentType.ALIGN_TERMINOLOGY: [
            "对齐", "标准化", "术语", "规范", "统一", "转换",
            "align", "standardize", "terminology", "normalize", "convert"
        ],
        IntentType.CHECK_COMPLIANCE: [
            "合规", "检查", "标准", "规范", "符合", "验证",
            "compliance", "check", "standard", "specification", "verify"
        ],
        IntentType.EXPORT_TO_PDM: [
            "导出", "上传", "同步", "PDM", "系统", "保存",
            "export", "upload", "sync", "pdm", "system", "save"
        ],
        IntentType.DRAFT_COMPLETE: [
            "补全", "补", "完善", "补充",
            "帮我改", "改一下", "帮我完善",
            "draft", "complete", "fill"
        ]
    }

    # draft_complete 复合触发模式（关键词 + 文档上下文）
    _DRAFT_COMPLETE_COMPOUND_PATTERNS = [
        # "补全/完善/补充" + "工艺文件/文件/文档" 组合
        re.compile(r"补全|完善|补充", re.IGNORECASE),
    ]
    _DRAFT_DOCUMENT_HINTS = re.compile(
        r"工艺文件|文件|文档|初稿|草稿|draft",
        re.IGNORECASE,
    )
    # Question-form gate (23:18 incident): a QUESTION about completeness
    # ("还需要补充吗") is a review/query, never a fill command. Questions are
    # excluded from the draft_complete composite boost entirely — only
    # imperative phrasing ("补充一下工序五") may boost.
    _QUESTION_FORM = re.compile(
        r"吗\s*[？?]?\s*$|呢\s*[？?]?\s*$|[？?]\s*$"
        r"|需不需要|有没有|是不是|还有什么|还缺什么",
        re.IGNORECASE,
    )

    # 工艺实体关键词
    PROCESS_ENTITIES = {
        "operation": ["工序", "步骤", "操作", "流程", "工步"],
        "parameter": ["参数", "数值", "尺寸", "公差", "要求"],
        "tool": ["工具", "刀具", "量具", "夹具", "设备"],
        "material": ["材料", "原料", "毛坯", "工件", "零件"],
        "quality": ["质量", "检验", "检测", "要求", "标准"]
    }

    # Short-but-routable commands (buttons / confirmations legitimately send
    # one or two words). Anything short NOT in this list is insufficient.
    _SHORT_COMMANDS = {
        "补齐", "生成", "继续", "重试", "确认", "取消", "是", "否", "好",
        "可以", "开始", "执行", "下一步", "上一步", "完成",
    }
    _MIN_MEANINGFUL_LEN = 4  # chars, punctuation/whitespace excluded

    def __init__(self):
        """初始化意图识别器"""
        # 编译正则表达式模式
        self.patterns = self._compile_patterns()
        logger.info("intent_recognizer_initialized")

    def _compile_patterns(self) -> Dict[IntentType, re.Pattern]:
        """编译意图识别模式"""
        patterns = {}
        for intent_type, keywords in self.INTENT_KEYWORDS.items():
            # 创建正则表达式模式
            pattern_str = "|".join(re.escape(keyword) for keyword in keywords)
            patterns[intent_type] = re.compile(pattern_str, re.IGNORECASE)
        return patterns

    async def recognize(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        识别用户意图

        Args:
            user_input: 用户输入的工艺描述
            context: 会话上下文

        Returns:
            识别结果，包含意图类型、置信度和提取的实体
        """
        try:
            # 1. 预处理输入 + draft_complete 复合检测（优先级最高，短路）
            processed_input = self._preprocess_input(user_input)
            draft_complete_boost = self._detect_draft_complete(processed_input, context)
            extracted_entities = self._extract_entities(processed_input)

            # 1.5 输入充分性闸门（零 LLM，纯规则）: too-short / meaningless
            # input ("安全", "嗯嗯") carries no decidable intent — the LLM
            # classifier would still confidently pick one (0.85) and the turn
            # would wander into a wrong pipeline. Hand back to the user
            # instead: unknown + needs_clarification, caller asks a
            # clarification question. Command whitelist ("补齐/继续/生成"…)
            # stays routable — buttons and confirmations legitimately send
            # short words.
            if self._is_insufficient_input(processed_input):
                logger.info(
                    "intent_input_insufficient",
                    length=len(processed_input), user_input=user_input[:50],
                )
                return {
                    "type": IntentType.UNKNOWN.value,
                    "confidence": 0.0,
                    "original_input": user_input,
                    "processed_input": processed_input,
                    "entities": extracted_entities,
                    "alternative_intents": [],
                    "context_used": bool(context),
                    "needs_clarification": True,
                }

            # 2. LLM 意图分类（fail-soft → 关键词正则兜底，绝不阻塞主流程）
            llm_intent = await self._classify_with_llm(user_input)
            intent_results: Dict[IntentType, float] = {}
            if llm_intent is not None:
                primary_intent = llm_intent
                confidence = 0.85
                source = "llm"
            else:
                # 关键词兜底（原 _match_intent_types 路径）
                intent_results = self._match_intent_types(processed_input)
                confidence = self._calculate_confidence(intent_results, extracted_entities)
                primary_intent = self._determine_primary_intent(intent_results, confidence, context)
                source = "keyword"

            # draft_complete 复合检测覆盖（优先于 LLM/关键词结果）
            if draft_complete_boost > 0:
                intent_results[IntentType.DRAFT_COMPLETE] = max(
                    intent_results.get(IntentType.DRAFT_COMPLETE, 0.0),
                    draft_complete_boost,
                )
                primary_intent = IntentType.DRAFT_COMPLETE
                confidence = max(confidence, draft_complete_boost)

            # 3. 构建意图结果
            intent_result = {
                "type": primary_intent.value,
                "confidence": round(confidence, 2),
                "original_input": user_input,
                "processed_input": processed_input,
                "entities": extracted_entities,
                "alternative_intents": [
                    {"type": it.value, "score": score}
                    for it, score in intent_results.items()
                    if it != primary_intent and score > 0.1
                ],
                "context_used": bool(context),
                # unknown must never silently fall through to a doing-something
                # branch — callers use this flag to ask for clarification.
                "needs_clarification": primary_intent == IntentType.UNKNOWN,
            }

            logger.info(
                "intent_recognized",
                intent_type=primary_intent.value,
                confidence=round(confidence, 2),
                source=source,
                entity_count=len(extracted_entities)
            )

            return intent_result

        except Exception as e:
            logger.error("intent_recognition_failed", error=str(e), user_input=user_input)
            return {
                "type": IntentType.UNKNOWN.value,
                "confidence": 0.0,
                "error": str(e),
                "entities": {},
                "needs_clarification": True,
            }

    async def _classify_with_llm(self, user_input: str) -> Optional[IntentType]:
        """LLM 意图分类。返回 IntentType 或 None（fail-soft，绝不抛）。"""
        # Local import avoids a module-load circular dependency
        from app.services.llm_service import llm_service

        valid_intents = [it.value for it in IntentType if it != IntentType.UNKNOWN]
        prompt = (
            "你是工艺文件辅助编辑系统的意图分类器。判断用户输入属于哪种意图。\n"
            f"可选意图类型: {', '.join(valid_intents)}\n"
            "类型说明: create_document=创建新工艺文件, edit_document=编辑/修改现有文件, "
            "review_document=审核文件, generate_document=生成/导出文件, "
            "draft_complete=基于初稿补全文件, parse_pdf=解析PDF, "
            "search_knowledge=搜索知识, align_terminology=对齐术语, "
            "check_compliance=检查合规, export_to_pdm=导出PDM。\n"
            "判定要点:\n"
            "- 问句形式的询问（…有什么问题吗/还需要补充吗/还缺什么/完整吗/有没有问题）"
            "是 review_document 或 search_knowledge，绝不是 draft_complete——"
            "draft_complete 只对应明确的补全指令（如\"补充完整这份文件\"\"把工序五补全\"）。\n"
            "- 关于已生成内容的评价、缺陷、完整性询问 → review_document。\n"
            "- 一般工艺知识咨询 → search_knowledge。\n"
            f"用户输入: {user_input[:500]}\n"
            '只输出JSON,示例: {"intent": "create_document"}\n'
            "不要输出多余文字。"
        )
        try:
            result = await llm_service.generate_with_messages(
                messages=[{"role": "user", "content": prompt}],
                tier="simple", temperature=0.1, max_tokens=80,
            )
            if result.get("status") != "success":
                logger.warning("intent_llm_non_success", status=result.get("status"))
                return None
            raw = result.get("content", "").strip()
            intent_str = self._parse_intent_json(raw)
            if not intent_str:
                logger.warning("intent_llm_parse_failed", raw=raw[:200])
                return None
            try:
                return IntentType(intent_str)
            except ValueError:
                logger.warning("intent_llm_invalid_type", intent=intent_str)
                return None
        except Exception as e:
            logger.warning("intent_llm_classify_failed", error=str(e))
            return None

    @staticmethod
    def _parse_intent_json(raw: str) -> Optional[str]:
        """Tolerate fenced code blocks / surrounding prose; return intent or None."""
        if not raw:
            return None
        candidate = raw
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if fence:
            candidate = fence.group(1)
        else:
            obj = re.search(r"\{.*\}", raw, re.DOTALL)
            if obj:
                candidate = obj.group(0)
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            return None
        intent = data.get("intent") if isinstance(data, dict) else None
        return str(intent).strip() if intent else None

    @classmethod
    def _is_insufficient_input(cls, processed_input: str) -> bool:
        """Input-sufficiency check (rule-based, zero LLM).

        True when the input is too short to carry a decidable intent and is
        not a whitelisted short command. Such turns must be handed back to
        the user for clarification — never classified (the LLM would
        confidently guess) and never silently routed.
        """
        stripped = "".join(
            ch for ch in processed_input if ch.isalnum()
        )
        if not stripped:
            return True
        if processed_input.strip() in cls._SHORT_COMMANDS:
            return False
        return len(stripped) < cls._MIN_MEANINGFUL_LEN

    def _preprocess_input(self, user_input: str) -> str:
        """
        预处理用户输入

        Args:
            user_input: 原始用户输入

        Returns:
            预处理后的文本
        """
        # 转换为小写（中文不区分大小写，但英文需要）
        processed = user_input.lower()

        # 移除多余空格
        processed = re.sub(r'\s+', ' ', processed).strip()

        # 移除标点符号（保留中英文标点）
        processed = re.sub(r'[^\w\u4e00-\u9fff\s]', ' ', processed)

        return processed

    def _detect_draft_complete(
        self, processed_input: str, context: Optional[Dict[str, Any]] = None
    ) -> float:
        """检测 draft_complete 复合意图

        触发条件：
        - 输入包含补全/完善/补充 等词
        - 且上下文中有初稿信息，或者输入同时提到文档/文件

        Returns:
            0.0 表示未检测到，>0.0 表示检测到的置信度
        """
        has_action = any(p.search(processed_input) for p in self._DRAFT_COMPLETE_COMPOUND_PATTERNS)
        if not has_action:
            return 0.0

        # Question gate: "还需要补充吗" is asking ABOUT completeness (review),
        # not commanding a fill. Never let a question trigger the boost —
        # it used to hijack the intent and rewrite the whole document.
        if self._QUESTION_FORM.search(processed_input):
            return 0.0

        # 检查是否提到了文档
        has_doc_hint = bool(self._DRAFT_DOCUMENT_HINTS.search(processed_input))

        # 检查上下文中是否有初稿
        has_draft_context = False
        if context:
            has_draft_context = bool(
                context.get("draft_id")
                or context.get("has_draft")
                or context.get("has_uploaded_file")
                or context.get("uploaded_file_content")
            )

        if has_doc_hint or has_draft_context:
            return 0.85  # 高置信度
        elif has_action:
            return 0.4  # 有动作词但没有文档上下文，给中等分

        return 0.0

    def _match_intent_types(self, processed_input: str) -> Dict[IntentType, float]:
        """
        匹配意图类型

        Args:
            processed_input: 预处理后的用户输入

        Returns:
            意图类型匹配分数字典
        """
        scores = {intent_type: 0.0 for intent_type in IntentType}

        for intent_type, pattern in self.patterns.items():
            # 查找匹配
            matches = pattern.findall(processed_input)
            if matches:
                # 计算匹配分数
                match_count = len(matches)
                total_keywords = len(self.INTENT_KEYWORDS[intent_type])
                score = min(match_count / total_keywords * 2, 1.0)  # 归一化到0-1

                # 考虑匹配位置（开头匹配得分更高）
                first_match = pattern.search(processed_input)
                if first_match:
                    position_score = 1.0 - (first_match.start() / len(processed_input))
                    score = (score + position_score) / 2

                scores[intent_type] = score

        return scores

    def _extract_entities(self, processed_input: str) -> Dict[str, List[str]]:
        """
        提取工艺实体

        Args:
            processed_input: 预处理后的用户输入

        Returns:
            提取的实体字典
        """
        entities = {entity_type: [] for entity_type in self.PROCESS_ENTITIES.keys()}

        for entity_type, keywords in self.PROCESS_ENTITIES.items():
            # 创建实体匹配模式
            pattern_str = "|".join(re.escape(keyword) for keyword in keywords)
            pattern = re.compile(pattern_str)

            # 查找实体
            matches = pattern.findall(processed_input)
            if matches:
                entities[entity_type] = list(set(matches))  # 去重

        return entities

    def _calculate_confidence(self, intent_scores: Dict[IntentType, float], entities: Dict[str, List[str]]) -> float:
        """
        计算意图识别置信度

        Args:
            intent_scores: 意图匹配分数
            entities: 提取的实体

        Returns:
            置信度（0-1）
        """
        # 1. 基于意图匹配分数的置信度
        max_score = max(intent_scores.values())
        intent_confidence = max_score

        # 2. 基于实体提取的置信度
        total_entities = sum(len(entity_list) for entity_list in entities.values())
        entity_confidence = min(total_entities / 5, 1.0)  # 最多5个实体

        # 3. 综合置信度
        confidence = (intent_confidence * 0.7) + (entity_confidence * 0.3)

        return round(confidence, 2)

    def _determine_primary_intent(
        self,
        intent_scores: Dict[IntentType, float],
        confidence: float,
        context: Optional[Dict[str, Any]] = None
    ) -> IntentType:
        """
        确定主要意图

        Args:
            intent_scores: 意图匹配分数
            confidence: 总体置信度
            context: 会话上下文

        Returns:
            主要意图类型
        """
        # 如果置信度过低，返回未知意图
        if confidence < 0.3:
            return IntentType.UNKNOWN

        # 找到分数最高的意图
        max_score = 0.0
        primary_intent = IntentType.UNKNOWN

        for intent_type, score in intent_scores.items():
            if score > max_score:
                max_score = score
                primary_intent = intent_type

        # 考虑上下文信息
        if context:
            # 如果上下文中有正在进行的工作，可能影响意图判断
            current_topic = context.get("topic")
            if current_topic and primary_intent == IntentType.UNKNOWN:
                # 尝试根据当前话题推断意图
                pass

        return primary_intent

    async def refine_intent(
        self,
        initial_intent: Dict[str, Any],
        additional_input: str,
        feedback: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        根据附加输入和反馈细化意图

        Args:
            initial_intent: 初始意图识别结果
            additional_input: 附加用户输入
            feedback: 用户反馈

        Returns:
            细化后的意图结果
        """
        try:
            # 合并输入
            combined_input = f"{initial_intent.get('original_input', '')} {additional_input}"

            # 重新识别意图
            refined_intent = await self.recognize(combined_input)

            # 应用反馈
            if feedback:
                refined_intent = self._apply_feedback(refined_intent, feedback)

            # 记录细化历史
            refined_intent["refinement_history"] = {
                "initial_intent": initial_intent.get("type"),
                "additional_input": additional_input,
                "refined_at": "timestamp_placeholder"  # 实际使用时需要添加时间戳
            }

            logger.info(
                "intent_refined",
                from_intent=initial_intent.get("type"),
                to_intent=refined_intent.get("type"),
                confidence_change=refined_intent.get("confidence", 0) - initial_intent.get("confidence", 0)
            )

            return refined_intent

        except Exception as e:
            logger.error("intent_refinement_failed", error=str(e))
            return initial_intent  # 返回原始意图作为回退

    def _apply_feedback(self, intent: Dict[str, Any], feedback: Dict[str, Any]) -> Dict[str, Any]:
        """
        应用用户反馈调整意图

        Args:
            intent: 当前意图
            feedback: 用户反馈

        Returns:
            调整后的意图
        """
        adjusted_intent = intent.copy()

        # 如果用户确认了特定意图
        if feedback.get("confirmed_intent"):
            confirmed_type = feedback["confirmed_intent"]
            try:
                intent_type = IntentType(confirmed_type)
                adjusted_intent["type"] = intent_type.value
                adjusted_intent["confidence"] = 0.9  # 用户确认后提高置信度
            except ValueError:
                logger.warning("invalid_confirmed_intent", confirmed_type=confirmed_type)

        # 如果用户提供了修正
        if feedback.get("correction"):
            correction = feedback["correction"]
            # 这里可以添加更复杂的修正逻辑
            adjusted_intent["user_correction"] = correction

        return adjusted_intent

    def get_supported_intents(self) -> List[Dict[str, Any]]:
        """
        获取支持的意图类型列表

        Returns:
            支持意图的详细信息
        """
        supported_intents = []
        for intent_type in IntentType:
            if intent_type != IntentType.UNKNOWN:
                keywords = self.INTENT_KEYWORDS.get(intent_type, [])
                supported_intents.append({
                    "type": intent_type.value,
                    "description": self._get_intent_description(intent_type),
                    "example_keywords": keywords[:5],  # 只显示前5个关键词作为示例
                    "common_use_cases": self._get_common_use_cases(intent_type)
                })

        return supported_intents

    def _get_intent_description(self, intent_type: IntentType) -> str:
        """获取意图描述"""
        descriptions = {
            IntentType.CREATE_DOCUMENT: "创建新的工艺文件",
            IntentType.EDIT_DOCUMENT: "编辑现有工艺文件",
            IntentType.REVIEW_DOCUMENT: "审核工艺文件",
            IntentType.GENERATE_DOCUMENT: "生成工艺文件输出",
            IntentType.PARSE_PDF: "解析PDF工艺文件",
            IntentType.SEARCH_KNOWLEDGE: "搜索工艺知识",
            IntentType.ALIGN_TERMINOLOGY: "对齐工艺术语",
            IntentType.CHECK_COMPLIANCE: "检查合规性",
            IntentType.EXPORT_TO_PDM: "导出到PDM系统",
            IntentType.DRAFT_COMPLETE: "基于初稿补全工艺文件"
        }
        return descriptions.get(intent_type, "未知意图")

    def _get_common_use_cases(self, intent_type: IntentType) -> List[str]:
        """获取常见用例"""
        use_cases = {
            IntentType.CREATE_DOCUMENT: [
                "为新零件创建工艺文件",
                "根据设计图纸制定工艺路线",
                "编写装配工艺规程"
            ],
            IntentType.EDIT_DOCUMENT: [
                "修改现有工序参数",
                "更新工艺文件版本",
                "调整加工顺序"
            ],
            IntentType.PARSE_PDF: [
                "从PDF工艺文件中提取表格数据",
                "识别工艺参数和工具信息",
                "解析工艺流程图"
            ],
            IntentType.DRAFT_COMPLETE: [
                "补全已有的工艺文件初稿",
                "基于标准完善初稿内容",
                "根据参考资料修改工艺文件"
            ]
        }
        return use_cases.get(intent_type, [])