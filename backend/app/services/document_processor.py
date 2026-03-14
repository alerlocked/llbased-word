"""
文档处理器
实现"全图像"处理流程：PDF/Word -> 图片 -> OCR -> Markdown + 图片提取
"""
import asyncio
from pathlib import Path
from typing import List, Dict, Optional
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
from app.utils.logger import logger

# Windows COM 初始化支持
if platform.system() == "Windows":
    import pythoncom


class DocumentProcessor:
    """文档处理器 - 全图像处理流程"""
    
    def __init__(self):
        """初始化文档处理器"""
        self.figures_dir = settings.FIGURES_DIR
        self.figures_dir.mkdir(parents=True, exist_ok=True)
        # 创建页面图片存储目录
        self.pages_dir = settings.DATA_DIR / "pages"
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
    
    async def process_document(self, file_path: Path, material_id: int, db: Session) -> Dict:
        """
        处理文档：转图片 -> OCR提取文字 -> 保存
        
        Args:
            file_path: 文档文件路径
            material_id: 素材ID
            db: 数据库会话
            
        Returns:
            处理结果字典
        """
        logger.info(f"🚀 开始全图像化处理文档: {file_path.name}")
        
        try:
            # 1. 栅格化：转换为图片序列
            image_paths = await self._convert_to_images(file_path, material_id)
            
            total_pages = len(image_paths)
            all_markdown_parts = []
            extracted_pages = []
            extracted_figures = []
            
            # 2. 逐页处理：OCR/VL提取
            for i, image_path in enumerate(image_paths):
                page_num = i + 1
                logger.info(f"🔍 处理第 {page_num}/{total_pages} 页...")
            
                # 使用VL服务识别页面内容（包含文字、表格、图片描述）
                # page_content: Markdown 文本
                # page_figures: 提取到的图表元数据列表
                page_content, page_figures = await vl_service.ocr_page_to_markdown(image_path)
                
                # 保存页信息到数据库
                page_record = MaterialPage(
                    material_id=material_id,
                    page_number=page_num,
                    image_path=str(image_path.relative_to(settings.BASE_DIR)),
                    text_content=page_content,
                    figures=page_figures  # 存储该页提取的图表元数据
                )
                db.add(page_record)
                
                extracted_pages.append({
                    "page_number": page_num,
                    "image_path": str(image_path.relative_to(settings.BASE_DIR)),
                    "content": page_content
                })
                        
                # 处理图表信息
                if page_figures:
                    logger.info(f"  📊 发现 {len(page_figures)} 个图表")
                    for fig_data in page_figures:
                        # 创建 Figure 记录
                        # 注意：目前我们复用整页图片的路径，因为不知道图表的具体坐标来裁剪
                        # 如果需要裁剪，需要让模型返回bbox，然后在此处裁剪保存
                        
                        figure = Figure(
                            material_id=material_id,
                            file_path=str(image_path.relative_to(settings.BASE_DIR)), # 复用页面图
                            caption=fig_data.get("caption", "无标题图表"),
                            page_number=page_num
                        )
                        # 如果有详细描述，可以追加到 caption 或另存字段
                        if fig_data.get("description"):
                            figure.caption = f"{figure.caption}\n\n{fig_data['description']}"
                            
                        db.add(figure)
                        extracted_figures.append({
                            "id": None, # 待 flush 后获取
                            "file_path": figure.file_path,
                            "caption": figure.caption,
                            "page_number": page_num,
                            "type": fig_data.get("type", "chart")
                        })
            
                # 组合Markdown
                all_markdown_parts.append(f"## 第 {page_num} 页\n\n{page_content}\n\n")
            
            # 提交数据库变更
            db.commit()
            
            # 组合最终全文（用于全文检索）
            final_content = "\n".join(all_markdown_parts)
            
            logger.info(f"✅ 文档处理完成: 共{total_pages}页, 提取 {len(extracted_figures)} 个图表")
            
            return {
                "content": final_content,
                "page_count": total_pages,
                "pages": extracted_pages,
                "figures": extracted_figures
            }
            
        except Exception as e:
            logger.error(f"❌ 文档处理失败: {str(e)}")
            raise

# 创建全局实例
document_processor = DocumentProcessor()
