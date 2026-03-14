"""
工艺文件辅助编辑系统 - PDM集成API
提供与PDM系统的数据交换接口
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from app.services.pdm_service import PDMService
from app.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/pdm-integration", tags=["pdm-integration"])


class PDMExportRequest(BaseModel):
    """PDM导出请求"""
    document: Dict[str, Any]
    options: Dict[str, Any]


class PDMImportResponse(BaseModel):
    """PDM导入响应"""
    success: bool
    document_id: str
    imported_data: Dict[str, Any]
    import_time: str
    status: str
    error: Optional[str] = None


class PDMExportResponse(BaseModel):
    """PDM导出响应"""
    success: bool
    export_id: str
    document_id: str
    pdm_system: str
    exported_files: List[str]
    export_time: str
    status: str
    error: Optional[str] = None


@router.post("/export", response_model=PDMExportResponse)
async def export_to_pdm(request: PDMExportRequest):
    """
    导出工艺文件到PDM系统
    """
    try:
        logger.info("export_to_pdm_requested", document_id=request.document.get("id", "unknown"))

        # 初始化PDM服务
        pdm_service = PDMService()

        # 执行导出
        result = await pdm_service.export_to_pdm(request.document, request.options)

        logger.info("export_to_pdm_completed", export_id=result.get("export_id", "unknown"))
        return result

    except Exception as e:
        logger.error("export_to_pdm_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.get("/import/{document_id}", response_model=PDMImportResponse)
async def import_from_pdm(document_id: str):
    """
    从PDM系统导入工艺文件
    """
    try:
        logger.info("import_from_pdm_requested", document_id=document_id)

        # 初始化PDM服务
        pdm_service = PDMService()

        # 执行导入
        result = await pdm_service.import_from_pdm(document_id)

        logger.info("import_from_pdm_completed", document_id=document_id)
        return result

    except Exception as e:
        logger.error("import_from_pdm_failed", error=str(e), document_id=document_id)
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.get("/status")
async def get_pdm_status():
    """
    获取PDM系统状态
    """
    try:
        pdm_service = PDMService()
        status = await pdm_service.get_pdm_status()
        return status
    except Exception as e:
        logger.error("get_pdm_status_failed", error=str(e))
        return {
            "connected": False,
            "system_name": "Unknown",
            "version": "Unknown"
        }


@router.post("/sync/{document_id}")
async def sync_to_pdm(document_id: str):
    """
    同步工艺文件到PDM
    """
    try:
        logger.info("sync_to_pdm_requested", document_id=document_id)

        pdm_service = PDMService()
        result = await pdm_service.sync_to_pdm(document_id)

        logger.info("sync_to_pdm_completed", sync_id=result.get("sync_id", "unknown"))
        return result

    except Exception as e:
        logger.error("sync_to_pdm_failed", error=str(e), document_id=document_id)
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.get("/documents")
async def get_pdm_documents():
    """
    获取PDM中的工艺文件列表
    """
    try:
        pdm_service = PDMService()
        documents = await pdm_service.get_pdm_documents()
        return {"documents": documents}
    except Exception as e:
        logger.error("get_pdm_documents_failed", error=str(e))
        return {"documents": []}