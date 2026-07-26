"""
分层上下文管理器
实现 Just-in-Time Retrieval + Progressive Disclosure
"""
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import json
import re
import time
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


def extract_keywords(text: str) -> List[str]:
    """提取关键词（支持中文）
    
    使用 jieba 分词，如果未安装则回退到简单正则匹配
    """
    if JIEBA_AVAILABLE:
        # 使用 jieba 分词
        words = jieba.cut(text)
        # 过滤停用词和单字
        stopwords = {'的', '了', '是', '有', '在', '我', '你', '他', '这', '那', '和', '与', '或', '个', '们', '等', '要', '会', '能', '对', '把', '被', '让', '给', '到', '从', '向', '往', '在', '着', '过', '地', '得'}
        return list(dict.fromkeys(
            w.lower() for w in words
            if len(w) > 1 and w not in stopwords and not w.isspace()
        ))
    else:
        # 简单正则匹配（中文字符 + 英文单词）
        chinese_words = re.findall(r'[\u4e00-\u9fff]{2,}', text)
        english_words = re.findall(r'[a-zA-Z]{2,}', text.lower())
        return list(dict.fromkeys(chinese_words + english_words))


# Audit/signature markers found in source process docs (every page has a
# 会签 block with 审核/批准/校对/签名/更改单号). These are company review
# workflow, NOT process content — filtered out when converting source HTML
# so the LLM never sees them and cannot copy them into generated output.
_AUDIT_MARKERS = ("会签", "审核", "批准", "校对", "签名", "更改单号")

# G25a substep filter. When grouping 工序内容 rows under a step, reject cells
# that are header residue (续页表头列名) or audit/signature noise. Originally
# only N.M-prefixed rows were captured, which silently dropped steps whose
# substeps carry no N.M number (e.g. step 9 → 0 substeps).
_SUBSTEP_HEADER_WORDS = frozenset({
    "车间", "工序号", "工序名称", "工序内容", "辅助材料", "专用仪器",
    "准结", "单件", "总计", "设备", "工艺装备",
    # 续页/首页表头残留列名 (产品/零件元信息区), never a real substep.
    # After parts-list detection was narrowed, these header words can leak
    # into the substep list, so reject them here too.
    "产品工号", "产品数字", "工艺文件编号", "装配工艺卡", "装配工艺卡片(续)",
    "零、部、组(整)件代号", "零、部、组(整)件名称", "代号", "名称", "数量",
})
_SUBSTEP_NOISE_MARKERS = (
    "会签", "审核", "批准", "校对", "签名", "编制", "标检", "更改单号",
    "日期", "页数", "页码",
)

# G25a 配套零件清单区. Each step ends with a parts sub-table
# (代号/名称/编号/数量). Once its header row appears, every row until the
# next step header belongs to the parts list — not process content — so skip
# them all to avoid pulling part names/codes into the substep list.
# NOTE: only the parts-list-EXCLUSIVE phrases are used. The generic header
# column names ("产品工号"/"产品数字"/"零、部、组(整)件代号") also appear in
# 续页表头 rows ("装配工艺卡片(续) ... 产品数字 ..."), so matching them would
# wrongly flag every continuation-page header as a parts list and drop all
# substeps on that page (G25a op5 lost 5.1.3/5.2/... this way). The exclusive
# phrases (交往何处/单套产品中装配件数量/本批装配件生产总数) only occur in the
# real parts-list header, so they distinguish the two safely.
_PARTS_LIST_MARKERS = (
    "交往何处", "单套产品中装配件数量", "本批装配件生产总数",
)


def _is_substep_content(content: str) -> bool:
    """True if a 工序内容 cell is a real substep, not header residue or noise."""
    if content in _SUBSTEP_HEADER_WORDS:
        return False
    if not content.strip("-–— \t"):  # pure separator row like '---'
        return False
    if any(m in content for m in _SUBSTEP_NOISE_MARKERS):
        return False
    return True


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
            from app.config import settings
            self.data_dir = settings.DOCUMENTS_DIR
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

        # Documents list cache (mirrors materials table; TTL-based to avoid
        # opening a DB session on every call within one build_context chain)
        self._documents_cache: Optional[List[Dict[str, Any]]] = None
        self._documents_cache_ts: float = 0.0
        self._documents_cache_ttl: float = 30.0

        # Layer 4: initialize memory service
        try:
            from app.config import settings
            from app.services.memory_service import MemoryService
            self._memory_service = MemoryService(str(settings.MEMORY_DIR))
        except Exception as e:
            logger.warning(f"[上下文] 记忆服务初始化失败: {e}")
            self._memory_service = None

    def invalidate_cache(self):
        """Clear all caches so next query reloads from disk."""
        self._meta_cache = None
        self._table_index_cache = None
        self._loaded_sessions.clear()
        self._material_status = {
            "has_documents": False,
            "document_count": 0,
            "documents": [],
        }
        self._documents_cache = None
        self._documents_cache_ts = 0.0
        logger.info("[上下文] 缓存已清除")
        
    def _get_all_documents(
        self, filters: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Get all available documents.

        Data source = materials table (素材库). Each Material maps to
        documents/{material_id}/, indexed by chapter_index.json + content.html.
        Falls back to scanning index.json so legacy/DB-less environments and
        existing tests still work.

        filters: optional {"model": ..., "specialty": ...} for 检索穿透 (节点4).
        When set, only DB docs matching are returned; file-scan fallback is
        skipped (legacy docs have no model/specialty).
        """
        # TTL cache: only for unfiltered calls (filtered result != full cache).
        if filters is None and self._documents_cache is not None and \
                (time.time() - self._documents_cache_ts) < self._documents_cache_ttl:
            return self._documents_cache

        documents: List[Dict[str, Any]] = []
        seen_dirs: Set[str] = set()

        # Primary path: materials table (source of truth for 素材库)
        try:
            from app.database import SessionLocal
            from app.models.database import Material
            db = SessionLocal()
            try:
                q = db.query(Material)
                if filters:
                    if filters.get("specialty"):
                        q = q.filter(Material.specialty == filters["specialty"])
                    if filters.get("model"):
                        q = q.filter(Material.model == filters["model"])
                materials = q.order_by(Material.created_at.desc()).all()
                for m in materials:
                    doc_dir_name = str(m.id)
                    doc_dir = self.data_dir / doc_dir_name
                    if not doc_dir.exists():
                        continue  # DB row exists but files removed → skip
                    documents.append(self._build_doc_dict(
                        doc_dir_name, m.name, m.model, m.specialty,
                    ))
                    seen_dirs.add(doc_dir_name)
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"[上下文] materials 查询失败，回退文件扫描: {e}")

        # Fallback path: scan index.json (legacy/standard docs, DB-less envs)
        if self.data_dir.exists():
            for doc_dir in self.data_dir.iterdir():
                if not doc_dir.is_dir() or doc_dir.name in seen_dirs:
                    continue
                index_path = doc_dir / "index.json"
                if not index_path.exists():
                    continue
                try:
                    with open(index_path, "r", encoding="utf-8") as f:
                        index_data = json.load(f)
                        index_data["_doc_dir"] = doc_dir.name
                        documents.append(index_data)
                        seen_dirs.add(doc_dir.name)
                except Exception as e:
                    logger.error(f"[上下文] 读取 index.json 失败: {index_path}, {e}")

        self._documents_cache = documents
        self._documents_cache_ts = time.time()
        logger.info(f"[上下文] 找到 {len(documents)} 个文档")
        return documents

    def _build_doc_dict(
        self, doc_dir_name: str, name: str,
        model: Optional[str] = None, specialty: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a doc dict for a materials-table document.

        Mirrors the index.json shape consumed by downstream layers
        (name/pages/tables/materials/_doc_dir/model/specialty). model/specialty
        carry the 检索穿透 dimensions (cleanup-and-dimensions 节点4).
        """
        doc_dir = self.data_dir / doc_dir_name
        pages = 0
        chapter_path = doc_dir / "chapter_index.json"
        if chapter_path.exists():
            try:
                with open(chapter_path, "r", encoding="utf-8") as f:
                    ch = json.load(f)
                    pages = ch.get("total_pages", 0) or 0
            except Exception as e:
                logger.warning(f"[上下文] 读取 chapter_index.json 失败: {chapter_path}, {e}")
        return {
            "name": name,
            "pages": pages,
            "tables": [],
            "materials": [],
            "_doc_dir": doc_dir_name,
            "model": model,
            "specialty": specialty,
        }
    
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
    
    def search_tables(
        self, query: str, top_k: int = 5,
        filters: Optional[Dict[str, str]] = None,
    ) -> List[TableMatch]:
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
        documents = self._get_all_documents(filters)
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
                        overlap = len(set(query_keywords) & set(type_keywords))
                        if overlap > 0:
                            score += overlap * 3.0
                
                # 3. 摘要关键词匹配（使用改进的分词）
                if summary:
                    summary_keywords = extract_keywords(summary)
                    overlap = len(set(query_keywords) & set(summary_keywords))
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
        """从 content.html / document.html 中提取指定表格

        Args:
            doc_dir_name: 文档目录名
            table_id: 表格 ID（如 "G4a"）

        Returns:
            表格的 HTML 内容
        """
        from app.config import settings
        doc_dir = self.data_dir / doc_dir_name
        html_path = settings.resolve_doc_content_html(doc_dir)

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
        max_tokens: int = 15000,
        mode: str = "write",
    ) -> str:
        """构建分层上下文

        Args:
            query: 用户查询
            session_id: 会话 ID
            max_tokens: 最大 token 数量（优先使用 set_max_tokens 设置的值）
            mode: context loading strategy
                - "qa": L0 + L3 + L4 (fast search, ~5000 tokens)
                - "write": L0-L4 full load (~15000 tokens)
                - "review": L0 + L1 + L3 (structure-aware, no heavy tables)

        Returns:
            构建的上下文字符串
        """
        # Adjust token budget by mode
        mode_budgets = {"qa": 5000, "write": 15000, "review": 10000}
        mode_budget = mode_budgets.get(mode, 15000)
        effective_max_tokens = min(max_tokens, self._max_rag_tokens, mode_budget)
        
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
        
        # Layer 1: 表格索引（write and review modes only）
        layer1_key = f"{session_id}_layer1"
        if mode in ("write", "review") and layer1_key not in self._loaded_sessions:
            table_index = self.load_table_index()
            table_index_tokens = self._estimate_tokens(table_index)
            context_parts.append(table_index)
            used_tokens += table_index_tokens
            self._layer_tokens["layer1"] = table_index_tokens
            self._loaded_sessions.add(layer1_key)
            logger.info(f"[上下文] Layer 1 已加载: 总计 {used_tokens} tokens")
        
        # Layer 2: On-demand table loading (write mode only — heavy)
        layer2_tokens = 0
        if mode != "write":
            logger.info(f"[上下文] Layer 2 跳过 (mode={mode})")
        else:
            matched_tables = self.search_tables(query, top_k=3)

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

        # Layer 3.5: KG (辅料-标准-参数图谱) — N3
        layer35_tokens = 0
        kg_remaining = effective_max_tokens - used_tokens
        kg_budget = min(1500, int(kg_remaining * 0.5))  # 留一半给 L4 memory
        if kg_budget > 200:
            try:
                kg_context = self._search_knowledge_graph(query, kg_budget)
                if kg_context:
                    layer35_tokens = self._estimate_tokens(kg_context)
                    context_parts.append(kg_context)
                    used_tokens += layer35_tokens
                    logger.info(f"[上下文] Layer 3.5 KG 加载完成: {layer35_tokens} tokens, 总计 {used_tokens} tokens")
            except Exception as e:
                logger.warning(f"[上下文] Layer 3.5 KG 加载失败: {e}")
        self._layer_tokens["layer3.5"] = layer35_tokens

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
    
    def global_keyword_search(
        self, query: str, top_k: int = 10,
        filters: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
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

        documents = self._get_all_documents(filters)
        results: List[Dict[str, Any]] = []

        for doc in documents:
            doc_dir_name = doc.get("_doc_dir")
            if not doc_dir_name:
                continue

            doc_name = doc.get("name", "未命名文档")
            doc_dir = self.data_dir / doc_dir_name
            from app.config import settings
            html_path = settings.resolve_doc_content_html(doc_dir)

            if not html_path.exists():
                continue

            try:
                with open(html_path, "r", encoding="utf-8") as f:
                    html_content = f.read()

                # 提取纯文本
                soup = BeautifulSoup(html_content, "html.parser")
                plain_text = soup.get_text(separator="\n")

                # Split into lines, then group by PDF page (## 第 N 页)
                lines = plain_text.split("\n")
                pages: Dict[int, str] = {}  # page_number -> full page text
                current_page = 0
                current_lines: List[str] = []
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("## 第") and "页" in stripped:
                        # Save previous page
                        if current_page > 0:
                            pages[current_page] = "\n".join(current_lines)
                        import re
                        m = re.search(r"第\s*(\d+)\s*页", stripped)
                        current_page = int(m.group(1)) if m else current_page + 1
                        current_lines = []
                    else:
                        if stripped:
                            current_lines.append(stripped)
                # Save last page
                if current_page > 0:
                    pages[current_page] = "\n".join(current_lines)

                # Build a paragraph->page mapping for keyword matching
                paragraphs = [p.strip() for p in plain_text.split("\n") if p.strip()]
                para_page_map: Dict[int, int] = {}  # para index -> page number
                page_boundary = 0
                for idx, para in enumerate(paragraphs):
                    if para.startswith("## 第") and "页" in para:
                        import re
                        m = re.search(r"第\s*(\d+)\s*页", para)
                        page_boundary = int(m.group(1)) if m else page_boundary
                    para_page_map[idx] = page_boundary

                # Track which (doc, page) combos already added to avoid duplicates
                seen_doc_pages: Set[tuple] = set()
                # Collect hits: (score, para_idx) to rank
                hits: List[tuple] = []

                for idx, para in enumerate(paragraphs):
                    para_lower = para.lower()
                    hit_keywords = {kw for kw in keywords if kw.lower() in para_lower}
                    if not hit_keywords:
                        continue
                    hits.append((len(hit_keywords), idx, para))

                # Sort by score descending
                hits.sort(key=lambda x: x[0], reverse=True)

                for score, idx, para in hits:
                    page_num = para_page_map.get(idx, 0)
                    doc_page_key = (doc_name, page_num)
                    if doc_page_key in seen_doc_pages:
                        continue
                    seen_doc_pages.add(doc_page_key)

                    # Inject entire page content
                    if page_num > 0 and page_num in pages:
                        snippet = pages[page_num]
                        # Truncate if page is very long (> 2000 chars)
                        if len(snippet) > 2000:
                            snippet = snippet[:2000] + "\n...(页面内容过长，已截断)"
                    else:
                        snippet = para

                    results.append({
                        "doc_name": doc_name,
                        "snippet": snippet,
                        "score": float(score),
                        "page": page_num,
                    })

                    if len(seen_doc_pages) >= top_k:
                        break

            except Exception as e:
                logger.error(f"[上下文] L3 搜索文档失败: {doc_dir_name}, {e}")

        # 按分数降序排序，取 top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:top_k]

        logger.info(f"[上下文] L3 搜索完成: 找到 {len(results)} 个匹配片段")
        return results

    def extract_reference_methods(
        self,
        step_names: List[str],
        top_k: int = 2,
        context_chars: int = 400,
    ) -> List[Dict[str, Any]]:
        """按工序名召回同类工艺文件的「工序工艺方法段落」（套用素材，N2）。

        global_keyword_search 先按工序名召回整页 → 从页内精准抽取该工序
        附近的工艺方法段落（工序级，非整页片段），供 LLM 套用改写（不照抄）。

        Returns:
            [{step_name, doc_name, page, method_segment}, ...]
        """
        results: List[Dict[str, Any]] = []
        for step_name in step_names or []:
            if not step_name or len(step_name) < 2:
                continue
            hits = self.global_keyword_search(step_name, top_k=top_k)
            for hit in hits:
                snippet = hit.get("snippet", "")
                segment = self._extract_step_segment(snippet, step_name, context_chars)
                if segment:
                    results.append({
                        "step_name": step_name,
                        "doc_name": hit.get("doc_name"),
                        "page": hit.get("page"),
                        "method_segment": segment,
                    })
        logger.info(
            f"[上下文] 套用素材抽取: {len(step_names or [])} 工序 → {len(results)} 段落"
        )
        return results

    def _extract_step_segment(
        self,
        text: str,
        step_name: str,
        context_chars: int = 400,
    ) -> str:
        """从整页文本中抽取工序名附近的工艺方法段落（工序级）。

        定位工序名位置 → 取前后 context_chars 字符，并在下一个工序边界
        （「工序N」「第N道」等标记）处截断，避免跨工序。
        """
        if not text or not step_name:
            return ""
        idx = text.find(step_name)
        if idx < 0:
            return ""
        start = max(0, idx - 60)  # include a little before (工序号/名)
        end = min(len(text), idx + context_chars)
        segment = text[start:end]
        # Truncate at the next step boundary if one appears after the anchor
        import re
        anchor_in_seg = idx - start
        for m in re.finditer(r"(?:工序\s*\d|第\s*\d+\s*道|下一道)", segment):
            if m.start() > anchor_in_seg + len(step_name):
                segment = segment[: m.start()]
                break
        return segment.strip()

    def _search_knowledge_graph(self, query: str, max_tokens: int) -> str:
        """L3.5 KG 层：辅料-标准-参数图谱检索 (N3)。

        实体提取 → craft_kg expand(辅料-参数-工序) + KnowledgeSearchService(物料/标准条款)
        → 组合注入文本。KG/DB 空时返回 ""(in-context 先行, 数据下沉后自动启用)。
        """
        from app.services.knowledge_graph import craft_kg
        parts: List[str] = []

        # 1. craft_kg: query 实体 → seed 节点 → expand_context (辅料-参数-工序关系)
        if craft_kg.node_count > 0:
            keywords = extract_keywords(query)
            seed_ids: List[str] = []
            for kw in keywords[:5]:
                for nid in list(craft_kg._graph.nodes):
                    if kw in (craft_kg._graph.nodes[nid].get("label", "") or ""):
                        seed_ids.append(nid)
                        break
                if len(seed_ids) >= 5:
                    break
            if seed_ids:
                kg_text = craft_kg.to_context_text(
                    seed_node_ids=seed_ids, max_tokens=max_tokens // 2
                )
                if kg_text:
                    parts.append("## 知识图谱(辅料-参数-工序)\n" + kg_text)

        # 2. 结构化知识: MaterialCatalog + StandardClause (knowledge_search)
        try:
            from app.database import SessionLocal
            from app.services.knowledge_search import KnowledgeSearchService
            db = SessionLocal()
            try:
                ks = KnowledgeSearchService()
                ks_text = ks.build_knowledge_context_text(db, query, max_items=4)
                if ks_text:
                    parts.append("## 结构化知识(物料/标准条款)\n" + ks_text)
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"[上下文] L3.5 knowledge_search 失败: {e}")

        if not parts:
            return ""
        text = "\n\n".join(parts)
        max_chars = max_tokens * 4
        if len(text) > max_chars:
            text = text[:max_chars] + "\n...(KG 层内容已截断)"
        return text

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
        # Ensure material status is populated. The generation path calls
        # get_material_status directly (not via build_context), so we must
        # trigger load_meta_index which fills _material_status from the
        # documents list (materials table).
        if self._meta_cache is None:
            self.load_meta_index()

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
                    overlap = len(set(query_keywords) & set(content_keywords))
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

    # ==================== Chapter-level content retrieval ====================

    def load_chapter_index(self, doc_dir_name: str) -> Optional[Dict[str, Any]]:
        """Load chapter_index.json for a document.

        If the index does not exist, attempt to build it on the fly.

        Args:
            doc_dir_name: document directory name (e.g. "1")

        Returns:
            chapter_index dict or None
        """
        doc_dir = self.data_dir / doc_dir_name
        index_path = doc_dir / "chapter_index.json"

        if index_path.exists():
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("chapter_index_load_failed", path=str(index_path), error=str(e))

        # Build index on the fly if missing
        try:
            from app.services.document_indexer import DocumentIndexer
            indexer = DocumentIndexer(data_dir=self.data_dir)
            return indexer.build_index(doc_dir_name)
        except Exception as e:
            logger.warning("chapter_index_build_failed", doc_dir=doc_dir_name, error=str(e))
            return None

    def get_chapter_content(
        self, doc_dir_name: str, chapter_title: str, max_tokens: int = 12000
    ) -> Optional[str]:
        """Return full plain-text content for a named chapter.

        Args:
            doc_dir_name: document directory name (e.g. "1")
            chapter_title: chapter title to match (exact or substring)
            max_tokens: max token budget (approximate)

        Returns:
            Chapter text content, or None if not found
        """
        chapter_index = self.load_chapter_index(doc_dir_name)
        if not chapter_index:
            return None

        # Find matching chapter
        chapter = None
        for ch in chapter_index.get("chapters", []):
            if chapter_title in ch["title"]:
                chapter = ch
                break

        if not chapter:
            logger.warning("chapter_not_found", doc_dir=doc_dir_name, title=chapter_title)
            return None

        pages = chapter.get("pages", [])
        if not pages:
            return None

        return self.get_pages_content(doc_dir_name, pages[0], pages[-1], max_tokens)

    def get_pages_content(
        self, doc_dir_name: str, start_page: int, end_page: int,
        max_tokens: int = 12000,
    ) -> Optional[str]:
        """Return plain-text content for a page range.

        Extracts pages from content.html, strips HTML tags, and
        concatenates into a single string.

        Args:
            doc_dir_name: document directory name
            start_page: first page number (inclusive)
            end_page: last page number (inclusive)
            max_tokens: token budget

        Returns:
            Concatenated page text or None on failure
        """
        doc_dir = self.data_dir / doc_dir_name
        from app.config import settings
        html_path = settings.resolve_doc_content_html(doc_dir)

        if not html_path.exists():
            return None

        try:
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            soup = BeautifulSoup(html_content, "html.parser")
            # Convert HTML tables to Markdown tables for structured extraction
            plain_text = self._html_to_readable(soup)

            # Split into pages using same logic as global_keyword_search
            pages = self._split_text_by_pages(plain_text)

            # Collect pages in range
            selected_pages = []
            for pn in range(start_page, end_page + 1):
                if pn in pages:
                    selected_pages.append(f"--- 第{pn}页 ---\n{pages[pn]}")

            if not selected_pages:
                return None

            result = "\n\n".join(selected_pages)

            # Truncate if over token budget
            estimated = self._estimate_tokens(result)
            if estimated > max_tokens:
                # Approximate truncation: 1 token ≈ 1.5 Chinese chars
                char_limit = int(max_tokens * 1.5)
                result = result[:char_limit] + "\n\n[内容已截断，超出 token 预算]"
                logger.info(
                    "chapter_content_truncated",
                    doc_dir=doc_dir_name,
                    pages=f"{start_page}-{end_page}",
                    max_tokens=max_tokens,
                )

            return result

        except Exception as e:
            logger.error("get_pages_content_failed", doc_dir=doc_dir_name, error=str(e))
            return None

    def _html_to_readable(self, soup: BeautifulSoup) -> str:
        """Convert HTML to readable text, preserving table structure as Markdown.

        Tables are converted to Markdown pipe tables so LLM receives
        structured row/column data instead of flattened cell text.
        """
        # Replace each <table> with its Markdown representation in-place
        for table in soup.find_all("table"):
            md = self._table_to_markdown(table)
            if md:
                table.replace_with(md)
            else:
                table.decompose()

        # Now extract text — tables are already Markdown strings
        return soup.get_text(separator="\n")

    def _has_colspan_rowspan(self, table) -> bool:
        """Return True if any <td> in the table spans multiple cols/rows.

        Tables without colspan/rowspan are left on the fast path (simple
        per-tr collection + pad). Only tables that actually use spans go
        through the grid-expansion path, keeping G18a-style plain tables on
        their original behavior (no regression risk).
        """
        for td in table.find_all("td"):
            try:
                cs = int(td.get("colspan", 1) or 1)
                rs = int(td.get("rowspan", 1) or 1)
            except (TypeError, ValueError):
                continue
            if cs > 1 or rs > 1:
                return True
        return False

    def _collect_table_rows(self, table) -> List[List[str]]:
        """Collect raw <td> text per <tr> (no span handling, legacy path).

        Skips rows where every cell is empty (blank filler rows in QJ 903
        tables). Used for tables without colspan/rowspan.
        """
        rows: List[List[str]] = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if any(c for c in cells):
                rows.append(cells)
        return rows

    def _expand_table_grid(self, table) -> List[List[str]]:
        """Expand a <table> with colspan/rowspan into a 2-D grid.

        Text from a spanned cell is placed at its top-left logical position
        (the column where the cell starts). Columns covered by a colspan
        beyond the first are left as empty strings, and rows covered by a
        rowspan (excluding the cell's own row) are marked occupied so the
        next <tr>'s cells shift past them. This keeps every row aligned on
        the same column axis, which is what downstream row-based parsers
        (e.g. extract_assembly_steps reading by header column index) rely
        on — naive per-tr collection + pad misaligns columns whenever a td
        spans, burying 工序内容 text under the wrong column.

        Returns a list of rows (each a list of cell strings). The grid is
        pre-trimmed to the real max column count but NOT yet post-filtered
        (audit/scrub/signature filtering still happens in the caller).
        """
        grid: List[List[str]] = []
        # occupied[r][c] = True when an upstream rowspan has claimed that
        # logical cell; the cell that owns the span stays its own text.
        occupied: Dict[int, Set[int]] = {}

        def _occ(r: int, c: int) -> bool:
            return c in occupied.get(r, set())

        for r, tr in enumerate(table.find_all("tr")):
            # Ensure row r exists in the grid.
            while len(grid) <= r:
                grid.append([])
            c = 0
            for td in tr.find_all("td"):
                try:
                    cs = int(td.get("colspan", 1) or 1)
                    rs = int(td.get("rowspan", 1) or 1)
                except (TypeError, ValueError):
                    cs, rs = 1, 1
                if cs < 1:
                    cs = 1
                if rs < 1:
                    rs = 1
                # Advance past columns already claimed by a rowspan.
                while _occ(r, c):
                    c += 1
                text = td.get_text(strip=True)
                # Place text at the cell's origin column; pad missing cols.
                while len(grid[r]) <= c:
                    grid[r].append("")
                grid[r][c] = text
                # Fill the rest of this colspan on this row with empties.
                for k in range(1, cs):
                    while len(grid[r]) <= c + k:
                        grid[r].append("")
                    if not grid[r][c + k]:
                        grid[r][c + k] = ""
                # Mark downstream rowspan columns as occupied (rows r+1..r+rs-1,
                # cols c..c+cs-1). Those cells get filled as "" when their rows
                # are built, preserving grid alignment.
                if rs > 1:
                    for rr in range(r + 1, r + rs):
                        for cc in range(c, c + cs):
                            occupied.setdefault(rr, set()).add(cc)
                c += cs

        # Normalize all rows to the real max column count.
        max_cols = max((len(r) for r in grid), default=0)
        for r in grid:
            while len(r) < max_cols:
                r.append("")
        return grid

    def _table_to_markdown(self, table) -> str:
        """Convert an HTML <table> to a Markdown pipe table string.

        Two paths:
          - No colspan/rowspan: collect <td> per <tr> directly (legacy
            behavior, unchanged for plain tables).
          - Has spans: expand into a 2-D grid so every row shares one
            column axis (text at the cell's origin column, spanned cells
            left empty). Without this, per-tr collection + pad misaligns
            columns whenever a td spans, burying cell text under the wrong
            column.

        Both paths keep the same post-processing: scrub audit/signature
        cells in place, drop signature/footer rows (long digit runs) and
        drop fully-empty rows.
        """
        if self._has_colspan_rowspan(table):
            rows = self._expand_table_grid(table)
        else:
            rows = self._collect_table_rows(table)

        # Drop audit/signature rows (company review workflow, not process
        # content). Filtered here so the LLM never receives 会签/审核/批准/
        # 校对/签名/更改单号 from the source docs.
        # Scrub audit/signature cells in-place (会签/审核/批准/校对/签名/
        # 更改单号 → empty) while preserving process content in the same
        # row. A whole-row drop would lose step names that share a row with
        # a 会签 label (e.g. G19a "会签 | 装前准备 | 安装密封圈2 | ...").
        def _scrub_audit(cell: str) -> str:
            compact = re.sub(r"\s", "", cell)
            return "" if any(m in compact for m in _AUDIT_MARKERS) else cell

        rows = [[_scrub_audit(c) for c in r] for r in rows]
        # Drop signature/footer rows: any single cell holding a long digit
        # run (dates like 20240828, audit stamps, page numbers). Process/step
        # cells never contain 6+ consecutive digits, so this safely removes
        # 编制/标检/审核/签名 + 人名 + 日期 footer without touching steps.
        # NOTE: must check per-cell, NOT "".join(row) — adjacent non-empty
        # cells (more common after grid expansion) can concatenate into a
        # spurious 6-digit run, e.g. "HG/T3596" + "75mm" → "...T359675mm",
        # which would wrongly drop a real step row (G25a op5 "5.1.1...").
        rows = [r for r in rows if not any(re.search(r"\d{6,}", c) for c in r)]
        rows = [r for r in rows if any(c for c in r)]

        if not rows:
            return ""

        # Normalize column count
        max_cols = max(len(r) for r in rows) if rows else 0
        for r in rows:
            while len(r) < max_cols:
                r.append("")

        # Build Markdown table
        lines: List[str] = []
        for i, row in enumerate(rows):
            line = "| " + " | ".join(row) + " |"
            lines.append(line)
            # Add separator after header row (first row)
            if i == 0:
                lines.append("| " + " | ".join(["---"] * max_cols) + " |")

        return "\n".join(lines)

    def _split_text_by_pages(self, plain_text: str) -> Dict[int, str]:
        """Split plain text into pages by ## 第 N 页 markers.

        Returns:
            Dict mapping page_number → page_text
        """
        lines = plain_text.split("\n")
        pages: Dict[int, str] = {}
        current_page = 0
        current_lines: List[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("## 第") and "页" in stripped:
                if current_page > 0:
                    pages[current_page] = "\n".join(current_lines)
                m = re.search(r"第\s*(\d+)\s*页", stripped)
                current_page = int(m.group(1)) if m else current_page + 1
                current_lines = []
            else:
                if stripped:
                    current_lines.append(stripped)

        if current_page > 0:
            pages[current_page] = "\n".join(current_lines)

        return pages

    def get_all_chapter_indexes(self) -> List[Dict[str, Any]]:
        """Load chapter indexes for all documents.

        Returns:
            List of chapter_index dicts
        """
        documents = self._get_all_documents()
        results = []
        for doc in documents:
            doc_dir_name = doc.get("_doc_dir")
            if not doc_dir_name:
                continue
            idx = self.load_chapter_index(doc_dir_name)
            if idx:
                idx["_doc_dir"] = doc_dir_name
                results.append(idx)
        return results

    def extract_process_steps(self, doc_dir_name: str = None, text: str = None) -> List[str]:
        """Extract process step names from a doc's 工艺流程图 (G19a) chapter.

        Reads the cleaned chapter text (audit/footer already scrubbed by
        _table_to_markdown) and pulls step names from the table. This is
        the source of truth for the process skeleton — downstream chapters
        (G22a/G25a) align to it instead of LLM-fabricated steps.

        Args:
            doc_dir_name: document dir (e.g. "1") — fetches the 工艺流程图
                chapter if text is not given.
            text: pre-fetched chapter text (skips the lookup).

        Returns:
            Ordered list of step names.
        """
        if text is None and doc_dir_name:
            text = self.get_chapter_content(doc_dir_name, "工艺流程图")
        if not text:
            return []
        header_words = {
            "产品工号", "工艺流程图", "产品数字", "工艺文件编号",
            "零、部、组(整)件代号", "零、部、组(整)件名称", "小产品", "---",
        }
        steps: List[str] = []
        for line in text.split("\n"):
            if "|" not in line:
                continue
            for cell in (c.strip() for c in line.split("|")):
                if not cell or cell in header_words:
                    continue
                # codes/numbers: KA0-0-KZD, 2080, S2
                if re.match(r"^[A-Za-z0-9\-\. ]+$", cell):
                    continue
                # short chinese (<=3 chars): 小产品 etc.
                if re.match(r"^[一-鿿]{1,3}$", cell):
                    continue
                if len(cell) >= 3 and re.search(r"[一-鿿]", cell):
                    steps.append(cell)
        return steps

    def extract_file_references(self, doc_dir_name: str = None, text: str = None) -> List[Dict[str, str]]:
        """Extract 引(借)用文件目录 (G5a) rows from the source chapter.

        Reads the cleaned chapter text (HTML table already converted to a
        Markdown pipe table by _html_to_readable) and pulls the list of
        referenced documents. Returns one dict per data row so downstream
        generation can source-fill G5a directly, instead of derive-ing part
        names from the assembly card (which is how part names leaked into
        the 文件名称 column).

        Column position is resolved dynamically from the header row (the G5a
        table has a complex multi-row header with colspan/rowspan, so a
        hardcoded column index would be fragile). A row counts as data only
        if its 序号 cell is a small integer (1..999) — this also rejects
        dates in signature rows like 20240828.

        Args:
            doc_dir_name: document dir (e.g. "1") — fetches the 引(借)用文件目录
                chapter if text is not given.
            text: pre-fetched chapter text (skips the lookup).

        Returns:
            Ordered list of {seq, ref_code, ref_name, pages, remarks}.
            Empty list if source missing or the header row is not found.
        """
        if text is None and doc_dir_name:
            text = self.get_chapter_content(doc_dir_name, "引(借)用文件目录")
        if not text:
            return []

        header_words = {"序号", "代号", "文件名称", "页数", "备注"}

        # 1. Locate the data column-header row and build col-name -> index map.
        #    The G5a header has a product-info block + countersign block on top
        #    of the data columns; match the data header by requiring both
        #    序号 and 文件名称 cells in the same row.
        col_index: Dict[str, int] = {}
        for line in text.split("\n"):
            if "|" not in line:
                continue
            cells = [c.strip() for c in line.split("|")]
            found = {c: i for i, c in enumerate(cells) if c in header_words}
            if "序号" in found and "文件名称" in found:
                col_index = found
                break
        if not col_index:
            return []

        seq_idx = col_index["序号"]

        def _cell(cells: List[str], name: str) -> str:
            i = col_index.get(name)
            if i is None or i >= len(cells):
                return ""
            return cells[i]

        # 2. Pull data rows: 序号 cell must be a small integer (rejects dates).
        refs: List[Dict[str, str]] = []
        for line in text.split("\n"):
            if "|" not in line:
                continue
            cells = [c.strip() for c in line.split("|")]
            if seq_idx >= len(cells):
                continue
            seq_val = cells[seq_idx]
            if not re.match(r"^[1-9]\d{0,2}$", seq_val):
                continue
            refs.append({
                "seq": seq_val,
                "ref_code": _cell(cells, "代号"),
                "ref_name": _cell(cells, "文件名称"),
                "pages": _cell(cells, "页数"),
                "remarks": _cell(cells, "备注"),
            })
        return refs

    def extract_doc_catalog(self, doc_dir_name: str = None, text: str = None) -> List[Dict[str, str]]:
        """Extract 工艺文件目录 (G4a) rows from the source chapter.

        G4a is the document's own table of contents (本文件章节目录). Like
        G5a it is source-driven: rows are pulled from the source chapter so
        generation fills them directly instead of derive-ing from the
        assembly card — derive leaks part names into 文件名称 and overwrites
        the product code/name in 零部组件 (which are always the product
        itself in G4a, never sub-parts).

        The G4a source table has a dual-row header AND data rows whose pipe
        column index drifts row-to-row: 源 HTML prefixes some 序号 cells
        with an empty colspan, so 序号 lands on a different column index in
        different rows (序号 1 -> col 3, 序号 6 -> col 4 in the same table).
        A fixed column index would misalign. Instead, after confirming the
        header (a row carrying both 编号 and 代号, G4a's unique sub-labels),
        each data row is reduced to its non-empty cells — stably ordered as
        [序号, 文件名称, 文件编号, 零部组件代号, 零部组件名称, 页数] — and the
        序号 cell must be a small integer (1..999), which also rejects dates
        in signature rows like 20240828.

        Args:
            doc_dir_name: document dir (e.g. "1") — fetches the 工艺文件目录
                chapter if text is not given.
            text: pre-fetched chapter text (skips the lookup).

        Returns:
            Ordered list of {seq, doc_name, doc_number, component_code,
            component_name, pages, volume, remarks}. 册数/备注 are blank in
            source data rows by convention. Empty list if source missing or
            the header row is not found.
        """
        if text is None and doc_dir_name:
            text = self.get_chapter_content(doc_dir_name, "工艺文件目录")
        if not text:
            return []

        pipe_lines = [ln for ln in text.split("\n") if "|" in ln]

        # 1. Confirm this is a G4a catalog table: a header row must carry
        #    both 编号 and 代号 (G4a's dual-header sub-labels). G5a's header
        #    has neither, so this also disambiguates from a G5a chapter.
        def _cells(ln: str) -> List[str]:
            return [c.strip() for c in ln.split("|")]

        if not any("编号" in _cells(ln) and "代号" in _cells(ln) for ln in pipe_lines):
            return []

        # 2. Pull data rows by non-empty-cell sequence. Column index drifts
        #    across rows, but the ordered non-empty values are stable.
        rows: List[Dict[str, str]] = []
        for ln in pipe_lines:
            vals = [v for v in _cells(ln) if v]  # drop pipe padding + colspan fillers
            if not vals or not re.match(r"^[1-9]\d{0,2}$", vals[0]):
                continue
            # vals = [seq, doc_name, doc_number, component_code, component_name, pages, ...]
            rows.append({
                "seq": vals[0],
                "doc_name": vals[1] if len(vals) > 1 else "",
                "doc_number": vals[2] if len(vals) > 2 else "",
                "component_code": vals[3] if len(vals) > 3 else "",
                "component_name": vals[4] if len(vals) > 4 else "",
                "pages": vals[5] if len(vals) > 5 else "",
                "volume": "",   # 册数/备注 blank in source data rows
                "remarks": "",
            })
        return rows

    def extract_assembly_steps(self, doc_dir_name: str) -> Dict[int, Dict[str, Any]]:
        """Extract per-step substeps (操作/材料/设备) from 装配工艺卡片 (G25a).

        G25a is the detailed per-step card. Reads the FULL chapter with a
        large token budget — G25a spans ~30 pages and exceeds the default
        12k truncation, which would drop later steps (6-10). Groups
        substeps by step number so downstream generation aligns to the
        skeleton instead of LLM-fabricating step content.

        Returns:
            {step_no: {"name": str, "substeps": [{"content","material"}]}}
        """
        idx = self.load_chapter_index(doc_dir_name)
        if not idx:
            return {}
        g25a = next(
            (c for c in idx.get("chapters", []) if "装配" in c.get("title", "")),
            None,
        )
        if not g25a or not g25a.get("pages"):
            return {}
        pages = g25a["pages"]
        # Large budget: G25a is ~33k chars across 30 pages.
        text = self.get_pages_content(
            doc_dir_name, pages[0], pages[-1], max_tokens=60000
        )
        if not text:
            return {}

        # Column keys recognized in the table header row. The header gives
        # the authoritative column→cell-index mapping per page block, so we
        # read content/material/instruments by column name (robust to
        # colspan shifts between first page and continuation pages) instead
        # of guessing by cell position.
        col_keys = {
            "车间": "workshop", "工序号": "step_no", "工序名称": "step_name",
            "工序内容": "content", "辅助材料": "material", "专用仪器": "instruments",
        }
        steps: Dict[int, Dict[str, Any]] = {}
        header: Dict[str, int] = {}  # column name -> cell index
        cur_no = None
        in_parts_list = False  # True while inside 配套零件清单 sub-table

        def _col(cells: List[str], name: str) -> str:
            i = header.get(name)
            return cells[i] if i is not None and i < len(cells) else ""

        for line in text.split("\n"):
            if "|" not in line:
                continue
            cells = [c.strip() for c in line.split("|")]
            # Header row: contains 车间 + 工序号 + 工序内容 → fix column map.
            # A continuation page re-emits the full column header; reset the
            # parts-list flag too so substeps on the new page are not swallowed
            # by a parts-list region that was left open at the previous page tail
            # (G25a 装配卡: 零件清单跨续页 → 7.1-7.4 lost, 7.5+ only on next page).
            if "车间" in cells and "工序号" in cells and "工序内容" in cells:
                header = {}
                for i, c in enumerate(cells):
                    for k, v in col_keys.items():
                        if k in c:
                            header[v] = i
                in_parts_list = False  # continuation header → leave parts-list region
                continue
            if not header:
                continue
            # Step header row: workshop + step_no both numeric
            wk = _col(cells, "workshop")
            sn = _col(cells, "step_no")
            if wk and re.match(r"^\d+$", wk) and sn and re.match(r"^\d+$", sn):
                cur_no = int(sn)
                in_parts_list = False  # new step leaves the parts-list region
                name = _col(cells, "step_name") or ""
                steps.setdefault(cur_no, {"name": name, "substeps": []})
                if not steps[cur_no]["name"]:
                    steps[cur_no]["name"] = name
                continue
            # 配套零件清单区: skip every row until the next step header —
            # those rows are part codes/names/qty, not process content.
            joined = " ".join(c for c in cells if c)
            # Narrow trigger: a single parts-list marker (e.g. "交往何处") can
            # appear in a continuation-page meta row; require TWO exclusive
            # parts-list phrases on the same row before opening the parts-list
            # region. The 代号/名称 column pair is NOT enough on its own — every
            # 装配卡 main header carries those as standard columns, so matching
            # them would wrongly flag the main header and drop the part-code row
            # beneath it (doc 1 step 4 lost "KA0-0-KZD" this way). Two exclusive
            # phrases only co-occur on the real parts sub-table header.
            _marker_hits = sum(1 for m in _PARTS_LIST_MARKERS if m in joined)
            if _marker_hits >= 2:
                in_parts_list = True
                continue
            if in_parts_list:
                continue
            # Substep row: any non-empty 工序内容 under the current step.
            # Originally only rows whose content began with an N.M id were
            # captured, which silently dropped steps whose substeps carry no
            # N.M number (e.g. step 9 → 0 substeps). Now accept every row with
            # non-empty content after filtering header residue and
            # audit/signature noise (续页表头与签名行不算子步骤).
            content = _col(cells, "content")
            if cur_no is not None and content and _is_substep_content(content):
                steps[cur_no]["substeps"].append({
                    "content": content,
                    "material": _col(cells, "material"),
                    "instruments": _col(cells, "instruments"),
                })
        return steps

    def extract_assembly_overview(self, doc_dir_name: str) -> str:
        """Extract the 适用范围/说明 overview block from 装配工艺卡片 (G25a).

        G25a's first page carries a 说明 cell (colspan over 工序内容) before
        the first numeric step row. It states what this assembly card is for
        (e.g. "本工艺用于指导KZD大批量P12及以后批次导弹全弹(火工)对接装配
        工作...") plus referenced design docs / 装配要求. This is chapter-level
        scope context, NOT step content — injected into the generation
        system_msg as background so the LLM knows the card's applicable range,
        but never written into any 工序 row's content.

        Reads the G25a chapter text (reusing the same colspan-expanded
        Markdown as extract_assembly_steps), then from the 说明 row
        accumulates 工序内容-column text until the first numeric step header
        (workshop + step_no both digits), filtering audit noise.

        Args:
            doc_dir_name: document directory name (e.g. "1")

        Returns:
            Joined overview string. Empty if not found.
        """
        idx = self.load_chapter_index(doc_dir_name)
        if not idx:
            return ""
        g25a = next(
            (c for c in idx.get("chapters", []) if "装配" in c.get("title", "")),
            None,
        )
        if not g25a or not g25a.get("pages"):
            return ""
        pages = g25a["pages"]
        # Overview lives on the first page; read a few pages in case the
        # 说明 block spills onto page 2 before the first numeric step.
        text = self.get_pages_content(
            doc_dir_name, pages[0], min(pages[-1], pages[0] + 2),
            max_tokens=20000,
        )
        if not text:
            return ""

        col_keys = {
            "车间": "workshop", "工序号": "step_no", "工序名称": "step_name",
            "工序内容": "content",
        }
        header: Dict[str, int] = {}

        def _col(cells: List[str], name: str) -> str:
            i = header.get(name)
            return cells[i] if i is not None and i < len(cells) else ""

        # Overview triggers: the 说明 label cell, or the lead-in phrases that
        # mark the start of the scope statement.
        overview_started = False
        parts: List[str] = []
        for line in text.split("\n"):
            if "|" not in line:
                continue
            cells = [c.strip() for c in line.split("|")]
            # Header row: fix column map (车间 + 工序号 + 工序内容)
            if "车间" in cells and "工序号" in cells and "工序内容" in cells:
                header = {}
                for i, c in enumerate(cells):
                    for k, v in col_keys.items():
                        if k in c:
                            header[v] = i
                continue
            if not header:
                continue
            # Stop at the first real step row (workshop + step_no both
            # numeric) — the overview region ends where process steps begin.
            wk = _col(cells, "workshop")
            sn = _col(cells, "step_no")
            if wk and re.match(r"^\d+$", wk) and sn and re.match(r"^\d+$", sn):
                break
            content = _col(cells, "content")
            if not content:
                continue
            # Skip audit/signature noise (会签/审核/...).
            if any(m in content for m in _AUDIT_MARKERS):
                continue
            # Skip header-column residue that leaks into the content column on
            # continuation pages (产品数字/工艺文件编号/装配工艺卡片(续) etc.)
            # and pure separator rows (--- / 第N页 markers).
            if content in _SUBSTEP_HEADER_WORDS:
                continue
            if re.fullmatch(r"[\-–—\s]+", content):
                continue
            if content.startswith("第") and content.endswith("页"):
                continue
            if not overview_started:
                if content == "说明" or "本工艺" in content or "用于指导" in content:
                    overview_started = True
                    if content != "说明":
                        parts.append(content)
                continue
            parts.append(content)
        return "".join(parts).strip()

    def extract_process_card_steps(self, doc_dir_name: str) -> Dict[int, Dict[str, str]]:
        """Extract per-step 工序名称 + 工序内容简述 from 工艺过程卡 (G22a).

        G22a is one row per process step (unlike G25a's multi-substep card).
        Reads the full chapter and maps columns by header name (robust to
        colspan) so step_name/step_desc come from source, not LLM fabrication.

        Returns:
            {step_no: {"step_name": str, "step_desc": str}}
        """
        idx = self.load_chapter_index(doc_dir_name)
        if not idx:
            return {}
        g22a = next(
            (c for c in idx.get("chapters", []) if "工艺过程卡" in c.get("title", "")),
            None,
        )
        if not g22a or not g22a.get("pages"):
            return {}
        pages = g22a["pages"]
        text = self.get_pages_content(
            doc_dir_name, pages[0], pages[-1], max_tokens=60000
        )
        if not text:
            return {}

        col_keys = {
            "车间": "workshop", "工序号": "step_no", "工序名称": "step_name",
            "工序内容简述": "step_desc", "设备": "equipment",
            "工艺装备": "tooling",
        }
        steps: Dict[int, Dict[str, str]] = {}
        header: Dict[str, int] = {}

        def _col(cells: List[str], name: str) -> str:
            i = header.get(name)
            return cells[i] if i is not None and i < len(cells) else ""

        for line in text.split("\n"):
            if "|" not in line:
                continue
            cells = [c.strip() for c in line.split("|")]
            # Header row: 车间 + 工序号 + 工序内容简述
            if "车间" in cells and "工序号" in cells and "工序内容简述" in cells:
                header = {}
                for i, c in enumerate(cells):
                    for k, v in col_keys.items():
                        if k in c:
                            header[v] = i
                continue
            if not header:
                continue
            # Step rows are anchored by 钳 (工序名称). Colspan in the source
            # shifts workshop/step_no cells (e.g. "|  | 33 | 3 | 钳 | ..."),
            # padding workshop with empty cells. Anchoring on 钳 — step_no is
            # the digit right before it, step_desc the cell right after — is
            # robust to that shift (so steps 3-7 aren't dropped).
            if "钳" in cells:
                j = cells.index("钳")
                sn_cell = cells[j - 1] if j - 1 >= 0 else ""
                if sn_cell.isdigit():
                    cur_no = int(sn_cell)
                    desc = cells[j + 1] if j + 1 < len(cells) else ""
                    if desc and _is_substep_content(desc):
                        steps[cur_no] = {"step_name": "钳", "step_desc": desc}
        return steps


# 全局单例
hierarchical_context = HierarchicalContext()
