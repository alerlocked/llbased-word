"""
ProfileService - 画像管理服务

管理用户画像（Markdown 格式），用于 LLM 上下文注入
"""
from typing import List, Optional
from pathlib import Path
import re
from app.utils.logger import logger


class ProfileService:
    """画像管理服务
    
    职责：
    - 加载 Markdown 格式的用户画像
    - 提供画像列表查询
    - Token 估算
    """
    
    def __init__(self, profile_dir: str):
        """初始化画像服务
        
        Args:
            profile_dir: 画像目录 (.project-meta/profiles/)
        """
        self.profile_dir = Path(profile_dir)
        
        if not self.profile_dir.exists():
            logger.warning(f"[画像服务] 画像目录不存在: {self.profile_dir}")
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[画像服务] 已创建画像目录: {self.profile_dir}")
    
    def load_profile(self, profile_name: str = "default") -> str:
        """加载画像内容
        
        查找顺序：
        1. {profile_dir}/{profile_name}.md
        2. {profile_dir}/default.md
        3. 返回空字符串（无画像）
        
        Args:
            profile_name: 画像名称（不含 .md 后缀）
            
        Returns:
            画像文本内容
        """
        # 尝试加载指定画像
        profile_path = self.profile_dir / f"{profile_name}.md"
        
        if profile_path.exists():
            try:
                with open(profile_path, "r", encoding="utf-8") as f:
                    content = f.read()
                logger.info(f"[画像服务] 加载画像成功: {profile_name}")
                return content
            except Exception as e:
                logger.error(f"[画像服务] 加载画像失败: {profile_path}, {e}")
        
        # 回退到默认画像
        if profile_name != "default":
            default_path = self.profile_dir / "default.md"
            if default_path.exists():
                try:
                    with open(default_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    logger.info(f"[画像服务] 画像 {profile_name} 不存在，使用默认画像")
                    return content
                except Exception as e:
                    logger.error(f"[画像服务] 加载默认画像失败: {e}")
        
        # 无画像
        logger.warning(f"[画像服务] 无可用画像")
        return ""
    
    def get_available_profiles(self) -> List[str]:
        """获取可用的画像列表
        
        Returns:
            画像名称列表（不含 .md 后缀）
        """
        if not self.profile_dir.exists():
            return []
        
        profiles = []
        for file_path in self.profile_dir.glob("*.md"):
            profiles.append(file_path.stem)
        
        logger.info(f"[画像服务] 可用画像: {profiles}")
        return profiles
    
    def estimate_tokens(self, content: str) -> int:
        """估算文本 token 数量
        
        中文按 1.5 tokens/字符，英文按 0.25 tokens/字符
        
        Args:
            content: 文本内容
            
        Returns:
            估算的 token 数量
        """
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
        other_chars = len(content) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars * 0.25)
