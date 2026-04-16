"""
文档上下文API
提供文档列表、表格查询、Markdown转换等接口
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from app.shared.logging import get_logger
from app.services.context_manager import ContextManager

logger = get_logger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


# ============ Pydantic Models ============

class DocumentInfo(BaseModel):
    """文档信息"""
    name: str
    path: str
    table_count: int
    page_count: int


class TableInfo(BaseModel):
    """表格信息"""
    page: int
    caption: str
    table_type: str
    has_html: bool


class DocumentListResponse(BaseModel):
    """文档列表响应"""
    documents: List[DocumentInfo]
    total: int


class TableListResponse(BaseModel):
    """表格列表响应"""
    doc_name: str
    tables: List[TableInfo]
    total: int


class DocumentContextResponse(BaseModel):
    """文档上下文响应"""
    doc_names: List[str]
    context: str
    table_count: int


# ============ Dependencies ============

def get_context_manager():
    """获取上下文管理器"""
    from app.config import settings
    # Use config constant for path
    project_data_dir = settings.EXPORTS_VLM_DIR
    # Ensure directory exists
    project_data_dir.mkdir(parents=True, exist_ok=True)
    return ContextManager(data_dir=str(project_data_dir))


# ============ API Endpoints ============

@router.get("", response_model=DocumentListResponse, summary="获取已解析文档列表")
async def list_documents(
    cm: ContextManager = Depends(get_context_manager),
):
    """
    获取exports_vlm_full目录下已解析的PDF文档列表

    返回所有已完成VLM解析的文档信息
    """
    documents = cm.get_document_list()

    doc_responses = [
        DocumentInfo(
            name=doc.name,
            path=str(doc.path),
            table_count=doc.table_count,
            page_count=doc.page_count,
        )
        for doc in documents
    ]

    logger.info("documents_listed", count=len(doc_responses))

    return DocumentListResponse(
        documents=doc_responses,
        total=len(doc_responses),
    )


@router.get("/{doc_name}/tables", response_model=TableListResponse, summary="获取文档表格列表")
async def get_document_tables(
    doc_name: str,
    cm: ContextManager = Depends(get_context_manager),
):
    """
    获取指定文档的所有表格信息

    - **doc_name**: 文档名称（不含.pdf后缀）
    """
    tables = cm.get_document_tables(doc_name)

    if not tables:
        logger.warning("document_tables_not_found", doc_name=doc_name)
        # 不抛出404，返回空列表
        return TableListResponse(
            doc_name=doc_name,
            tables=[],
            total=0,
        )

    table_responses = [
        TableInfo(
            page=t.page,
            caption=t.caption,
            table_type=t.table_type,
            has_html=bool(t.html),
        )
        for t in tables
    ]

    logger.info("document_tables_retrieved", doc_name=doc_name, count=len(tables))

    return TableListResponse(
        doc_name=doc_name,
        tables=table_responses,
        total=len(table_responses),
    )


@router.get("/{doc_name}/markdown", summary="获取文档Markdown")
async def get_document_markdown(
    doc_name: str,
    cm: ContextManager = Depends(get_context_manager),
):
    """
    获取文档的Markdown表示

    - **doc_name**: 文档名称（不含.pdf后缀）
    """
    markdown = cm.get_document_markdown(doc_name)

    if not markdown:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_name}")

    logger.info("document_markdown_retrieved", doc_name=doc_name, length=len(markdown))

    return {
        "doc_name": doc_name,
        "markdown": markdown,
        "length": len(markdown),
    }


@router.get("/{doc_name}/search", summary="按标题搜索表格")
async def search_tables_by_caption(
    doc_name: str,
    caption: str = Query(..., description="表格标题关键词，如G4a, G5a"),
    cm: ContextManager = Depends(get_context_manager),
):
    """
    按表格标题搜索

    - **doc_name**: 文档名称
    - **caption**: 标题关键词（如G4a, G5a）
    """
    tables = cm.search_by_caption(doc_name, caption)

    return {
        "doc_name": doc_name,
        "caption": caption,
        "matched_tables": [
            {
                "page": t.page,
                "caption": t.caption,
                "table_type": t.table_type,
            }
            for t in tables
        ],
        "total": len(tables),
    }


@router.post("/context", response_model=DocumentContextResponse, summary="构建多文档上下文")
async def build_document_context(
    doc_names: List[str],
    include_html: bool = Query(False, description="是否包含HTML"),
    max_tables: int = Query(50, ge=1, le=200, description="最大表格数量"),
    cm: ContextManager = Depends(get_context_manager),
):
    """
    构建多文档上下文

    将多个文档的内容合并为LLM可理解的上下文

    - **doc_names**: 文档名称列表
    - **include_html**: 是否包含HTML（会增加长度）
    - **max_tables**: 最大表格数量限制
    """
    if not doc_names:
        raise HTTPException(status_code=400, detail="doc_names cannot be empty")

    context = cm.build_document_context(
        doc_names=doc_names,
        include_html=include_html,
        max_tables=max_tables,
    )

    # 统计表格数量
    table_count = 0
    for doc_name in doc_names:
        tables = cm.get_document_tables(doc_name)
        table_count += len(tables)

    logger.info(
        "document_context_built",
        doc_count=len(doc_names),
        table_count=table_count,
        context_length=len(context),
    )

    return DocumentContextResponse(
        doc_names=doc_names,
        context=context,
        table_count=table_count,
    )


@router.get("/summary/json", summary="获取解析摘要")
async def get_extraction_summary(
    cm: ContextManager = Depends(get_context_manager),
):
    """
    获取PDF解析摘要信息

    返回extraction_summary.json的内容
    """
    summary = cm.get_extraction_summary()

    if not summary:
        raise HTTPException(status_code=404, detail="Extraction summary not found")

    return summary


@router.get("/{doc_name}/table/{page}", summary="获取单个表格详情")
async def get_table_detail(
    doc_name: str,
    page: int,
    cm: ContextManager = Depends(get_context_manager),
):
    """
    获取指定页面的表格详情

    - **doc_name**: 文档名称
    - **page**: 页码
    """
    tables = cm.get_document_tables(doc_name)

    # 找到对应页面的表格
    matched = [t for t in tables if t.page == page]

    if not matched:
        raise HTTPException(
            status_code=404,
            detail=f"No table found on page {page} in document {doc_name}"
        )

    table = matched[0]

    return {
        "doc_name": doc_name,
        "page": table.page,
        "caption": table.caption,
        "table_type": table.table_type,
        "html": table.html[:5000] if table.html else None,  # 限制HTML长度
        "image_path": table.image_path,
    }
