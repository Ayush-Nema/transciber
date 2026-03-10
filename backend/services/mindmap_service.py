"""Generate Mermaid mind-map from transcription text."""
import re
import logging
from collections import Counter

logger = logging.getLogger(__name__)

# Common Hindi stop words to filter out
HINDI_STOP_WORDS = {
    "है", "हैं", "था", "थे", "थी", "को", "का", "के", "की", "में", "पर", "से",
    "ने", "और", "या", "भी", "तो", "ही", "एक", "यह", "वह", "इस", "उस", "जो",
    "कि", "हम", "तुम", "वो", "मैं", "आप", "कर", "हो", "जा", "ला", "दे",
    "ले", "कोई", "कुछ", "सब", "बहुत", "अभी", "बस", "तक", "साथ", "लिए",
    "अपने", "अपनी", "अपना", "होता", "करता", "करते", "होते", "करना", "होना",
    "रहा", "रही", "रहे", "गया", "गई", "गए", "वाला", "वाली", "वाले",
    "the", "is", "are", "was", "were", "a", "an", "and", "or", "but", "in",
    "on", "at", "to", "for", "of", "with", "by", "from", "this", "that",
    "it", "he", "she", "we", "they", "you", "i", "me", "my", "your",
    "his", "her", "its", "our", "their", "be", "have", "has", "had", "do",
    "does", "did", "not", "so", "if", "as", "can", "will", "would", "about",
}

ENGLISH_STOP_WORDS = {
    "the", "is", "are", "was", "were", "a", "an", "and", "or", "but", "in",
    "on", "at", "to", "for", "of", "with", "by", "from", "this", "that",
    "it", "he", "she", "we", "they", "you", "i", "me", "my", "your",
}


def sanitize_mermaid_text(text: str) -> str:
    """Remove/escape characters that break Mermaid syntax."""
    text = text.strip()
    text = re.sub(r'[(){}[\]"\'`#;|<>]', '', text)
    text = text.replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text[:60]  # Limit label length


def extract_key_phrases(text: str, max_phrases: int = 8) -> list[str]:
    """Extract key phrases from text using simple frequency analysis."""
    # Split into sentences
    sentences = re.split(r'[।.!?\n]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    # Extract meaningful words
    all_words = []
    for sentence in sentences:
        words = re.findall(r'\b[\w\u0900-\u097F]+\b', sentence)
        for word in words:
            if len(word) > 2 and word.lower() not in HINDI_STOP_WORDS:
                all_words.append(word)

    # Get top words
    word_counts = Counter(all_words)
    top_words = [w for w, _ in word_counts.most_common(30)]

    # Build phrases by grouping nearby top words in sentences
    phrases = []
    for sentence in sentences[:20]:
        words = sentence.split()
        phrase_words = [w for w in words if any(tw in w for tw in top_words[:15])]
        if len(phrase_words) >= 2:
            phrase = " ".join(phrase_words[:5])
            phrases.append(phrase)

    # Deduplicate and limit
    seen = set()
    unique = []
    for p in phrases:
        p_clean = sanitize_mermaid_text(p)
        if p_clean and p_clean not in seen and len(p_clean) > 5:
            seen.add(p_clean)
            unique.append(p_clean)
            if len(unique) >= max_phrases:
                break

    # Fallback: use top words if phrases extraction yields little
    if len(unique) < 3:
        unique = [sanitize_mermaid_text(w) for w in top_words[:max_phrases] if len(w) > 2]

    return unique


def generate_mindmap_from_segments(segments: list[dict], title: str = "Transcription") -> str:
    """Generate Mermaid mind-map from timestamped segments."""
    if not segments:
        return generate_mindmap_from_text("", title)

    # Group segments into time-based sections
    total_duration = segments[-1]["end"] if segments else 0
    section_count = min(5, max(2, len(segments) // 10))
    section_duration = total_duration / section_count if section_count > 0 else total_duration

    sections = {}
    for seg in segments:
        section_idx = int(seg["start"] / section_duration) if section_duration > 0 else 0
        section_idx = min(section_idx, section_count - 1)
        if section_idx not in sections:
            sections[section_idx] = []
        sections[section_idx].append(seg["text"])

    safe_title = sanitize_mermaid_text(title) or "Transcription"

    lines = ["mindmap", f"  root(({safe_title}))"]

    for idx in sorted(sections.keys()):
        start_min = int((idx * section_duration) / 60)
        end_min = int(((idx + 1) * section_duration) / 60)
        section_label = sanitize_mermaid_text(f"{start_min}m - {end_min}m")
        lines.append(f"    {section_label}")

        section_text = " ".join(sections[idx])
        phrases = extract_key_phrases(section_text, max_phrases=4)
        for phrase in phrases:
            lines.append(f"      {phrase}")

    return "\n".join(lines)


def generate_mindmap_from_text(text: str, title: str = "Transcription") -> str:
    """Generate Mermaid mind-map from plain text (fallback when no segments)."""
    safe_title = sanitize_mermaid_text(title) or "Transcription"

    if not text or len(text.strip()) < 10:
        return f"mindmap\n  root(({safe_title}))\n    No content available"

    phrases = extract_key_phrases(text, max_phrases=8)

    lines = ["mindmap", f"  root(({safe_title}))"]

    # Group phrases into logical clusters (simple: just pairs)
    for i in range(0, len(phrases), 2):
        group = phrases[i:i+2]
        if group:
            lines.append(f"    {group[0]}")
            for sub in group[1:]:
                lines.append(f"      {sub}")

    return "\n".join(lines)
