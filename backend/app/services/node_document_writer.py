"""
节点文档写入服务
负责生成、存储和检索节点文档
"""
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.database import NodeDocument
from app.services.context_engineering import get_ltm, LongTermMemory
from app.shared.logging import get_logger
logger = get_logger(__name__)
from app.database import SessionLocal


class NodeDocumentWriter:
    """
    节点文档写入器
    负责将节点输出写入数据库和LTM
    """
    
    def __init__(self, session_id: str):
        """
        初始化节点文档写入器
        
        Args:
            session_id: 会话ID
        """
        self.session_id = session_id
        self.ltm: Optional[LongTermMemory] = None
        logger.debug(f"📝 [NodeDocumentWriter] 初始化: session_id={session_id}")
    
    def _get_ltm(self) -> LongTermMemory:
        """获取LTM实例（延迟初始化）"""
        if self.ltm is None:
            self.ltm = get_ltm(self.session_id)
        return self.ltm
    
    def _generate_summary(self, node_name: str, node_type: str, document_data: Dict[str, Any]) -> str:
        """
        生成文档摘要（用于LTM语义检索）
        
        Args:
            node_name: 节点名称
            node_type: 节点类型
            document_data: 文档数据
            
        Returns:
            str: 文档摘要
        """
        summary_parts = [f"节点: {node_name} ({node_type})"]
        
        # 根据节点类型提取关键信息
        if node_type == "analysis":
            output = document_data.get("output", {})
            completeness = output.get("completeness_result", {})
            decision = output.get("decision", {})
            
            summary_parts.append(f"完整度: {completeness.get('completeness_score', 0):.2f}")
            summary_parts.append(f"决策: {decision.get('action', 'unknown')}")
            if output.get("solutions"):
                summary_parts.append(f"改进方案: {len(output.get('solutions', []))}个")
        
        elif node_type == "planning":
            output = document_data.get("output", {})
            plan_options = output.get("plan_options", [])
            if plan_options:
                summary_parts.append(f"计划选项: {len(plan_options)}个")
                for i, opt in enumerate(plan_options[:3], 1):
                    summary_parts.append(f"  选项{i}: {opt.get('title', '')}")
        
        elif node_type == "retrieval":
            output = document_data.get("output", {})
            materials = output.get("materials", {})
            if materials:
                total = sum(len(v) if isinstance(v, (list, dict)) else 1 for v in materials.values())
                summary_parts.append(f"检索素材: {total}个")
        
        elif node_type == "writing":
            output = document_data.get("output", {})
            content = output.get("content", "")
            if content:
                summary_parts.append(f"生成内容: {len(content)}字")
        
        elif node_type == "review":
            output = document_data.get("output", {})
            review = output.get("review", {})
            if review:
                score = review.get("overall_score", 0)
                summary_parts.append(f"质量评分: {score:.2f}")
        
        return "\n".join(summary_parts)
    
    def write_node_document(
        self,
        node_name: str,
        node_type: str,
        node_input: Optional[Dict[str, Any]] = None,
        node_output: Dict[str, Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        state: str = "IDLE",  # PR1 新增参数：节点状态
        options: Optional[List[str]] = None,  # PR1 新增参数：待选项列表
        extract_key_data_async: bool = True  # PR5 新增参数：是否异步提取 key_data
    ) -> str:
        """
        写入节点文档（PR5版本：支持延迟提取）
        
        Args:
            node_name: 节点名称（如analyze_node, planner_node）
            node_type: 节点类型（analysis, planning, retrieval, writing, review）
            node_input: 节点输入（可选）
            node_output: 节点输出（必需）
            metadata: 额外元数据（可选）
            state: 节点状态（如 "AWAITING_SOLUTION"、"AWAITING_PLAN"），默认 "IDLE"
            options: 待选项列表（如 ["sol_1", "sol_2"]），默认 None
            extract_key_data_async: 是否异步提取 key_data（默认 True），PR5 新增
            
        Returns:
            str: 文档ID
        """
        if node_output is None:
            node_output = {}
        
        # 构建文档数据
        document_data = {
            "node_name": node_name,
            "node_type": node_type,
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "input": node_input or {},
            "output": node_output,
            "metadata": metadata or {}
        }
        
        # 生成摘要
        summary = self._generate_summary(node_name, node_type, document_data)
        
        # 写入数据库
        db = SessionLocal()
        try:
            doc = NodeDocument(
                session_id=self.session_id,
                node_name=node_name,
                node_type=node_type,
                document_data=document_data,
                summary=summary,
                meta_data=metadata or {},
                state=state,  # PR1 新增：状态字段
                options=options,  # PR1 新增：选项字段
                key_data=None  # PR5 新增：延迟填充，不阻塞主流程
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            doc_id = str(doc.id)
            
            logger.info(
                f"💾 [NodeDocumentWriter] 写入节点文档: "
                f"node={node_name}, type={node_type}, state={state}, "
                f"options={len(options or [])}, id={doc_id}"
            )
            
            # 写入LTM（用于语义检索）
            ltm = self._get_ltm()
            ltm_metadata = {
                "type": "node_document",
                "node_name": node_name,
                "node_type": node_type,
                "document_id": doc_id,
                "session_id": self.session_id
            }
            ltm.write(summary, metadata=ltm_metadata)
            logger.debug(f"📚 [NodeDocumentWriter] 已写入LTM: {summary[:50]}...")
            
            # PR5：发布后台任务（不阻塞）
            if extract_key_data_async:
                try:
                    from app.tasks.extract_key_data_task import extract_key_data_task
                    extract_key_data_task.delay(int(doc_id))
                    logger.debug(f"📤 [NodeDocumentWriter] 已发布异步提取任务: doc_id={doc_id}")
                except Exception as e:
                    # 任务发布失败不影响主流程
                    logger.warning(
                        f"⚠️ [NodeDocumentWriter] 发布异步任务失败: {str(e)}，"
                        f"key_data 将保持为 None"
                    )
            
            return doc_id
            
        except Exception as e:
            db.rollback()
            logger.error("❌ [NodeDocumentWriter] 写入节点文档失败: %s", str(e))
            raise
        finally:
            db.close()
    
    def get_node_documents(
        self,
        node_types: Optional[List[str]] = None,
        node_names: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        从数据库读取节点文档
        
        Args:
            node_types: 节点类型过滤（可选）
            node_names: 节点名称过滤（可选）
            limit: 返回数量限制（可选）
            
        Returns:
            List[Dict[str, Any]]: 文档列表
        """
        db = SessionLocal()
        try:
            query = db.query(NodeDocument).filter(
                NodeDocument.session_id == self.session_id
            )
            
            if node_types:
                query = query.filter(NodeDocument.node_type.in_(node_types))
            
            if node_names:
                query = query.filter(NodeDocument.node_name.in_(node_names))
            
            query = query.order_by(desc(NodeDocument.created_at))
            
            if limit:
                query = query.limit(limit)
            
            docs = query.all()
            
            result = []
            for doc in docs:
                result.append({
                    "id": doc.id,
                    "session_id": doc.session_id,
                    "node_name": doc.node_name,
                    "node_type": doc.node_type,
                    "document_data": doc.document_data,
                    "summary": doc.summary,
                    "metadata": doc.meta_data,  # 返回时使用metadata字段名保持API兼容
                    "created_at": doc.created_at.isoformat() if doc.created_at else None
                })
            
            logger.debug(
                f"📖 [NodeDocumentWriter] 读取节点文档: "
                f"session={self.session_id}, count={len(result)}"
            )
            
            return result
            
        except Exception as e:
            logger.error("❌ [NodeDocumentWriter] 读取节点文档失败: %s", str(e))
            raise
        finally:
            db.close()
    
    def get_node_document_by_ltm(
        self,
        query: str,
        node_types: Optional[List[str]] = None,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        从LTM语义检索节点文档
        
        Args:
            query: 查询文本
            node_types: 节点类型过滤（可选）
            top_k: 返回Top-K结果
            
        Returns:
            List[Dict[str, Any]]: 文档列表（按相似度排序）
        """
        try:
            ltm = self._get_ltm()
            
            # 从LTM检索相关记忆
            ltm_results = ltm.retrieve(query, top_k=top_k * 2)  # 多检索一些，后续过滤
            
            # 过滤出节点文档类型的记忆
            node_doc_ids = []
            for mem in ltm_results:
                mem_metadata = mem.get("metadata", {})
                if mem_metadata.get("type") == "node_document":
                    # 检查节点类型过滤
                    if node_types and mem_metadata.get("node_type") not in node_types:
                        continue
                    doc_id = mem_metadata.get("document_id")
                    if doc_id:
                        node_doc_ids.append(doc_id)
            
            if not node_doc_ids:
                logger.debug(f"🔍 [NodeDocumentWriter] LTM检索未找到节点文档")
                return []
            
            # 从数据库读取完整文档
            db = SessionLocal()
            try:
                docs = db.query(NodeDocument).filter(
                    NodeDocument.id.in_(node_doc_ids),
                    NodeDocument.session_id == self.session_id
                ).all()
                
                # 按LTM检索顺序排序
                id_to_doc = {str(doc.id): doc for doc in docs}
                result = []
                for doc_id in node_doc_ids[:top_k]:
                    if doc_id in id_to_doc:
                        doc = id_to_doc[doc_id]
                        result.append({
                            "id": doc.id,
                            "session_id": doc.session_id,
                            "node_name": doc.node_name,
                            "node_type": doc.node_type,
                            "document_data": doc.document_data,
                            "summary": doc.summary,
                            "metadata": doc.meta_data,  # 返回时使用metadata字段名保持API兼容
                            "created_at": doc.created_at.isoformat() if doc.created_at else None
                        })
                
                logger.info(
                    f"🔍 [NodeDocumentWriter] LTM检索节点文档: "
                    f"query={query[:30]}..., found={len(result)}"
                )
                
                return result
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error("❌ [NodeDocumentWriter] LTM检索节点文档失败: %s", str(e))
            return []
    
    def get_latest_document(
        self,
        node_name: Optional[str] = None,
        node_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取最新的节点文档
        
        Args:
            node_name: 节点名称（可选）
            node_type: 节点类型（可选）
            
        Returns:
            Optional[Dict[str, Any]]: 最新文档，如果不存在返回None
        """
        filters = {}
        if node_name:
            filters["node_names"] = [node_name]
        if node_type:
            filters["node_types"] = [node_type]
        
        docs = self.get_node_documents(**filters, limit=1)
        return docs[0] if docs else None
    
    def get_current_state(self) -> Optional[str]:
        """
        获取当前会话的状态（PR1新增）
        
        Returns:
            当前状态（如 "AWAITING_SOLUTION"、"AWAITING_PLAN"），如果没有文档返回 None
        """
        db = SessionLocal()
        try:
            latest_doc = db.query(NodeDocument).filter(
                NodeDocument.session_id == self.session_id
            ).order_by(desc(NodeDocument.created_at)).first()
            
            if latest_doc:
                logger.debug(
                    f"📖 [NodeDocumentWriter] 当前状态: "
                    f"session={self.session_id}, state={latest_doc.state}"
                )
                return latest_doc.state
            
            return None
        except Exception as e:
            logger.error("❌ [NodeDocumentWriter] 获取当前状态失败: %s", str(e))
            return None
        finally:
            db.close()
    
    def get_awaiting_options(self) -> Optional[List[str]]:
        """
        获取等待选择的选项列表（PR1新增）
        
        Returns:
            选项ID列表（如 ["plan_1", "plan_2"]），如果没有返回 None
        """
        db = SessionLocal()
        try:
            latest_doc = db.query(NodeDocument).filter(
                NodeDocument.session_id == self.session_id,
                NodeDocument.state.in_(["AWAITING_SOLUTION", "AWAITING_PLAN"])
            ).order_by(desc(NodeDocument.created_at)).first()
            
            if latest_doc and latest_doc.options:
                logger.debug(
                    f"📖 [NodeDocumentWriter] 等待选项: "
                    f"session={self.session_id}, options={latest_doc.options}"
                )
                return latest_doc.options
            
            return None
        except Exception as e:
            logger.error("❌ [NodeDocumentWriter] 获取等待选项失败: %s", str(e))
            return None
        finally:
            db.close()
    
    def get_key_data(self, node_type: str, path: str = None, default: Any = None) -> Any:
        """
        获取结构化关键数据（PR5：无降级，直接返回）
        
        Args:
            node_type: 节点类型
            path: 数据路径（如 "selections.selected_plan_id"），None 返回完整数据
            default: 默认值（key_data 不存在时返回）
        
        Returns:
            关键数据（完整或指定路径的值），不存在时返回 default
        """
        db = SessionLocal()
        try:
            # 获取最新文档
            latest_doc = db.query(NodeDocument).filter(
                NodeDocument.session_id == self.session_id,
                NodeDocument.node_type == node_type
            ).order_by(desc(NodeDocument.created_at)).first()
            
            if not latest_doc or not latest_doc.key_data:
                # 无降级：直接返回默认值
                logger.debug(
                    f"📖 [NodeDocumentWriter] key_data 不存在: "
                    f"session={self.session_id}, node_type={node_type}"
                )
                return default
            
            # 获取数据（支持嵌套路径）
            data = latest_doc.key_data
            if path:
                return self._get_nested_value(data, path, default)
            return data
            
        except Exception as e:
            logger.error(f"❌ [NodeDocumentWriter] 获取关键数据失败: {str(e)}")
            return default
        finally:
            db.close()
    
    def _get_nested_value(self, data: Dict, path: str, default: Any = None) -> Any:
        """
        获取嵌套值（如 "selections.selected_plan_id"）
        
        Args:
            data: 数据字典
            path: 路径（用 "." 分隔）
            default: 默认值
        
        Returns:
            嵌套值或默认值
        """
        keys = path.split(".")
        current = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    return default
            else:
                return default
        return current
