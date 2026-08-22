"""
DocumentProfileLearner - Extract user profile from parsed documents.

Extracts triple-structured knowledge (subject, relation, object) from
process documents, ready for direct migration to knowledge graphs.
"""
import re
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from collections import Counter
from datetime import datetime

from app.shared.logging import get_logger

logger = get_logger(__name__)

STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你",
    "会", "着", "没有", "看", "好", "自己", "这", "他", "她", "它",
    "与", "及", "或", "等", "为", "中", "对", "其", "之", "从",
    "以", "可", "能", "将", "把", "被", "让", "使", "由", "按",
    "应", "需", "须", "根据", "按照", "应按", "不得", "严禁",
    "应按", "一般", "通常", "适当", "相应", "符合", "满足",
}

# Generic subject values that carry no domain-specific meaning
GENERIC_SUBJECTS = {"工艺", "工序", "要求", "操作", "步骤", "方法", "过程"}

# Relations that indicate high-value process knowledge
HIGH_VALUE_RELATIONS = {"温度", "力矩", "压力", "时间", "速度", "公差", "硬度", "标准", "下一步"}

# Quantity specs — "温度控制在800-850°C" / "力矩为45±5 N·m"
# (pattern, relation). Reused by _extract_triples and _extract_triples_from_substeps.
QTY_PATTERNS: List[Tuple[str, str]] = [
    (r"([一-鿿]{0,6})(?:温度|温度控制)(?:为|在|应[为在])?((?:\d+(?:\.\d+)?(?:[-–]\d+(?:\.\d+)?)?(?:±\d+(?:\.\d+)?)?)\s*(?:°C|度|℃))", "温度"),
    (r"([一-鿿]{0,6})(?:力矩|扭矩)(?:为|是|应[为在])?((?:\d+(?:\.\d+)?(?:[-–]\d+(?:\.\d+)?)?(?:±\d+(?:\.\d+)?)?)\s*(?:N·m|Nm|N\.m|kgf))", "力矩"),
    (r"([一-鿿]{0,6})(?:压力)(?:为|在|应[为在])?((?:\d+(?:\.\d+)?(?:[-–]\d+(?:\.\d+)?)?(?:±\d+(?:\.\d+)?)?)\s*(?:MPa|Pa|kPa|bar))", "压力"),
    (r"([一-鿿]{0,6})(?:时间|保温时间|保压时间)(?:为|是|不少于)?((?:\d+(?:\.\d+)?(?:[-–]\d+(?:\.\d+)?)?(?:±\d+(?:\.\d+)?)?)\s*(?:小时|min|s|秒|分钟))", "时间"),
    (r"([一-鿿]{0,6})(?:速度|进给速度)(?:为|是|应[为在])?((?:\d+(?:\.\d+)?(?:[-–]\d+(?:\.\d+)?)?(?:±\d+(?:\.\d+)?)?)\s*(?:mm/min|cm/min|m/min|r/min|rpm))", "速度"),
    (r"([一-鿿]{0,6})(?:间隙|公差|精度)(?:为|是|应[为在])?((?:\d+(?:\.\d+)?(?:[-–]\d+(?:\.\d+)?)?(?:±\d+(?:\.\d+)?)?)\s*mm)", "公差"),
    (r"([一-鿿]{0,6})(?:硬度)(?:为|应[为在达到])?((?:\d+(?:\.\d+)?(?:[-–]\d+(?:\.\d+)?)?(?:±\d+(?:\.\d+)?)?)\s*(?:HRC|HB|HV|HRB))", "硬度"),
]

# Spec patterns — element specs (螺栓/密封圈/焊条/工装代号) used as the subject
# of a parameter triple, one layer above the raw parameter value.
SPEC_PATTERNS: List[str] = [
    r"M\d+\S*螺[栓钉柱]",      # M5×8 螺栓 / M6螺钉 / M4螺柱 (加"柱")
    r"螺[栓钉柱]\s*M\d+",       # 反序: "螺柱 M5 8" 表述
    r"M\d+[-×xX]\d+",           # M5×8 螺纹规格(不带螺字也认)
    r"GB/T\s*\d+[—-]\d+",     # GB/T68-2000 标准件
    r"密封圈\s*\d",            # 密封圈2
    r"O[型]?圈",               # O型圈
    r"焊[条丝]",               # 焊条/焊丝
    r"涂[料漆]",               # 涂料/漆
    r"W\d+电缆",              # W17电缆
    r"楔环\s*\d",              # 楔环1
    r"T2D\d+",                 # 工装代号 T2D30034
]


class DocumentProfileLearner:
    """Extract profile features and triple-structured knowledge from documents."""

    async def learn_from_content(
        self,
        content: str,
        domain: str = "assembly",
        document_id: Optional[str] = None,
        skip_llm_validate: bool = False,
        assembly_steps: Optional[Dict[int, Dict[str, Any]]] = None,
        skeleton_steps: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Extract profile features including triples from document text.

        assembly_steps / skeleton_steps: optional G25a/G19a structured extract.
        When assembly_steps is provided (装配工艺卡片), substep-derived triples
        are merged — each carrying process = skeleton 真工序名 (G19a), NOT the
        G25a step "name" (which is a 工种 like 钳/机). Empty → current path.
        """
        features: Dict[str, Any] = {
            "domain": domain,
            "extracted_at": datetime.now().isoformat(),
        }

        if document_id:
            features["source_document_id"] = document_id

        # 1. Extract triples (core knowledge structure) + LLM 校验（节点2，可跳过）
        _triples = self._extract_triples(content)
        # G25a 装配文档：合并 substeps 提的 triples（带真工序名 process）
        if assembly_steps:
            _triples.extend(
                self._extract_triples_from_substeps(assembly_steps, skeleton_steps or [])
            )
        if not skip_llm_validate:
            _triples = await self._llm_validate_triples(_triples)
        # source-visibility: tag every triple with its origin material. Profile
        # entries are cross-material shared experience (user decision); the
        # tag is for provenance/management only, never a retrieval filter.
        if document_id:
            for t in _triples:
                t.setdefault("source_doc", document_id)
        features["triples"] = _triples

        # 2. Extract term frequency (supplementary)
        features["frequent_terms"] = self._extract_terms(content)

        # 3. Extract style indicators
        style = self._extract_style(content)
        features.update(style)

        # 4. Generate summary
        features["ai_generated_summary"] = self._generate_summary(
            content, domain, len(features["triples"])
        )

        logger.info(
            "document_profile_learned",
            domain=domain,
            triples=len(features["triples"]),
            terms=len(features["frequent_terms"]),
        )
        return features

    async def _llm_validate_triples(
        self, triples: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """LLM batch-validate triples, drop nonsensical ones (节点2).

        Fail-soft: on any error return all triples (don't block learning)."""
        if not triples:
            return triples
        from app.services.llm_service import llm_service
        triples_text = "\n".join(
            f"{i}. {t['s']} → {t['r']}: {t['o']}"
            for i, t in enumerate(triples, 1)
        )
        prompt = (
            "判断以下从工艺文档抽取的知识三元组是否合理（subject 与 object 语义通顺、数值合理）。\n"
            f"{triples_text}\n"
            "输出合理的序号（从1开始），逗号分隔。只输出序号。"
        )
        try:
            result = await llm_service.generate_with_messages(
                messages=[{"role": "user", "content": prompt}],
                tier="simple", temperature=0.1, max_tokens=200,
            )
            if result.get("status") != "success":
                return triples
            import re as _re
            nums = {int(x) for x in _re.findall(r"\d+", result.get("content", ""))}
            if not nums:
                return triples
            validated = [t for i, t in enumerate(triples, 1) if i in nums]
            logger.info("triples_llm_validated", total=len(triples), kept=len(validated))
            return validated
        except Exception as e:
            logger.warning("triples_llm_validate_failed", error=str(e))
            return triples

    def _extract_triples(self, content: str) -> List[Dict[str, str]]:
        """
        Extract (subject, relation, object) triples from process documents.

        Uses rule-based patterns common in Chinese process documentation:
        - "XX温度控制在YY" → (XX, 温度, YY)
        - "使用XX拧紧" → (当前工序, 使用, XX)
        - "XX力矩为YY" → (XX, 力矩, YY)
        - "按XX标准执行" → (检验, 标准, XX)
        """
        triples: List[Dict[str, str]] = []
        seen: set = set()

        def _add(s: str, r: str, o: str, process: str = None) -> None:
            if not s or not o:
                return  # current_section may be None (no generic fallback)
            key = f"{s}|{r}|{o}"
            if key not in seen and len(s) >= 2 and len(o) >= 2:
                seen.add(key)
                triples.append({"s": s, "r": r, "o": o, "process": process})

        # Pattern 1: quantity specs — reuse module-level QTY_PATTERNS / SPEC_PATTERNS
        self._content_cached = content
        headers = self._collect_headers(content)
        current_section = self._guess_current_section(content)
        for pattern, relation in QTY_PATTERNS:
            for match in re.finditer(pattern, content):
                # subject 优先同句规格，其次 qty 主体，最后 current_section
                subject = self._find_spec(content, match.start()) or (match.group(1) or current_section)
                _add(subject, relation, match.group(2), process=self._section_at(match.start(), headers))

        # Pattern 2: standards references — "按XX标准执行" / "符合XX"
        std_matches = re.findall(
            r"按\s*([\u4e00-\u9fff]+[/T\d]*\s*[\u4e00-\u9fff]*(?:\d+(?:\.\d+)*)?)\s*(?:标准|规范|规程|要求)",
            content,
        )
        for std in std_matches:
            std = std.strip()
            # 过滤句段残留（照工艺文件的 / 本标准 等），只留真标准名
            if len(std) >= 2 and not any(w in std for w in ["文件", "照", "的", "本", "该", "以下"]):
                _add("检验", "标准", std)

        # Pattern 3: tool/equipment usage — "使用XX" / "采用XX方法"
        tool_matches = re.findall(
            r"(?:使用|采用|选用|使用)\s*([\u4e00-\u9fff]{2,10}(?:螺栓|扳手|量具|工具|设备|仪器|焊机|卡尺))",
            content,
        )
        context_section = self._guess_current_section(content)
        for tool in tool_matches:
            _add(context_section, "使用", tool.strip())

        # Pattern 4: process flow — "XX后进行YY" / "先XX再YY"
        flow_matches = re.findall(
            r"([\u4e00-\u9fff]{2,6})(?:后|完成后|合格后)\s*(?:进行|开始|转入)\s*([\u4e00-\u9fff]{2,6})",
            content,
        )
        for before, after in flow_matches:
            _add(before.strip(), "下一步", after.strip())

        # Pattern 5: safety constraints — "严禁XX" / "禁止XX"
        safety_matches = re.findall(
            r"(?:严禁|禁止|不得|不允许)\s*([\u4e00-\u9fff]{2,15})",
            content,
        )
        for safety in safety_matches:
            _add(context_section, "禁止", safety.strip())

        return self._score_and_filter(triples)[:100]


    @staticmethod
    def _find_spec(text: str, pos: int, window: int = 80) -> str:
        """Nearest spec token before pos within the same sentence (reuse SPEC_PATTERNS).

        Same-sentence boundary = 句号/换行/分号; picks the closest preceding spec
        to avoid cross-sentence mis-binding. Shared by _extract_triples and
        _extract_triples_from_substeps.
        """
        sent_start = max(text.rfind('。', 0, pos), text.rfind('\n', 0, pos), text.rfind('；', 0, pos)) + 1
        before = text[sent_start: pos]
        candidates: List[Tuple[int, str]] = []
        for sp in SPEC_PATTERNS:
            for m in re.finditer(sp, before):
                candidates.append((m.start(), m.group(0).strip()))
        if not candidates:
            return ""
        candidates.sort(key=lambda x: -x[0])  # 最近优先
        return candidates[0][1]

    def _extract_triples_from_substeps(
        self,
        asm: Dict[int, Dict[str, Any]],
        skeleton: List[str],
    ) -> List[Dict[str, str]]:
        """Extract triples from G25a assembly substeps, binding process = G19a skeleton name.

        For each step, process = skeleton[step_no-1] (G19a 真工序名) — NEVER
        asm[k]["name"] (which is a 工种 like 钳/机). Out-of-range step_no →
        process=None (no proc→spec edge; better than binding the wrong process,
        consistent with PLAN risk note 1). Each substep's content is scanned
        with the same QTY_PATTERNS / SPEC_PATTERNS as _extract_triples; subject
        falls back to sub.material if content has no spec but material does.
        """
        if not asm:
            return []
        triples: List[Dict[str, str]] = []
        seen: set = set()

        def _add(s: str, r: str, o: str, process: Optional[str]) -> None:
            if not s or not o:
                return
            key = f"{s}|{r}|{o}"
            if key not in seen and len(s) >= 2 and len(o) >= 2:
                seen.add(key)
                triples.append({"s": s, "r": r, "o": o, "process": process})

        for step_no, step_data in asm.items():
            # process = skeleton 真工序名；越界/非整数 → None
            process: Optional[str] = None
            if isinstance(step_no, int):
                idx = step_no - 1
                if 0 <= idx < len(skeleton):
                    process = skeleton[idx]
            for sub in step_data.get("substeps", []):
                content = sub.get("content", "") or ""
                for pattern, relation in QTY_PATTERNS:
                    for match in re.finditer(pattern, content):
                        subject = self._find_spec(content, match.start()) or (match.group(1) or "")
                        # fallback: sub.material 若含规格则取最近规格作 subject
                        if not subject:
                            material = sub.get("material", "") or ""
                            ms = self._find_spec(material, len(material)) if material else ""
                            subject = ms
                        _add(subject, relation, match.group(2), process=process)
                # Material triple: proc→material REQUIRES edge (build_from_triples
                # "使用" branch auto-builds the edge). Reverse-lookup
                # material→proc gives "which process uses this material" for G18a
                # source. Material name cleaned to strip spec suffix (e.g.
                # "螺纹HG/T3596" → "螺纹", "密封圈φ20" → "密封圈"); r="使用" dedups
                # via _add seen-set.
                # Material cell may list multiple materials separated by
                # 、/,/，— extract ALL segments (content-based, per user
                # principle), each through the same cleaning pipeline.
                if process:
                    mat = (sub.get("material") or "").strip()
                    if mat and len(mat) >= 2:
                        for seg in re.split(r"[、,，]", mat):
                            head = seg.strip()
                            if not head or len(head) < 2:
                                continue
                            # Cut at first ASCII-letter/digit/slash boundary
                            # where a spec suffix begins (keeps the CJK name).
                            m = re.match(r"^[^\s/]+", head)
                            cjk = m.group(0) if m else head
                            spec_cut = re.split(r"[A-Za-z0-9/]", cjk)
                            mat_clean = (spec_cut[0] or cjk)[:12]
                            _add(process, "使用", mat_clean, process=process)
        return triples

    def _score_and_filter(self, triples: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Score triples by information value and filter low-value ones."""
        scored: List[Tuple[int, Dict[str, str]]] = []
        for t in triples:
            score = 0
            s, r, o = t["s"], t["r"], t["o"]
            # Object contains numeric value or unit → high value
            if re.search(r"\d", o):
                score += 2
            # High-value relation
            if r in HIGH_VALUE_RELATIONS:
                score += 2
            # Non-generic subject → more specific
            if s not in GENERIC_SUBJECTS:
                score += 2
            # Subject mentions a known process type
            if re.search(r"(?:装配|焊接|涂装|热处理|机加|检验|试验|包装|搬运|存储)", s):
                score += 1
            # Object has unit
            if re.search(r"(?:°C|MPa|mm|min|N·m|HRC|rpm)", o):
                score += 1
            # Drop triples with score 0 (no useful signal)
            if score > 0:
                scored.append((score, t))

        # Sort by score descending
        scored.sort(key=lambda x: -x[0])
        return [t for _, t in scored]

    def _collect_headers(self, content: str) -> List[Tuple[int, str]]:
        """Collect all (pos, title) section headers — 数字+中文 标题，按位置升序。"""
        headers: List[Tuple[int, str]] = []
        for m in re.finditer(r"(?:^|\n)\s*(\d+(?:\.\d+)*)\s+([\u4e00-\u9fff]{2,10})", content):
            headers.append((m.start(), m.group(2).strip()))
        return headers

    def _section_at(self, pos: int, headers: List[Tuple[int, str]] = None) -> str:
        """按位置取最近前置工序标题（数字+中文），比 _guess_current_section 整篇取一个更精确。

        用于规格 triple 绑定所在工序：不同位置的规格绑不同工序。
        headers 按 pos 升序，线性扫取 hpos <= pos 的最后一个。
        """
        if headers is None:
            headers = self._collect_headers(self._content_cached) if getattr(self, "_content_cached", None) else []
        candidate = None
        for hpos, title in headers:
            if hpos <= pos:
                candidate = title
            else:
                break
        return candidate  # 可能 None（pos 在第一个标题前）

    def _guess_current_section(self, content: str) -> str:
        """Guess the current process section from context.

        Returns the most specific process-related section header found.
        Falls back to generic "工艺" only if nothing better is available.
        """
        # Collect all section headers with their positions
        headers = self._collect_headers(content)

        if not headers:
            return None  # 不返回泛词「工艺」（避免 subject=工艺 串行错位）

        # Prefer headers that contain process-related keywords
        process_keywords = (
            "装配", "焊接", "涂装", "热处理", "机加", "检验",
            "试验", "包装", "搬运", "存储", "清洗", "表面处理",
            "前处理", "喷漆", "铆接", "压接", "胶接", "密封",
        )
        for _, title in reversed(headers):
            for kw in process_keywords:
                if kw in title:
                    return title

        # No process keyword found: return last header if specific enough
        last = headers[-1][1]
        if last not in GENERIC_SUBJECTS and len(last) >= 2:
            return last

        return "工艺"

    def _extract_terms(self, content: str) -> Dict[str, int]:
        """Extract high-frequency technical terms, filtering generic ones."""
        term_patterns = [
            r"[\u4e00-\u9fff]{2,4}(?:工艺|参数|要求|设备|方法|标准|规范|规程|检验|试验|测量)",
            r"[\u4e00-\u9fff]{2,4}(?:温度|压力|时间|速度|力矩|精度|公差|表面|硬度)",
            r"(?:装配|焊接|涂装|热处理|机加|检验|试验|包装|搬运|存储)[\u4e00-\u9fff]{0,4}",
        ]

        # Generic compound terms that look specific but carry no domain value
        generic_terms = {
            "工艺参数", "工艺要求", "工艺方法", "工艺设备", "工艺标准", "工艺规范",
            "工艺规程", "工艺过程", "操作要求", "操作方法", "操作步骤", "操作规程",
            "检验要求", "检验方法", "检验标准", "检验设备", "检验过程",
            "质量要求", "质量标准", "技术要求", "技术标准", "技术参数",
        }

        counter: Counter = Counter()
        for pattern in term_patterns:
            for m in re.findall(pattern, content):
                if m not in STOP_WORDS and m not in generic_terms and len(m) >= 2:
                    counter[m] += 1

        # Only keep terms that appear more than once (reduces noise)
        return {t: c for t, c in counter.most_common(50) if c >= 2}

    def _extract_style(self, content: str) -> Dict[str, Any]:
        """Extract writing style indicators."""
        style: Dict[str, Any] = {}

        sentences = [s.strip() for s in re.split(r"[。！？\n]+", content) if s.strip()]
        if sentences:
            avg_len = sum(len(s) for s in sentences) / len(sentences)
            style["preferred_sentence_length"] = (
                "short" if avg_len < 20 else ("long" if avg_len > 50 else "medium")
            )

        passive = len(re.findall(r"被|受|由.*?(?:完成|处理|执行)", content))
        active = len(re.findall(r"将|把|使", content))
        if passive + active > 0:
            style["use_passive_voice"] = passive > active

        style["include_caution_notes"] = bool(
            re.search(r"注意|警告|安全|危险|禁止|严禁", content)
        )
        return style

    def _generate_summary(self, content: str, domain: str, triple_count: int) -> str:
        """Generate a compact profile summary."""
        domain_labels = {"assembly": "装配", "welding": "焊接", "coating": "涂装"}
        label = domain_labels.get(domain, domain)

        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        first = paragraphs[0][:100] if paragraphs else ""

        parts = [f"[{label}]领域工艺文件画像", f"三元组{triple_count}条"]
        if re.search(r"\d+(?:\.\d+)?\s*(?:mm|cm|m|kg|N|MPa|°C|度)", content):
            parts.append("含数值规格")
        if first:
            parts.append(f"摘要: {first}")
        return "。".join(parts)

    def merge_features_to_profile(
        self,
        profile_data: Dict[str, Any],
        features: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Merge extracted features into existing profile.

        Triples are deduplicated by (s, r, o) key.
        Graph is rebuilt from all triples after merge.
        """
        # Merge triples (deduplicate by s|r|o key)
        existing_triples = profile_data.get("triples", [])
        seen_keys = {f"{t['s']}|{t['r']}|{t['o']}" for t in existing_triples}
        for t in features.get("triples", []):
            key = f"{t['s']}|{t['r']}|{t['o']}"
            if key not in seen_keys:
                seen_keys.add(key)
                existing_triples.append(t)
        profile_data["triples"] = existing_triples[:200]

        # Merge frequent terms (accumulate)
        existing_terms: Dict[str, int] = profile_data.get("frequent_terms", {})
        for term, count in features.get("frequent_terms", {}).items():
            existing_terms[term] = existing_terms.get(term, 0) + count
        profile_data["frequent_terms"] = dict(
            sorted(existing_terms.items(), key=lambda x: -x[1])[:100]
        )

        # Update style preferences
        for key in ("preferred_sentence_length", "use_passive_voice", "include_caution_notes"):
            if key in features:
                profile_data.setdefault("preferences", {})[key] = features[key]

        if features.get("ai_generated_summary"):
            profile_data["ai_generated_summary"] = features["ai_generated_summary"]

        doc_id = features.get("source_document_id")
        if doc_id:
            ids = profile_data.get("source_document_ids", [])
            if doc_id not in ids:
                ids.append(doc_id)
            profile_data["source_document_ids"] = ids

        if features.get("domain"):
            profile_data["domain"] = features["domain"]

        # KnowledgeGraph rebuild removed in retrieval cleanup; triples no longer
        # turned into a graph object. Reintroduce a builder in Step F if graph
        # reconstruction is needed.


        return profile_data
