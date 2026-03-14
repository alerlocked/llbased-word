# -*- coding: utf-8 -*-
"""
工艺文件辅助编辑系统 - 麒麟系统兼容性模块
处理麒麟操作系统下的特殊兼容性需求
"""
import os
import sys
import platform
from typing import Dict, Any, Optional
import asyncio

from app.shared.logging import get_logger

logger = get_logger(__name__)


class KylinCompatibility:
    """
    麒麟系统兼容性处理类

    处理麒麟操作系统下的各种兼容性问题，
    包括国产CPU架构、桌面环境集成、网络安全合规等
    """

    def __init__(self):
        """初始化麒麟系统兼容性模块"""
        self.enabled = False
        self.config = self._load_config()
        self.cpu_architecture = self._detect_cpu_architecture()
        logger.info("kylin_compatibility_module_initialized")

    def _load_config(self) -> Dict[str, Any]:
        """加载麒麟系统兼容性配置"""
        try:
            config_path = "app/compatibility/kylin_config.json"
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return eval(f.read())  # 简化配置加载
            return {}
        except Exception as e:
            logger.warning("failed_to_load_kylin_config", error=str(e))
            return {}

    def _detect_cpu_architecture(self) -> str:
        """检测CPU架构"""
        try:
            arch = platform.machine().lower()
            if 'loongarch' in arch:
                return 'loongarch64'
            elif 'aarch64' in arch or 'arm64' in arch:
                return 'arm64'
            else:
                return 'x86_64'
        except Exception as e:
            logger.warning("cpu_architecture_detection_failed", error=str(e))
            return 'x86_64'

    def enable_compatibility_mode(self):
        """启用麒麟系统兼容性模式"""
        if self.enabled:
            return

        try:
            # 1. 配置国产CPU架构优化
            self._configure_cpu_optimization()

            # 2. 配置桌面环境集成
            self._configure_desktop_integration()

            # 3. 配置网络安全合规
            self._configure_security_compliance()

            # 4. 配置性能优化
            self._configure_performance_optimization()

            self.enabled = True
            logger.info("kylin_compatibility_mode_enabled", cpu_arch=self.cpu_architecture)

        except Exception as e:
            logger.error("failed_to_enable_kylin_compatibility", error=str(e))

    def _configure_cpu_optimization(self):
        """配置CPU架构优化"""
        try:
            # 根据CPU架构设置优化参数
            if self.cpu_architecture == 'loongarch64':
                # 龙芯架构优化
                os.environ["LOONGARCH_OPTIMIZATION"] = "1"
                os.environ["USE_LOONGSON_LIBS"] = "1"
            elif self.cpu_architecture == 'arm64':
                # ARM64架构优化
                os.environ["ARM64_OPTIMIZATION"] = "1"
                os.environ["USE_NEON_INSTRUCTIONS"] = "1"
            else:
                # x86_64架构优化
                os.environ["X86_64_OPTIMIZATION"] = "1"

            logger.debug("cpu_optimization_configured", architecture=self.cpu_architecture)

        except Exception as e:
            logger.warning("cpu_optimization_configuration_failed", error=str(e))

    def _configure_desktop_integration(self):
        """配置桌面环境集成"""
        try:
            # 启用系统托盘支持
            if self.config.get("enable_system_tray", True):
                os.environ["ENABLE_SYSTEM_TRAY"] = "1"

            # 启用麒麟通知支持
            if self.config.get("support_kylin_notifications", True):
                os.environ["KYLIN_NOTIFICATIONS"] = "1"

            # 集成麒麟桌面环境
            os.environ["DESKTOP_ENVIRONMENT"] = "kylin"

            logger.debug("desktop_integration_configured")

        except Exception as e:
            logger.warning("desktop_integration_configuration_failed", error=str(e))

    def _configure_security_compliance(self):
        """配置网络安全合规"""
        try:
            # 使用国内CDN
            if self.config.get("use_domestic_cdn", True):
                os.environ["USE_DOMESTIC_CDN"] = "1"
                os.environ["PYPI_MIRROR"] = "https://pypi.tuna.tsinghua.edu.cn/simple"
                os.environ["NPM_REGISTRY"] = "https://registry.npmmirror.com"

            # 合规性设置
            os.environ["CHINA_COMPLIANCE"] = "1"

            logger.debug("security_compliance_configured")

        except Exception as e:
            logger.warning("security_compliance_configuration_failed", error=str(e))

    def _configure_performance_optimization(self):
        """配置性能优化"""
        try:
            # 设置内存限制
            max_memory_mb = self.config.get("max_memory_mb", 4096)
            os.environ["MAX_MEMORY_MB"] = str(max_memory_mb)

            # 启用性能监控
            if self.config.get("enable_performance_monitoring", True):
                os.environ["PERFORMANCE_MONITORING"] = "1"

            # 配置asyncio事件循环
            if sys.platform.startswith("linux"):
                asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

            logger.debug("performance_optimization_configured", max_memory_mb=max_memory_mb)

        except Exception as e:
            logger.warning("performance_optimization_configuration_failed", error=str(e))

    def is_kylin_system(self) -> bool:
        """检测是否为麒麟系统"""
        try:
            # 检查麒麟系统标识文件
            if os.path.exists("/etc/kylin-release"):
                return True

            # 检查系统信息
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release", "r", encoding="utf-8") as f:
                    content = f.read()
                    if "Kylin" in content or "kylin" in content:
                        return True

            return False
        except Exception:
            return False

    def get_compatibility_info(self) -> Dict[str, Any]:
        """获取兼容性信息"""
        return {
            "enabled": self.enabled,
            "is_kylin_system": self.is_kylin_system(),
            "cpu_architecture": self.cpu_architecture,
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
            # 配置国产化适配
            os.environ["FASTAPI_KYLIN_MODE"] = "1"
            logger.debug("fastapi_compatibility_patches_applied")
        except Exception as e:
            logger.warning("fastapi_compatibility_patches_failed", error=str(e))

    def _apply_pymupdf_patches(self):
        """应用PyMuPDF兼容性补丁"""
        try:
            # 配置PyMuPDF以使用国产化模式
            os.environ["PYMUPDF_KYLIN_MODE"] = "1"
            logger.debug("pymupdf_compatibility_patches_applied")
        except Exception as e:
            logger.warning("pymupdf_compatibility_patches_failed", error=str(e))

    def _apply_chromadb_patches(self):
        """应用ChromaDB兼容性补丁"""
        try:
            # 配置ChromaDB以使用国产化模式
            os.environ["CHROMADB_KYLIN_MODE"] = "1"
            logger.debug("chromadb_compatibility_patches_applied")
        except Exception as e:
            logger.warning("chromadb_compatibility_patches_failed", error=str(e))


# 全局兼容性实例
kylin_compat = KylinCompatibility()


def initialize_kylin_compatibility():
    """初始化麒麟系统兼容性"""
    if kylin_compat.is_kylin_system():
        kylin_compat.enable_compatibility_mode()
        kylin_compat.apply_compatibility_patches()
        logger.info("kylin_compatibility_initialized", cpu_arch=kylin_compat.cpu_architecture)
    else:
        logger.debug("kylin_compatibility_not_needed")


# 在模块导入时自动初始化
initialize_kylin_compatibility()