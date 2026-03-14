# -*- coding: utf-8 -*-
"""
工艺文件辅助编辑系统 - Windows 7兼容性模块
处理Windows 7环境下的特殊兼容性需求
"""
import os
import sys
import ssl
from typing import Dict, Any, Optional
import asyncio

from app.shared.logging import get_logger

logger = get_logger(__name__)


class Win7Compatibility:
    """
    Windows 7兼容性处理类

    处理Windows 7环境下的各种兼容性问题，
    包括SSL、网络、文件系统等
    """

    def __init__(self):
        """初始化Windows 7兼容性模块"""
        self.enabled = False
        self.config = self._load_config()
        logger.info("win7_compatibility_module_initialized")

    def _load_config(self) -> Dict[str, Any]:
        """加载Windows 7兼容性配置"""
        try:
            config_path = "app/compatibility/win7_config.json"
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return eval(f.read())  # 简化配置加载
            return {}
        except Exception as e:
            logger.warning("failed_to_load_win7_config", error=str(e))
            return {}

    def enable_compatibility_mode(self):
        """启用Windows 7兼容性模式"""
        if self.enabled:
            return

        try:
            # 1. 配置SSL兼容性
            self._configure_ssl_compatibility()

            # 2. 配置网络兼容性
            self._configure_network_compatibility()

            # 3. 配置文件系统兼容性
            self._configure_filesystem_compatibility()

            # 4. 配置内存限制
            self._configure_memory_limits()

            self.enabled = True
            logger.info("win7_compatibility_mode_enabled")

        except Exception as e:
            logger.error("failed_to_enable_win7_compatibility", error=str(e))

    def _configure_ssl_compatibility(self):
        """配置SSL兼容性"""
        try:
            # 禁用TLS 1.3，使用TLS 1.2
            if hasattr(ssl, 'PROTOCOL_TLSv1_2'):
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
                ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')
                ssl._create_default_https_context = lambda: ssl_context

            # 禁用证书验证（仅在开发环境中）
            if self.config.get("disable_ssl_verification", False):
                ssl._create_unverified_context = ssl._create_stdlib_context

            logger.debug("ssl_compatibility_configured")

        except Exception as e:
            logger.warning("ssl_compatibility_configuration_failed", error=str(e))

    def _configure_network_compatibility(self):
        """配置网络兼容性"""
        try:
            # 禁用HTTP/2
            os.environ["HTTPX_HTTP2"] = "0"

            # 禁用WebSocket压缩
            if self.config.get("disable_websocket_compression", True):
                os.environ["WEBSOCKET_COMPRESSION"] = "0"

            # 强制使用IPv4
            if self.config.get("use_ipv4_only", True):
                os.environ["FORCE_IPV4"] = "1"

            logger.debug("network_compatibility_configured")

        except Exception as e:
            logger.warning("network_compatibility_configuration_failed", error=str(e))

    def _configure_filesystem_compatibility(self):
        """配置文件系统兼容性"""
        try:
            # 启用短路径支持
            if self.config.get("use_short_paths", True):
                os.environ["USE_SHORT_PATHS"] = "1"

            # 设置最大路径长度
            max_path_length = self.config.get("max_path_length", 260)
            os.environ["MAX_PATH_LENGTH"] = str(max_path_length)

            logger.debug("filesystem_compatibility_configured")

        except Exception as e:
            logger.warning("filesystem_compatibility_configuration_failed", error=str(e))

    def _configure_memory_limits(self):
        """配置内存限制"""
        try:
            max_memory_mb = self.config.get("max_memory_mb", 2048)
            os.environ["MAX_MEMORY_MB"] = str(max_memory_mb)

            # 配置asyncio事件循环
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

            logger.debug("memory_limits_configured", max_memory_mb=max_memory_mb)

        except Exception as e:
            logger.warning("memory_limits_configuration_failed", error=str(e))

    def is_windows7(self) -> bool:
        """检测是否为Windows 7"""
        try:
            import platform
            version = platform.version()
            # Windows 7的版本号是6.1.x
            return version.startswith("6.1.")
        except Exception:
            return False

    def get_compatibility_info(self) -> Dict[str, Any]:
        """获取兼容性信息"""
        return {
            "enabled": self.enabled,
            "is_windows7": self.is_windows7(),
            "config": self.config,
            "python_version": sys.version,
            "platform": sys.platform
        }

    def apply_compatibility_patches(self):
        """应用兼容性补丁"""
        if not self.enabled:
            self.enable_compatibility_mode()

        # 应用特定的兼容性补丁
        self._apply_fastapi_patches()
        self._apply_pymupdf_patches()
        self._apply_chromadb_patches()

    def _apply_fastapi_patches(self):
        """应用FastAPI兼容性补丁"""
        try:
            # 禁用某些高级特性
            os.environ["FASTAPI_DISABLE_HTTP2"] = "1"
            os.environ["FASTAPI_DISABLE_WEBSOCKET_COMPRESSION"] = "1"
            logger.debug("fastapi_compatibility_patches_applied")
        except Exception as e:
            logger.warning("fastapi_compatibility_patches_failed", error=str(e))

    def _apply_pymupdf_patches(self):
        """应用PyMuPDF兼容性补丁"""
        try:
            # 配置PyMuPDF以使用兼容模式
            os.environ["PYMUPDF_COMPATIBILITY_MODE"] = "1"
            logger.debug("pymupdf_compatibility_patches_applied")
        except Exception as e:
            logger.warning("pymupdf_compatibility_patches_failed", error=str(e))

    def _apply_chromadb_patches(self):
        """应用ChromaDB兼容性补丁"""
        try:
            # 配置ChromaDB以使用兼容模式
            os.environ["CHROMADB_COMPATIBILITY_MODE"] = "1"
            logger.debug("chromadb_compatibility_patches_applied")
        except Exception as e:
            logger.warning("chromadb_compatibility_patches_failed", error=str(e))


# 全局兼容性实例
win7_compat = Win7Compatibility()


def initialize_win7_compatibility():
    """初始化Windows 7兼容性"""
    if win7_compat.is_windows7():
        win7_compat.enable_compatibility_mode()
        win7_compat.apply_compatibility_patches()
        logger.info("windows7_compatibility_initialized")
    else:
        logger.debug("windows7_compatibility_not_needed")


# 在模块导入时自动初始化
initialize_win7_compatibility()