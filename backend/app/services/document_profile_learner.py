"""
DocumentProfileLearner - Extract user profile from parsed documents.

Analyzes document content (from PDF parsing, standards, or user uploads)
to extract terminology, style patterns, and structural preferences.
"""
import re
import json
from typing import Any, Dict, List, Optional
from pathlib import Path
from collections import Counter
from datetime import datetime

from app.shared.logging import get_logger

logger = get_logger(__name__)

# Common Chinese stop words to filter out from term extraction
STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你",
    "会", "着", "没有", "看", "好", "自己", "这", "他", "她", "它",
    "与", "及", "或", "等", "为", "中", "对", "其", "之", "从",
    "以", "可", "能", "将", "把", "被", "让", "使", "由", "按",
    "应", "需", "须", "根据", "按照", "应按", "不得", "严禁",
    "应按", "一般", "通常", "适当", "相应", "符合", "满足",
}


class DocumentProfileLearner:
    """Extract profile features from parsed document content."""

    def learn_from_content(
        self,
        content: str,
        domain: str = "assembly",
        document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract profile features from document text.

        Args:
            content: Parsed document text content
            domain: Document domain (assembly, welding, coating)
            document_id: Source document ID for traceability

        Returns:
            Extracted profile features ready to merge into Profile
        """
        features: Dict[str, Any] = {
            "domain": domain,
            "extracted_at": datetime.now().isoformat(),
        }

        if document_id:
            features["source_document_id"] = document_id

        # 1. Extract terminology frequency
        features["frequent_terms"] = self._extract_terms(content)

        # 2. Extract document structure patterns
        features["document_patterns"] = self._extract_patterns(content)

        # 3. Extract style indicators
        style = self._extract_style(content)
        features.update(style)

        # 4. Generate compact summary
        features["ai_generated_summary"] = self._generate_summary(content, domain)

        logger.info(
            "document_profile_learned",
            domain=domain,
            terms_count=len(features["frequent_terms"]),
            patterns_count=len(features["document_patterns"]),
        )
        return features

    def _extract_terms(self, content: str) -> Dict[str, int]:
        """
        Extract high-frequency technical terms.

        Returns terms sorted by frequency, top 50.
        """
        # Extract noun-like phrases: 2-4 char Chinese words excluding stop words
        # Technical terms often appear as: XX工艺, XX参数, XX要求, XX设备
        term_patterns = [
            r"[\u4e00-\u9fff]{2,4}(?:工艺|参数|要求|设备|方法|标准|规范|规程|检验|试验|测量)",
            r"[\u4e00-\u9fff]{2,4}(?:温度|压力|时间|速度|力矩|精度|公差|表面|硬度)",
            r"(?:装配|焊接|涂装|热处理|机加|检验|试验|包装|搬运|存储)[\u4e00-\u9fff]{0,4}",
        ]

        counter: Counter = Counter()
        for pattern in term_patterns:
            matches = re.findall(pattern, content)
            for m in matches:
                if m not in STOP_WORDS and len(m) >= 2:
                    counter[m] += 1

        # Also extract terms from numbered items: 1. xxx 2. xxx
        numbered_items = re.findall(r"\d+[.、]\s*([^\n]{2,20})", content)
        for item in numbered_items:
            item = item.strip()
            if item not in STOP_WORDS and len(item) >= 2:
                counter[item] += 1

        return dict(counter.most_common(50))

    def _extract_patterns(self, content: str) -> List[str]:
        """
        Extract document structural patterns.

        Detects heading patterns, table references, section structures.
        """
        patterns: List[str] = []

        # Detect heading patterns
        headings = re.findall(r"(?:^|\n)(#{1,4}\s+.+)", content)
        if headings:
            patterns.extend([h.strip() for h in headings[:10]])

        # Detect numbered section patterns
        sections = re.findall(r"(?:^|\n)(\d+(?:\.\d+)*\s+[^\n]{2,30})", content)
        if sections:
            patterns.extend([s.strip() for s in sections[:10]])

        # Detect table-like patterns
        tables = re.findall(r"\|.+\|.+\|", content)
        if tables:
            patterns.append(f"tables:{len(tables)}")

        return patterns[:20]

    def _extract_style(self, content: str) -> Dict[str, Any]:
        """Extract writing style indicators."""
        style: Dict[str, Any] = {}

        # Sentence length
        sentences = re.split(r"[。！？\n]+", content)
        sentences = [s.strip() for s in sentences if s.strip()]
        if sentences:
            avg_len = sum(len(s) for s in sentences) / len(sentences)
            if avg_len < 20:
                style["preferred_sentence_length"] = "short"
            elif avg_len > 50:
                style["preferred_sentence_length"] = "long"
            else:
                style["preferred_sentence_length"] = "medium"

        # Passive voice tendency
        passive_markers = len(re.findall(r"被|受|由.*?(?:完成|处理|执行)", content))
        active_markers = len(re.findall(r"将|把|使", content))
        if passive_markers + active_markers > 0:
            style["use_passive_voice"] = passive_markers > active_markers

        # Caution/safety notes presence
        has_caution = bool(re.search(r"注意|警告|安全|危险|禁止|严禁", content))
        style["include_caution_notes"] = has_caution

        return style

    def _generate_summary(self, content: str, domain: str) -> str:
        """
        Generate a compact profile summary from document content.

        This is a rule-based summary (no LLM call). Can be upgraded
        to LLM-generated summary later for richer extraction.
        """
        domain_labels = {
            "assembly": "装配",
            "welding": "焊接",
            "coating": "涂装",
        }
        domain_label = domain_labels.get(domain, domain)

        # Extract first meaningful paragraph as basis
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        first_para = paragraphs[0][:100] if paragraphs else ""

        # Count key indicators
        term_count = len(self._extract_terms(content))
        has_tables = bool(re.search(r"\|.+\|.+\|", content))
        has_specs = bool(re.search(r"\d+(?:\.\d+)?\s*(?:mm|cm|m|kg|N|MPa|°C|度)", content))

        summary_parts = [
            f"[{domain_label}]领域工艺文件画像",
            f"提取术语{term_count}个",
        ]
        if has_tables:
            summary_parts.append("含表格数据")
        if has_specs:
            summary_parts.append("含数值规格")
        if first_para:
            summary_parts.append(f"摘要: {first_para}")

        return "。".join(summary_parts)

    def merge_features_to_profile(
        self,
        profile_data: Dict[str, Any],
        features: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Merge extracted features into an existing profile.

        Args:
            profile_data: Current profile as dict
            features: Features from learn_from_content

        Returns:
            Updated profile dict
        """
        # Merge frequent terms (accumulate counts)
        existing_terms: Dict[str, int] = profile_data.get("frequent_terms", {})
        new_terms: Dict[str, int] = features.get("frequent_terms", {})
        for term, count in new_terms.items():
            existing_terms[term] = existing_terms.get(term, 0) + count
        profile_data["frequent_terms"] = dict(
            sorted(existing_terms.items(), key=lambda x: -x[1])[:100]
        )

        # Merge document patterns (deduplicate)
        existing_patterns = set(profile_data.get("document_patterns", []))
        for p in features.get("document_patterns", []):
            existing_patterns.add(p)
        profile_data["document_patterns"] = list(existing_patterns)[:30]

        # Update style preferences (latest wins)
        for key in ("preferred_sentence_length", "use_passive_voice", "include_caution_notes"):
            if key in features:
                profile_data.setdefault("preferences", {})[key] = features[key]

        # Update summary
        if features.get("ai_generated_summary"):
            profile_data["ai_generated_summary"] = features["ai_generated_summary"]

        # Track source document
        doc_id = features.get("source_document_id")
        if doc_id:
            source_ids = profile_data.get("source_document_ids", [])
            if doc_id not in source_ids:
                source_ids.append(doc_id)
            profile_data["source_document_ids"] = source_ids

        # Update domain
        if features.get("domain"):
            profile_data["domain"] = features["domain"]

        return profile_data
