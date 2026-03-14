"""
节点文档API
提供节点文档的查询接口
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.node_document_writer import NodeDocumentWriter
from app.utils.logger import logger

router = APIRouter(prefix="/api/node-documents", tags=["node-documents"])


@router.get("/{session_id}")
async def get_node_documents(
    session_id: str,
    node_types: Optional[List[str]] = Query(None, description="节点类型过滤（analysis, planning, retrieval, writing, review）"),
    node_names: Optional[List[str]] = Query(None, description="节点名称过滤"),
    limit: Optional[int] = Query(None, description="返回数量限制"),
    db: Session = Depends(get_db)
):
    """
    获取会话的所有节点文档
    
    Args:
        session_id: 会话ID
        node_types: 节点类型过滤（可选）
        node_names: 节点名称过滤（可选）
        limit: 返回数量限制（可选）
        db: 数据库会话
        
    Returns:
        节点文档列表
    """
    try:
        document_writer = NodeDocumentWriter(session_id=session_id)
        documents = document_writer.get_node_documents(
            node_types=node_types,
            node_names=node_names,
            limit=limit
        )
        
        return {
            "success": True,
            "session_id": session_id,
            "count": len(documents),
            "documents": documents
        }
        
    except Exception as e:
        logger.error("❌ 获取节点文档失败: %s", str(e))
        raise HTTPException(status_code=500, detail=f"获取节点文档失败: {str(e)}")


@router.get("/{session_id}/{node_name}")
async def get_node_document_by_name(
    session_id: str,
    node_name: str,
    db: Session = Depends(get_db)
):
    """
    获取特定节点的最新文档
    
    Args:
        session_id: 会话ID
        node_name: 节点名称（如analyze_node, planner_node）
        db: 数据库会话
        
    Returns:
        节点文档（如果存在）
    """
    try:
        document_writer = NodeDocumentWriter(session_id=session_id)
        document = document_writer.get_latest_document(node_name=node_name)
        
        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"未找到节点文档: {session_id}/{node_name}"
            )
        
        return {
            "success": True,
            "document": document
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ 获取节点文档失败: %s", str(e))
        raise HTTPException(status_code=500, detail=f"获取节点文档失败: {str(e)}")


@router.get("/{session_id}/latest")
async def get_latest_document(
    session_id: str,
    node_type: Optional[str] = Query(None, description="节点类型过滤"),
    db: Session = Depends(get_db)
):
    """
    获取最新生成的文档
    
    Args:
        session_id: 会话ID
        node_type: 节点类型过滤（可选）
        db: 数据库会话
        
    Returns:
        最新节点文档
    """
    try:
        document_writer = NodeDocumentWriter(session_id=session_id)
        document = document_writer.get_latest_document(node_type=node_type)
        
        if not document:
            raise HTTPException(
                status_code=404,
                detail=f"未找到最新节点文档: {session_id}"
            )
        
        return {
            "success": True,
            "document": document
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ 获取最新节点文档失败: %s", str(e))
        raise HTTPException(status_code=500, detail=f"获取最新节点文档失败: {str(e)}")


@router.get("/{session_id}/search")
async def search_node_documents(
    session_id: str,
    query: str = Query(..., description="查询文本（用于语义检索）"),
    node_types: Optional[List[str]] = Query(None, description="节点类型过滤"),
    top_k: int = Query(3, description="返回Top-K结果"),
    db: Session = Depends(get_db)
):
    """
    通过LTM语义检索节点文档
    
    Args:
        session_id: 会话ID
        query: 查询文本
        node_types: 节点类型过滤（可选）
        top_k: 返回Top-K结果（默认3）
        db: 数据库会话
        
    Returns:
        匹配的节点文档列表
    """
    try:
        document_writer = NodeDocumentWriter(session_id=session_id)
        documents = document_writer.get_node_document_by_ltm(
            query=query,
            node_types=node_types,
            top_k=top_k
        )
        
        return {
            "success": True,
            "query": query,
            "count": len(documents),
            "documents": documents
        }
        
    except Exception as e:
        logger.error("❌ 语义检索节点文档失败: %s", str(e))
        raise HTTPException(status_code=500, detail=f"语义检索节点文档失败: {str(e)}")
