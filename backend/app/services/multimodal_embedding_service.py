"""
MultimodalEmbeddingService - 多模态向量编码服务
使用 BGE-VL 模型将图片和文本编码到同一向量空间
支持图文混合检索
"""
import os
from typing import List, Dict, Optional, Union
from pathlib import Path
import hashlib
from app.shared.logging import get_logger
logger = get_logger(__name__)

# 延迟导入，避免启动时加载大模型
_model = None
_tokenizer = None
_processor = None


class MultimodalEmbeddingService:
    """
    多模态 Embedding 服务
    - 支持图片和文本的向量编码
    - 使用 BGE-VL 模型（或 CLIP 作为备选）
    - 向量存储在 ChromaDB 中，通过 type 字段区分
    """
    
    def __init__(self, model_name: str = "BAAI/bge-visualized-base-en-v1.5"):
        """
        初始化服务
        
        Args:
            model_name: 模型名称，支持:
                - BAAI/bge-visualized-base-en-v1.5 (BGE-VL, 推荐)
                - openai/clip-vit-base-patch32 (CLIP, 备选)
        """
        self.model_name = model_name
        self.dimension = 768  # BGE-VL base 维度
        self._initialized = False
        
    def _ensure_initialized(self):
        """延迟初始化模型，首次使用时加载"""
        global _model, _tokenizer, _processor
        
        if self._initialized:
            return
            
        try:
            # 尝试使用 BGE-VL
            if "bge-visualized" in self.model_name.lower():
                self._init_bge_vl()
            else:
                # 备选：使用 CLIP
                self._init_clip()
                
            self._initialized = True
            logger.info(f"✅ 多模态 Embedding 模型已加载: {self.model_name}")
            
        except Exception as e:
            logger.error(f"❌ 多模态模型加载失败: {e}")
            raise
    
    def _init_bge_vl(self):
        """初始化 BGE-VL 模型"""
        global _model, _processor
        
        try:
            from FlagEmbedding.visual.modeling import Visualized_BGE
            
            # BGE-VL 模型路径（会自动下载）
            _model = Visualized_BGE(
                model_name_bge="BAAI/bge-base-en-v1.5",
                model_weight="./models/bge_visualized_base_en_v1.5",  # 本地缓存路径
            )
            self._use_fallback = False
            self.dimension = 768
            
        except ImportError:
            logger.warning("FlagEmbedding 未安装，尝试使用 CLIP")
            self._init_clip()
        except Exception as e:
            logger.warning(f"BGE-VL 加载失败: {e}，尝试使用 CLIP")
            self._init_clip()
    
    def _init_clip(self):
        """初始化 CLIP 模型（备选方案）"""
        global _model, _processor
        
        try:
            from transformers import CLIPProcessor, CLIPModel
            import torch
            
            model_name = "openai/clip-vit-base-patch32"
            _model = CLIPModel.from_pretrained(model_name)
            _processor = CLIPProcessor.from_pretrained(model_name)
            
            # 移到 GPU（如果可用）
            device = "cuda" if torch.cuda.is_available() else "cpu"
            _model = _model.to(device)
            _model.eval()
            
            self._use_fallback = False
            self._use_clip = True
            self.dimension = 512  # CLIP base 维度
            logger.info(f"✅ CLIP 模型已加载，device: {device}")
            
        except Exception as e:
            logger.error(f"CLIP 加载失败: {e}")
            self._use_fallback = True
    
    def encode_image(self, image_path: str) -> Optional[List[float]]:
        """
        编码图片为向量
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            向量列表，失败返回 None
        """
        self._ensure_initialized()
        
        if not os.path.exists(image_path):
            logger.warning(f"图片不存在: {image_path}")
            return None
            
        try:
            
            global _model, _processor
            
            if hasattr(self, '_use_clip') and self._use_clip:
                # 使用 CLIP
                from PIL import Image
                import torch
                
                image = Image.open(image_path).convert("RGB")
                inputs = _processor(images=image, return_tensors="pt")
                
                device = next(_model.parameters()).device
                inputs = {k: v.to(device) for k, v in inputs.items()}
                
                with torch.no_grad():
                    image_features = _model.get_image_features(**inputs)
                    # 归一化
                    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                    
                return image_features[0].cpu().numpy().tolist()
            else:
                # 使用 BGE-VL
                embedding = _model.encode(image=image_path)
                return embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
                
        except Exception as e:
            logger.error(f"图片编码失败 {image_path}: {e}")
            raise
    
    def encode_text(self, text: str) -> Optional[List[float]]:
        """
        编码文本为向量
        
        Args:
            text: 文本内容
            
        Returns:
            向量列表，失败返回 None
        """
        self._ensure_initialized()
        
        if not text or not text.strip():
            return None
            
        try:
            
            global _model, _processor
            
            if hasattr(self, '_use_clip') and self._use_clip:
                # 使用 CLIP
                import torch
                
                inputs = _processor(text=[text], return_tensors="pt", padding=True, truncation=True)
                
                device = next(_model.parameters()).device
                inputs = {k: v.to(device) for k, v in inputs.items()}
                
                with torch.no_grad():
                    text_features = _model.get_text_features(**inputs)
                    text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                    
                return text_features[0].cpu().numpy().tolist()
            else:
                # 使用 BGE-VL
                embedding = _model.encode(text=text)
                return embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
                
        except Exception as e:
            logger.error(f"文本编码失败: {e}")
            raise
        import hashlib
        import struct
        
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content
            
        # 生成多个 hash 来填充向量
        vectors = []
        for i in range(self.dimension // 8):
            h = hashlib.sha256(content_bytes + str(i).encode()).digest()
            # 将 hash 转换为浮点数
            for j in range(0, 32, 4):
                val = struct.unpack('f', h[j:j+4])[0]
                # 归一化到 [-1, 1]
                val = max(-1, min(1, val / 1e38))
                vectors.append(val)
                if len(vectors) >= self.dimension:
                    break
            if len(vectors) >= self.dimension:
                break
                
        return vectors[:self.dimension]
    
    def compute_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算两个向量的余弦相似度"""
        import math
        
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        return dot / (norm1 * norm2)


# 单例
_service_instance = None

def get_multimodal_embedding_service() -> MultimodalEmbeddingService:
    """获取多模态 Embedding 服务单例"""
    global _service_instance
    if _service_instance is None:
        _service_instance = MultimodalEmbeddingService()
    return _service_instance

