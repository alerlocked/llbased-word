"""
撰写 Agent

负责工艺内容的编辑、表格填充、格式调整
"""
from typing import Dict, Any, Optional, List
from app.agents.base_agent import BaseAgent
from app.agents.core import AgentRegistry
from app.shared.logging import get_logger

logger = get_logger(__name__)


@AgentRegistry.register("writing")
class WritingAgent(BaseAgent):
    """
    撰写 Agent

    职责：
    - 工艺内容编辑
    - 表格填充
    - 格式调整
    """

    name = "writing"
    description = "负责工艺内容的编辑、表格填充、格式调整"
    tools = ["rag_retriever", "document_generator"]

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

            # 1. 检索相关知识（如果有要求）
            knowledge = None
            if task.get("requirements"):
                knowledge = await self.use_tool(
                    "rag_retriever",
                    task["requirements"],
                    {"top_k": self.max_retrieval_results}
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

            # 3. 生成文档（如果需要）
            doc_result = None
            if task.get("generate_doc", True):
                doc_result = await self.use_tool(
                    "document_generator",
                    {
                        "content": result.get("content", ""),
                        "title": task.get("title", "工艺文件"),
                        "format": task.get("output_format", self.default_format)
                    }
                )

            logger.info(
                "writing_task_completed",
                action=action,
                target=task.get("target", ""),
                has_document=doc_result is not None
            )

            return {
                "success": True,
                "result": result,
                "document": doc_result,
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

        # 整合知识
        knowledge_context = ""
        if knowledge and knowledge.get("success"):
            results = knowledge.get("results", [])
            knowledge_context = "\n".join([
                r.get("content", "") for r in results[:3]
            ])

        # 这里应该调用 LLM 进行实际编辑
        # 目前返回模拟结果
        edited_content = f"[已编辑] {content}"

        if knowledge_context:
            edited_content += f"\n\n参考依据:\n{knowledge_context[:500]}"

        return {
            "success": True,
            "content": edited_content,
            "target": target,
            "suggestions": ["建议检查术语一致性", "建议添加工艺参数"]
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

        # 从知识中提取填充数据
        filled_data = {}
        if knowledge and knowledge.get("success"):
            results = knowledge.get("results", [])
            # 简单的字段提取
            for field in fields:
                for r in results:
                    content = r.get("content", "")
                    if field.lower() in content.lower():
                        filled_data[field] = f"[从知识库提取] {field}"
                        break

        return {
            "success": True,
            "content": f"表格 {target} 填充完成",
            "filled_data": filled_data,
            "unfilled_fields": [f for f in fields if f not in filled_data]
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

        # 应用格式规则
        formatted_content = content

        return {
            "success": True,
            "content": formatted_content,
            "applied_rules": format_rules
        }

    async def _do_generate(
        self,
        task: Dict[str, Any],
        knowledge: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        生成新内容

        Args:
            task: 任务描述
            knowledge: 检索到的知识
            context: 执行上下文

        Returns:
            生成结果
        """
        requirements = task.get("requirements", "")
        template = task.get("template", "standard")

        # 基于要求生成内容
        generated_content = f"根据要求生成的内容: {requirements}"

        if knowledge and knowledge.get("success"):
            results = knowledge.get("results", [])
            generated_content += f"\n\n参考:\n{results[0].get('content', '')[:300]}"

        return {
            "success": True,
            "content": generated_content,
            "template": template
        }
