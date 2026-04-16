"""
ProfileLearningService - Learn writing preferences from user interactions.

Analyzes edits that users make to AI-generated content to extract
writing style preferences (vocabulary, sentence structure, formatting).
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from app.shared.logging import get_logger

logger = get_logger(__name__)


class ProfileLearningService:
    """
    Extract writing preferences by comparing original AI output
    with user-edited content.
    """

    def analyze_edit(
        self,
        original: str,
        edited: str,
    ) -> Dict[str, Any]:
        """
        Compare original AI output with user edit to extract preferences.

        Args:
            original: AI-generated content
            edited: User-edited version

        Returns:
            Extracted preference updates (partial dict for merge_update)
        """
        updates: Dict[str, Any] = {}

        # 1. Sentence length preference
        orig_avg = self._avg_sentence_length(original)
        edit_avg = self._avg_sentence_length(edited)
        if edit_avg > 0:
            if edit_avg < orig_avg * 0.7:
                updates["preferred_sentence_length"] = "short"
            elif edit_avg > orig_avg * 1.3:
                updates["preferred_sentence_length"] = "long"
            else:
                updates["preferred_sentence_length"] = "medium"

        # 2. Passive vs active voice
        passive_count = len(re.findall(r"被|受|遭|由.*?完成", edited))
        active_count = len(re.findall(r"将|把|使|让", edited))
        if passive_count + active_count > 0:
            updates["use_passive_voice"] = passive_count > active_count

        # 3. Examples inclusion
        has_examples = bool(re.search(r"例如|比如|举例|如：|示例", edited))
        orig_has_examples = bool(re.search(r"例如|比如|举例|如：|示例", original))
        if has_examples != orig_has_examples:
            updates["include_examples"] = has_examples

        # 4. Caution notes
        has_caution = bool(re.search(r"注意|警告|注意事項|安全|危险", edited))
        orig_has_caution = bool(re.search(r"注意|警告|注意事項|安全|危险", original))
        if has_caution != orig_has_caution:
            updates["include_caution_notes"] = has_caution

        # 5. Custom vocabulary additions
        new_vocab = self._extract_new_vocabulary(original, edited)
        if new_vocab:
            updates["_new_vocabulary"] = new_vocab

        # 6. Avoid phrases (content removed by user)
        removed = self._extract_removed_phrases(original, edited)
        if removed:
            updates["_avoid_phrases"] = removed

        logger.info(
            "preferences_extracted",
            edits_count=len(updates),
            sentence_length=updates.get("preferred_sentence_length"),
        )
        return updates

    def _avg_sentence_length(self, text: str) -> float:
        """Average sentence length in characters."""
        sentences = re.split(r"[。！？\n]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return 0.0
        return sum(len(s) for s in sentences) / len(sentences)

    def _extract_new_vocabulary(
        self, original: str, edited: str
    ) -> Dict[str, str]:
        """Extract vocabulary terms added by the user."""
        vocab: Dict[str, str] = {}
        # Look for technical terms in parentheses pattern: 中文(English)
        new_terms = set(re.findall(r"[\u4e00-\u9fff]+（[^）]+）", edited))
        orig_terms = set(re.findall(r"[\u4e00-\u9fff]+（[^）]+）", original))
        for term in new_terms - orig_terms:
            match = re.match(r"([\u4e00-\u9fff]+)（([^）]+)）", term)
            if match:
                vocab[match.group(1)] = match.group(2)
        return vocab

    def _extract_removed_phrases(
        self, original: str, edited: str
    ) -> List[str]:
        """Extract phrases that were removed by the user."""
        removed: List[str] = []
        orig_words = set(original.split())
        edit_words = set(edited.split())
        # Only track multi-character removals (likely intentional)
        for word in orig_words - edit_words:
            if len(word) >= 4:
                removed.append(word)
        return removed[:10]  # Cap at 10 to avoid noise
