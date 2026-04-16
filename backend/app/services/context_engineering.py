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
        Persist a memory entry to ChromaDB for cross-session durability.

        Best-effort: failures are logged but do not block the write.
        """
        try:
            import asyncio
            from app.tools.vector_store import VectorStore

            vs = VectorStore({"collection_name": "long_term_memory"})
            documents = [{
                "id": memory["id"],
                "text": f"{memory['topic']}\n{memory['content']}",
            }]
            metadatas = [{
                "source": "ltm",
                "session_id": self.session_id,
                "topic": memory["topic"],
                "timestamp": memory["timestamp"],
            }]

            async def _do_persist():
                await vs.add_documents(documents, metadatas)

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # Already in async context — spawn a background thread
                import threading
                def _run_in_thread():
                    asyncio.run(_do_persist())
                t = threading.Thread(target=_run_in_thread, daemon=True)
                t.start()
            else:
                asyncio.run(_do_persist())
        except Exception as e:
            logger.debug(f"[LTM] ChromaDB persist skipped: {e}")

    def _is_duplicate(self, memory: Dict[str, Any]) -> bool:
        """
        检查是否重复（改进版：使用Embedding语义相似度）
        
        Args:
            memory: 记忆项（包含content和可选的embedding）
            
        Returns:
            bool: 是否重复
        """
        content = memory.get("content", "")
        new_embedding = memory.get("embedding")
        
        # 必须有embedding才能进行语义去重
        if not new_embedding:
            logger.warning("⚠️ [LTM] 新记忆无embedding，跳过语义去重检查")
            return False
        
        # 使用语义相似度检查
        similarity_threshold = getattr(settings, 'CONTEXT_SEMANTIC_DEDUP_THRESHOLD', 0.85)
        
        for existing in self.memories:
            existing_embedding = existing.get("embedding")
            if not existing_embedding:
                # 如果已有记忆没有embedding，尝试计算（但可能影响性能）
                existing_content = existing.get("content", "")
                if existing_content:
                    existing_embedding = calculate_embedding(existing_content)
                    if existing_embedding:
                        existing["embedding"] = existing_embedding  # 缓存embedding
            
            if existing_embedding:
                similarity = calculate_similarity(new_embedding, existing_embedding)
                if similarity > similarity_threshold:
                    logger.debug(
                        f"🔄 [LTM] 语义重复检测：相似度={similarity:.3f} > {similarity_threshold}，"
                        f"跳过重复记忆: {content[:30]}..."
                    )
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
        
        # 使用Embedding进行语义搜索
        query_embedding = calculate_embedding(query)
        if not query_embedding:
            logger.warning(f"⚠️ [LTM] Embedding计算失败，无法检索: {query[:30]}...")
            return []
        
        # 使用Embedding计算相似度
        results = []
        for memory in self.memories:
            # 计算记忆内容的embedding
            memory_text = f"{memory['topic']} {memory['content']}"
            memory_embedding = calculate_embedding(memory_text)
            
            if memory_embedding:
                similarity = calculate_similarity(query_embedding, memory_embedding)
                results.append({
                    **memory,
                    "relevance_score": similarity
                })
        
        # 按相关性排序
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        logger.debug(f"📚 [LTM] 使用Embedding检索: 查询='{query[:30]}...', 找到{len(results)}条相关记忆")
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


class ContextCompressor:
    """
    上下文压缩器 - 压缩层
    摘要压缩、关键信息提取，用于减少Token消耗
    
    简化版：关键词提取法
    """
    
    def __init__(self):
        """初始化上下文压缩器"""
        logger.info("🗜️ [ContextCompressor] 初始化上下文压缩器")
    
    def should_compress(
        self,
        current_tokens: int,
        max_tokens: int,
        history_turns: int
    ) -> bool:
        """
        判断是否需要压缩
        
        触发条件：达到窗口85%且历史轮次>15
        
        Args:
            current_tokens: 当前Token数
            max_tokens: 最大Token数
            history_turns: 历史轮次
            
        Returns:
            bool: 是否需要压缩
        """
        if max_tokens <= 0:
            return False
        
        token_ratio = current_tokens / max_tokens
        should_compress = (token_ratio >= settings.CONTEXT_COMPRESSION_THRESHOLD and 
                          history_turns > settings.CONTEXT_MAX_HISTORY_TURNS)
        
        if should_compress:
            logger.info(f"🗜️ [ContextCompressor] 触发压缩: token_ratio={token_ratio:.2f}, turns={history_turns}")
        
        return should_compress
    
    def compress(
        self,
        conversation_history: List[Dict[str, str]],
        method: str = "key_info"
    ) -> List[Dict[str, str]]:
        """
        压缩对话历史
        
        Args:
            conversation_history: 对话历史
            method: 压缩方法（"key_info" 或 "summary"）
            
        Returns:
            List[Dict[str, str]]: 压缩后的对话历史
        """
        if method == "dimension_aware":
            return self._compress_dimension_aware(conversation_history)
        elif method == "key_info":
            return self._compress_key_info(conversation_history)
        else:
            return self._compress_summary(conversation_history)
    
    def extract_key_nodes(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        识别对话中的关键节点（不压缩）
        包括：需求确认、方案选择、用户反馈等
        
        Args:
            history: 对话历史
            
        Returns:
            List[Dict[str, str]]: 关键节点列表
        """
        key_keywords = ["决定", "选择", "确认", "采用", "方案", "需求", "目标", "完成"]
        key_nodes = []
        
        for msg in history:
            content = msg.get("content", "")
            # 检查是否包含关键关键词
            if any(keyword in content for keyword in key_keywords):
                key_nodes.append({
                    "role": msg.get("role", "user"),
                    "content": content,
                    "type": "key_node"
                })
        
        logger.debug(f"🔑 [ContextCompressor] 提取了{len(key_nodes)}个关键节点")
        return key_nodes
    
    def extract_dimension(self, history: List[Dict[str, str]], dimension: str) -> str:
        """
        从历史中提取特定维度的信息
        用于生成维度摘要
        
        Args:
            history: 对话历史
            dimension: 维度名称（如"目标受众"、"立场观点"等）
            
        Returns:
            str: 该维度的信息摘要
        """
        dimension_keywords = getattr(settings, 'CONTEXT_DIMENSION_KEYWORDS', {})
        keywords = dimension_keywords.get(dimension, [])
        
        if not keywords:
            return ""
        
        dimension_content = []
        for msg in history:
            content = msg.get("content", "")
            # 检查是否包含该维度的关键词
            if any(keyword in content for keyword in keywords):
                dimension_content.append(content)
        
        if dimension_content:
            # 简单合并（后续可以优化为LLM摘要）
            return "\n".join(dimension_content[:3])  # 最多3条
        
        return ""
    
    def _compress_dimension_aware(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        维度感知压缩（改进版）
        保留维度信息，不丢失关键实体
        
        Args:
            history: 对话历史
            
        Returns:
            List[Dict[str, str]]: 压缩后的历史
        """
        compressed = []
        
        # 1. 提取关键节点（不压缩）
        key_nodes = self.extract_key_nodes(history)
        key_node_contents = [node["content"] for node in key_nodes]
        
        # 2. 提取维度摘要
        dimension_keywords = getattr(settings, 'CONTEXT_DIMENSION_KEYWORDS', {})
        dimension_summaries = {}
        for dimension in dimension_keywords.keys():
            summary = self.extract_dimension(history, dimension)
            if summary:
                dimension_summaries[dimension] = summary
        
        # 3. 保留最近3轮原文（保证连贯性）
        recent_raw = history[-3:] if len(history) >= 3 else history
        
        # 4. 构建压缩后的历史
        # 先添加关键节点摘要
        if key_node_contents:
            compressed.append({
                "role": "system",
                "content": f"[关键信息]\n" + "\n".join(key_node_contents[:5])  # 最多5个关键节点
            })
        
        # 添加维度摘要
        if dimension_summaries:
            dimension_text = "\n".join([f"{dim}: {summary[:100]}..." for dim, summary in dimension_summaries.items()])
            compressed.append({
                "role": "system",
                "content": f"[维度摘要]\n{dimension_text}"
            })
        
        # 添加最近对话原文
        compressed.extend(recent_raw)
        
        logger.info(
            f"🗜️ [ContextCompressor] 维度感知压缩完成: "
            f"关键节点={len(key_node_contents)}, 维度={len(dimension_summaries)}, "
            f"最近轮次={len(recent_raw)}, 压缩后={len(compressed)}条"
        )
        
        return compressed
    
    def _compress_key_info(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        关键信息提取法（简化版：保留包含关键词的句子）
        
        Args:
            history: 对话历史
            
        Returns:
            List[Dict[str, str]]: 压缩后的历史
        """
        key_keywords = ["决定", "选择", "确认", "需求", "方案", "问题", "目标"]
        compressed = []
        
        for msg in history:
            content = msg.get("content", "")
            # 提取包含关键词的句子
            sentences = re.split(r'[。！？\n]', content)
            key_sentences = [s.strip() for s in sentences if any(kw in s for kw in key_keywords) and s.strip()]
            
            if key_sentences:
                compressed_content = "。".join(key_sentences[:3])  # 最多3个关键句子
                compressed.append({
                    "role": msg.get("role", "user"),
                    "content": compressed_content
                })
            else:
                # 保留原始消息（如果没有关键词，保留前50字）
                compressed.append({
                    "role": msg.get("role", "user"),
                    "content": content[:50] + "..." if len(content) > 50 else content
                })
        
        return compressed
    
    def _compress_summary(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        摘要压缩法（简化版：保留核心需求、已确认方案、未解决问题、关键决策点）
        
        如果LangChain可用，可以使用LLMChain进行摘要压缩
        
        Args:
            history: 对话历史
            
        Returns:
            List[Dict[str, str]]: 压缩后的历史
        """
        # 如果LangChain可用，使用LLMChain进行摘要压缩
        if LANGCHAIN_CHAIN_AVAILABLE:
            return self._compress_summary_with_llm(history)
        
        # 使用关键信息提取
        return self._compress_key_info(history)
    
    def _compress_summary_with_llm(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        使用LLMChain进行摘要压缩（LangChain兼容）
        
        Args:
            history: 对话历史
            
        Returns:
            List[Dict[str, str]]: 压缩后的历史
        """
        # 简化版：当前使用关键词提取（LLM摘要压缩需要LLM实例，暂时回退）
        # TODO: 实现LLM摘要压缩（需要LLM实例）
        return self._compress_key_info(history)


class ProgressiveContextLoader:
    """
    渐进式上下文加载器
    分层加载上下文：Layer 1（最近5轮）、Layer 2（摘要层）、Layer 3（LTM）
    
    简化版：基础分层加载
    """
    
    def __init__(self, compressor: Optional[ContextCompressor] = None):
        """
        初始化渐进式上下文加载器
        
        Args:
            compressor: 上下文压缩器（可选）
        """
        self.compressor = compressor or ContextCompressor()
        logger.info("📦 [ProgressiveContextLoader] 初始化渐进式上下文加载器")
    
    def load(
        self,
        conversation_history: List[Dict[str, str]],
        ltm: Optional[LongTermMemory] = None,
        depth: str = "shallow"
    ) -> Dict[str, Any]:
        """
        渐进式加载上下文
        
        Args:
            conversation_history: 对话历史
            ltm: 长期记忆（可选）
            depth: 加载深度（"shallow", "medium", "deep"）
            
        Returns:
            Dict[str, Any]: 加载的上下文
        """
        context = {
            "layer1": [],  # 最近5轮（常驻）
            "layer2": [],  # 摘要层（6-20轮）
            "layer3": []   # LTM上下文
        }
        
        # Layer 1：最近5轮（常驻）
        context["layer1"] = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
        
        # Layer 2：摘要层（如果需要深度加载）
        if depth in ["medium", "deep"] and len(conversation_history) > 5:
            layer2_history = conversation_history[-20:-5]  # 6-20轮
            if layer2_history:
                context["layer2"] = self.compressor.compress(layer2_history, method="key_info")
        
        # Layer 3：LTM上下文（如果需要深度加载）
        if depth == "deep" and ltm:
            # 从最近的对话中提取查询
            if conversation_history:
                last_query = conversation_history[-1].get("content", "")
                ltm_results = ltm.retrieve(last_query, top_k=settings.CONTEXT_LTM_RETRIEVE_TOP_K)
                context["layer3"] = [mem["content"] for mem in ltm_results]
        
        return context


# 全局LTM实例缓存（按session_id）
_ltm_cache: Dict[str, LongTermMemory] = {}


class TokenEfficiencyMonitor:
    """
    Token效率监控器
    计算有效信息Token/总Token消耗，目标值>0.6，记录到日志便于分析
    """
    
    def __init__(self):
        """初始化Token效率监控器"""
        self.metrics_history: List[Dict[str, Any]] = []
        logger.info("📊 [TokenEfficiencyMonitor] 初始化Token效率监控器")
    
    def calculate_efficiency(
        self,
        total_tokens: int,
        effective_tokens: int
    ) -> float:
        """
        计算Token效率
        
        Args:
            total_tokens: 总Token数
            effective_tokens: 有效信息Token数
            
        Returns:
            float: Token效率（0-1之间）
        """
        if total_tokens == 0:
            return 0.0
        
        efficiency = effective_tokens / total_tokens
        return float(max(0.0, min(1.0, efficiency)))
    
    def estimate_effective_tokens(
        self,
        conversation_history: List[Dict[str, str]],
        context_size: int = 0
    ) -> int:
        """
        估算有效信息Token数
        
        简化版：使用启发式方法估算
        - 用户消息：100%有效
        - 助手消息：80%有效（可能有冗余）
        - 系统消息：50%有效
        
        Args:
            conversation_history: 对话历史
            context_size: 上下文大小（Token数）
            
        Returns:
            int: 有效信息Token数
        """
        effective = 0
        
        for msg in conversation_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            tokens = count_tokens(content)
            
            if role == "user":
                effective += tokens  # 用户消息100%有效
            elif role == "assistant":
                effective += int(tokens * 0.8)  # 助手消息80%有效
            elif role == "system":
                effective += int(tokens * 0.5)  # 系统消息50%有效
            else:
                effective += int(tokens * 0.7)  # 其他消息70%有效
        
        # 上下文开销：假设30%是有效信息
        effective += int(context_size * 0.3)
        
        return effective
    
    def monitor_and_log(
        self,
        total_tokens: int,
        effective_tokens: int,
        session_id: str = "unknown",
        step: str = "unknown"
    ) -> Dict[str, Any]:
        """
        监控并记录Token效率
        
        Args:
            total_tokens: 总Token数
            effective_tokens: 有效信息Token数
            session_id: 会话ID
            step: 当前步骤
            
        Returns:
            Dict[str, Any]: 监控指标
        """
        efficiency = self.calculate_efficiency(total_tokens, effective_tokens)
        target_efficiency = settings.CONTEXT_TOKEN_EFFICIENCY_TARGET
        
        metric = {
            "session_id": session_id,
            "step": step,
            "total_tokens": total_tokens,
            "effective_tokens": effective_tokens,
            "efficiency": efficiency,
            "target": target_efficiency,
            "meets_target": efficiency >= target_efficiency,
            "timestamp": datetime.now().isoformat()
        }
        
        # 记录到历史
        self.metrics_history.append(metric)
        # 只保留最近1000条记录
        if len(self.metrics_history) > 1000:
            self.metrics_history = self.metrics_history[-1000:]
        
        # 记录到日志
        if efficiency >= target_efficiency:
            logger.info(
                f"📊 [TokenEfficiency] ✅ 效率达标: {efficiency:.2f} >= {target_efficiency:.2f} "
                f"(有效={effective_tokens}/{total_tokens}, session={session_id}, step={step})"
            )
        else:
            logger.warning(
                f"📊 [TokenEfficiency] ⚠️ 效率不足: {efficiency:.2f} < {target_efficiency:.2f} "
                f"(有效={effective_tokens}/{total_tokens}, session={session_id}, step={step})"
            )
        
        return metric
    
    def get_statistics(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取统计信息
        
        Args:
            session_id: 会话ID（可选，如果提供则只统计该会话）
            
        Returns:
            Dict[str, Any]: 统计信息
        """
        if session_id:
            metrics = [m for m in self.metrics_history if m["session_id"] == session_id]
        else:
            metrics = self.metrics_history
        
        if not metrics:
            return {
                "count": 0,
                "avg_efficiency": 0.0,
                "min_efficiency": 0.0,
                "max_efficiency": 0.0,
                "meets_target_rate": 0.0
            }
        
        efficiencies = [m["efficiency"] for m in metrics]
        meets_target = [m["meets_target"] for m in metrics]
        
        return {
            "count": len(metrics),
            "avg_efficiency": sum(efficiencies) / len(efficiencies),
            "min_efficiency": min(efficiencies),
            "max_efficiency": max(efficiencies),
            "meets_target_rate": sum(meets_target) / len(meets_target) if meets_target else 0.0,
            "total_tokens": sum(m["total_tokens"] for m in metrics),
            "total_effective_tokens": sum(m["effective_tokens"] for m in metrics)
        }


# 全局Token效率监控器实例
_token_efficiency_monitor = None


def get_token_efficiency_monitor() -> TokenEfficiencyMonitor:
    """
    获取Token效率监控器实例（单例模式）
    
    Returns:
        TokenEfficiencyMonitor: Token效率监控器实例
    """
    global _token_efficiency_monitor
    if _token_efficiency_monitor is None:
        _token_efficiency_monitor = TokenEfficiencyMonitor()
    return _token_efficiency_monitor


class ErrorPropagationDetector:
    """
    错误传播检测与自动纠正器
    检测连续3轮出现错误关键词，实现自动纠正机制（重置STM、注入纠正性上下文、从LTM重新加载）
    """
    
    # 错误关键词列表
    ERROR_KEYWORDS = [
        "错误", "失败", "异常", "无法", "不能", "不支持", "未找到", "不存在",
        "error", "failed", "exception", "cannot", "not found", "missing"
    ]
    
    def __init__(self, ltm: Optional[LongTermMemory] = None):
        """
        初始化错误传播检测器
        
        Args:
            ltm: 长期记忆实例（可选）
        """
        # 使用object.__setattr__绕过可能的Pydantic字段验证（虽然这个类不继承Pydantic模型，但为了保持一致性）
        object.__setattr__(self, 'ltm', ltm)
        object.__setattr__(self, 'error_history', [])  # 错误历史记录
        logger.info("🔍 [ErrorPropagationDetector] 初始化错误传播检测器")
    
    def detect_error_keywords(self, content: str) -> Tuple[bool, List[str]]:
        """
        检测内容中是否包含错误关键词
        
        Args:
            content: 要检测的内容
            
        Returns:
            Tuple[bool, List[str]]: (是否包含错误关键词, 匹配的关键词列表)
        """
        content_lower = content.lower()
        matched_keywords = [kw for kw in self.ERROR_KEYWORDS if kw in content_lower]
        return len(matched_keywords) > 0, matched_keywords
    
    def check_error_propagation(
        self,
        conversation_history: List[Dict[str, str]],
        recent_turns: int = 3
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        检查是否出现错误传播（连续N轮出现错误关键词）
        
        Args:
            conversation_history: 对话历史
            recent_turns: 检查最近N轮（默认3轮）
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (是否出现错误传播, 错误信息)
        """
        if len(conversation_history) < recent_turns * 2:  # 需要至少N轮（每轮2条消息）
            return False, {}
        
        # 检查最近N轮
        recent_messages = conversation_history[-recent_turns * 2:]
        error_count = 0
        error_messages = []
        
        for msg in recent_messages:
            content = msg.get("content", "")
            has_error, keywords = self.detect_error_keywords(content)
            
            if has_error:
                error_count += 1
                error_messages.append({
                    "role": msg.get("role", "unknown"),
                    "content": content[:200],  # 只保留前200字符
                    "keywords": keywords
                })
        
        # 如果连续N轮都出现错误，判定为错误传播
        if error_count >= recent_turns:
            error_info = {
                "error_count": error_count,
                "recent_turns": recent_turns,
                "error_messages": error_messages,
                "detected_at": datetime.now().isoformat()
            }
            
            logger.warning(
                f"⚠️ [ErrorPropagationDetector] 检测到错误传播: "
                f"最近{recent_turns}轮中出现{error_count}次错误"
            )
            
            return True, error_info
        
        return False, {}
    
    def generate_correction_context(
        self,
        error_info: Dict[str, Any],
        original_context: str
    ) -> str:
        """
        生成纠正性上下文
        
        Args:
            error_info: 错误信息
            original_context: 原始上下文
            
        Returns:
            str: 纠正性上下文
        """
        correction = "【上下文纠正】\n"
        correction += "检测到连续错误，建议：\n"
        correction += "1. 重新理解用户意图\n"
        correction += "2. 检查上下文是否完整\n"
        correction += "3. 参考之前的成功对话记录\n"
        correction += f"\n错误摘要：检测到{error_info.get('error_count', 0)}个错误\n"
        
        if error_info.get("error_messages"):
            correction += "\n最近的错误消息：\n"
            for i, err_msg in enumerate(error_info["error_messages"][-3:], 1):  # 只显示最近3个
                correction += f"{i}. [{err_msg.get('role', 'unknown')}] {err_msg.get('content', '')[:100]}...\n"
        
        return correction
    
    def apply_correction(
        self,
        conversation_history: List[Dict[str, str]],
        error_info: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        应用纠正机制
        
        Args:
            conversation_history: 对话历史
            error_info: 错误信息
            
        Returns:
            List[Dict[str, str]]: 纠正后的对话历史
        """
        corrected_history = conversation_history.copy()
        
        # 1. 重置STM：只保留最近1轮，去除错误消息
        # 保留用户最近的消息，移除助手的错误回复
        recent_user_msg = None
        for msg in reversed(corrected_history):
            if msg.get("role") == "user":
                recent_user_msg = msg
                break
        
        # 重置历史：保留前面正常的对话，只保留最近用户消息
        safe_history = []
        for msg in corrected_history[:-6]:  # 保留除了最近3轮（6条消息）之外的历史
            safe_history.append(msg)
        
        if recent_user_msg:
            safe_history.append(recent_user_msg)
        
        # 2. 注入纠正性上下文
        correction_context = self.generate_correction_context(error_info, "")
        safe_history.append({
            "role": "system",
            "content": correction_context
        })
        
        # 3. 从LTM重新加载相关记忆（如果有LTM）
        if self.ltm:
            # 使用最近用户消息作为查询
            if recent_user_msg:
                query = recent_user_msg.get("content", "")
                ltm_memories = self.ltm.retrieve(query, top_k=3)
                
                if ltm_memories:
                    ltm_context = "【从长期记忆恢复的相关信息】\n"
                    ltm_context += "\n".join([mem["content"][:200] for mem in ltm_memories])
                    safe_history.append({
                        "role": "system",
                        "content": ltm_context
                    })
                    logger.info(f"📚 [ErrorPropagationDetector] 从LTM恢复{len(ltm_memories)}条相关记忆")
        
        logger.info(
            f"🔧 [ErrorPropagationDetector] 应用纠正机制: "
            f"原始历史{len(corrected_history)}条 -> 纠正后{len(safe_history)}条"
        )
        
        return safe_history


class AgentIsolationLayer:
    """
    Agent隔离层 - 隔离层
    实现L1/L2/L3分级缓存策略，每个Agent维护独立上下文缓存
    """
    
    def __init__(self):
        """初始化Agent隔离层"""
        # L1缓存：Agent级别的上下文缓存（最近N轮）
        self.l1_cache: Dict[str, List[Dict[str, str]]] = {}
        # L2缓存：Agent级别的摘要缓存（压缩后的历史）
        self.l2_cache: Dict[str, List[Dict[str, str]]] = {}
        # L3缓存：Agent级别的LTM缓存（长期记忆）
        self.l3_cache: Dict[str, List[Dict[str, Any]]] = {}
        logger.info("🔒 [AgentIsolationLayer] 初始化Agent隔离层")
    
    def get_agent_context(
        self,
        agent_id: str,
        conversation_history: List[Dict[str, str]],
        ltm: Optional[LongTermMemory] = None,
        query: str = ""
    ) -> Dict[str, Any]:
        """
        获取Agent的隔离上下文
        
        Args:
            agent_id: Agent ID（如"analyzer", "writer", "reviewer"等）
            conversation_history: 全局对话历史
            ltm: 长期记忆实例（可选）
            query: 当前查询（用于LTM检索）
            
        Returns:
            Dict[str, Any]: Agent的隔离上下文
        """
        context = {
            "l1_cache": [],  # 最近N轮（常驻）
            "l2_cache": [],  # 摘要缓存
            "l3_cache": []   # LTM缓存
        }
        
        # L1缓存：Agent级别的最近N轮（默认5轮）
        if agent_id not in self.l1_cache:
            self.l1_cache[agent_id] = []
        
        # 更新L1缓存：添加最新的对话（去重）
        latest_messages = conversation_history[-10:]  # 检查最近10轮
        agent_l1 = self.l1_cache[agent_id]
        
        # 只添加新的消息
        for msg in latest_messages:
            if msg not in agent_l1:
                agent_l1.append(msg)
        
        # 保持L1缓存大小（最多5轮，10条消息）
        if len(agent_l1) > 10:
            agent_l1 = agent_l1[-10:]
        self.l1_cache[agent_id] = agent_l1
        context["l1_cache"] = agent_l1[-5:]  # 返回最近5轮
        
        # L2缓存：Agent级别的摘要缓存
        if agent_id not in self.l2_cache:
            self.l2_cache[agent_id] = []
        
        # 如果需要，压缩历史并更新L2缓存
        if len(conversation_history) > 10:
            compressor = ContextCompressor()
            older_history = conversation_history[:-10]  # 除了最近10轮之外的历史
            if older_history:
                compressed = compressor.compress(older_history, method="key_info")
                # 合并到L2缓存（去重）
                agent_l2 = self.l2_cache[agent_id]
                for msg in compressed:
                    if msg not in agent_l2:
                        agent_l2.append(msg)
                # 保持L2缓存大小（最多20条）
                if len(agent_l2) > 20:
                    agent_l2 = agent_l2[-20:]
                self.l2_cache[agent_id] = agent_l2
                context["l2_cache"] = agent_l2
        
        # L3缓存：Agent级别的LTM缓存
        if ltm and query:
            if agent_id not in self.l3_cache:
                self.l3_cache[agent_id] = []
            
            # 从LTM检索相关记忆
            ltm_results = ltm.retrieve(query, top_k=3)
            # 更新L3缓存（去重，基于记忆ID）
            agent_l3 = self.l3_cache[agent_id]
            existing_ids = {mem.get("id") for mem in agent_l3}
            for mem in ltm_results:
                if mem.get("id") not in existing_ids:
                    agent_l3.append(mem)
            # 保持L3缓存大小（最多10条）
            if len(agent_l3) > 10:
                agent_l3 = agent_l3[-10:]
            self.l3_cache[agent_id] = agent_l3
            context["l3_cache"] = [mem["content"] for mem in agent_l3]
        
        return context
    
    def clear_agent_cache(self, agent_id: str):
        """
        清除Agent的缓存
        
        Args:
            agent_id: Agent ID
        """
        if agent_id in self.l1_cache:
            del self.l1_cache[agent_id]
        if agent_id in self.l2_cache:
            del self.l2_cache[agent_id]
        if agent_id in self.l3_cache:
            del self.l3_cache[agent_id]
        logger.info(f"🗑️ [AgentIsolationLayer] 清除Agent缓存: {agent_id}")
    
    def clear_all_cache(self):
        """清除所有Agent的缓存"""
        self.l1_cache.clear()
        self.l2_cache.clear()
        self.l3_cache.clear()
        logger.info("🗑️ [AgentIsolationLayer] 清除所有Agent缓存")


# 全局Agent隔离层实例
_agent_isolation_layer = None


def get_agent_isolation_layer() -> AgentIsolationLayer:
    """
    获取Agent隔离层实例（单例模式）
    
    Returns:
        AgentIsolationLayer: Agent隔离层实例
    """
    global _agent_isolation_layer
    if _agent_isolation_layer is None:
        _agent_isolation_layer = AgentIsolationLayer()
    return _agent_isolation_layer


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
