"""
会话管理服务
负责对话会话的创建、保存、恢复等操作
"""
import uuid
import json
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from typing import TypedDict, Optional, Dict, Any
from app.shared.logging import get_logger
logger = get_logger(__name__)
from app.models.database import ConversationSession
from app.services.context_engineering import get_ltm
from app.services.memory_service import MemoryService
from app.config import settings


# GraphState type alias - conversation state dict
class GraphState(TypedDict, total=False):
    user_input: str
    user_id: Optional[int]
    project_id: Optional[int]
    session_id: str
    plan: Optional[Any]
    materials: Dict[str, Any]
    content: str
    review: Dict[str, Any]
    current_step: str
    intermediate_steps: list
    conversation_history: list
    pending_questions: list
    user_confirmations: Dict[str, Any]
    reference_texts: list
    style_profile: Optional[Any]
    business_scenario: Optional[Any]
    plan_options: list
    material_report: Optional[Any]
    review_suggestions: Optional[Any]
    shared_knowledge: Dict[str, Any]
    knowledge_version: Dict[str, Any]
    knowledge_update_history: list
    agent_commands: list
    command_results: Dict[str, Any]
    call_stack: list
    improvement_solutions: list
    selected_solutions: list
    todo_items: list
    completed_todo_ids: list


class ConversationService:
    """会话管理服务类"""
    
    def create_session(
        self,
        db: Session,
        user_id: Optional[int] = None,
        project_id: Optional[int] = None,
        initial_state: Optional[Dict[str, Any]] = None
    ) -> ConversationSession:
        """
        创建新会话
        
        Args:
            db: 数据库会话
            user_id: 用户ID（可选）
            project_id: 项目ID（可选）
            initial_state: 初始状态数据（可选）
            
        Returns:
            ConversationSession: 创建的会话对象
        """
        try:
            # 生成唯一会话ID
            session_id = str(uuid.uuid4())
            
            # 处理特殊类型（如 TaskPlan）的序列化
            state_data = initial_state.copy() if initial_state else {}
            if "plan" in state_data and state_data["plan"] is not None:
                plan = state_data["plan"]
                if hasattr(plan, "model_dump"):
                    state_data["plan"] = plan.model_dump()
                elif hasattr(plan, "dict"):
                    state_data["plan"] = plan.dict()
            
            # 创建会话对象
            session = ConversationSession(
                user_id=user_id,
                project_id=project_id,
                session_id=session_id,
                current_step="initialized",
                state_data=state_data
            )
            
            db.add(session)
            db.commit()
            db.refresh(session)
            
            logger.info(f"✅ 创建新会话: {session_id} (user_id={user_id}, project_id={project_id})")
            return session
            
        except IntegrityError as e:
            db.rollback()
            logger.error(f"❌ 创建会话失败（唯一性冲突）: {str(e)}")
            # 如果session_id冲突，重试一次
            return self.create_session(db, user_id, project_id, initial_state)
        except Exception as e:
            db.rollback()
            logger.error(f"❌ 创建会话失败: {str(e)}")
            raise
    
    def get_session(
        self,
        db: Session,
        session_id: str
    ) -> Optional[ConversationSession]:
        """
        获取会话状态
        
        Args:
            db: 数据库会话
            session_id: 会话ID
            
        Returns:
            ConversationSession: 会话对象，如果不存在返回None
        """
        try:
            session = db.query(ConversationSession).filter(
                ConversationSession.session_id == session_id
            ).first()
            
            if session:
                logger.debug(f"📖 获取会话: {session_id} (step={session.current_step})")
            else:
                logger.warning(f"⚠️ 会话不存在: {session_id}")
            
            return session
            
        except Exception as e:
            logger.error(f"❌ 获取会话失败: {str(e)}")
            return None
    
    def update_session(
        self,
        db: Session,
        session_id: str,
        current_step: Optional[str] = None,
        state_data: Optional[Dict[str, Any]] = None
    ) -> Optional[ConversationSession]:
        """
        更新会话状态
        
        Args:
            db: 数据库会话
            session_id: 会话ID
            current_step: 当前步骤（可选）
            state_data: 状态数据（可选，会与现有数据合并）
            
        Returns:
            ConversationSession: 更新后的会话对象，如果不存在返回None
        """
        try:
            session = self.get_session(db, session_id)
            if not session:
                return None
            
            # 更新当前步骤
            if current_step is not None:
                session.current_step = current_step
            
            # 更新状态数据（合并而非替换）
            if state_data is not None:
                if session.state_data:
                    session.state_data = {**session.state_data, **state_data}
                else:
                    session.state_data = state_data
            
            db.commit()
            db.refresh(session)
            
            logger.info(f"✅ 更新会话: {session_id} (step={session.current_step})")
            return session
            
        except Exception as e:
            db.rollback()
            logger.error(f"❌ 更新会话失败: {str(e)}")
            return None
    
    def save_state(
        self,
        db: Session,
        session_id: str,
        state: GraphState
    ) -> bool:
        """
        持久化 GraphState 到数据库
        
        Args:
            db: 数据库会话
            session_id: 会话ID
            state: GraphState 状态对象
            
        Returns:
            bool: 是否保存成功
        """
        try:
            session = self.get_session(db, session_id)
            if not session:
                logger.warning(f"⚠️ 会话不存在，无法保存状态: {session_id}")
                return False
            
            # 将 GraphState 转换为字典
            # 注意：TypedDict 可以直接转换为 dict
            state_dict = dict(state)
            
            # 处理特殊类型（如 TaskPlan）
            if state_dict.get("plan"):
                plan = state_dict["plan"]
                if hasattr(plan, "model_dump"):
                    state_dict["plan"] = plan.model_dump()
                elif hasattr(plan, "dict"):
                    state_dict["plan"] = plan.dict()
            
            # 保存到数据库
            session.state_data = state_dict
            session.current_step = state.get("current_step", "unknown")
            
            db.commit()
            db.refresh(session)
            
            logger.info(f"✅ 保存状态到会话: {session_id} (step={session.current_step})")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"❌ 保存状态失败: {str(e)}")
            return False
    
    def save_state_with_context_engineering(
        self,
        db: Session,
        session_id: str,
        state: GraphState
    ) -> bool:
        """
        持久化状态并应用上下文工程逻辑
        
        检测关键决策点并自动写入LTM，更新上下文选择器的短期记忆（STM）
        
        Args:
            db: 数据库会话
            session_id: 会话ID
            state: GraphState 状态对象
            
        Returns:
            bool: 是否保存成功
        """
        try:
            # 1. 先保存状态（复用原有逻辑）
            if not self.save_state(db, session_id, state):
                return False
            
            # 2. 获取LTM实例
            ltm = get_ltm(session_id)
            
            # 3. 检测关键决策点并写入LTM
            conversation_history = state.get("conversation_history", [])
            user_input = state.get("user_input", "")
            
            # 检查是否应该写入LTM
            if user_input:
                should_write, reason = ltm.should_write(user_input, conversation_history)
                if should_write:
                    # 提取元数据
                    metadata = {
                        "user_id": state.get("user_id"),
                        "project_id": state.get("project_id"),
                        "current_step": state.get("current_step"),
                        "trigger_reason": reason
                    }
                    
                    # 写入LTM
                    memory_id = ltm.write(user_input, metadata)
                    if memory_id:
                        logger.info(f"💾 [ConversationService] 写入LTM: memory_id={memory_id}, reason={reason}")
            
            # 4. 检查改进方案选择（也属于关键决策点）
            selected_solutions = state.get("selected_solutions", [])
            improvement_solutions = state.get("improvement_solutions", [])
            
            if selected_solutions and improvement_solutions:
                # 提取选中的方案信息
                selected_data = [
                    sol for sol in improvement_solutions
                    if sol.get("id") in selected_solutions
                ]
                
                if selected_data:
                    solution_text = f"用户选择的方案: {', '.join([sol.get('title', '') for sol in selected_data])}"
                    metadata = {
                        "user_id": state.get("user_id"),
                        "project_id": state.get("project_id"),
                        "type": "solution_selection",
                        "selected_ids": selected_solutions
                    }
                    ltm.write(solution_text, metadata)
                    logger.info(f"💾 [ConversationService] 写入方案选择到LTM: {selected_solutions}")

            # 5. Save session summary for cross-session memory
            if conversation_history:
                self._save_session_summary(session_id, conversation_history)

            return True
            
        except Exception as e:
            logger.error(f"❌ 保存状态（上下文工程）失败: {str(e)}")
            return False

    def _save_session_summary(
        self,
        session_id: str,
        conversation_history: list,
    ) -> None:
        """Save a brief summary of the conversation to MemoryService.

        Called after every save_state_with_context_engineering so that
        cross-session memory is always up to date.
        """
        try:
            memory_dir = str(settings.DATA_DIR / "memory")
            memory_service = MemoryService(memory_dir)

            # Build summary from last few turns
            recent = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
            summary_lines = []
            for msg in recent:
                role = msg.get("role", "unknown") if isinstance(msg, dict) else "unknown"
                content = msg.get("content", "")[:200] if isinstance(msg, dict) else str(msg)[:200]
                role_label = "用户" if role == "user" else "助手"
                summary_lines.append(f"{role_label}: {content}")
            summary = "\n".join(summary_lines)

            memory_service.save_summary(session_id=session_id, summary=summary)
        except Exception as e:
            logger.warning(f"[ConversationService] Session summary save skipped: {e}")

    def restore_state(
        self,
        db: Session,
        session_id: str
    ) -> Optional[GraphState]:
        """
        从数据库恢复 GraphState
        
        Args:
            db: 数据库会话
            session_id: 会话ID
            
        Returns:
            GraphState: 恢复的状态对象，如果不存在返回None
        """
        try:
            session = self.get_session(db, session_id)
            if not session or not session.state_data:
                logger.warning(f"⚠️ 会话不存在或状态为空: {session_id}")
                return None
            
            # 从数据库恢复状态数据
            state_dict = session.state_data.copy()
            
            # 恢复 TaskPlan 对象（如果存在）
            if state_dict.get("plan"):
                from app.models.schemas import TaskPlan
                try:
                    state_dict["plan"] = TaskPlan(**state_dict["plan"])
                except Exception as e:
                    logger.warning(f"⚠️ 恢复 TaskPlan 失败: {str(e)}")
                    state_dict["plan"] = None
            
            # 确保所有必需字段存在
            default_state: GraphState = {
                "user_input": "",
                "user_id": None,
                "project_id": None,
                "session_id": session_id,  # 添加session_id到默认状态
                "plan": None,
                "materials": {},
                "content": "",
                "review": {},
                "current_step": "restored",
                "intermediate_steps": [],
                "conversation_history": [],
                "pending_questions": [],
                "user_confirmations": {},
                "reference_texts": [],
                "style_profile": None,
                "business_scenario": None,
                "plan_options": [],
                "material_report": None,
                "review_suggestions": None,
                # 新增：共享知识库（参考OpenDraft）
                "shared_knowledge": {},
                "knowledge_version": {},
                "knowledge_update_history": [],
                # 新增：Agent调用机制（使用Command模式）
                "agent_commands": [],
                "command_results": {},
                "call_stack": [],
                # 新增：改进方案和待办事项（修复：恢复状态时需要这些字段）
                "improvement_solutions": [],
                "selected_solutions": [],
                "todo_items": [],
                "completed_todo_ids": []
            }
            
            # 合并恢复的数据
            restored_state = {**default_state, **state_dict}
            
            logger.info(f"✅ 恢复会话状态: {session_id} (step={restored_state.get('current_step')})")
            return restored_state
            
        except Exception as e:
            logger.error(f"❌ 恢复状态失败: {str(e)}")
            return None
    
    def delete_session(
        self,
        db: Session,
        session_id: str
    ) -> bool:
        """
        删除会话
        
        Args:
            db: 数据库会话
            session_id: 会话ID
            
        Returns:
            bool: 是否删除成功
        """
        try:
            session = self.get_session(db, session_id)
            if not session:
                return False
            
            db.delete(session)
            db.commit()
            
            logger.info(f"✅ 删除会话: {session_id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"❌ 删除会话失败: {str(e)}")
            return False


# 全局服务实例
_conversation_service: Optional[ConversationService] = None


def get_conversation_service() -> ConversationService:
    """
    获取会话管理服务实例（单例模式）
    
    Returns:
        ConversationService: 会话管理服务实例
    """
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service

