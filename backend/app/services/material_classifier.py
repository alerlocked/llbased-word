"""LLM-based model/specialty classifier for uploaded materials.

Infers product model + process specialty from filename at upload time, so the
Material row gets model/specialty dimensions for retrieval filtering (cleanup-
and-dimensions 节点3). User confirms/edits via frontend (节点5).

Fail-soft: any LLM/parse error returns {None, "general"} so upload never blocks.
"""
import json
import re
from typing import Dict, Optional

from app.shared.logging import get_logger

logger = get_logger(__name__)

VALID_SPECIALTIES = [
    "assembly", "welding", "coating", "machining",
    "inspection", "heat_treatment", "general",
]


async def infer_model_specialty(filename: str) -> Dict[str, Optional[str]]:
    """Infer {model, specialty} from a craft-document filename via LLM.

    Returns {"model": str|None, "specialty": str}. specialty is always one of
    VALID_SPECIALTIES (defaults to "general" on any failure).
    """
    from app.services.llm_service import llm_service

    prompt = (
        "从工艺文件名推断【产品型号】和【工艺专业】。\n"
        f"文件名: {filename}\n"
        "工艺专业必须是下列之一: assembly(装配)/welding(焊接)/coating(涂覆)/"
        "machining(机加)/inspection(检验)/heat_treatment(热处理)/general(通用)。\n"
        "型号提取产品代号/名称（如「XX-1 型导弹」→ model=XX-1）；提取不出则 null。\n"
        "只输出 JSON，不要解释: {\"model\": \"型号或null\", \"specialty\": \"枚举值\"}"
    )

    try:
        result = await llm_service.generate_with_messages(
            messages=[{"role": "user", "content": prompt}],
            tier="simple",
            temperature=0.1,
            max_tokens=200,
        )
        if result.get("status") != "success":
            logger.info("infer_no_success", file_name=filename, status=result.get("status"))
            return {"model": None, "specialty": "general"}

        content = result.get("content", "").strip()
        match = re.search(r"\{[^}]+\}", content)
        if not match:
            return {"model": None, "specialty": "general"}

        data = json.loads(match.group())
        specialty = data.get("specialty", "general")
        if specialty not in VALID_SPECIALTIES:
            specialty = "general"
        model = data.get("model")
        if model in (None, "", "null", "None"):
            model = None
        logger.info("infer_ok", file_name=filename, model=model, specialty=specialty)
        return {"model": model, "specialty": specialty}
    except Exception as e:
        logger.warning("infer_failed", file_name=filename, error=str(e))
        return {"model": None, "specialty": "general"}
