"""
DraftService - 工艺文件初稿服务
提供上传、解析、快照、回滚、版本管理功能
Phase 3 - PIV: piv_20260411_draft_service_phase3
"""
import difflib
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.database import DraftDocument, DraftVersion
from app.shared.logging import get_logger

logger = get_logger(__name__)

# 默认版本保留上限
DEFAULT_MAX_VERSIONS = 50


class DraftService:
    """工艺文件初稿服务"""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # 上传
    # ------------------------------------------------------------------

    async def upload_draft(
        self, file: UploadFile, project_id: int = None
    ) -> DraftDocument:
        """上传初稿文件（PDF/Word）

        1. 保存文件到 data/drafts/{draft_id}/original.{ext}
        2. 解析文件内容（PyMuPDF for PDF）
        3. 创建 DraftDocument 记录
        4. 创建第一个版本快照（snapshot_source='upload'）
        """
        # 提取扩展名
        filename = file.filename or "unknown"
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext not in ("pdf", "docx", "doc"):
            raise ValueError(f"不支持的文件类型: {ext}")

        file_type = "pdf" if ext == "pdf" else "docx"

        # 读取文件内容
        content_bytes = await file.read()

        # 先创建 DraftDocument 以获取 ID
        draft = DraftDocument(
            title=Path(filename).stem,
            file_type=file_type,
            parsed_content=None,
            content="",
            status="draft",
            project_id=project_id,
        )
        self.db.add(draft)
        self.db.flush()  # 分配 ID

        # 保存文件到 data/drafts/{draft_id}/
        draft_dir = self._draft_dir(draft.id)
        draft_dir.mkdir(parents=True, exist_ok=True)
        file_save_path = draft_dir / f"original.{ext}"
        file_save_path.write_bytes(content_bytes)

        draft.file_path = str(file_save_path)

        # 解析文件
        parsed_content = None
        text_content = ""
        if file_type == "pdf":
            parsed_content, text_content = self._parse_pdf(content_bytes)

        draft.parsed_content = parsed_content
        draft.content = text_content
        self.db.flush()

        # 创建初始版本快照
        self._create_snapshot(draft, source="upload")
        self.db.commit()
        self.db.refresh(draft)

        logger.info(f"DraftService.upload_draft: id={draft.id}, title={draft.title}")
        return draft

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_draft(self, draft_id: int) -> Optional[DraftDocument]:
        """获取初稿当前内容"""
        return self.db.query(DraftDocument).filter(DraftDocument.id == draft_id).first()

    def list_drafts(self, project_id: int = None) -> List[DraftDocument]:
        """列出所有初稿，可选按 project_id 过滤"""
        q = self.db.query(DraftDocument)
        if project_id is not None:
            q = q.filter(DraftDocument.project_id == project_id)
        return q.order_by(DraftDocument.updated_at.desc()).all()

    # ------------------------------------------------------------------
    # 更新内容（核心：先快照再覆盖）
    # ------------------------------------------------------------------

    def update_content(
        self, draft_id: int, new_content: str, source: str = "ai_complete"
    ) -> Optional[DraftDocument]:
        """更新内容（先快照再覆盖）

        1. 读取当前 DraftDocument.content
        2. 创建 DraftVersion 快照
        3. 覆盖 DraftDocument.content = new_content
        """
        draft = self.get_draft(draft_id)
        if draft is None:
            return None

        # 先快照当前内容
        self._create_snapshot(draft, source=source)

        # 再覆盖
        draft.content = new_content
        draft.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(draft)

        logger.info(f"DraftService.update_content: draft_id={draft_id}, source={source}")
        return draft

    # ------------------------------------------------------------------
    # 回滚（核心：先快照再回滚）
    # ------------------------------------------------------------------

    def rollback(self, draft_id: int, version_id: int) -> Optional[DraftDocument]:
        """回滚到指定版本

        1. 快照当前内容（snapshot_source='rollback'）
        2. 读取目标版本的内容
        3. 覆盖 DraftDocument.content = 目标内容
        """
        draft = self.get_draft(draft_id)
        if draft is None:
            return None

        target_version = self.get_version(version_id)
        if target_version is None or target_version.draft_id != draft_id:
            return None

        # 先快照当前内容
        self._create_snapshot(draft, source="rollback")

        # 再用目标版本覆盖
        draft.content = target_version.snapshot_content
        draft.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(draft)

        logger.info(
            f"DraftService.rollback: draft_id={draft_id}, version_id={version_id}"
        )
        return draft

    # ------------------------------------------------------------------
    # 版本管理
    # ------------------------------------------------------------------

    def list_versions(
        self, draft_id: int, limit: int = DEFAULT_MAX_VERSIONS
    ) -> List[DraftVersion]:
        """版本历史列表（按时间倒序）"""
        return (
            self.db.query(DraftVersion)
            .filter(DraftVersion.draft_id == draft_id)
            .order_by(DraftVersion.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_version(self, version_id: int) -> Optional[DraftVersion]:
        """获取某个版本的内容"""
        return (
            self.db.query(DraftVersion)
            .filter(DraftVersion.id == version_id)
            .first()
        )

    def get_diff(
        self, draft_id: int, version_id_1: int, version_id_2: int
    ) -> Dict:
        """两个版本的差异对比（用 difflib）"""
        v1 = self.get_version(version_id_1)
        v2 = self.get_version(version_id_2)

        if v1 is None or v2 is None:
            return {"error": "版本不存在"}
        if v1.draft_id != draft_id or v2.draft_id != draft_id:
            return {"error": "版本不属于该初稿"}

        text1_lines = (v1.snapshot_content or "").splitlines(keepends=True)
        text2_lines = (v2.snapshot_content or "").splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            text1_lines, text2_lines,
            fromfile=f"version_{version_id_1}",
            tofile=f"version_{version_id_2}",
            lineterm="",
        ))

        return {
            "version_id_1": version_id_1,
            "version_id_2": version_id_2,
            "diff": "".join(diff),
            "has_changes": len(diff) > 0,
        }

    # ------------------------------------------------------------------
    # 删除 / 清理
    # ------------------------------------------------------------------

    def delete_draft(self, draft_id: int) -> bool:
        """删除初稿及其所有版本"""
        draft = self.get_draft(draft_id)
        if draft is None:
            return False

        # 删除所有版本
        self.db.query(DraftVersion).filter(
            DraftVersion.draft_id == draft_id
        ).delete()

        # 删除文件目录
        draft_dir = self._draft_dir(draft_id)
        if draft_dir.exists():
            shutil.rmtree(draft_dir, ignore_errors=True)

        # 删除文档记录
        self.db.delete(draft)
        self.db.commit()

        logger.info(f"DraftService.delete_draft: id={draft_id}")
        return True

    def cleanup_old_versions(
        self, draft_id: int, max_versions: int = DEFAULT_MAX_VERSIONS
    ) -> int:
        """清理旧版本，保留最新的 max_versions 个"""
        versions = (
            self.db.query(DraftVersion)
            .filter(DraftVersion.draft_id == draft_id)
            .order_by(DraftVersion.created_at.desc())
            .all()
        )

        if len(versions) <= max_versions:
            return 0

        # 保留最新的 max_versions 个，删除其余
        to_delete = versions[max_versions:]
        for v in to_delete:
            self.db.delete(v)

        self.db.commit()
        deleted_count = len(to_delete)
        logger.info(
            f"DraftService.cleanup_old_versions: draft_id={draft_id}, "
            f"deleted={deleted_count}"
        )
        return deleted_count

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _create_snapshot(
        self, draft: DraftDocument, source: str
    ) -> DraftVersion:
        """创建版本快照（不 commit，由调用方决定）"""
        snapshot = DraftVersion(
            draft_id=draft.id,
            snapshot_content=draft.content or "",
            snapshot_source=source,
        )
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

    @staticmethod
    def _parse_pdf(content_bytes: bytes) -> tuple:
        """用 PyMuPDF 解析 PDF 文件

        Returns:
            (parsed_content: dict, text_content: str)
        """
        doc = fitz.open(stream=content_bytes, filetype="pdf")
        pages = []
        all_text = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            all_text.append(text)
            pages.append({
                "page_number": page_num + 1,
                "text": text,
            })

        doc.close()

        parsed_content = {
            "total_pages": len(pages),
            "pages": pages,
        }
        text_content = "\n".join(all_text)

        return parsed_content, text_content

    @staticmethod
    def _draft_dir(draft_id: int) -> Path:
        """初稿文件存储目录"""
        from app.config import settings
        return settings.DATA_DIR / "drafts" / str(draft_id)
