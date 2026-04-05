"""
Agent 通信机制

实现 Writing Agent 和 Review Agent 之间的文件通信
"""
import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


# ========================================
# 目录结构
# ========================================

class AgentPaths:
    """Agent 通信路径配置"""
    
    # 基础路径
    OUTPUT_DIR = ".agent-outputs"
    FEEDBACK_DIR = ".agent-feedback"
    ARCHIVE_DIR = ".agent-archive"
    
    @classmethod
    def get_output_dir(cls, session_id: str, base_path: Optional[Path] = None) -> Path:
        """获取输出目录"""
        base = base_path or Path.cwd()
        return base / cls.OUTPUT_DIR / session_id
    
    @classmethod
    def get_feedback_dir(cls, base_path: Optional[Path] = None) -> Path:
        """获取反馈目录"""
        base = base_path or Path.cwd()
        return base / cls.FEEDBACK_DIR
    
    @classmethod
    def get_archive_dir(cls, base_path: Optional[Path] = None) -> Path:
        """获取归档目录"""
        base = base_path or Path.cwd()
        return base / cls.ARCHIVE_DIR


# ========================================
# 数据模型
# ========================================

@dataclass
class FeedbackData:
    """反馈数据"""
    review_id: str
    source_file: str
    score: int
    issues: List[Dict[str, Any]]
    suggestions: List[Dict[str, Any]]
    timestamp: str
    passed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeedbackData":
        return cls(
            review_id=data.get("review_id", str(uuid.uuid4())),
            source_file=data.get("source_file", ""),
            score=data.get("score", 0),
            issues=data.get("issues", []),
            suggestions=data.get("suggestions", []),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            passed=data.get("passed", False)
        )


# ========================================
# 输出文件管理
# ========================================

class AgentOutputWriter:
    """
    Agent 输出文件管理
    
    Writing Agent 使用此类写入输出文件
    Review Agent 使用此类读取输出文件
    """
    
    def __init__(self, session_id: str, base_path: Optional[Path] = None):
        """
        初始化
        
        Args:
            session_id: 会话 ID
            base_path: 基础路径
        """
        self.session_id = session_id
        self.base_path = base_path or Path.cwd()
        self.output_dir = AgentPaths.get_output_dir(session_id, self.base_path)
        
        # 确保目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def write_output(self, content: str, filename: Optional[str] = None) -> Path:
        """
        写入输出文件
        
        Args:
            content: 文档内容
            filename: 文件名（可选，自动生成时间戳）
            
        Returns:
            文件路径
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"output_{timestamp}.md"
        
        file_path = self.output_dir / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(
            "agent_output_written",
            session_id=self.session_id,
            file=str(file_path)
        )
        
        return file_path
    
    def get_latest_output(self) -> Optional[str]:
        """
        获取最新的输出文件内容
        
        Returns:
            文件内容，如果没有文件返回 None
        """
        output_files = sorted(
            self.output_dir.glob("output_*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        if not output_files:
            return None
        
        latest_file = output_files[0]
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info(
            "agent_output_read",
            session_id=self.session_id,
            file=str(latest_file)
        )
        
        return content
    
    def list_outputs(self) -> List[Path]:
        """
        列出所有输出文件
        
        Returns:
            文件路径列表
        """
        return sorted(
            self.output_dir.glob("output_*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )


# ========================================
# 反馈文件管理
# ========================================

class AgentFeedbackManager:
    """
    Agent 反馈文件管理
    
    Review Agent 使用此类写入反馈文件
    Writing Agent 使用此类读取反馈文件
    """
    
    def __init__(self, base_path: Optional[Path] = None):
        """
        初始化
        
        Args:
            base_path: 基础路径
        """
        self.base_path = base_path or Path.cwd()
        self.feedback_dir = AgentPaths.get_feedback_dir(self.base_path)
        
        # 确保目录存在
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
    
    def write_feedback(self, feedback: FeedbackData) -> Path:
        """
        写入反馈文件
        
        Args:
            feedback: 反馈数据
            
        Returns:
            文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"review_feedback_{timestamp}.json"
        
        file_path = self.feedback_dir / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(feedback.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(
            "review_feedback_written",
            review_id=feedback.review_id,
            score=feedback.score,
            file=str(file_path)
        )
        
        return file_path
    
    def get_latest_feedback(self) -> Optional[FeedbackData]:
        """
        获取最新的反馈文件
        
        Returns:
            反馈数据，如果没有文件返回 None
        """
        feedback_files = sorted(
            self.feedback_dir.glob("review_feedback_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        if not feedback_files:
            return None
        
        latest_file = feedback_files[0]
        
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(
            "review_feedback_read",
            file=str(latest_file)
        )
        
        return FeedbackData.from_dict(data)
    
    def clear_feedback(self, feedback_file: Path):
        """
        清除反馈文件（Writing Agent 处理后调用）
        
        Args:
            feedback_file: 反馈文件路径
        """
        if feedback_file.exists():
            feedback_file.unlink()
            logger.info("review_feedback_cleared", file=str(feedback_file))
    
    def list_feedbacks(self) -> List[Path]:
        """
        列出所有反馈文件
        
        Returns:
            文件路径列表
        """
        return sorted(
            self.feedback_dir.glob("review_feedback_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
    
    def has_pending_feedback(self) -> bool:
        """
        检查是否有待处理的反馈
        
        Returns:
            是否有待处理的反馈
        """
        return len(list(self.feedback_dir.glob("review_feedback_*.json"))) > 0


# ========================================
# 清理工具
# ========================================

class AgentCleanupManager:
    """
    Agent 文件清理工具
    
    - 清理超过 7 天的输出文件
    - 清理超过 24 小时未处理的反馈文件
    - 归档通过的文件
    """
    
    def __init__(self, base_path: Optional[Path] = None):
        """
        初始化
        
        Args:
            base_path: 基础路径
        """
        self.base_path = base_path or Path.cwd()
        self.output_dir = Path(self.base_path) / AgentPaths.OUTPUT_DIR
        self.feedback_dir = Path(self.base_path) / AgentPaths.FEEDBACK_DIR
        self.archive_dir = Path(self.base_path) / AgentPaths.ARCHIVE_DIR
        
        # 确保归档目录存在
        self.archive_dir.mkdir(parents=True, exist_ok=True)
    
    def cleanup_old_outputs(self, days: int = 7) -> int:
        """
        清理旧的输出文件
        
        Args:
            days: 保留天数
            
        Returns:
            清理的文件数量
        """
        import time
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        
        cleaned = 0
        
        # 遍历所有 session 目录
        if not self.output_dir.exists():
            return 0
        
        for session_dir in self.output_dir.iterdir():
            if not session_dir.is_dir():
                continue
            
            for output_file in session_dir.glob("output_*.md"):
                if output_file.stat().st_mtime < cutoff_time:
                    output_file.unlink()
                    cleaned += 1
        
        if cleaned > 0:
            logger.info("cleaned_old_outputs", count=cleaned, days=days)
        
        return cleaned
    
    def cleanup_expired_feedbacks(self, hours: int = 24) -> int:
        """
        清理过期的反馈文件
        
        Args:
            hours: 保留小时数
            
        Returns:
            清理的文件数量
        """
        import time
        cutoff_time = time.time() - (hours * 60 * 60)
        
        cleaned = 0
        
        if not self.feedback_dir.exists():
            return 0
        
        for feedback_file in self.feedback_dir.glob("review_feedback_*.json"):
            if feedback_file.stat().st_mtime < cutoff_time:
                # 标记为已过期（可选：删除或移动到过期目录）
                feedback_file.unlink()
                cleaned += 1
        
        if cleaned > 0:
            logger.info("cleaned_expired_feedbacks", count=cleaned, hours=hours)
        
        return cleaned
    
    def archive_passed_files(self, session_id: str) -> int:
        """
        归档通过的文件
        
        Args:
            session_id: 会话 ID
            
        Returns:
            归档的文件数量
        """
        import shutil
        
        session_output_dir = AgentPaths.get_output_dir(session_id, self.base_path)
        
        if not session_output_dir.exists():
            return 0
        
        archived = 0
        
        # 创建归档目录
        archive_session_dir = self.archive_dir / session_id
        archive_session_dir.mkdir(parents=True, exist_ok=True)
        
        # 移动所有输出文件到归档目录
        for output_file in session_output_dir.glob("output_*.md"):
            archive_path = archive_session_dir / output_file.name
            shutil.move(str(output_file), str(archive_path))
            archived += 1
        
        if archived > 0:
            logger.info("archived_passed_files", session_id=session_id, count=archived)
        
        return archived
