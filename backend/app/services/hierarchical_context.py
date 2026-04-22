"""
分层上下文管理器
实现 Just-in-Time Retrieval + Progressive Disclosure
"""
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import json
import re
from bs4 import BeautifulSoup
from app.shared.logging import get_logger
logger = get_logger(__name__)

# 尝试导入 jieba，失败时使用简单分词
try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    logger.warning("[上下文] jieba 未安装，将使用简单分词")


def extract_keywords(text: str) -> Set[str]:
    """提取关键词（支持中文）
    
    使用 jieba 分词，如果未安装则回退到简单正则匹配
    """
    if JIEBA_AVAILABLE:
        # 使用 jieba 分词
        words = jieba.cut(text)
        # 过滤停用词和单字
        stopwords = {'的', '了', '是', '有', '在', '我', '你', '他', '这', '那', '和', '与', '或', '个', '们', '等', '要', '会', '能', '对', '把', '被', '让', '给', '到', '从', '向', '往', '在', '着', '过', '地', '得'}
        return {w.lower() for w in words if len(w) > 1 and w not in stopwords and not w.isspace()}
    else:
        # 简单正则匹配（中文字符 + 英文单词）
        chinese_words = set(re.findall(r'[\u4e00-\u9fff]{2,}', text))
        english_words = set(re.findall(r'[a-zA-Z]{2,}', text.lower()))
        return chinese_words | english_words


class TableMatch:
    """表格匹配结果"""
    def __init__(self, doc_name: str, table_id: str, table_type: str, 
                 page: int, summary: str, score: float = 0.0):
        self.doc_name = doc_name
        self.table_id = table_id
        self.table_type = table_type
        self.page = page
        self.summary = summary
        self.score = score
        self.tokens = 0  # 估算的 token 数量


class HierarchicalContext:
    """分层上下文管理器

    架构：
    - Layer 0: 元信息索引（所有文档的名称 + 表格ID列表 + 材料列表）~500 tokens
    - Layer 1: 表格索引（表格 ID → 类型 → 页码 → 摘要）~2000 tokens
    - Layer 2: 按需加载表格（根据查询匹配相关表格，加载 HTML）~5000-20000 tokens
    - Layer 3: 精确检索（参数搜索、关键词匹配、全文搜索）~500-2000 tokens
    - Layer 4: 历史对话记忆（跨会话持久化摘要）~800 tokens
    """

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            # 默认使用项目根目录下的 data/exports_html
            # backend/app/services -> ../../../data/exports_html
            backend_dir = Path(__file__).parent.parent.parent
            self.data_dir = backend_dir.parent / "data" / "exports_html"
        else:
            self.data_dir = Path(data_dir)
        self._meta_cache: Optional[str] = None  # Layer 0 缓存
        self._table_index_cache: Optional[str] = None  # Layer 1 缓存
        self._loaded_sessions: Set[str] = set()  # 已加载 Layer 0/1 的会话
        self._max_rag_tokens: int = 15000  # RAG 层最大 token 数量
        self._layer_tokens: Dict[str, int] = {"layer0": 0, "layer1": 0, "layer2": 0, "layer3": 0, "layer4": 0, "total": 0}  # 各层 token 使用量

        # Material status tracking
        self._material_status: Dict[str, Any] = {
            "has_documents": False,
            "document_count": 0,
            "documents": [],
        }

        # Layer 4: initialize memory service
        try:
            from app.config import settings
            from app.services.memory_service import MemoryService
            self._memory_service = MemoryService(str(settings.MEMORY_DIR))
        except Exception as e:
            logger.warning(f"[上下文] 记忆服务初始化失败: {e}")
            self._memory_service = None
        
    def _get_all_documents(self) -> List[Dict[str, Any]]:
        """获取所有文档的 index.json"""
        documents = []
        
        if not self.data_dir.exists():
            logger.warning(f"[上下文] 数据目录不存在: {self.data_dir}")
            return documents
        
        for doc_dir in self.data_dir.iterdir():
            if not doc_dir.is_dir():
                continue
            
            index_path = doc_dir / "index.json"
            if not index_path.exists():
                continue
            
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    index_data = json.load(f)
                    index_data["_doc_dir"] = doc_dir.name  # 保存目录名
                    documents.append(index_data)
            except Exception as e:
                logger.error(f"[上下文] 读取 index.json 失败: {index_path}, {e}")
        
        logger.info(f"[上下文] 找到 {len(documents)} 个文档")
        return documents
    
    def load_meta_index(self, force_reload: bool = False) -> str:
        """加载 Layer 0: 元信息索引
        
        包含：
        - 所有文档的名称
        - 每个文档的表格 ID 列表
        - 每个文档的材料列表
        
        预估 tokens: ~500
        """
        if self._meta_cache and not force_reload:
            return self._meta_cache
        
        documents = self._get_all_documents()
        
        if not documents:
            self._meta_cache = "# 参考文档\n\n当前没有可用的工艺文档。"
            self._material_status = {
                "has_documents": False,
                "document_count": 0,
                "documents": [],
            }
            return self._meta_cache
        
        # 构建元信息
        lines = ["# 参考文档索引\n"]
        lines.append("以下是系统中可用的工艺文档：\n")

        # Track material status
        doc_list = []
        for doc in documents:
            doc_name = doc.get("name", "未命名文档")
            pages = doc.get("pages", 0)
            tables = doc.get("tables", [])
            materials = doc.get("materials", [])
            
            lines.append(f"## {doc_name}")
            lines.append(f"- 页数: {pages}")
            
            if tables:
                table_ids = [t.get("id", "") for t in tables]
                lines.append(f"- 表格: {', '.join(table_ids[:10])}" + 
                           (f" 等{len(tables)}个" if len(tables) > 10 else ""))
            
            if materials:
                lines.append(f"- 材料: {', '.join(materials[:5])}" + 
                           (f" 等{len(materials)}种" if len(materials) > 5 else ""))
            
            lines.append("")

            doc_list.append({
                "name": doc_name,
                "pages": pages,
                "table_count": len(tables),
                "materials": materials,
            })

        self._material_status = {
            "has_documents": len(doc_list) > 0,
            "document_count": len(doc_list),
            "documents": doc_list,
        }

        self._meta_cache = "\n".join(lines)
        logger.info(f"[上下文] Layer 0 加载完成，长度: {len(self._meta_cache)}")
        return self._meta_cache
    
    def load_table_index(self, force_reload: bool = False) -> str:
        """加载 Layer 1: 表格索引
        
        包含：
        - 所有表格的 ID、类型、页码、摘要
        
        预估 tokens: ~2000
        """
        if self._table_index_cache and not force_reload:
            return self._table_index_cache
        
        documents = self._get_all_documents()
        
        if not documents:
            self._table_index_cache = ""
            return self._table_index_cache
        
        # 构建表格索引
        lines = ["# 表格索引\n"]
        lines.append("以下是所有可用表格的详细信息：\n")
        
        for doc in documents:
            doc_name = doc.get("name", "未命名文档")
            tables = doc.get("tables", [])
            
            if not tables:
                continue
            
            lines.append(f"## {doc_name}")
            
            for table in tables:
                table_id = table.get("id", "")
                table_type = table.get("type", "")
                page = table.get("page", 0)
                summary = table.get("summary", "")
                
                lines.append(f"- **{table_id}** (第{page}页): {table_type}")
                if summary:
                    lines.append(f"  - {summary}")
            
            lines.append("")
        
        self._table_index_cache = "\n".join(lines)
        logger.info(f"[上下文] Layer 1 加载完成，长度: {len(self._table_index_cache)}")
        return self._table_index_cache
    
    def search_tables(self, query: str, top_k: int = 5) -> List[TableMatch]:
        """搜索相关表格
        
        匹配规则：
        1. 表格 ID 精确匹配（如 "G4a"）
        2. 表格类型匹配（如 "工艺卡片"）- 支持子串匹配
        3. 摘要关键词匹配 - 使用 jieba 分词
        4. 材料名称匹配
        5. 文档名称匹配
        
        Args:
            query: 用户查询
            top_k: 返回最多 top_k 个结果
            
        Returns:
            匹配的表格列表，按相关性排序
        """
        documents = self._get_all_documents()
        matches = []
        
        query_lower = query.lower()
        query_keywords = extract_keywords(query)
        
        for doc in documents:
            doc_name = doc.get("name", "未命名文档")
            tables = doc.get("tables", [])
            materials = doc.get("materials", [])
            
            for table in tables:
                table_id = table.get("id", "")
                table_type = table.get("type", "")
                page = table.get("page", 0)
                summary = table.get("summary", "")
                
                score = 0.0
                
                # 1. 表格 ID 精确匹配（最高优先级）
                if table_id.lower() in query_lower:
                    score += 10.0
                
                # 2. 表格类型匹配（支持子串匹配，如 "工艺卡片" 匹配 "装配工艺卡片"）
                if table_type:
                    type_lower = table_type.lower()
                    # 双向匹配：查询包含类型，或类型包含查询中的词
                    if type_lower in query_lower:
                        score += 5.0
                    else:
                        # 检查是否有部分匹配（如 "装配工艺卡片" 包含 "工艺卡片"）
                        type_keywords = extract_keywords(table_type)
                        overlap = len(query_keywords & type_keywords)
                        if overlap > 0:
                            score += overlap * 3.0
                
                # 3. 摘要关键词匹配（使用改进的分词）
                if summary:
                    summary_keywords = extract_keywords(summary)
                    overlap = len(query_keywords & summary_keywords)
                    score += overlap * 2.0
                
                # 4. 材料名称匹配
                for material in materials:
                    if material.lower() in query_lower:
                        score += 3.0
                        break
                
                # 5. 文档名称匹配
                if doc_name.lower() in query_lower:
                    score += 4.0
                
                # 只保留有匹配的结果
                if score > 0:
                    match = TableMatch(
                        doc_name=doc_name,
                        table_id=table_id,
                        table_type=table_type,
                        page=page,
                        summary=summary,
                        score=score
                    )
                    matches.append(match)
        
        # 按分数排序，返回 top_k
        matches.sort(key=lambda x: x.score, reverse=True)
        result = matches[:top_k]
        
        logger.info(f"[上下文] 表格搜索完成: query={query[:30]}, 找到 {len(result)} 个匹配")
        return result
    
    def search_meta_info(self, query: str) -> Optional[str]:
        """查询元信息（文档页数、材料列表等）
        
        适用于：
        - "XX文档有多少页"
        - "有哪些材料"
        - "XX表格在哪个文档"
        - "工艺卡片在哪"
        
        Returns:
            快速回答字符串，如果没有匹配则返回 None
        """
        documents = self._get_all_documents()
        query_lower = query.lower()
        
        # 检测查询类型
        is_page_query = any(kw in query_lower for kw in ['多少页', '页数', '几页'])
        is_location_query = any(kw in query_lower for kw in ['在哪个', '在哪', '在哪里', '位置'])
        is_material_query = any(kw in query_lower for kw in ['有哪些材料', '什么材料', '材料列表'])
        
        if is_page_query:
            # 查询页数
            for doc in documents:
                doc_name = doc.get("name", "")
                if doc_name and doc_name.lower() in query_lower:
                    pages = doc.get("pages", "未知")
                    tables_count = len(doc.get("tables", []))
                    return f"文档「{doc_name}」共有 {pages} 页，包含 {tables_count} 个表格。"
            
            # 如果没有指定文档，返回所有文档的页数
            if '所有' in query_lower or '全部' in query_lower:
                summary = []
                for doc in documents:
                    doc_name = doc.get("name", "")
                    pages = doc.get("pages", "未知")
                    summary.append(f"「{doc_name}」: {pages} 页")
                return "文档页数统计：\n" + "\n".join(summary)
        
        if is_location_query:
            # 查询表格位置
            for doc in documents:
                doc_name = doc.get("name", "")
                tables = doc.get("tables", [])
                for table in tables:
                    table_id = table.get("id", "")
                    table_type = table.get("type", "")
                    if table_id.lower() in query_lower or (table_type and table_type.lower() in query_lower):
                        page = table.get("page", "未知")
                        return f"表格 {table_id}（{table_type}）位于文档「{doc_name}」第 {page} 页。"
        
        if is_material_query:
            # 查询材料列表
            all_materials = set()
            for doc in documents:
                materials = doc.get("materials", [])
                all_materials.update(materials)
            
            if all_materials:
                return f"系统中包含的材料：{', '.join(sorted(all_materials)[:20])}"
        
        return None
    
    def extract_table_html(self, doc_dir_name: str, table_id: str) -> str:
        """从 document.html 中提取指定表格
        
        Args:
            doc_dir_name: 文档目录名
            table_id: 表格 ID（如 "G4a"）
            
        Returns:
            表格的 HTML 内容
        """
        doc_dir = self.data_dir / doc_dir_name
        html_path = doc_dir / "document.html"
        
        if not html_path.exists():
            logger.warning(f"[上下文] HTML 文件不存在: {html_path}")
            return f"[表格 {table_id} 的 HTML 内容未找到]"
        
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            
            soup = BeautifulSoup(html_content, "html.parser")
            
            # 策略 1: 查找 id="table-{table_id}" 的 div，然后提取其中的 table
            table_anchor = soup.find("div", {"id": f"table-{table_id}"})
            if table_anchor:
                # 查找这个 div 的下一个兄弟元素中的 table-container
                table_container = table_anchor.find_next_sibling("div", class_="table-container")
                if table_container:
                    table = table_container.find("table")
                    if table:
                        return str(table)
            
            # 策略 2: 查找包含 table_id 的表格（如 id="G4a" 或 data-id="G4a"）
            table = soup.find("table", {"id": table_id})
            if table:
                return str(table)
            
            table = soup.find("table", {"data-id": table_id})
            if table:
                return str(table)
            
            # 策略 3: 查找包含 table_id 文本的表格（如标题行）
            tables = soup.find_all("table")
            for table in tables:
                table_text = table.get_text()
                if table_id in table_text:
                    # 提取这个表格
                    return str(table)
            
            # 策略 4: 根据 page 信息定位（如果有页码标记）
            # 这里假设 HTML 中有页码标记，如 <div class="page" data-page="2">
            # 如果没有找到，返回提示信息
            logger.warning(f"[上下文] 未找到表格 {table_id}")
            return f"[表格 {table_id} 的内容未在 HTML 中找到]"
            
        except Exception as e:
            logger.error(f"[上下文] 提取表格失败: {e}")
            return f"[提取表格 {table_id} 失败: {str(e)}]"
    
    def _estimate_tokens(self, text: str) -> int:
        """估算文本的 token 数量
        
        中文按 1.5 tokens/字符，英文按 0.25 tokens/字符
        """
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars * 0.25)
    
    def build_context(
        self, 
        query: str, 
        session_id: str, 
        max_tokens: int = 15000
    ) -> str:
        """构建分层上下文
        
        流程：
        1. 加载 Layer 0（元信息）- 会话级加载一次
        2. 加载 Layer 1（表格索引）- 会话级加载一次
        3. 根据查询匹配相关表格（Layer 2）
        4. 如果有参数关键词，进行精确检索（Layer 3）
        
        Args:
            query: 用户查询
            session_id: 会话 ID
            max_tokens: 最大 token 数量（优先使用 set_max_tokens 设置的值）
            
        Returns:
            构建的上下文字符串
        """
        # 使用 set_max_tokens 设置的值，如果未设置则使用参数
        effective_max_tokens = min(max_tokens, self._max_rag_tokens)
        
        context_parts = []
        used_tokens = 0
        
        # 重置 token 统计
        self._layer_tokens = {"layer0": 0, "layer1": 0, "layer2": 0, "layer3": 0, "layer4": 0, "total": 0}
        
        logger.info(f"[上下文] 开始构建上下文: session={session_id}, query={query[:50]}, max_tokens={effective_max_tokens}")
        
        # Layer 0: 元信息索引（会话级加载一次）
        layer0_key = f"{session_id}_layer0"
        if layer0_key not in self._loaded_sessions:
            meta = self.load_meta_index()
            meta_tokens = self._estimate_tokens(meta)
            context_parts.append(meta)
            used_tokens += meta_tokens
            self._layer_tokens["layer0"] = meta_tokens
            self._loaded_sessions.add(layer0_key)
            logger.info(f"[上下文] Layer 0 已加载: {used_tokens} tokens")
        
        # Layer 1: 表格索引（会话级加载一次）
        layer1_key = f"{session_id}_layer1"
        if layer1_key not in self._loaded_sessions:
            table_index = self.load_table_index()
            table_index_tokens = self._estimate_tokens(table_index)
            context_parts.append(table_index)
            used_tokens += table_index_tokens
            self._layer_tokens["layer1"] = table_index_tokens
            self._loaded_sessions.add(layer1_key)
            logger.info(f"[上下文] Layer 1 已加载: 总计 {used_tokens} tokens")
        
        # Layer 2: 按需加载相关表格
        matched_tables = self.search_tables(query, top_k=3)
        layer2_tokens = 0
        
        for table in matched_tables:
            # 获取文档目录名
            documents = self._get_all_documents()
            doc_dir_name = None
            for doc in documents:
                if doc.get("name") == table.doc_name:
                    doc_dir_name = doc.get("_doc_dir")
                    break
            
            if not doc_dir_name:
                continue
            
            # 提取表格 HTML
            table_html = self.extract_table_html(doc_dir_name, table.table_id)
            table_tokens = self._estimate_tokens(table_html)
            
            # 检查是否超过 token 限制
            if used_tokens + table_tokens > effective_max_tokens:
                logger.warning(f"[上下文] 达到 token 限制，跳过表格 {table.table_id}")
                break
            
            # 添加表格上下文
            table_context = f"\n## 表格 {table.table_id} (第{table.page}页)\n\n{table_html}\n"
            context_parts.append(table_context)
            used_tokens += table_tokens
            layer2_tokens += table_tokens
            logger.info(f"[上下文] Layer 2 加载表格 {table.table_id}: {table_tokens} tokens, 总计 {used_tokens} tokens")
        
        self._layer_tokens["layer2"] = layer2_tokens

        # Layer 3: 全局关键词搜索
        layer3_tokens = 0
        remaining_tokens = effective_max_tokens - used_tokens
        l3_budget = int(remaining_tokens * 0.5)  # L3 使用剩余 token 的 50%

        if l3_budget > 200:  # 至少要有 200 token 的预算
            search_results = self.global_keyword_search(query, top_k=10)

            if search_results:
                l3_lines = ["\n## 全局关键词搜索结果\n"]
                l3_current_tokens = self._estimate_tokens(l3_lines[0])

                for result in search_results:
                    entry = (
                        f"- **{result['doc_name']}** (第{result['page']}页, "
                        f"相关度:{result['score']:.0f}): {result['snippet']}"
                    )
                    entry_tokens = self._estimate_tokens(entry)

                    if l3_current_tokens + entry_tokens > l3_budget:
                        break

                    l3_lines.append(entry)
                    l3_current_tokens += entry_tokens

                if len(l3_lines) > 1:  # 有实际内容（不只是标题）
                    l3_context = "\n".join(l3_lines)
                    context_parts.append(l3_context)
                    used_tokens += l3_current_tokens
                    layer3_tokens = l3_current_tokens
                    logger.info(f"[上下文] Layer 3 加载完成: {layer3_tokens} tokens, 总计 {used_tokens} tokens")

        self._layer_tokens["layer3"] = layer3_tokens

        # Layer 4: historical conversation memory
        layer4_tokens = 0
        if self._memory_service:
            try:
                from app.config import settings
                memory_budget = min(settings.MEMORY_MAX_TOKENS, effective_max_tokens - used_tokens)
                if memory_budget > 100:
                    memory_text = self._load_filtered_memory(query, memory_budget)
                    if memory_text:
                        memory_section = f"\n## 历史对话记忆\n\n{memory_text}\n"
                        layer4_tokens = self._estimate_tokens(memory_section)
                        context_parts.append(memory_section)
                        used_tokens += layer4_tokens
                        logger.info(f"[上下文] Layer 4 加载完成: {layer4_tokens} tokens, 总计 {used_tokens} tokens")
            except Exception as e:
                logger.warning(f"[上下文] Layer 4 记忆加载失败: {e}")

        self._layer_tokens["layer4"] = layer4_tokens

        final_context = "\n\n---\n\n".join(context_parts)
        final_tokens = self._estimate_tokens(final_context)
        
        self._layer_tokens["total"] = final_tokens
        
        logger.info(f"[上下文] 上下文构建完成: {final_tokens} tokens, 长度 {len(final_context)}")
        return final_context
    
    def global_keyword_search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """全局关键词搜索 (Layer 3)

        遍历所有文档的 document.html，在纯文本中搜索关键词，
        返回包含关键词的段落/片段。

        Args:
            query: 用户查询文本
            top_k: 返回最多 top_k 个结果

        Returns:
            匹配片段列表，格式：
            [{"doc_name": ..., "snippet": ..., "score": ..., "page": ...}, ...]
        """
        keywords = extract_keywords(query)
        if not keywords:
            logger.info("[上下文] L3 搜索: 无有效关键词，跳过")
            return []

        logger.info(f"[上下文] L3 搜索: query={query[:50]}, keywords={keywords}")

        documents = self._get_all_documents()
        results: List[Dict[str, Any]] = []

        for doc in documents:
            doc_dir_name = doc.get("_doc_dir")
            if not doc_dir_name:
                continue

            doc_name = doc.get("name", "未命名文档")
            html_path = self.data_dir / doc_dir_name / "document.html"

            if not html_path.exists():
                continue

            try:
                with open(html_path, "r", encoding="utf-8") as f:
                    html_content = f.read()

                # 提取纯文本
                soup = BeautifulSoup(html_content, "html.parser")
                plain_text = soup.get_text(separator="\n")

                # 按段落分割（非空行）
                paragraphs = [p.strip() for p in plain_text.split("\n") if p.strip()]

                for para in paragraphs:
                    para_lower = para.lower()
                    # 计算命中关键词数
                    hit_keywords = {kw for kw in keywords if kw.lower() in para_lower}
                    if not hit_keywords:
                        continue

                    score = len(hit_keywords)

                    # 估算页码：简单按段落位置估算
                    page = self._estimate_page(para, paragraphs, doc.get("pages", 1))

                    # 提取片段：以第一个命中关键词为中心，前后各 100 字
                    snippet = self._extract_snippet(para, hit_keywords)

                    results.append({
                        "doc_name": doc_name,
                        "snippet": snippet,
                        "score": float(score),
                        "page": page,
                    })

            except Exception as e:
                logger.error(f"[上下文] L3 搜索文档失败: {doc_dir_name}, {e}")

        # 按分数降序排序，取 top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:top_k]

        logger.info(f"[上下文] L3 搜索完成: 找到 {len(results)} 个匹配片段")
        return results

    def _extract_snippet(self, paragraph: str, hit_keywords: Set[str]) -> str:
        """从段落中提取包含关键词的片段

        以第一个命中关键词为中心，前后各 100 字符。
        如果段落长度 <= 300 字符，直接返回整个段落。
        多个命中关键词距离近的合并为一个大片段。
        """
        MAX_SNIPPET = 300
        HALF_CONTEXT = 100

        if len(paragraph) <= MAX_SNIPPET:
            return paragraph

        # 找到所有命中关键词的位置
        positions = []
        para_lower = paragraph.lower()
        for kw in hit_keywords:
            start = 0
            while True:
                idx = para_lower.find(kw.lower(), start)
                if idx == -1:
                    break
                positions.append(idx)
                start = idx + 1

        if not positions:
            return paragraph[:MAX_SNIPPET]

        positions.sort()

        # 合并距离近的命中位置（距离 < 200 的合并为一个区间）
        MERGE_THRESHOLD = 200
        ranges = []
        cur_start = max(0, positions[0] - HALF_CONTEXT)
        cur_end = min(len(paragraph), positions[0] + HALF_CONTEXT)

        for pos in positions[1:]:
            new_start = max(0, pos - HALF_CONTEXT)
            new_end = min(len(paragraph), pos + HALF_CONTEXT)
            if new_start <= cur_end + MERGE_THRESHOLD:
                # 合并
                cur_end = max(cur_end, new_end)
            else:
                ranges.append((cur_start, cur_end))
                cur_start = new_start
                cur_end = new_end
        ranges.append((cur_start, cur_end))

        # 拼接片段，用 "..." 连接
        snippets = []
        total_len = 0
        for start, end in ranges:
            snippet_part = paragraph[start:end]
            snippets.append(snippet_part)
            total_len += len(snippet_part) + 3  # +3 for "..."
            if total_len >= MAX_SNIPPET:
                break

        result = "...".join(snippets)
        if len(result) > MAX_SNIPPET:
            result = result[:MAX_SNIPPET] + "..."

        return result

    def _estimate_page(self, paragraph: str, all_paragraphs: List[str], total_pages: int) -> int:
        """根据段落位置估算页码"""
        if total_pages <= 1:
            return 1
        try:
            idx = all_paragraphs.index(paragraph)
            # 按比例估算
            ratio = idx / len(all_paragraphs)
            return max(1, min(total_pages, int(ratio * total_pages) + 1))
        except ValueError:
            return 1

    def clear_session(self, session_id: str):
        """清除会话的缓存
        
        当会话结束或需要重新加载时调用
        """
        layer0_key = f"{session_id}_layer0"
        layer1_key = f"{session_id}_layer1"
        
        self._loaded_sessions.discard(layer0_key)
        self._loaded_sessions.discard(layer1_key)
        
        logger.info(f"[上下文] 会话缓存已清除: {session_id}")
    
    def set_max_tokens(self, max_tokens: int) -> None:
        """设置 RAG 层最大 token 数量
        
        供 ContextService 调用，限制 RAG 层的 token 使用
        
        Args:
            max_tokens: 最大 token 数量
        """
        self._max_rag_tokens = max_tokens
        logger.info(f"[上下文] RAG 层 token 限制设置为: {max_tokens}")
    
    def get_layer_tokens(self) -> Dict[str, int]:
        """获取各层 token 使用情况

        Returns:
            {"layer0": 500, "layer1": 2000, "layer2": 3000, "layer3": 500, "layer4": 300, "total": 6300}
        """
        return self._layer_tokens.copy()

    def get_material_status(self, query: str = "") -> Dict[str, Any]:
        """Get structured material status summary.

        Returns a dict with:
        - has_documents: bool
        - document_count: int
        - documents: list of available documents
        - search_performed: bool (whether any search context was built)
        - missing_topics: list of topics from the query not covered by materials

        Args:
            query: User query to analyze for missing topics

        Returns:
            Material status dict
        """
        status = dict(self._material_status)
        status["search_performed"] = self._meta_cache is not None

        # Analyze missing topics from query
        missing: List[str] = []
        if query and status["has_documents"]:
            query_keywords = extract_keywords(query)
            covered: Set[str] = set()
            for doc in status["documents"]:
                # Collect all known topics from document names, materials, table types
                covered.add(doc["name"].lower())
                for m in doc.get("materials", []):
                    covered.update(extract_keywords(m))

            # Check which query keywords are not covered
            for kw in query_keywords:
                kw_lower = kw.lower()
                if not any(kw_lower in c or c in kw_lower for c in covered):
                    missing.append(kw)

        status["missing_topics"] = missing
        return status

    def _load_filtered_memory(self, query: str, max_tokens: int) -> str:
        """Load memory filtered by query relevance.

        1. Keyword-match against query; inject top 2-3 relevant memories.
        2. Fallback: inject the most recent 1 memory.
        """
        if not self._memory_service:
            return ""

        query_keywords = extract_keywords(query)
        memory_dir = self._memory_service.memory_dir
        if not memory_dir.exists():
            return ""

        def _safe_mtime(p: Path) -> float:
            try:
                return p.stat().st_mtime
            except OSError:
                return 0.0

        memory_files = sorted(
            memory_dir.glob("*.md"),
            key=_safe_mtime,
            reverse=True,
        )
        if not memory_files:
            return ""

        # Score each memory file by keyword overlap
        scored: List[tuple] = []  # (score, path, content)
        for mf in memory_files:
            try:
                content = mf.read_text(encoding="utf-8")
                if not query_keywords:
                    scored.append((0.0, mf, content))
                else:
                    content_keywords = extract_keywords(content)
                    overlap = len(query_keywords & content_keywords)
                    scored.append((float(overlap), mf, content))
            except Exception:
                continue

        # Sort: relevant first, then recent (already sorted by mtime desc)
        scored.sort(key=lambda x: x[0], reverse=True)

        # Pick relevant memories (score > 0) or fallback to most recent
        relevant = [(s, c) for s, _, c in scored if s > 0]
        selected = relevant[:2] if relevant else [(scored[0][0], scored[0][2])] if scored else []

        if not selected:
            return ""

        parts: List[str] = []
        used_tokens = 0
        for _, content in selected:
            tokens = self._estimate_tokens(content)
            if used_tokens + tokens > max_tokens:
                remaining = max_tokens - used_tokens
                if remaining > 100:
                    parts.append(self._memory_service._truncate_to_tokens(content, remaining))
                    used_tokens += remaining
                break
            parts.append(content)
            used_tokens += tokens

        return "\n\n---\n\n".join(parts)


# 全局单例
hierarchical_context = HierarchicalContext()
