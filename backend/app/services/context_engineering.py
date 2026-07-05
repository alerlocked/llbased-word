"""
上下文工程核心模块
基于Manus方案的四层架构：写、选、压、隔
作为项目的底层基础设施，提供上下文管理能力

支持LangChain架构，提供BaseMemory、BaseRetriever、BaseTool兼容接口
"""
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime
import json
import re

from app.shared.logging import get_logger
logger = get_logger(__name__)
from app.config import settings

# LangChain兼容性导入（可选，如果未安装LangChain则使用适配器模式）
try:
    from langchain.memory import BaseMemory
    from langchain_core.memory import BaseChatMessageHistory
    LANGCHAIN_AVAILABLE = True
except ImportError:
    try:
        from langchain_core.memory import BaseMemory
        LANGCHAIN_AVAILABLE = True
    except ImportError:
        # 定义抽象基类作为适配器
        class BaseMemory:
            """BaseMemory适配器（LangChain未安装时使用）"""
            pass
        LANGCHAIN_AVAILABLE = False

try:
    from langchain.retrievers import BaseRetriever
    from langchain_core.documents import Document
    LANGCHAIN_RETRIEVER_AVAILABLE = True
except ImportError:
    try:
        from langchain_core.retrievers import BaseRetriever
        from langchain_core.documents import Document
        LANGCHAIN_RETRIEVER_AVAILABLE = True
    except ImportError:
        # 定义Document和BaseRetriever适配器
        class Document:
            """Document适配器"""
            def __init__(self, page_content: str, metadata: Dict[str, Any] = None):
                self.page_content = page_content
                self.metadata = metadata or {}
        
        class BaseRetriever:
            """BaseRetriever适配器（LangChain未安装时使用）"""
            pass
        LANGCHAIN_RETRIEVER_AVAILABLE = False

try:
    from langchain.chains import LLMChain
    from langchain.prompts import PromptTemplate
    LANGCHAIN_CHAIN_AVAILABLE = True
except ImportError:
    class LLMChain:
        """LLMChain适配器（LangChain未安装时使用）"""
        pass
    class PromptTemplate:
        """PromptTemplate适配器（LangChain未安装时使用）"""
        pass
    LANGCHAIN_CHAIN_AVAILABLE = False

# Embedding服务（延迟初始化，已废弃，改用直接HTTP调用）
_embedding_service = None

# HTTP客户端（用于直接调用硅基流动API）
import requests

# numpy（延迟导入，用于相似度计算）
_numpy_available = None


def _check_numpy():
    """检查numpy是否可用"""
    global _numpy_available
    if _numpy_available is None:
        try:
            import numpy as np
            _numpy_available = True
        except ImportError:
            _numpy_available = False
    return _numpy_available

# Token计数服务（延迟初始化）
_token_counter = None


def _get_token_counter():
    """
    获取Token计数器（单例模式，延迟初始化）
    
    Returns:
        tiktoken.Encoding: Token编码器
    """
    global _token_counter
    if _token_counter is None:
        try:
            import tiktoken
            # 使用cl100k_base编码（GPT-4/Qwen等模型使用）
            _token_counter = tiktoken.get_encoding("cl100k_base")
            logger.info("✅ [ContextEngineering] 初始化Token计数器: cl100k_base")
        except ImportError:
            logger.warning("⚠️ [ContextEngineering] tiktoken未安装，Token计数功能受限")
            _token_counter = None
        except Exception as e:
            logger.error(f"❌ [ContextEngineering] Token计数器初始化失败: {str(e)}")
            _token_counter = None
    return _token_counter


def count_tokens(text: str) -> int:
    """
    计算文本的Token数量
    
    Args:
        text: 输入文本
        
    Returns:
        int: Token数量（如果计数失败，使用字符数/4估算）
    """
    tokenizer = _get_token_counter()
    if tokenizer is None:
        raise ValueError("Token计数器不可用")
    
    tokens = tokenizer.encode(text)
    return len(tokens)


def _get_embedding_service():
    """
    获取Embedding服务实例（已废弃，保留用于兼容性检查）
    
    注意：现在直接使用HTTP调用硅基流动API，不再使用LangChain包装
    
    Returns:
        None（已废弃）
    """
    # 此函数已废弃，保留仅用于兼容性检查
    return None


def calculate_embedding(text: str, max_retries: int = 3, retry_delay: float = 1.0) -> Optional[List[float]]:
    """
    计算文本的embedding向量（直接调用硅基流动API，带重试机制）
    
    根据硅基流动官方文档：https://docs.siliconflow.cn/cn/api-reference/embeddings/create-embeddings
    使用REST API直接调用，不再依赖LangChain包装
    
    Args:
        text: 输入文本（字符串）
        max_retries: 最大重试次数（默认3次）
        retry_delay: 重试延迟（秒，默认1.0秒）
        
    Returns:
        List[float]: embedding向量，失败返回None
    """
    import time
    
    # 空文本检查
    if not text or not text.strip():
        logger.warning("⚠️ [ContextEngineering] 输入文本为空，跳过Embedding计算")
        return None
    
    # 检查API Key是否配置
    if not settings.SILICONFLOW_API_KEY:
        logger.warning("⚠️ [ContextEngineering] SILICONFLOW_API_KEY 未配置，Embedding功能将不可用")
        return None
    
    # 构建API请求URL和headers
    api_url = f"{settings.SILICONFLOW_BASE_URL}/embeddings"
    headers = {
        "Authorization": f"Bearer {settings.SILICONFLOW_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 构建请求体（根据官方文档格式）
    payload = {
        "model": settings.SILICONFLOW_EMBEDDING_MODEL,
        "input": text,
        "encoding_format": "float"  # 返回float格式的embedding向量
    }
    
    # 重试机制
    last_error = None
    for attempt in range(max_retries):
        try:
            # 发送POST请求到硅基流动API
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=30  # 30秒超时
            )
            
            # 检查HTTP状态码
            if response.status_code == 200:
                result = response.json()
                
                # 解析响应（根据官方文档格式）
                if "data" in result and len(result["data"]) > 0:
                    embedding = result["data"][0].get("embedding")
                    if embedding and isinstance(embedding, list) and len(embedding) > 0:
                        if attempt > 0:
                            logger.info(f"✅ [ContextEngineering] Embedding计算成功（第{attempt + 1}次尝试），维度={len(embedding)}")
                        else:
                            logger.debug(f"✅ [ContextEngineering] Embedding计算成功，维度={len(embedding)}")
                        return embedding
                    else:
                        logger.warning(f"⚠️ [ContextEngineering] Embedding返回空结果（第{attempt + 1}次尝试）")
                else:
                    logger.warning(f"⚠️ [ContextEngineering] API响应格式异常（第{attempt + 1}次尝试）: {result}")
            elif response.status_code == 401:
                # 认证失败，不需要重试
                logger.error(f"❌ [ContextEngineering] Embedding认证失败（API Key无效）: {response.text[:200]}")
                return None
            elif response.status_code == 400:
                # 请求参数错误，不需要重试
                logger.error(f"❌ [ContextEngineering] Embedding请求参数错误: {response.text[:200]}")
                return None
            elif response.status_code == 429:
                # 速率限制，需要重试
                error_msg = f"速率限制（429）: {response.text[:200]}"
                logger.warning(f"⏱️ [ContextEngineering] {error_msg}（第{attempt + 1}次尝试）")
                last_error = Exception(error_msg)
            elif response.status_code >= 500:
                # 服务端错误，需要重试
                error_msg = f"服务端错误（{response.status_code}）: {response.text[:200]}"
                logger.warning(f"⚠️ [ContextEngineering] {error_msg}（第{attempt + 1}次尝试）")
                last_error = Exception(error_msg)
            else:
                # 其他错误
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.error(f"❌ [ContextEngineering] Embedding请求失败（第{attempt + 1}次尝试）: {error_msg}")
                last_error = Exception(error_msg)
                
        except requests.exceptions.Timeout:
            error_msg = "请求超时"
            logger.warning(f"⏱️ [ContextEngineering] Embedding请求超时（第{attempt + 1}次尝试）")
            last_error = Exception(error_msg)
        except requests.exceptions.ConnectionError:
            error_msg = "网络连接错误"
            logger.warning(f"🌐 [ContextEngineering] Embedding网络连接错误（第{attempt + 1}次尝试）")
            last_error = Exception(error_msg)
        except Exception as e:
            last_error = e
            error_msg = str(e)
            
            # 详细错误日志（仅第一次和最后一次尝试）
            if attempt == 0 or attempt == max_retries - 1:
                logger.error(f"❌ [ContextEngineering] Embedding计算失败（第{attempt + 1}次尝试）: {error_msg[:200]}")
        
        # 如果不是最后一次尝试，等待后重试（指数退避）
        if attempt < max_retries - 1 and last_error:
            wait_time = retry_delay * (attempt + 1)  # 指数退避：1s, 2s, 3s...
            logger.debug(f"⏳ [ContextEngineering] 等待{wait_time:.1f}秒后重试...")
            time.sleep(wait_time)
    
    # 所有重试都失败
    if last_error:
        logger.error(f"❌ [ContextEngineering] Embedding计算最终失败（已重试{max_retries}次）: {str(last_error)[:200]}")
    return None


def calculate_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """
    计算两个embedding向量的余弦相似度
    
    Args:
        embedding1: 第一个embedding向量
        embedding2: 第二个embedding向量
        
    Returns:
        float: 余弦相似度（0-1之间）
    """
    try:
        if _check_numpy():
            import numpy as np
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # 计算余弦相似度
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            # 确保结果在0-1之间
            return float(max(0.0, min(1.0, similarity)))
        else:
            raise ValueError("numpy不可用，无法计算余弦相似度")
    except Exception as e:
        logger.error(f"❌ [ContextEngineering] 相似度计算失败: {str(e)}")
        return 0.0


class LongTermMemory(BaseMemory if LANGCHAIN_AVAILABLE else object):
    """
    长期记忆（LTM）- 写入层
    主题化长期记忆存储，用于存储关键决策点、用户偏好等信息
    
    简化版：使用关键词匹配进行主题提取和相似度判断
    
    支持LangChain BaseMemory接口（可选）：
    - save_context: 保存上下文
    - load_memory_variables: 加载记忆变量
    - clear: 清除记忆
    """
    
    def __setattr__(self, name, value):
        # memories/session_id are injected via object.__setattr__ to bypass
        # pydantic v1 BaseMemory field validation; route any later assignment
        # the same way so callers can do `ltm.memories = [...]` without crashing.
        if name in ("memories", "session_id"):
            object.__setattr__(self, name, value)
        else:
            super().__setattr__(name, value)

    def __init__(self, session_id: str):
        """
        初始化长期记忆
        
        Args:
            session_id: 会话ID，用于隔离不同会话的长期记忆
        """
        # 如果是BaseMemory的子类，尝试调用父类初始化
        # 但BaseMemory可能是Pydantic模型，不允许任意字段，所以使用object.__setattr__绕过验证
        if LANGCHAIN_AVAILABLE:
            try:
                if issubclass(type(self), BaseMemory):
                    try:
                        super().__init__()
                    except Exception as e:
                        # 如果父类初始化失败（可能是字段验证问题），继续执行
                        logger.debug(f"⚠️ [LTM] BaseMemory初始化跳过: {str(e)}")
            except Exception:
                # 如果检查失败，继续执行
                pass
        
        # 使用object.__setattr__绕过可能的Pydantic字段验证
        object.__setattr__(self, 'session_id', session_id)
        object.__setattr__(self, 'memories', [])
        logger.info(f"📚 [LTM] 初始化长期记忆: session_id={session_id}")
    
    def should_write(self, content: str, conversation_history: List[Dict[str, str]]) -> Tuple[bool, str]:
        """
        判断是否应该写入LTM
        
        触发条件：
        1. 用户明确说"记住..."
        2. 关键决策点（"决定采用方案X"、"选择方案X"等）
        3. 对话中出现重复确认的信息（>2次）
        
        Args:
            content: 当前内容
            conversation_history: 对话历史
            
        Returns:
            Tuple[bool, str]: (是否应该写入, 触发原因)
        """
        # 检查用户明确说"记住..."
        remember_keywords = ["记住", "记下", "保存", "记录"]
        if any(keyword in content for keyword in remember_keywords):
            return True, "用户明确要求记住"
        
        # 检查关键决策点
        decision_keywords = ["决定采用", "选择方案", "采用方案", "决定使用", "确定使用"]
        if any(keyword in content for keyword in decision_keywords):
            return True, "检测到关键决策点"
        
        # 检查重复确认（简化版：检查最近3轮对话中是否出现相同关键词）
        if len(conversation_history) >= 6:  # 至少3轮对话
            recent_messages = [msg.get("content", "") for msg in conversation_history[-6:]]
            # 提取关键词（简单版本：取前10个字）
            if len(content) > 10:
                key_phrase = content[:10]
                count = sum(1 for msg in recent_messages if key_phrase in msg)
                if count >= 2:  # 出现2次以上
                    return True, "检测到重复确认（>2次）"
        
        return False, ""
    
    def write(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        写入长期记忆（改进版：存储embedding，使用语义去重）
        
        Args:
            content: 要存储的内容
            metadata: 可选的元数据（主题、标签等）
            
        Returns:
            str: 记忆ID
        """
        # 提取主题（简化版：使用关键词匹配）
        topic = self._extract_topic(content)
        
        # 计算并存储embedding（用于语义检索和去重）
        embedding = calculate_embedding(content)
        
        memory = {
            "id": f"mem_{len(self.memories)}",
            "content": content,
            "topic": topic,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
            "embedding": embedding  # 存储embedding向量
        }
        
        # 检查去重（使用语义相似度）
        if not self._is_duplicate(memory):
            self.memories.append(memory)
            # Persist to ChromaDB for cross-session durability
            self._persist_to_chroma(memory)
            logger.info(f"💾 [LTM] 写入长期记忆: topic={topic}, id={memory['id']}, embedding={'已计算' if embedding else '未计算'}")
            return memory["id"]
        else:
            logger.debug(f"⏭️ [LTM] 跳过重复记忆: topic={topic}")
            return ""
    
    def _extract_topic(self, content: str) -> str:
        """
        提取主题（简化版：使用关键词匹配）
        
        Args:
            content: 内容
            
        Returns:
            str: 主题
        """
        # 简化版：取前30个字符作为主题
        if len(content) <= 30:
            return content
        return content[:30] + "..."
    
    def _persist_to_chroma(self, memory: Dict[str, Any]) -> None:
        """
        Persist a memory entry for cross-session durability.

        VectorStore (ChromaDB) backend removed in retrieval cleanup.
        Currently a no-op; memories live only in-process. Reintroduce a
        durable backend in Step F if cross-session LTM is needed.
        """
        return

    def _is_duplicate(self, memory: Dict[str, Any]) -> bool:
        """
        Check if memory is a duplicate.

        Uses embedding similarity when available, falls back to text overlap.
        """
        content = memory.get("content", "")
        new_embedding = memory.get("embedding")

        similarity_threshold = getattr(settings, 'CONTEXT_SEMANTIC_DEDUP_THRESHOLD', 0.85)

        for existing in self.memories:
            existing_content = existing.get("content", "")

            # Fast path: exact match
            if content == existing_content:
                return True

            # Semantic similarity if embeddings available
            existing_embedding = existing.get("embedding")
            if new_embedding and existing_embedding:
                similarity = calculate_similarity(new_embedding, existing_embedding)
                if similarity > similarity_threshold:
                    logger.debug(f"[LTM] Semantic dedup: similarity={similarity:.3f}")
                    return True

            # Fallback: text overlap when no embeddings
            if not new_embedding or not existing_embedding:
                if len(content) > 10 and content[:10] in existing_content:
                    return True

        return False
    
    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        检索相关记忆（使用Embedding语义搜索）

        Args:
            query: 查询内容
            top_k: 返回Top-K结果

        Returns:
            List[Dict[str, Any]]: 相关记忆列表
        """
        if not self.memories:
            return []

        # Use Embedding for semantic search
        query_embedding = calculate_embedding(query)
        if not query_embedding:
            logger.warning(f"[LTM] Embedding unavailable, falling back to keyword retrieval")
            return self._retrieve_by_keywords(query, top_k)

        # Use stored embeddings where available, avoid N+1 API calls
        results: List[Dict[str, Any]] = []
        for memory in self.memories:
            memory_embedding = memory.get("embedding")
            if not memory_embedding:
                # Only compute if not already stored
                memory_text = f"{memory['topic']} {memory['content']}"
                memory_embedding = calculate_embedding(memory_text)
                if memory_embedding:
                    memory["embedding"] = memory_embedding  # cache for next time

            if memory_embedding:
                similarity = calculate_similarity(query_embedding, memory_embedding)
                results.append({
                    **memory,
                    "relevance_score": similarity
                })
            else:
                # No embedding available, assign low score
                results.append({
                    **memory,
                    "relevance_score": 0.0
                })

        # Sort by relevance
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        logger.debug(f"[LTM] Retrieved {len(results)} memories for query='{query[:30]}...'")
        return results[:top_k]
    
    def _retrieve_by_keywords(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """
        使用关键词匹配检索记忆（回退方案）
        
        Args:
            query: 查询内容
            top_k: 返回Top-K结果
            
        Returns:
            List[Dict[str, Any]]: 相关记忆列表
        """
        query_keywords = set(query.split())
        results = []
        
        for memory in self.memories:
            relevance_score = self._calculate_keyword_score(query, memory)
            if relevance_score > 0:
                results.append({
                    **memory,
                    "relevance_score": relevance_score
                })
        
        # 按相关性排序
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        logger.debug(f"📚 [LTM] 使用关键词检索: 查询='{query[:30]}...', 找到{len(results)}条相关记忆")
        return results[:top_k]
    
    def _calculate_keyword_score(self, query: str, memory: Dict[str, Any]) -> float:
        """
        计算关键词匹配分数（辅助方法）
        
        Args:
            query: 查询内容
            memory: 记忆项
            
        Returns:
            float: 相关性分数（0-1之间）
        """
        query_keywords = set(query.split())
        content_keywords = set(memory["content"].split())
        topic_keywords = set(memory["topic"].split())
        
        # 计算关键词重叠度
        overlap = len(query_keywords & (content_keywords | topic_keywords))
        if overlap > 0:
            relevance_score = overlap / max(len(query_keywords), 1)
            return min(1.0, relevance_score)
        return 0.0
    
    def get_all(self) -> List[Dict[str, Any]]:
        """获取所有记忆"""
        return self.memories
    
    # LangChain BaseMemory兼容方法（可选）
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """
        保存上下文（LangChain BaseMemory接口）
        
        Args:
            inputs: 输入字典（包含用户输入等）
            outputs: 输出字典（包含AI回复等）
        """
        user_input = inputs.get("input", "") or inputs.get("question", "")
        ai_output = outputs.get("output", "") or outputs.get("answer", "")
        
        if user_input:
            # 使用现有的write方法
            conversation_history = []  # 简化：不传入历史
            should_write, reason = self.should_write(user_input, conversation_history)
            if should_write:
                self.write(user_input, metadata={"trigger": "langchain_save_context", "reason": reason})
        
        if ai_output:
            # 也可以保存AI的输出（如果需要）
            pass
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        加载记忆变量（LangChain BaseMemory接口）
        
        Args:
            inputs: 输入字典
            
        Returns:
            Dict[str, Any]: 记忆变量字典
        """
        query = inputs.get("input", "") or inputs.get("question", "") or ""
        
        if query:
            # 使用现有的retrieve方法
            memories = self.retrieve(query, top_k=settings.CONTEXT_LTM_RETRIEVE_TOP_K)
            memory_texts = [mem["content"] for mem in memories]
        else:
            memory_texts = [mem["content"] for mem in self.memories[:settings.CONTEXT_LTM_RETRIEVE_TOP_K]]
        
        return {"history": "\n".join(memory_texts), "memories": memory_texts}
    
    def clear(self) -> None:
        """
        清除记忆（LangChain BaseMemory接口）
        """
        self.memories.clear()
        logger.info(f"🗑️ [LTM] 清除长期记忆（LangChain接口）: session_id={self.session_id}")
    
    @property
    def memory_variables(self) -> List[str]:
        """返回记忆变量名列表（LangChain BaseMemory接口）"""
        return ["history", "memories"]


class ContextSelector(BaseRetriever if LANGCHAIN_RETRIEVER_AVAILABLE else object):
    """
    上下文选择器 - 选择层
    动态上下文选择，包括LTM检索、选择性历史、工具子集选择
    
    简化版：使用关键词匹配进行语义路由
    
    支持LangChain BaseRetriever接口（可选）：
    - get_relevant_documents: 获取相关文档
    """
    
    def __init__(self, ltm: Optional[LongTermMemory] = None):
        """
        初始化上下文选择器
        
        Args:
            ltm: 长期记忆实例（可选）
        """
        # 如果是BaseRetriever的子类，尝试调用父类初始化
        # 但BaseRetriever可能是Pydantic模型，不允许自定义字段，所以使用object.__setattr__绕过验证
        if LANGCHAIN_RETRIEVER_AVAILABLE:
            try:
                # 尝试检查是否是BaseRetriever的子类
                if issubclass(type(self), BaseRetriever):
                    try:
                        super().__init__()
                    except Exception as e:
                        # 如果父类初始化失败（可能是字段验证问题），继续执行
                        logger.debug(f"⚠️ [ContextSelector] BaseRetriever初始化跳过: {str(e)}")
            except Exception:
                # 如果检查失败，继续执行
                pass
        
        # 使用object.__setattr__绕过可能的Pydantic字段验证
        object.__setattr__(self, 'ltm', ltm)
        logger.info("🔍 [ContextSelector] 初始化上下文选择器")
    
    def build_context(
        self,
        query: str,
        conversation_history: List[Dict[str, str]],
        max_history_turns: int = 5
    ) -> Dict[str, Any]:
        """
        构建动态上下文
        
        Args:
            query: 当前查询
            conversation_history: 对话历史
            max_history_turns: 最大历史轮次
            
        Returns:
            Dict[str, Any]: 构建的上下文，包含LTM记忆、选择性历史等
        """
        context = {
            "ltm_memories": [],
            "selected_history": [],
            "relevant_tools": []
        }
        
        # 1. 从LTM检索相关记忆
        if self.ltm:
            ltm_results = self.ltm.retrieve(query, top_k=settings.CONTEXT_LTM_RETRIEVE_TOP_K)
            context["ltm_memories"] = [mem["content"] for mem in ltm_results]
            logger.debug(f"📚 [ContextSelector] 检索到{len(ltm_results)}条LTM记忆")
        
        # 2. 选择性历史（使用语义相似度）
        context["selected_history"] = self._select_history(
            conversation_history, 
            max_history_turns, 
            query
        )
        
        # 3. 工具子集选择（使用Embedding计算工具相关性）
        context["relevant_tools"] = self._get_relevant_tools(query)
        
        return context
    
    def _get_relevant_tools(
        self,
        query: str,
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """
        获取相关工具子集（使用Embedding计算工具相关性）
        
        Args:
            query: 当前查询
            top_k: 返回Top-K相关工具（默认使用配置值）
            
        Returns:
            List[Dict[str, Any]]: 相关工具列表（包含工具名称、描述、相关性分数）
        """
        if top_k is None:
            top_k = settings.CONTEXT_TOOL_SUBSET_TOP_K
        
        # 简化版：预定义工具列表（使用统一命名规范：material_、agent_前缀）
        # 后续可以从AgentRegistry动态获取
        available_tools = [
            {
                "name": "material_query_project_materials",  # 统一命名：material_前缀
                "legacy_name": "query_project_materials",  # 向后兼容：旧名称
                "description": "查询项目素材库，根据用户意图搜索相关音频素材",
                "category": "material"
            },
            {
                "name": "material_web_search",  # 统一命名：material_前缀
                "legacy_name": "web_search",  # 向后兼容：旧名称
                "description": "网络搜索，获取最新的网络信息",
                "category": "search"
            },
            {
                "name": "material_local_search",  # 统一命名：material_前缀
                "legacy_name": "local_search",  # 向后兼容：旧名称
                "description": "本地搜索，在项目内搜索相关内容",
                "category": "search"
            },
            {
                "name": "material_rag_retrieve",  # 统一命名：material_前缀
                "legacy_name": "rag_retriever",  # 向后兼容：旧名称
                "description": "RAG检索，从知识库中检索相关信息",
                "category": "retrieval"
            },
            {
                "name": "material_image_search",  # 统一命名：material_前缀
                "legacy_name": "image_search",  # 向后兼容：旧名称
                "description": "图片搜索，搜索相关图片素材",
                "category": "material"
            },
            {
                "name": "agent_analyze_requirement",  # 统一命名：agent_前缀
                "legacy_name": "analyze_requirement",  # 向后兼容：旧名称
                "description": "需求分析，分析用户需求的完整性和缺失信息",
                "category": "agent"
            },
            {
                "name": "agent_create_plan",  # 统一命名：agent_前缀
                "legacy_name": "create_plan",  # 向后兼容：旧名称
                "description": "创建计划，根据需求生成文章大纲和计划",
                "category": "agent"
            }
        ]
        
        # 使用Embedding计算工具相关性
        query_embedding = calculate_embedding(query)
        if query_embedding is None:
            logger.warning(f"⚠️ [ContextSelector] Embedding计算失败，无法选择工具: {query[:50]}...")
            return []
        
        # 计算每个工具的描述与查询的相似度
        tool_scores = []
        for tool in available_tools:
            tool_desc = tool.get("description", "")
            tool_embedding = calculate_embedding(tool_desc)
            
            if tool_embedding:
                similarity = calculate_similarity(query_embedding, tool_embedding)
                tool_scores.append({
                    **tool,
                    "relevance_score": similarity
                })
            else:
                # Embedding计算失败，跳过该工具
                logger.warning(f"⚠️ [ContextSelector] 工具'{tool.get('name')}'的Embedding计算失败，跳过")
                continue
        
        # 按相关性排序
        tool_scores.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        # 过滤低相关性工具（阈值）
        relevant_tools = [
            tool for tool in tool_scores
            if tool["relevance_score"] >= settings.CONTEXT_RELEVANCE_THRESHOLD
        ]
        
        logger.debug(
            f"🔧 [ContextSelector] 工具子集选择: "
            f"查询='{query[:50]}...', 找到{len(relevant_tools)}个相关工具（Top-{top_k}）"
        )
        
        return relevant_tools[:top_k]
    
    def _get_relevant_tools_by_keywords(
        self,
        query: str,
        available_tools: List[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        使用关键词匹配获取相关工具（回退方案）
        
        Args:
            query: 当前查询
            available_tools: 可用工具列表
            top_k: 返回Top-K结果
            
        Returns:
            List[Dict[str, Any]]: 相关工具列表
        """
        query_keywords = set(query.lower().split())
        tool_scores = []
        
        for tool in available_tools:
            tool_desc = tool.get("description", "").lower()
            tool_keywords = set(tool_desc.split())
            
            # 计算关键词重叠度
            overlap = len(query_keywords & tool_keywords)
            if overlap > 0:
                relevance_score = overlap / max(len(query_keywords), 1)
                tool_scores.append({
                    **tool,
                    "relevance_score": relevance_score
                })
        
        # 按相关性排序
        tool_scores.sort(key=lambda x: x["relevance_score"], reverse=True)
        return tool_scores[:top_k]
    
    def _select_history(
        self,
        history: List[Dict[str, str]],
        max_turns: int,
        current_query: str
    ) -> List[Dict[str, str]]:
        """
        选择性历史（使用语义相似度）
        
        Args:
            history: 完整历史
            max_turns: 最大轮次
            current_query: 当前查询
            
        Returns:
            List[Dict[str, str]]: 选择性历史
        """
        if len(history) <= max_turns:
            return history
        
        selected = []
        
        # 1. 使用语义相似度选择相关历史
        query_embedding = calculate_embedding(current_query)
        if query_embedding:
            # 计算每条历史与当前查询的语义相似度
            history_scores = []
            for i, msg in enumerate(history):
                content = msg.get("content", "")
                if not content or len(content.strip()) < 10:
                    continue
                
                msg_embedding = calculate_embedding(content)
                if msg_embedding:
                    similarity = calculate_similarity(query_embedding, msg_embedding)
                    history_scores.append((i, msg, similarity))
            
            # 按相似度排序，选择Top-K
            history_scores.sort(key=lambda x: x[2], reverse=True)
            top_k = min(max_turns * 2, len(history_scores))
            
            for i, msg, similarity in history_scores[:top_k]:
                if similarity > getattr(settings, 'CONTEXT_RELEVANCE_THRESHOLD', 0.7):
                    if msg not in selected:
                        selected.append(msg)
            
            logger.debug(f"🔍 [ContextSelector] 语义相似度选择：选择了{len(selected)}条相关历史")
        else:
            # Embedding计算失败，无法进行语义选择
            logger.warning("⚠️ [ContextSelector] Embedding计算失败，无法进行语义选择")
            selected = []
        
        # 3. 保留最近N轮（保证连贯性）
        recent = history[-max_turns:]
        for msg in recent:
            if msg not in selected:
                selected.append(msg)
        
        # 4. 保留决策点（包含决策关键词的轮次）
        decision_keywords = ["决定", "选择", "采用", "确定", "确认"]
        for msg in history[:-max_turns]:  # 排除最近N轮
            content = msg.get("content", "")
            if any(keyword in content for keyword in decision_keywords):
                if msg not in selected:
                    selected.append(msg)
        
        # 按时间顺序排序
        selected.sort(key=lambda x: history.index(x) if x in history else len(history))
        
        # 限制返回数量
        return selected[:max_turns * 2]  # 最多返回2倍数量的历史
    
    # LangChain BaseRetriever兼容方法（可选）
    def get_relevant_documents(self, query: str) -> List[Document]:
        """
        获取相关文档（LangChain BaseRetriever接口）
        
        Args:
            query: 查询字符串
            
        Returns:
            List[Document]: 相关文档列表
        """
        # 使用现有的build_context方法
        context = self.build_context(query, [], max_history_turns=settings.CONTEXT_STM_MAX_LENGTH)
        
        documents = []
        
        # 将LTM记忆转换为Document
        for memory_content in context.get("ltm_memories", []):
            documents.append(Document(
                page_content=memory_content,
                metadata={"source": "ltm", "type": "memory"}
            ))
        
        # 将选择性历史转换为Document
        for history_msg in context.get("selected_history", []):
            content = history_msg.get("content", "")
            role = history_msg.get("role", "unknown")
            if content:
                documents.append(Document(
                    page_content=content,
                    metadata={"source": "history", "role": role, "type": "conversation"}
                ))
        
        return documents
    
    async def aget_relevant_documents(self, query: str) -> List[Document]:
        """
        异步获取相关文档（LangChain BaseRetriever接口）
        
        Args:
            query: 查询字符串
            
        Returns:
            List[Document]: 相关文档列表
        """
        # 同步版本的异步包装
        return self.get_relevant_documents(query)


# global LTM instance cache (per session_id)
_ltm_cache: Dict[str, LongTermMemory] = {}


def get_ltm(session_id: str) -> LongTermMemory:
    """
    获取长期记忆实例（单例模式，按session_id隔离）
    
    Args:
        session_id: 会话ID
        
    Returns:
        LongTermMemory: 长期记忆实例
    """
    if session_id not in _ltm_cache:
        _ltm_cache[session_id] = LongTermMemory(session_id)
    return _ltm_cache[session_id]


def clear_ltm(session_id: str):
    """
    清除长期记忆（会话结束时调用）
    
    Args:
        session_id: 会话ID
    """
    if session_id in _ltm_cache:
        del _ltm_cache[session_id]
        logger.info(f"🗑️ [LTM] 清除长期记忆: session_id={session_id}")
