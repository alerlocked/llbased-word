"""
创作相关API路由
处理素材管理、AI辅助写作、版本管理等操作
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import shutil
import json
from PIL import Image

from app.database import get_db
from app.models.database import Material, CreationProject, EditorVersion, SearchResult, Figure, MaterialPage, WebImage, UploadedImage
from app.services.llm_service import llm_service
from app.services.document_processor import document_processor
from app.services.vl_service import vl_service
from app.shared.logging import get_logger
logger = get_logger(__name__)
from app.shared.logging import log_workflow
from app.config import settings
from app.agents.tools.image_search import get_image_search_tool
from app.utils.path_utils import build_static_url
from app.utils.db_utils import get_or_404
from app.utils.file_utils import calculate_file_hash
from app.services.pdf_queue_manager import (
    get_pdf_queue_manager,
    PDFTaskPriority
)

router = APIRouter()


def _check_duplicate_document(filename: str) -> Optional[dict]:
    """Check if a document with this filename already exists on disk.

    Scans data/documents/*/index.json for matching name field.
    Returns existing doc info if found, None otherwise.
    """
    documents_dir = Path(settings.DATA_DIR) / "documents"
    if not documents_dir.exists():
        return None
    for doc_dir in documents_dir.iterdir():
        if not doc_dir.is_dir():
            continue
        index_path = doc_dir / "index.json"
        if not index_path.exists():
            continue
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                index_data = json.load(f)
            if index_data.get("name") == filename:
                return {
                    "material_id": index_data.get("material_id", doc_dir.name),
                    "name": index_data.get("name"),
                    "pages": index_data.get("pages", 0),
                }
        except Exception:
            continue
    return None

class CreateProjectRequest(BaseModel):
    """创建项目请求"""
    name: str = "新项目"

class AddMaterialRequest(BaseModel):
    """添加素材请求"""
    project_id: int
    material_ids: List[int]  # 要添加的素材ID列表

class GenerateDraftRequest(BaseModel):
    """生成初稿请求"""
    outline: str
    style: str = "news"
    word_count: int = 1000
    reference_materials: Optional[List[int]] = []

class ComprehensiveSearchRequest(BaseModel):
    """综合检索请求"""
    query_text: str
    context: Optional[str] = ""
    search_types: List[str] = ["local", "web"]

class AskRequest(BaseModel):
    """提问请求"""
    question: str
    context: Optional[str] = ""
    selected_text: Optional[str] = ""

class TextOperationRequest(BaseModel):
    """文本操作请求(改写/扩写/精简)"""
    text: str
    operation: str  # rewrite/expand/simplify

@router.post("/projects")
async def create_project(
    request: CreateProjectRequest,
    db: Session = Depends(get_db)
):
    """
    创建新项目
    
    Args:
        request: 创建请求
        db: 数据库会话
    
    Returns:
        新项目信息
    """
    log_workflow("创建项目", "开始", {"name": request.name})
    
    try:
        # 创建项目
        project = CreationProject(
            name=request.name,
            content="",
            material_ids=[]
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        
        logger.info(f"✅ 项目创建成功: {project.id} - {project.name}")
        
        return {
            "id": project.id,
            "name": project.name,
            "created_at": project.created_at.isoformat(),
            "updated_at": project.updated_at.isoformat()
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ 创建项目失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建失败: {str(e)}"
        )

@router.get("/projects")
async def list_projects(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    获取项目列表
    
    Args:
        limit: 返回数量限制
        offset: 偏移量
        db: 数据库会话
    
    Returns:
        项目列表
    """
    try:
        # 查询项目
        projects = db.query(CreationProject).order_by(
            CreationProject.updated_at.desc()
        ).offset(offset).limit(limit).all()
        
        items = [
            {
                "id": p.id,
                "name": p.name,
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat()
            }
            for p in projects
        ]
        
        logger.info(f"✅ 获取项目列表,共{len(items)}个")
        
        return {"items": items}
        
    except Exception as e:
        logger.error(f"❌ 获取项目列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}"
        )

@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    """
    删除项目
    
    Args:
        project_id: 项目ID
        db: 数据库会话
    
    Returns:
        删除结果
    """
    try:
        # 查找项目
        project = get_or_404(db, CreationProject, CreationProject.id == project_id, "项目不存在")
        
        # 删除关联的素材（从 material_ids 中获取素材ID列表）
        material_ids = project.material_ids or []
        if material_ids:
            db.query(Material).filter(Material.id.in_(material_ids)).delete(synchronize_session=False)

        # 删除版本历史
        db.query(EditorVersion).filter(EditorVersion.project_id == project_id).delete()

        # 删除关联的上传图片（project_id 是 NOT NULL，需要先删除）
        image_count = db.query(UploadedImage).filter(UploadedImage.project_id == project_id).count()
        if image_count > 0:
            logger.info(f"🗑️ 删除项目{project_id}关联的{image_count}个上传图片")
            db.query(UploadedImage).filter(UploadedImage.project_id == project_id).delete(synchronize_session=False)

        # 删除项目
        db.delete(project)
        db.commit()

        logger.info(f"✅ 已删除项目{project_id}")
        
        return {"message": "删除成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ 删除项目失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {str(e)}"
        )

@router.get("/materials")
async def get_available_materials(db: Session = Depends(get_db)):
    """
    获取所有可用的文档素材

    Args:
        db: 数据库会话

    Returns:
        文档素材列表
    """
    try:
        # 获取所有文档素材
        materials = db.query(Material).filter(
            Material.material_type.in_(["pdf", "docx", "txt"])
        ).order_by(Material.created_at.desc()).all()

        items = []
        for material in materials:
            items.append({
                "id": material.id,
                "name": material.name,
                "type": material.material_type,
                "content_length": len(material.content) if material.content else 0,
                "created_at": material.created_at.isoformat()
            })

        logger.info(f"✅ 获取可用素材列表,共{len(items)}个")
        return {"items": items}

    except Exception as e:
        logger.error(f"❌ 获取素材列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}"
        )

@router.post("/projects/{project_id}/materials")
async def add_materials_to_project(
    project_id: int,
    request: AddMaterialRequest,
    db: Session = Depends(get_db)
):
    """
    添加素材到项目

    Args:
        project_id: 项目ID
        request: 添加请求
        db: 数据库会话

    Returns:
        添加结果
    """
    log_workflow("添加素材", "开始", {"project_id": project_id, "count": len(request.material_ids)})

    try:
        # 获取项目
        project = get_or_404(db, CreationProject, CreationProject.id == project_id, "项目不存在")

        # 验证素材是否存在
        existing_materials = db.query(Material).filter(
            Material.id.in_(request.material_ids)
        ).all()
        existing_ids = {m.id for m in existing_materials}

        # 添加素材ID到项目
        current_material_ids = project.material_ids or []
        added_count = 0
        for material_id in request.material_ids:
            if material_id in existing_ids and material_id not in current_material_ids:
                current_material_ids.append(material_id)
                added_count += 1

        # 更新项目的material_ids
        project.material_ids = current_material_ids
        db.commit()

        logger.info(f"✅ 已添加{added_count}个素材到项目{project_id}")

        return {"message": "添加成功", "added_count": added_count}

    except Exception as e:
        db.rollback()
        logger.error(f"❌ 添加素材失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加失败: {str(e)}"
        )

@router.get("/projects/{project_id}/materials")
async def get_project_materials(
    project_id: int,
    db: Session = Depends(get_db)
):
    """
    获取项目的所有素材
    
    Args:
        project_id: 项目ID
        db: 数据库会话

    Returns:
        素材列表
    """
    try:
        # Return all materials globally (shared across projects)
        materials = db.query(Material).order_by(Material.created_at.desc()).all()

        result = {
            "searches": [],
            "documents": []
        }

        pdf_manager = get_pdf_queue_manager()

        for material in materials:
            if material.material_type == "search" and material.search_result_id:
                search = db.query(SearchResult).filter(SearchResult.id == material.search_result_id).first()
                if search:
                    result["searches"].append({
                        "id": search.id,
                        "title": search.title,
                        "content": search.content,
                        "source": search.source,
                        "searchType": search.search_type,
                        "createdAt": search.created_at.isoformat()
                    })
            elif material.material_type in ["document", "pdf", "docx", "txt"]:
                pages = db.query(MaterialPage).filter(MaterialPage.material_id == material.id).order_by(MaterialPage.page_number).all()

                parse_status = "unknown"
                parse_error = None

                if material.material_type in ["pdf", "document"]:
                    # Check parse status via output file existence
                    doc_html = Path(settings.DATA_DIR) / "documents" / str(material.id) / "document.html"
                    content_html = Path(settings.DATA_DIR) / "documents" / str(material.id) / "content.html"
                    # Also check materials directory
                    materials_dir = Path(settings.DATA_DIR) / "materials"
                    material_parsed = False
                    if materials_dir.exists():
                        for d in materials_dir.iterdir():
                            if d.is_dir() and d.name.startswith(f"{material.id}_"):
                                if (d / "full.html").exists() or (d / "summary.json").exists():
                                    material_parsed = True
                                    break
                    if doc_html.exists() or content_html.exists() or material_parsed:
                        parse_status = "completed"
                    else:
                        # Try matching PDF queue task by scanning all upload dirs
                        task = pdf_manager.get_task_by_path(
                            str(Path(settings.DATA_DIR) / "uploads" / str(material.id) / material.name)
                        )
                        if task:
                            parse_status = task.status.value
                            if task.error_message:
                                parse_error = task.error_message
                        else:
                            parse_status = "pending"

                # Get parse progress from queue task
                parse_progress = 0
                if material.material_type in ["pdf", "document"]:
                    task = pdf_manager.get_task_by_path(
                        str(Path(settings.DATA_DIR) / "uploads" / str(material.id) / material.name)
                    )
                    if task:
                        parse_progress = task.progress

                result["documents"].append({
                    "id": material.id,
                    "name": material.name,
                    "type": material.material_type,
                    "parse_status": parse_status,
                    "parse_progress": parse_progress,
                    "parse_error": parse_error,
                    "pages": [
                        {
                            "page_number": p.page_number,
                            "image_path": p.image_path
                        } for p in pages
                    ],
                    "createdAt": material.created_at.isoformat()
                })

        logger.info(f"✅ 获取全部素材,检索:{len(result['searches'])},文档:{len(result['documents'])}")

        return result

    except Exception as e:
        logger.error(f"❌ 获取项目素材失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}"
        )


@router.get("/projects/{project_id}/materials/{material_id}")
async def get_material_content(
    project_id: int,
    material_id: int,
    db: Session = Depends(get_db)
):
    """
    获取单个素材的内容（用于预览）
    
    Args:
        project_id: 项目ID
        material_id: 素材ID
        db: 数据库会话

    Returns:
        素材内容
    """
    try:
        # 验证项目存在
        project = get_or_404(db, CreationProject, CreationProject.id == project_id, "项目不存在")
        
        # 验证素材属于该项目
        if material_id not in (project.material_ids or []):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="素材不在该项目中"
            )
        
        # 获取素材
        material = get_or_404(db, Material, Material.id == material_id, "素材不存在")
        
        # 读取内容文件 - 优先 content.json (完整内容)
        content_json_path = Path(settings.DATA_DIR) / "documents" / str(material_id) / "content.json"
        content_html_path = Path(settings.DATA_DIR) / "documents" / str(material_id) / "content.html"

        if content_json_path.exists():
            import json
            with open(content_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            content = data.get("content", "")
            logger.info(f"✅ 获取素材内容: {material_id} (from JSON, {len(content)} chars)")
            return {
                "id": material.id,
                "name": material.name,
                "type": material.material_type,
                "content": content,
                "content_type": "html"
            }
        elif content_html_path.exists():
            with open(content_html_path, "r", encoding="utf-8") as f:
                content = f.read()
            logger.info(f"✅ 获取素材内容: {material_id} (from HTML)")
            return {
                "id": material.id,
                "name": material.name,
                "type": material.material_type,
                "content": content,
                "content_type": "html"
            }

        # Check materials directory (pre-parsed by PDF pipeline)
        materials_dir = Path(settings.DATA_DIR) / "materials"
        if materials_dir.exists():
            for d in materials_dir.iterdir():
                if d.is_dir() and d.name.startswith(f"{material_id}_"):
                    full_html = d / "full.html"
                    summary_json = d / "summary.json"
                    if full_html.exists():
                        with open(full_html, "r", encoding="utf-8") as f:
                            content = f.read()
                        logger.info(f"✅ 获取素材内容: {material_id} (from materials/full.html)")
                        return {
                            "id": material.id,
                            "name": material.name,
                            "type": material.material_type,
                            "content": content,
                            "content_type": "html"
                        }
                    elif summary_json.exists():
                        with open(summary_json, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        content = json.dumps(data, ensure_ascii=False, indent=2)
                        logger.info(f"✅ 获取素材内容: {material_id} (from materials/summary.json)")
                        return {
                            "id": material.id,
                            "name": material.name,
                            "type": material.material_type,
                            "content": content,
                            "content_type": "json"
                        }
                    break

        # Fallback: check legacy format
            # 检查旧格式
            legacy_path = Path(settings.DATA_DIR) / "parsed_pdfs" / str(project_id) / f"{Path(material.name).stem}.html"
            if legacy_path.exists():
                with open(legacy_path, "r", encoding="utf-8") as f:
                    content = f.read()
                logger.info(f"✅ 获取素材内容(旧格式): {material_id}")
                return {
                    "id": material.id,
                    "name": material.name,
                    "type": material.material_type,
                    "content": content,
                    "content_type": "html"
                }
            
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="素材内容文件不存在，可能尚未解析完成"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取素材内容失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}"
        )


@router.delete("/projects/{project_id}/materials/{material_id}")
async def remove_material_from_project(
    project_id: int,
    material_id: int,
    db: Session = Depends(get_db)
):
    """
    从项目中移除素材

    Args:
        project_id: 项目ID
        material_id: 素材ID
        db: 数据库会话

    Returns:
        移除结果
    """
    try:
        # 查找项目
        project = get_or_404(db, CreationProject, CreationProject.id == project_id, "项目不存在")

        # 检查素材是否在项目的 material_ids 中
        material_ids = list(project.material_ids) if project.material_ids else []

        if material_id not in material_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="素材不在该项目中"
            )

        # 从项目的 material_ids 中移除该素材ID（创建新列表，确保SQLAlchemy检测到变化）
        new_material_ids = [mid for mid in material_ids if mid != material_id]
        project.material_ids = new_material_ids

        # 对于JSON字段，需要显式标记为已修改
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(project, "material_ids")

        db.commit()

        logger.info(f"✅ 已从项目{project_id}移除素材{material_id}")

        return {"message": "移除成功"}

    except Exception as e:
        db.rollback()
        logger.error(f"❌ 移除素材失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"移除失败: {str(e)}"
        )


@router.get("/materials/{material_id}")
async def get_material_detail(
    material_id: int,
    db: Session = Depends(get_db)
):
    """Get material content by material ID (global, no project scope)"""
    try:
        material = get_or_404(db, Material, Material.id == material_id, "素材不存在")

        content_json_path = Path(settings.DATA_DIR) / "documents" / str(material_id) / "content.json"
        content_html_path = Path(settings.DATA_DIR) / "documents" / str(material_id) / "content.html"

        if content_json_path.exists():
            import json
            with open(content_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            content = data.get("content", "")
            return {"id": material.id, "name": material.name, "type": material.material_type, "content": content, "content_type": "html"}
        elif content_html_path.exists():
            with open(content_html_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {"id": material.id, "name": material.name, "type": material.material_type, "content": content, "content_type": "html"}

        # Check materials directory (pre-parsed by PDF pipeline)
        materials_dir = Path(settings.DATA_DIR) / "materials"
        if materials_dir.exists():
            for d in materials_dir.iterdir():
                if d.is_dir() and d.name.startswith(f"{material_id}_"):
                    full_html = d / "full.html"
                    summary_json = d / "summary.json"
                    if full_html.exists():
                        with open(full_html, "r", encoding="utf-8") as f:
                            content = f.read()
                        return {"id": material.id, "name": material.name, "type": material.material_type, "content": content, "content_type": "html"}
                    elif summary_json.exists():
                        with open(summary_json, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        return {"id": material.id, "name": material.name, "type": material.material_type, "content": json.dumps(data, ensure_ascii=False, indent=2), "content_type": "json"}
                    break

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="素材内容文件不存在")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取素材内容失败: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取失败: {str(e)}")


@router.delete("/materials/{material_id}")
async def delete_material(
    material_id: int,
    db: Session = Depends(get_db)
):
    """Delete material globally"""
    try:
        material = get_or_404(db, Material, Material.id == material_id, "素材不存在")

        # Remove document files
        doc_dir = Path(settings.DATA_DIR) / "documents" / str(material_id)
        if doc_dir.exists():
            import shutil
            shutil.rmtree(doc_dir, ignore_errors=True)

        # Remove materials directory ({id}_{name}/)
        materials_dir = Path(settings.DATA_DIR) / "materials"
        if materials_dir.exists():
            for d in list(materials_dir.iterdir()):
                if d.is_dir() and d.name.startswith(f"{material_id}_"):
                    shutil.rmtree(d, ignore_errors=True)

        # Remove parsed_pdfs output
        parsed_dir = Path(settings.DATA_DIR) / "parsed_pdfs"
        if parsed_dir.exists():
            import glob
            for f in glob.glob(str(parsed_dir / "**" / f"*{material.name}*"), recursive=True):
                Path(f).unlink(missing_ok=True)

        # Remove from all projects' material_ids
        projects = db.query(CreationProject).all()
        for project in projects:
            if project.material_ids and material_id in project.material_ids:
                project.material_ids = [mid for mid in project.material_ids if mid != material_id]
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(project, "material_ids")

        # Remove associated pages
        db.query(MaterialPage).filter(MaterialPage.material_id == material_id).delete()

        # Remove material record
        db.delete(material)
        db.commit()

        logger.info(f"✅ 已删除素材{material_id}")
        return {"message": "删除成功"}
    except Exception as e:
        db.rollback()
        logger.error(f"❌ 删除素材失败: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"删除失败: {str(e)}")


@router.get("/materials/{material_id}/parse-status")
async def get_material_parse_status(
    material_id: int,
    db: Session = Depends(get_db)
):
    """Get parse status and progress for a single material (lightweight polling endpoint)."""
    try:
        material = get_or_404(db, Material, Material.id == material_id, "素材不存在")

        if material.material_type not in ["pdf", "document"]:
            return {"status": "completed", "progress": 100, "error_message": None}

        # Check file existence first
        doc_html = Path(settings.DATA_DIR) / "documents" / str(material_id) / "document.html"
        content_html = Path(settings.DATA_DIR) / "documents" / str(material_id) / "content.html"
        # Also check materials directory (for pre-parsed files)
        materials_dir = Path(settings.DATA_DIR) / "materials"
        material_parsed = False
        if materials_dir.exists():
            for d in materials_dir.iterdir():
                if d.is_dir() and d.name.startswith(f"{material_id}_"):
                    full_html = d / "full.html"
                    if full_html.exists():
                        # Verify it's not an empty skeleton (has actual table content)
                        size = full_html.stat().st_size
                        if size > 20000:  # Real content is typically > 20KB
                            material_parsed = True
                            break
                    if (d / "summary.json").exists() and (d / "original.pdf").exists():
                        material_parsed = True
                        break
        if doc_html.exists() or content_html.exists() or material_parsed:
            return {"status": "completed", "progress": 100, "error_message": None}

        # Check queue task
        pdf_manager = get_pdf_queue_manager()
        task = pdf_manager.get_task_by_path(
            str(Path(settings.DATA_DIR) / "uploads" / str(material_id) / material.name)
        )
        if task:
            return {
                "status": task.status.value,
                "progress": task.progress,
                "error_message": task.error_message
            }

        return {"status": "pending", "progress": 0, "error_message": None}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取解析状态失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}"
        )

@router.post("/generate-draft")
async def generate_draft(
    request: GenerateDraftRequest,
    db: Session = Depends(get_db)
):
    """
    生成AI初稿 (已弃用: 请使用 /api/agent/generate-stream)
    
    Args:
        request: 生成请求
        db: 数据库会话
    
    Returns:
        生成的初稿内容和差异
    """
    logger.warning("⚠️ 调用了已弃用的 /generate-draft 接口，建议转向 /api/agent/generate-stream")
    log_workflow("AI初稿生成", "开始", {"style": request.style, "word_count": request.word_count})
    
    try:
        # 构建提示词
        style_map = {
            "news": "新闻",
            "essay": "散文",
            "comment": "评论",
            "report": "报道"
        }
        style_name = style_map.get(request.style, "新闻")
        
        prompt = f"""请根据以下大纲和主题,写一篇{style_name}风格的文章,字数约{request.word_count}字。

大纲/主题:
{request.outline}

要求:
1. 符合{style_name}的写作风格
2. 结构清晰,逻辑严密
3. 语言流畅,表达准确
4. 字数控制在{request.word_count}字左右

请直接输出文章内容,不要包含其他说明文字。"""

        # 调用LLM生成
        response = await llm_service.generate_text(prompt)
        
        if response.get("status") == "success":
            content = response.get("content", "")
            
            logger.info(f"✅ AI初稿生成成功,字数: {len(content)}")
            
            return {
                "content": content,
                "diff": {
                    "added": content,
                    "removed": ""
                }
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=response.get("error", "生成失败")
            )
            
    except Exception as e:
        logger.error(f"❌ AI初稿生成失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成失败: {str(e)}"
        )

@router.post("/comprehensive-search")
async def comprehensive_search(
    request: ComprehensiveSearchRequest,
    db: Session = Depends(get_db)
):
    """
    综合检索
    
    Args:
        request: 检索请求
        db: 数据库会话
    
    Returns:
        检索结果列表
    """
    log_workflow("综合检索", "开始", {"query_text": request.query_text[:50]})
    
    try:
        # 使用AI分析检索角度
        analysis_prompt = f"""请分析以下文本,从内容、地理、历史、政治、经济等角度提取检索关键词。

文本: {request.query_text}

请输出3-5个检索关键词,用逗号分隔。"""
        
        results = []
        
        # 如果包含网络搜索，执行网络搜索
        if "web" in request.search_types:
            try:
                from app.agents.tools.web_search import WebSearchTool
                from app.config import settings
                
                web_tool = WebSearchTool(settings)
                search_result = web_tool.search(request.query_text, max_results=10)
                
                # 解析搜索结果
                import json
                search_data = json.loads(search_result)
                if search_data.get("status") == "success":
                    for item in search_data.get("results", []):
                        results.append({
                            "title": item.get("title", ""),
                            "content": item.get("snippet", ""),
                            "url": item.get("url", ""),
                            "source": item.get("source", "网络搜索"),
                            "type": "web"
                        })
                    logger.info(f"✅ 网络搜索完成,找到{len(search_data.get('results', []))}条结果")
            except Exception as e:
                logger.error(f"❌ 网络搜索失败: {str(e)}")
        
        # 如果包含本地搜索，执行本地搜索
        if "local" in request.search_types:
            try:
                analysis_response = await llm_service.generate_text(analysis_prompt)
                keywords = analysis_response.get("content", request.query_text).split(",")[:5]
                
                # 本地搜索逻辑（可以从数据库查询）
                for keyword in keywords:
                    if keyword.strip():
                        results.append({
                            "title": f"关于'{keyword.strip()}'的本地检索结果",
                            "content": f"这是关于{keyword.strip()}的详细内容...",
                            "source": "本地知识库",
                            "type": "local"
                        })
            except Exception as e:
                logger.error(f"❌ 本地搜索失败: {str(e)}")
        
        logger.info(f"✅ 综合检索完成,找到{len(results)}条结果")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ 综合检索失败: {str(e)}")
        return []

@router.post("/ask")
async def ask_question(
    request: AskRequest,
    db: Session = Depends(get_db)
):
    """
    AI问答
    
    Args:
        request: 提问请求
        db: 数据库会话
    
    Returns:
        AI回答和参考资料
    """
    log_workflow("AI问答", "开始", {"question": request.question[:50]})
    
    try:
        # TODO: [上下文工程重构] 使用ContextSelector统一上下文构建逻辑
        # 参考：backend/app/services/context_engineering.py - ContextSelector类
        # 构建提示词
        prompt = f"""请基于以下上下文回答用户的问题。

上下文:
{request.context}

用户问题: {request.question}

请提供准确、详细的回答。如果涉及事实,请注明信息来源。"""

        response = await llm_service.generate_text(prompt)
        
        if response.get("status") == "success":
            answer = response.get("content", "")
            
            logger.info(f"✅ AI问答完成")
            
            return {
                "answer": answer,
                "references": []
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=response.get("error", "回答失败")
            )
            
    except Exception as e:
        logger.error(f"❌ AI问答失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"回答失败: {str(e)}"
        )

@router.post("/text-operation")
async def text_operation(
    request: TextOperationRequest,
    db: Session = Depends(get_db)
):
    """
    文本操作(改写/扩写/精简)
    
    Args:
        request: 操作请求
        db: 数据库会话
    
    Returns:
        处理后的文本
    """
    log_workflow("文本操作", "开始", {"operation": request.operation})
    
    try:
        operation_map = {
            "rewrite": "改写",
            "expand": "扩写",
            "simplify": "精简"
        }
        operation_name = operation_map.get(request.operation, "改写")
        
        prompt = f"""请{operation_name}以下文本,保持原意和风格。

原文:
{request.text}

请直接输出{operation_name}后的文本,不要包含其他说明。"""

        response = await llm_service.generate_text(prompt)
        
        if response.get("status") == "success":
            result = response.get("content", "")
            
            logger.info(f"✅ 文本{operation_name}完成")
            
            return {
                "content": result,
                "diff": {
                    "added": result,
                    "removed": request.text
                }
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=response.get("error", "操作失败")
            )
            
    except Exception as e:
        logger.error(f"❌ 文本操作失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"操作失败: {str(e)}"
        )

@router.get("/projects/{project_id}/versions")
async def get_versions(
    project_id: int,
    db: Session = Depends(get_db)
):
    """
    获取版本历史
    
    Args:
        project_id: 项目ID
        db: 数据库会话
    
    Returns:
        版本列表
    """
    versions = db.query(EditorVersion).filter(
        EditorVersion.project_id == project_id
    ).order_by(EditorVersion.created_at.desc()).limit(50).all()
    
    return {
        "versions": [
            {
                "id": v.id,
                "project_id": v.project_id,
                "content": v.content,
                "diff": v.diff,
                "operation": v.operation,
                "created_at": v.created_at.isoformat()
            }
            for v in versions
        ]
    }

@router.post("/projects/{project_id}/rollback/{version_id}")
async def rollback_version(
    project_id: int,
    version_id: int,
    db: Session = Depends(get_db)
):
    """
    回滚到指定版本
    
    Args:
        project_id: 项目ID
        version_id: 版本ID
        db: 数据库会话
    
    Returns:
        回滚结果
    """
    # 获取版本
    version = db.query(EditorVersion).filter(
        EditorVersion.id == version_id,
        EditorVersion.project_id == project_id
    ).first()
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="版本不存在"
        )
    
    # 获取项目
    project = get_or_404(db, CreationProject, CreationProject.id == project_id, "项目不存在")
    
    # 更新项目内容
    project.content = version.content
    db.commit()
    
    logger.info(f"✅ 已回滚项目{project_id}到版本{version_id}")
    
    return {"message": "回滚成功"}


# 新增：简化的项目内容管理API
class UpdateContentRequest(BaseModel):
    """更新项目内容请求"""
    content: str


@router.put("/projects/{project_id}/content")
async def update_project_content(
    project_id: int,
    request: UpdateContentRequest,
    db: Session = Depends(get_db)
):
    """
    更新项目内容（用于AI创作页面）
    
    Args:
        project_id: 项目ID
        request: 内容更新请求
        db: 数据库会话
    
    Returns:
        更新结果
    """
    try:
        # 查找项目
        project = get_or_404(db, CreationProject, CreationProject.id == project_id, "项目不存在")
        
        # 处理图片：自动下载网络图片和data URL
        processed_content = request.content
        try:
            from app.services.image_save_service import get_image_save_service
            image_service = get_image_save_service()
            processed_content = await image_service.process_project_images(
                request.content,
                project_id,
                db
            )
        except Exception as e:
            # 图片处理失败不影响内容保存，只记录错误
            logger.error(f"⚠️ 图片处理失败（不影响内容保存）: {str(e)}")
        
        # 更新内容
        project.content = processed_content
        project.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"✅ 项目{project_id}内容已更新")
        
        return {"message": "保存成功", "updated_at": project.updated_at.isoformat()}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ 更新项目内容失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新失败: {str(e)}"
        )


@router.post("/projects/{project_id}/documents")
async def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    relative_path: str = Form(default=""),
    db: Session = Depends(get_db)
):
    """
    上传并处理文档（PDF/Word）
    使用Qwen-VL进行OCR识别，提取文字和图片

    Args:
        project_id: 项目ID
        file: 上传的文件
        relative_path: 相对路径（用于保持文件夹层级结构，如 "工艺文档/装配/工序1.pdf"）
        db: 数据库会话

    Returns:
        处理结果
    """
    log_workflow("上传文档", "开始", {"project_id": project_id, "filename": file.filename, "relative_path": relative_path})

    try:
        # 检查项目是否存在
        project = get_or_404(db, CreationProject, CreationProject.id == project_id, "项目不存在")

        # 检查文件格式
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ['.pdf', '.docx', '.doc', '.txt']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不支持的文件格式，仅支持PDF、Word和TXT文档"
            )

        # Check for duplicate document on disk
        existing_doc = _check_duplicate_document(file.filename)
        if existing_doc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"文档已存在: {existing_doc['name']} (material_id={existing_doc['material_id']}, pages={existing_doc['pages']})。如需重新上传，请先删除已有文档。"
            )

        # 保存上传的文件，保持目录结构
        upload_base_dir = Path(settings.DATA_DIR) / "uploads" / str(project_id)
        upload_base_dir.mkdir(parents=True, exist_ok=True)

        # 如果有相对路径，创建子目录
        if relative_path:
            # 解析相对路径，创建目录结构
            # 例如：relative_path = "工艺文档/装配/工序1.pdf"
            parts = relative_path.replace('\\', '/').split('/')
            if len(parts) > 1:
                # 创建子目录
                subdir = upload_base_dir.joinpath(*parts[:-1])
                subdir.mkdir(parents=True, exist_ok=True)
                file_path = upload_base_dir / Path(relative_path.replace('\\', '/'))
            else:
                file_path = upload_base_dir / file.filename

            # 保存相对路径用于数据库
            db_relative_path = relative_path.replace('\\', '/')
        else:
            file_path = upload_base_dir / f"material_{project_id}_{file.filename}"
            db_relative_path = file.filename

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"📄 文件已保存: {file_path}")

        # 创建素材记录（Material 没有 project_id 字段，通过 CreationProject.material_ids 关联）
        material = Material(
            material_type="document",
            name=file.filename  # 确保有名称
            # content 已删除，内容保存在文件系统
        )
        db.add(material)
        db.commit()
        db.refresh(material)
        
        # 将素材添加到项目的 material_ids 列表中
        material_ids = project.material_ids if project.material_ids else []
        if material.id not in material_ids:
            material_ids.append(material.id)
            project.material_ids = material_ids
            db.commit()
        
        # 添加到 PDF 解析队列（异步处理）
        manager = get_pdf_queue_manager()

        # 计算输出路径（保持文件夹结构）
        output_path = Path(settings.DATA_DIR) / "parsed_pdfs" / str(project_id)
        if relative_path:
            # 保持相对路径结构
            output_path = output_path / Path(relative_path).with_suffix(".html")
        else:
            output_path = output_path / f"{file.filename}.html"

        task_id = await manager.add_task(
            source_path=str(file_path),
            output_path=str(output_path),
            priority=PDFTaskPriority.NORMAL
        )

        if task_id:
            logger.info(f"✅ 文件已加入解析队列: task_id={task_id}, file={file.filename}")

            return {
                "message": "文档已加入解析队列",
                "material_id": material.id,
                "task_id": task_id,
                "filename": file.filename,
                "size": file_path.stat().st_size,
                "queue_position": manager.get_stats().pending_tasks
            }
        else:
            # task_id 为 None 表示文件已存在且已解析
            logger.info(f"ℹ️ 文件已存在且已解析，跳过: {file.filename}")

            return {
                "message": "文档已存在，无需重复解析",
                "material_id": material.id,
                "task_id": None,
                "filename": file.filename,
                "size": file_path.stat().st_size
            }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ 上传文档失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传失败: {str(e)}"
        )

@router.get("/projects/{project_id}/content")
async def get_project_content(
    project_id: int,
    db: Session = Depends(get_db)
):
    """
    获取项目内容
    
    Args:
        project_id: 项目ID
        db: 数据库会话
    
    Returns:
        项目内容
    """
    try:
        project = get_or_404(db, CreationProject, CreationProject.id == project_id, "项目不存在")
        
        return {
            "id": project.id,
            "name": project.name,
            "content": project.content or "",
            "updated_at": project.updated_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取项目内容失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取失败: {str(e)}"
        )

class SearchImagesRequest(BaseModel):
    """图片搜索请求"""
    query: str
    source: str = "all"  # local, web, all
    count: int = 20  # 返回数量（用于分页加载）

@router.post("/projects/{project_id}/images/search")
async def search_images(
    project_id: int,
    request: SearchImagesRequest,
    db: Session = Depends(get_db)
):
    """
    搜索图片（本地素材 + 网络）
    
    Args:
        project_id: 项目ID
        request: 搜索请求
        db: 数据库会话
    
    Returns:
        图片列表
    """
    try:
        results = []
        query = request.query.strip()
        if not query:
            return []
            
        # 1. 本地搜索 (Local)
        if request.source in ["all", "local"]:
            # 1.1 搜索项目关联的文档图片 (Figures)
            # 先获取项目的 material_ids，然后查询关联的 Figure
            project = get_or_404(db, CreationProject, CreationProject.id == project_id, "项目不存在")
            material_ids = project.material_ids or []
            
            # 查询这些 Material 关联的 Figure
            figures = []
            if material_ids:
                figures = db.query(Figure).join(Material).filter(
                    Material.id.in_(material_ids),
                    Figure.caption.like(f"%{query}%")
                ).limit(20).all()
            
            for fig in figures:
                # 构建 URL (data 目录挂载在 /static/data)
                url = build_static_url(fig.file_path)
                results.append({
                    "type": "local_figure",
                    "url": url,
                    "thumbnail": url,
                    "title": fig.caption or "文档图片",
                    "source": "项目文档",
                    "id": fig.id
                })
                
            # 1.2 搜索已下载的网络图片 (WebImages)
            # 简单起见，搜索所有已下载的库，或者只搜索当前项目的?
            # 这里搜索所有已下载的，作为"素材库"
            web_images = db.query(WebImage).filter(
                (WebImage.keyword.like(f"%{query}%")) | 
                (WebImage.title.like(f"%{query}%")) |
                (WebImage.description.like(f"%{query}%"))
            ).order_by(WebImage.created_at.desc()).limit(20).all()
            
            for img in web_images:
                url = build_static_url(img.local_path)
                results.append({
                    "type": "local_web",
                    "url": url,
                    "thumbnail": url,
                    "title": img.title or img.keyword,
                    "source": "本地素材库",
                    "id": img.id
                })

        # 2. RAG 向量检索本地图片（补充数据库搜索）
        if request.source in ["all", "local"]:
            try:
                image_tool = get_image_search_tool()
                rag_results = await image_tool.search_local_images(query, project_id, count=10)
                
                # 去重：检查是否已在 results 中
                existing_urls = {r.get("url") for r in results}
                for res in rag_results:
                    url = res.get("url")
                    if url and url not in existing_urls:
                        results.append({
                            "type": "local_rag",
                            "url": url,
                            "thumbnail": url,
                            "title": res.get("title", ""),
                            "source": "本地素材库(语义)",
                            "id": None,
                            "score": res.get("score", 0)
                        })
                        existing_urls.add(url)
            except Exception as e:
                logger.warning(f"RAG 图片搜索失败: {e}")

        # 3. 网络搜索 (Web) - 只搜索，不下载（用户选中后再下载）
        if request.source in ["all", "web"]:
            image_tool = get_image_search_tool()
            # 只搜索图片URL，不下载
            web_results = await image_tool.search_images(query, count=request.count, safe_search=True)
            
            for res in web_results:
                # 检查该URL是否已经下载过（根据original_url）
                web_image = db.query(WebImage).filter(
                    WebImage.original_url == res.get('url', '')
                ).first()
                
                if web_image and web_image.local_path:
                    # 如果已下载，返回本地路径（静态文件挂载在 /static/data）
                    image_url = build_static_url(web_image.local_path)
                    image_id = web_image.id
                else:
                    # 未下载，返回原始URL
                    image_url = res.get('url', '')
                    image_id = None
                
                results.append({
                    "type": "web",
                    "url": image_url,
                    "original_url": res.get('url', ''),  # 保存原始URL，用于后续下载
                    "thumbnail": res.get('thumbnail') or res.get('url', ''),
                    "title": res.get('title', ''),
                    "source": res.get('source', '网络搜索'),
                    "id": image_id,  # 如果已下载则有ID，否则为None
                    "is_downloaded": web_image is not None and web_image.local_path is not None
                })
                
        return results

    except Exception as e:
        logger.error(f"❌ 图片搜索失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索失败: {str(e)}"
        )


class DownloadImageRequest(BaseModel):
    """下载图片请求"""
    url: str  # 图片原始URL
    keyword: Optional[str] = None  # 搜索关键词（用于记录）


@router.post("/projects/{project_id}/images/download")
async def download_image(
    project_id: int,
    request: DownloadImageRequest,
    db: Session = Depends(get_db)
):
    """
    下载选中的图片到本地
    
    Args:
        project_id: 项目ID
        request: 下载请求（包含图片URL）
        db: 数据库会话
    
    Returns:
        下载结果（包含本地路径）
    """
    try:
        image_tool = get_image_search_tool()
        
        # 检查是否已下载
        existing = db.query(WebImage).filter(
            WebImage.original_url == request.url
        ).first()
        
        if existing and existing.local_path:
            # 已下载，直接返回（静态文件挂载在 /static/data）
            return {
                "success": True,
                "id": existing.id,
                "url": build_static_url(existing.local_path),
                "local_path": existing.local_path,
                "existed": True
            }
        
        # 下载图片
        download_result = await image_tool.download_image(
            request.url,
            request.keyword or "用户选择",
            None
        )
        
        if not download_result:
            # 提供更详细的错误信息
            error_detail = "图片下载失败，可能原因：网络连接问题、图片链接失效或服务器拒绝访问"
            logger.error(f"❌ 图片下载失败: {request.url[:50]}...")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_detail
            )
        
        # 保存到数据库
        web_image = WebImage(
            keyword=request.keyword or "用户选择",
            original_url=request.url,
            thumbnail_url=request.url,
            local_path=download_result.get('local_path', ''),
            title="",
            source_website="",
            width=0,
            height=0,
            file_size=download_result.get('file_size', 0),
            file_hash=download_result.get('file_hash', ''),
            description=None,
            relevance_score=None,
            is_verified=False
        )
        
        db.add(web_image)
        db.commit()
        db.refresh(web_image)
        
        logger.info(f"✅ 图片下载成功: {web_image.id}")
        
        return {
            "success": True,
            "id": web_image.id,
            "url": build_static_url(web_image.local_path),
            "local_path": web_image.local_path,
            "existed": False
        }
        
    except Exception as e:
        logger.error(f"❌ 图片下载失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下载失败: {str(e)}"
        )


@router.post("/images/upload")
async def upload_image(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    上传图片并自动生成关键词和描述
    
    Args:
        project_id: 项目ID（必填，创作项目ID）
        file: 图片文件
        db: 数据库会话
    
    Returns:
        上传结果，包含图片信息和AI生成的关键词、描述
    """
    log_workflow("图片上传", "开始", {"filename": file.filename, "project_id": project_id})
    
    # 验证项目是否存在
    get_or_404(db, CreationProject, CreationProject.id == project_id, "项目不存在")
    
    # 验证文件格式
    allowed_formats = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_formats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的图片格式: {file_ext}，仅支持 {', '.join(allowed_formats)}"
        )
    
    try:
        # 读取文件内容
        file_content = await file.read()
        file_size = len(file_content)
        
        # 验证文件大小（10MB限制）
        if file_size > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="图片文件过大，最大支持10MB"
            )
        
        # 计算文件哈希（用于去重）
        file_hash = calculate_file_hash(file_content)
        
        # 检查是否已上传
        existing = db.query(UploadedImage).filter(UploadedImage.file_hash == file_hash).first()
        if existing:
            logger.info(f"✅ 图片已存在，跳过上传: {existing.original_name}")
            return {
                "success": True,
                "id": existing.id,
                "url": build_static_url(existing.file_path),
                "file_path": existing.file_path,
                "description": existing.description,
                "keywords": existing.keywords or [],
                "existed": True
            }
        
        # 获取图片尺寸
        from io import BytesIO
        try:
            img = Image.open(BytesIO(file_content))
            width, height = img.size
        except Exception as e:
            logger.warning(f"⚠️ 无法读取图片尺寸: {str(e)}")
            width, height = None, None
        
        # 保存文件 - 使用统一配置的路径
        date_str = datetime.now().strftime("%Y%m%d")
        date_dir = settings.UPLOADED_IMAGES_DIR / date_str
        date_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成唯一文件名
        file_name = f"{file_hash}{file_ext}"
        file_path = date_dir / file_name
        relative_path = f"uploads/images/{date_str}/{file_name}"
        
        # 写入文件
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        logger.info(f"✅ 图片已保存: {file_path}")
        
        # 创建数据库记录（先保存，后续更新AI生成的内容）
        uploaded_image = UploadedImage(
            project_id=project_id,
            original_name=file.filename,
            file_path=relative_path,
            file_hash=file_hash,
            file_size=file_size,
            width=width,
            height=height
        )
        db.add(uploaded_image)
        db.commit()
        db.refresh(uploaded_image)
        
        # 异步生成描述和关键词
        try:
            # 生成图片描述
            description = await vl_service.generate_caption(file_path)
            uploaded_image.description = description
            
            # 从描述中提取关键词（使用LLM）
            try:
                keyword_prompt = f"""请从以下图片描述中提取5-10个关键词，用于图片检索。
要求：
1. 关键词要简洁，每个关键词1-4个字
2. 涵盖图片的主要内容、对象、场景、类型等
3. 用JSON数组格式返回，例如：["关键词1", "关键词2", "关键词3"]

图片描述：
{description}

请只返回JSON数组，不要其他内容。"""
                
                keyword_response = await llm_service.chat(
                    messages=[{"role": "user", "content": keyword_prompt}],
                    temperature=0.3
                )
                
                # 解析关键词
                keyword_text = keyword_response.get("content", "").strip()
                # 尝试提取JSON数组
                import re
                json_match = re.search(r'\[.*?\]', keyword_text, re.DOTALL)
                if json_match:
                    keywords = json.loads(json_match.group())
                else:
                    # 如果无法解析JSON，从描述中提取关键词
                    keywords = [kw.strip() for kw in description.split('，')[:10] if kw.strip()]
                
                uploaded_image.keywords = keywords
                logger.info(f"✅ 关键词提取成功: {keywords}")
                
            except Exception as e:
                logger.warning(f"⚠️ 关键词提取失败: {str(e)}")
                # 如果关键词提取失败，至少保存描述
                uploaded_image.keywords = []
            
            db.commit()
            db.refresh(uploaded_image)
            
        except Exception as e:
            logger.error(f"❌ AI分析失败: {str(e)}")
            # 即使AI分析失败，也返回上传成功的结果
        
        logger.info(f"✅ 图片上传完成: {uploaded_image.id}")
        
        return {
            "success": True,
            "id": uploaded_image.id,
            "url": build_static_url(uploaded_image.file_path),
            "file_path": uploaded_image.file_path,
            "description": uploaded_image.description,
            "keywords": uploaded_image.keywords or [],
            "existed": False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 图片上传失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传失败: {str(e)}"
        )


@router.get("/images/search")
async def search_uploaded_images(
    project_id: int,
    query: str = "",
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    搜索已上传的图片
    
    Args:
        project_id: 项目ID（必填）
        query: 搜索关键词（在关键词或描述中搜索）
        limit: 返回数量限制
        db: 数据库会话
    
    Returns:
        图片列表
    """
    try:
        # 验证项目是否存在
        get_or_404(db, CreationProject, CreationProject.id == project_id, "项目不存在")
        
        query_text = query.strip()
        
        # 基础查询：只查询该项目的图片
        base_query = db.query(UploadedImage).filter(UploadedImage.project_id == project_id)
        
        if query_text:
            # 按关键词或描述搜索
            # 使用LIKE查询（简单实现，后续可以优化为全文搜索）
            images = base_query.filter(
                (UploadedImage.description.contains(query_text)) |
                (UploadedImage.keywords.contains([query_text]))
            ).order_by(UploadedImage.upload_time.desc()).limit(limit).all()
        else:
            # 返回该项目的所有图片
            images = base_query.order_by(
                UploadedImage.upload_time.desc()
            ).limit(limit).all()
        
        results = []
        for img in images:
            results.append({
                "id": img.id,
                "url": build_static_url(img.file_path),
                "file_path": img.file_path,
                "original_name": img.original_name,
                "description": img.description,
                "keywords": img.keywords or [],
                "width": img.width,
                "height": img.height,
                "upload_time": img.upload_time.isoformat() if img.upload_time else None
            })
        
        return {
            "success": True,
            "count": len(results),
            "images": results
        }

    except Exception as e:
        logger.error(f"❌ 图片搜索失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索失败: {str(e)}"
        )


# ==================== 素材索引 API ====================

from app.services.material_index import material_index_service, MaterialManifest
from fastapi import Form


# Pydantic models for API
class GenerateIndexRequest(BaseModel):
    """生成索引请求"""
    folder_path: str = Field(..., description="素材文件夹路径")
    project_id: Optional[int] = Field(None, description="项目ID")
    save_to_db: bool = Field(False, description="是否保存索引到数据库")
    auto_save: bool = Field(True, description="是否自动保存 manifest.json 文件")


class IndexResponse(BaseModel):
    """索引生成响应"""
    manifest: MaterialManifest
    manifest_path: Optional[str] = None
    file_count: int
    directory_count: int
    total_size: int
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# API endpoints
@router.post("/projects/{project_id}/materials/generate-index", response_model=IndexResponse)
async def generate_material_index(
    project_id: int,
    request: GenerateIndexRequest = Depends(),
    db: Session = Depends(get_db)
):
    """
    生成素材库索引文件

    扫描指定文件夹，生成包含文件列表、目录结构、文件哈希等信息的索引清单
    """
    log_workflow("生成素材索引", "开始", {
        "project_id": project_id,
        "folder_path": request.folder_path
    })

    try:
        # 验证项目是否存在
        project = get_or_404(db, CreationProject, CreationProject.id == project_id, "项目不存在")

        # 验证文件夹路径
        folder_path = Path(request.folder_path)
        if not folder_path.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件夹不存在: {request.folder_path}"
            )

        if not folder_path.is_dir():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"路径不是文件夹: {request.folder_path}"
            )

        # 生成索引
        manifest, saved_path = await material_index_service.generate_and_save_manifest(
            folder_path=str(folder_path),
            project_id=project_id,
            output_path=str(folder_path / "manifest.json") if request.auto_save else None
        )

        # 保存索引到数据库（如果需要）- 只存元数据，内容在文件系统
        if request.save_to_db:
            existing = db.query(Material).filter(
                Material.name == "manifest.json",
                Material.id.in_(project.material_ids or [])
            ).first()

            if not existing:
                # 创建新的素材记录（只存元数据）
                new_material = Material(
                    name="manifest.json",
                    material_type="index"
                    # content 已删除，manifest 保存在文件系统
                )
                db.add(new_material)
                db.commit()
                db.refresh(new_material)
                project.material_ids = (project.material_ids or []) + [new_material.id]
                db.commit()

        # 扫描文件夹中的所有 PDF，添加到解析队列
        pdf_files = []
        folder_path_obj = Path(request.folder_path)

        if folder_path_obj.is_dir():
            for file_path in folder_path_obj.rglob("*.pdf"):
                relative_path = file_path.relative_to(folder_path_obj)
                pdf_files.append({
                    "absolute_path": str(file_path),
                    "relative_path": str(relative_path)
                })

            logger.info(f"📁 找到 {len(pdf_files)} 个 PDF 文件")

            # 复制到上传目录（保持文件夹结构）
            upload_base_dir = Path(settings.DATA_DIR) / "uploads" / str(project_id)
            copied_paths = []

            for pdf in pdf_files:
                target_path = upload_base_dir / pdf["relative_path"]
                target_path.parent.mkdir(parents=True, exist_ok=True)

                # 复制文件
                shutil.copy2(pdf["absolute_path"], target_path)
                copied_paths.append(str(target_path))

            logger.info(f"✅ 已复制 {len(copied_paths)} 个文件到上传目录")

            # 批量添加到解析队列
            task_ids = []

            if copied_paths:
                manager = get_pdf_queue_manager()

                # 准备输出路径
                for pdf, source_path in zip(pdf_files, copied_paths):
                    output_path = str(
                        Path(settings.DATA_DIR) / "parsed_pdfs" / str(project_id) / Path(pdf["relative_path"]).with_suffix(".html")
                    )

                    task_id = await manager.add_task(
                        source_path=source_path,
                        output_path=output_path,
                        priority=PDFTaskPriority.NORMAL
                    )

                    if task_id:
                        task_ids.append(task_id)

                logger.info(f"✅ {len(task_ids)} 个文件已加入解析队列")
        else:
            task_ids = []

        logger.info(f"✅ 素材索引生成完成: {len(manifest.files)} 个文件")

        return {
            "manifest": manifest,
            "manifest_path": saved_path if request.auto_save else None,
            "file_count": len(manifest.files),
            "directory_count": len(manifest.directories),
            "total_size": manifest.total_size,
            "generated_at": datetime.now().isoformat(),
            "task_ids": task_ids,
            "queue_message": f"{len(task_ids)} 个 PDF 已加入解析队列"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 生成素材索引失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成索引失败: {str(e)}"
        )


@router.post("/projects/{project_id}/materials/upload-folder", response_model=IndexResponse)
async def upload_folder_and_generate_index(
    project_id: int,
    folder_path: str = Form(...),
    db: Session = Depends(get_db)
):
    """上传文件夹并自动生成索引"""
    return await generate_material_index(
        project_id,
        GenerateIndexRequest(
            folder_path=folder_path,
            project_id=project_id,
            save_to_db=True,
            auto_save=True
        ),
        db
    )


@router.get("/projects/{project_id}/materials/index", response_model=MaterialManifest)
async def get_material_index(
    project_id: int,
    db: Session = Depends(get_db)
):
    """获取项目的素材索引"""
    try:
        project = get_or_404(db, CreationProject, CreationProject.id == project_id, "项目不存在")

        manifest_material = db.query(Material).filter(
            Material.name == "manifest.json",
            Material.id.in_(project.material_ids or [])
        ).first()

        if not manifest_material:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="索引文件不存在，请先生成索引"
            )

        manifest_data = json.loads(manifest_material.content)
        return MaterialManifest(**manifest_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 获取素材索引失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取索引失败: {str(e)}"
        )


# ==================== 批量上传 API ====================

class BatchUploadResponse(BaseModel):
    """批量上传响应"""
    status: str
    uploaded_count: int
    failed_count: int
    files: List[dict]
    manifest_path: Optional[str] = None


@router.post("/projects/{project_id}/materials/batch-upload", response_model=BatchUploadResponse)
async def batch_upload_materials(
    project_id: int,
    files: List[UploadFile] = File(...),
    relative_paths: str = Form(default=""),  # JSON 数组格式的相对路径列表
    db: Session = Depends(get_db)
):
    """
    批量上传素材文件，保持目录结构

    Args:
        project_id: 项目ID
        files: 上传的文件列表
        relative_paths: JSON 数组格式的相对路径列表（与 files 顺序对应）
        db: 数据库会话

    Returns:
        上传结果和索引路径
    """
    log_workflow("批量上传素材", "开始", {
        "project_id": project_id,
        "file_count": len(files)
    })

    try:
        # 验证项目存在
        project = get_or_404(db, CreationProject, CreationProject.id == project_id, "项目不存在")

        # 解析相对路径
        paths_list = []
        if relative_paths:
            try:
                paths_list = json.loads(relative_paths)
            except json.JSONDecodeError:
                logger.warning(f"无法解析 relative_paths: {relative_paths}")

        # 准备上传目录
        upload_base_dir = Path(settings.DATA_DIR) / "uploads" / str(project_id)
        upload_base_dir.mkdir(parents=True, exist_ok=True)

        uploaded_files = []
        failed_count = 0
        skipped_files = []

        for idx, file in enumerate(files):
            try:
                # 获取对应的相对路径
                relative_path = paths_list[idx] if idx < len(paths_list) else ""

                # 检查文件格式
                file_ext = Path(file.filename).suffix.lower()
                if file_ext not in ['.pdf', '.docx', '.doc', '.txt', '.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    logger.warning(f"跳过不支持的文件格式: {file.filename}")
                    failed_count += 1
                    continue

                # Check for duplicate document on disk (only for document types)
                if file_ext in ['.pdf', '.docx', '.doc', '.txt']:
                    existing_doc = _check_duplicate_document(file.filename)
                    if existing_doc:
                        logger.info(f"跳过重复文档: {file.filename} (已有 material_id={existing_doc['material_id']})")
                        skipped_files.append({
                            "name": file.filename,
                            "reason": f"文档已存在 (material_id={existing_doc['material_id']}, pages={existing_doc['pages']})",
                            "existing_material_id": existing_doc["material_id"],
                        })
                        continue

                # 确定保存路径
                if relative_path:
                    # 保持目录结构
                    parts = relative_path.replace('\\', '/').split('/')
                    if len(parts) > 1:
                        subdir = upload_base_dir.joinpath(*parts[:-1])
                        subdir.mkdir(parents=True, exist_ok=True)
                        file_path = upload_base_dir / Path(relative_path.replace('\\', '/'))
                    else:
                        file_path = upload_base_dir / file.filename
                    db_relative_path = relative_path.replace('\\', '/')
                else:
                    file_path = upload_base_dir / file.filename
                    db_relative_path = file.filename

                # 保存文件
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                # 计算文件哈希
                file_hash = calculate_file_hash(file_path)

                uploaded_files.append({
                    "name": file.filename,
                    "path": db_relative_path,
                    "size": file_path.stat().st_size,
                    "hash": file_hash
                })

                logger.info(f"✅ 文件上传成功: {file_path}")

            except Exception as e:
                logger.error(f"❌ 文件上传失败 {file.filename}: {str(e)}")
                failed_count += 1

        # 上传完成后自动生成索引
        manifest_path = None
        if uploaded_files:
            try:
                manifest, manifest_path = await material_index_service.generate_and_save_manifest(
                    folder_path=str(upload_base_dir),
                    project_id=project_id,
                    output_path=str(upload_base_dir / "manifest.json")
                )
                logger.info(f"✅ 索引生成完成: {manifest_path}")
            except Exception as e:
                logger.error(f"❌ 索引生成失败: {str(e)}")

        # 批量添加到解析队列
        pdf_files = [f for f in uploaded_files if Path(f["name"]).suffix.lower() == ".pdf"]
        task_ids = []

        if pdf_files:
            manager = get_pdf_queue_manager()

            # 准备输出路径列表
            source_paths = []
            output_paths = []

            for pdf in pdf_files:
                source_path = str(upload_base_dir / pdf["path"])
                output_path = str(Path(settings.DATA_DIR) / "parsed_pdfs" / str(project_id) / Path(pdf["path"]).with_suffix(".html"))

                source_paths.append(source_path)
                output_paths.append(output_path)

            # 批量添加任务
            for source_path, output_path in zip(source_paths, output_paths):
                task_id = await manager.add_task(
                    source_path=source_path,
                    output_path=output_path,
                    priority=PDFTaskPriority.NORMAL
                )
                if task_id:
                    task_ids.append(task_id)

            logger.info(f"✅ {len(task_ids)} 个文件已加入解析队列")

        logger.info(f"✅ 批量上传完成: {len(uploaded_files)} 个文件成功, {failed_count} 个失败")

        return {
            "status": "success",
            "uploaded_count": len(uploaded_files),
            "failed_count": failed_count,
            "files": uploaded_files,
            "manifest_path": manifest_path,
            "task_ids": task_ids,
            "queue_message": f"{len(task_ids)} 个 PDF 已加入解析队列",
            "skipped": skipped_files
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 批量上传失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量上传失败: {str(e)}"
        )
