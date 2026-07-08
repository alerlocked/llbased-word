"""
文档处理器
实现"全图像"处理流程：PDF/Word -> 图片 -> OCR -> Markdown + 图片提取 + HTML生成
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from io import BytesIO
import fitz  # PyMuPDF
from PIL import Image
import docx
from sqlalchemy.orm import Session
import platform
from docx2pdf import convert

from app.config import settings
from app.models.database import Material, Figure, MaterialPage
from app.services.vl_service import vl_service
from app.shared.logging import get_logger
logger = get_logger(__name__)
from app.utils.markdown_utils import convert_vl_output_to_content_list
from app.services.pdf_queue_manager import PDFTask
from datetime import datetime

# Windows COM 初始化支持
if platform.system() == "Windows":
    import pythoncom


# 动态导入 HTML 生成函数
def _import_html_generator():
    """动态导入 HTML 生成模块"""
    from app.config import settings
    scripts_dir = settings.SCRIPTS_DIR
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    
    try:
        from generate_document_html import generate_document_html, generate_index_json
        return generate_document_html, generate_index_json
    except ImportError as e:
        logger.warning(f"无法导入 HTML 生成模块: {e}")
        return None, None


class DocumentProcessor:
    """文档处理器 - 全图像处理流程"""
    
    def __init__(self):
        """初始化文档处理器"""
        self.figures_dir = settings.FIGURES_DIR
        self.figures_dir.mkdir(parents=True, exist_ok=True)
        # 创建页面图片存储目录
        self.pages_dir = settings.PAGES_DIR
        self.pages_dir.mkdir(parents=True, exist_ok=True)
    
    def _convert_docx_to_pdf_with_com(self, input_path: str, output_path: str):
        """
        在Windows环境下，使用COM初始化转换Word到PDF
        """
        if platform.system() == "Windows":
            # 初始化 COM
            pythoncom.CoInitialize()
            try:
                convert(input_path, output_path)
            finally:
                # 清理 COM
                pythoncom.CoUninitialize()
        else:
            convert(input_path, output_path)
    
    async def _convert_to_images(self, file_path: Path, material_id: int) -> List[Path]:
        """
        将文档（PDF/Word）转换为一系列图片
        
        Args:
            file_path: 源文件路径
            material_id: 素材ID
            
        Returns:
            生成的图片路径列表
        """
        file_ext = file_path.suffix.lower()
        pdf_path = file_path
        
        # 如果是Word文档，先转换为PDF
        if file_ext in [".docx", ".doc"]:
            logger.info(f"🔄 将Word转换为PDF: {file_path.name}")
            try:
                # 只有在Windows或macOS上且安装了Word才能使用docx2pdf
                if platform.system() == "Windows":
                    pdf_path = file_path.with_suffix(".pdf")
                    # 在线程中运行，并确保COM初始化
                    await asyncio.to_thread(self._convert_docx_to_pdf_with_com, str(file_path), str(pdf_path))
                    logger.info(f"✅ Word转PDF成功: {pdf_path}")
                else:
                    logger.warning("⚠️ 非Windows环境，Word转PDF可能受限，尝试直接处理")
                    # 这里可以添加其他转换逻辑
            except Exception as e:
                logger.error(f"❌ Word转PDF失败: {str(e)}")
                raise ValueError(f"Word转PDF失败: {str(e)}")

        # 打开PDF并渲染为图片
        image_paths = []
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            logger.info(f"📄 正在将PDF渲染为图片，共{total_pages}页")
            
            for page_num in range(total_pages):
                page = doc[page_num]
                
                # 高分辨率渲染 (适当提高清晰度以利于OCR/图表检测)
                zoom = 3.0
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                
                # 保存图片: material_{id}_page_{num}.png
                image_filename = f"material_{material_id}_page_{page_num + 1}.png"
                image_path = self.pages_dir / image_filename
                pix.save(str(image_path))
                
                image_paths.append(image_path)
                
            doc.close()
            
            # 如果是生成的临时PDF，可以删除（源文件是Word时）
            if file_ext in [".docx", ".doc"] and pdf_path != file_path and pdf_path.exists():
                try:
                    pdf_path.unlink()
                except Exception:
                    pass
                    
            return image_paths
            
        except Exception as e:
            logger.error(f"❌ PDF转图片失败: {str(e)}")
            raise
    
    async def process_document(
        self,
        file_path: Path,
        material_id: int,
        db: Session,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict:
        """
        处理文档：转图片 -> OCR提取文字 -> 保存 -> 生成HTML

        Args:
            file_path: 文档文件路径
            material_id: 素材ID
            db: 数据库会话
            progress_callback: optional callback(pct: int, message: str)

        Returns:
            处理结果字典
        """
        logger.info(f"🚀 开始全图像化处理文档: {file_path.name}")
        
        try:
            # 1. 栅格化：转换为图片序列
            image_paths = await self._convert_to_images(file_path, material_id)

            if progress_callback:
                progress_callback(5, f"已转换为 {len(image_paths)} 页图片，开始解析...")
            
            total_pages = len(image_paths)
            all_markdown_parts = []
            extracted_pages = []
            extracted_figures = []
            
            # 收集 VL Service 输出用于生成 HTML
            vl_pages_data = {}
            
            # 2. Batch VL extraction (mineru 3.4 true-batch) then serial DB writes.
            #    Extraction runs in batched true-batch calls; DB writes stay serial
            #    because the SQLAlchemy session is not thread/concurrent-safe.
            batch_size = max(1, settings.VL_SERVICE_MAX_WORKERS)
            pages_extracted: list = [None] * total_pages

            if progress_callback:
                progress_callback(8, f"批量解析 {total_pages} 页中…")

            for batch_start in range(0, total_pages, batch_size):
                batch_end = min(batch_start + batch_size, total_pages)
                batch_paths = image_paths[batch_start:batch_end]
                try:
                    batch_results = await vl_service.ocr_pages_batch_mineru(batch_paths)
                except Exception as e:
                    # Fallback to per-page serial on batch failure (keeps system working)
                    logger.warning(f"⚠️ mineru batch failed, fallback serial: {e}")
                    batch_results = []
                    for p in batch_paths:
                        md, figs = await vl_service.ocr_page_to_markdown(p)
                        batch_results.append((md, figs))
                for j, res in enumerate(batch_results):
                    pages_extracted[batch_start + j] = res
                if progress_callback:
                    pct = 10 + int(batch_end / total_pages * 70)
                    progress_callback(min(pct, 80), f"已解析 {batch_end}/{total_pages} 页")

            # 2b. Serial DB writes — reuse existing per-page write logic
            for i, image_path in enumerate(image_paths):
                page_num = i + 1
                logger.info(f"🔍 处理第 {page_num}/{total_pages} 页...")
            
                # 使用VL服务识别页面内容（包含文字、表格、图片描述）
                # page_content: Markdown 文本
                # page_figures: 提取到的图表元数据列表
                page_content, page_figures = pages_extracted[i]
                
                # 保存页信息到数据库（只存储元数据，内容在文件系统）
                page_record = MaterialPage(
                    material_id=material_id,
                    page_number=page_num,
                    image_path=str(image_path.relative_to(settings.DATA_DIR))
                )
                db.add(page_record)
                
                # 收集 VL Service 输出
                vl_pages_data[page_num] = {
                    "markdown": page_content,
                    "figures": page_figures,
                    "image_path": str(image_path.relative_to(settings.DATA_DIR))
                }
                
                extracted_pages.append({
                    "page_number": page_num,
                    "image_path": str(image_path.relative_to(settings.DATA_DIR)),
                    "content": page_content
                })
                        
                # 处理图表信息
                if page_figures:
                    logger.info(f"  📊 发现 {len(page_figures)} 个图表")
                    for fig_data in page_figures:
                        # 创建 Figure 记录
                        figure = Figure(
                            material_id=material_id,
                            file_path=str(image_path.relative_to(settings.DATA_DIR)),
                            caption=fig_data.get("caption", "无标题图表"),
                            page_number=page_num
                        )
                        if fig_data.get("description"):
                            figure.caption = f"{figure.caption}\n\n{fig_data['description']}"
                            
                        db.add(figure)
                        extracted_figures.append({
                            "id": None,
                            "file_path": figure.file_path,
                            "caption": figure.caption,
                            "page_number": page_num,
                            "type": fig_data.get("type", "chart")
                        })
            
                # 组合Markdown
                all_markdown_parts.append(f"## 第 {page_num} 页\n\n{page_content}\n\n")

                # Update progress — write phase (extraction done in batch above)
                if progress_callback:
                    pct = 80 + int(page_num / total_pages * 10)
                    progress_callback(min(pct, 90), f"正在写入第 {page_num}/{total_pages} 页")
            
            # 提交数据库变更
            db.commit()
            
            # 组合最终全文（用于全文检索）
            final_content = "\n".join(all_markdown_parts)
            
            logger.info(f"✅ OCR完成: 共{total_pages}页, 提取 {len(extracted_figures)} 个图表")
            
            # ===== 新增：自动生成 HTML =====
            try:
                # 动态导入 HTML 生成函数
                generate_document_html, generate_index_json = _import_html_generator()
                if not generate_document_html or not generate_index_json:
                    logger.warning("HTML 生成模块不可用，跳过 HTML 生成")
                else:
                    # 获取 material 对象
                    material = db.query(Material).filter(Material.id == material_id).first()
                    if not material:
                        raise ValueError(f"Material {material_id} not found")
                    
                    # 准备文档输出目录 - 使用统一配置
                    doc_output_dir = settings.DOCUMENTS_DIR / str(material_id)
                    doc_output_dir.mkdir(parents=True, exist_ok=True)
                    
                    # 创建 vlm 子目录并复制图片
                    vlm_dir = doc_output_dir / "vlm"
                    vlm_dir.mkdir(parents=True, exist_ok=True)
                    vlm_images_dir = vlm_dir / "images"
                    vlm_images_dir.mkdir(parents=True, exist_ok=True)
                    
                    # 复制页面图片到 vlm/images/
                    import shutil
                    for image_path in image_paths:
                        dst_path = vlm_images_dir / image_path.name
                        if not dst_path.exists():
                            shutil.copy2(image_path, dst_path)
                    
                    # 转换 VL Service 输出为 content_list_v2.json 格式
                    content_list_data = convert_vl_output_to_content_list(vl_pages_data)
                    
                    # 保存 content_list_v2.json
                    content_list_path = vlm_dir / f"{material.name}_content_list_v2.json"
                    with open(content_list_path, 'w', encoding='utf-8') as f:
                        json.dump(content_list_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"✅ 生成 content_list_v2.json: {content_list_path}")
                    
                    # 生成 document.html
                    html_content = generate_document_html(
                        doc_name=material.name,
                        pages_data=content_list_data,
                        images_base_path="vlm/images"
                    )
                    html_path = doc_output_dir / "document.html"
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    logger.info(f"✅ 生成 document.html: {html_path}")
                    
                    # 生成 index.json
                    index_data = generate_index_json(
                        doc_name=material.name,
                        file_name=f"{material.name}.pdf",
                        pages_data=content_list_data
                    )
                    index_path = doc_output_dir / "index.json"
                    with open(index_path, 'w', encoding='utf-8') as f:
                        json.dump(index_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"✅ 生成 index.json: {index_path}")
                    logger.info(f"   - 表格数: {len(index_data.get('tables', []))}")
                    
            except Exception as e:
                # HTML 生成失败不影响 OCR 结果
                logger.error(f"⚠️ HTML生成失败（不影响OCR）: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())

            # 知识提取（revive-extract-funnel 节点3）：解析完成后落库物料/工序/标准。
            # try-except 不阻塞——失败记日志，不影响解析结果（素材库不并发，简单触发够）。
            try:
                from app.services.knowledge_extractor import KnowledgeExtractor
                _counts = KnowledgeExtractor().extract_and_save(str(material_id), db)
                logger.info(f"📚 [知识提取] doc={material_id}: {_counts.get('materials', 0)} 物料, {_counts.get('process_steps', 0)} 工序")
                # 标准文档检测（QJ903 → StandardExtractor）
                _mat = db.query(Material).filter(Material.id == material_id).first()
                if _mat and _mat.name and "QJ903" in _mat.name.upper():
                    from app.services.standard_extractor import StandardExtractor
                    _std = StandardExtractor().extract_and_save(str(material_id), db)
                    logger.info(f"📋 [标准提取] doc={material_id}: {_std}")
            except Exception as e:
                logger.warning(f"⚠️ [知识提取] 失败（不影响解析）: {str(e)}")

            if progress_callback:
                progress_callback(95, "正在生成结构化文档...")

            return {
                "content": final_content,
                "page_count": total_pages,
                "pages": extracted_pages,
                "figures": extracted_figures
            }
            
        except Exception as e:
            logger.error(f"❌ 文档处理失败: {str(e)}")
            raise

    async def process_document_from_task(
        self,
        task: PDFTask,
        db: Session,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        从队列任务处理文档

        Args:
            task: PDF 队列任务
            db: 数据库会话
            progress_callback: optional callback(pct: int, message: str)

        Returns:
            处理结果
        """
        # 1. 获取源文件路径
        source_path = Path(task.source_path)

        # 2. 从 source_path 和 DB 提取 material_id
        material_id = self._extract_material_id(task.source_path, db)

        logger.info(f"开始处理队列任务: {task.task_id}, material_id={material_id}")

        # 3. 调用现有的 process_document
        result = await self.process_document(
            file_path=source_path,
            material_id=material_id,
            db=db,
            progress_callback=progress_callback
        )

        # 4. 更新素材内容
        material = db.query(Material).filter(Material.id == material_id).first()
        if material:
            material.updated_at = datetime.utcnow()
            db.commit()

        # 5. 生成 HTML 和 JSON
        output_path = Path(task.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        html_path = output_path.with_suffix(".html")
        self._save_html(result, html_path)

        json_path = output_path.with_suffix(".json")
        self._save_json(result, json_path)

        # 6. Also save to documents/{material_id}/ for API discovery
        if material_id and material_id > 0:
            doc_dir = Path(settings.DATA_DIR) / "documents" / str(material_id)
            doc_dir.mkdir(parents=True, exist_ok=True)
            content_html = doc_dir / "content.html"
            self._save_html(result, content_html)
            logger.info(f"Content synced to documents/{material_id}/content.html")

        # 7. Invalidate hierarchical context cache so AI can discover new documents
        try:
            from app.services.hierarchical_context import hierarchical_context
            hierarchical_context.invalidate_cache()
            logger.info("Hierarchical context cache invalidated after parse")
        except Exception as e:
            logger.warning(f"Failed to invalidate context cache: {e}")

        logger.info(f"队列任务完成: {task.task_id}")

        return {
            "page_count": result.get("page_count", 0),
            "content_length": len(result.get("content", "")),
            "output_path": str(output_path)
        }

    def _extract_material_id(self, source_path: str, db) -> int:
        """Extract material_id by looking up the filename in DB.

        Source path format: data/uploads/{project_id}/material_{project_id}_{filename}
        The filename part is the original upload name, which matches Material.name.
        """
        import re
        # Extract original filename from upload path
        # Path: .../material_{project_id}_{original_filename}
        m = re.search(r'material_\d+_(.+)$', source_path)
        if m:
            filename = m.group(1)
            # Look up material by name (most recently created match)
            material = db.query(Material).filter(
                Material.name == filename
            ).order_by(Material.id.desc()).first()
            if material:
                return material.id

        # Fallback: try the directory name under uploads
        m = re.search(r'uploads[/\\](\d+)[/\\]', source_path)
        if m:
            # Check if there's a material with this as part of its path
            potential_id = int(m.group(1))
            material = db.query(Material).filter(Material.id == potential_id).first()
            if material:
                return potential_id

        return 0

    def _save_html(self, result: Dict, html_path: Path):
        """保存 HTML 文件"""
        html_content = result.get("html", "")
        if not html_content:
            html_content = f"<html><body><pre>{result.get('content', '')}</pre></body></html>"

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"HTML 已保存: {html_path}")

    def _save_json(self, result: Dict, json_path: Path):
        """保存 JSON 文件"""
        import json
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"JSON 已保存: {json_path}")


# 创建全局实例
document_processor = DocumentProcessor()
