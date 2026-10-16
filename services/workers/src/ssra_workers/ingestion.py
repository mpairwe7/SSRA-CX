"""Legal-structure document chunker for South Sudan Acts, Financial Acts & Circulars (Section 7)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_PART_RE = re.compile(r"^\s*PART\s+([IVXLCDM0-9]+)\b[:\s-]*(.*)$", flags=re.IGNORECASE)
_SECTION_RE = re.compile(r"^\s*(?:SECTION|SEC\.?)\s+(\d+[A-Z]?)\b[:\s-]*(.*)$", flags=re.IGNORECASE)


@dataclass(frozen=True)
class LegalChunk:
    chunk_id: str
    doc_id: str
    part: str
    section: str
    section_anchor: str
    content: str
    checksum_sha256: str


def chunk_legal_document_by_structure(*, doc_id: str, raw_text: str) -> list[LegalChunk]:
    """Chunk statutory text by Part and Section hierarchy, preserving section_anchor citations."""
    current_part = "I"
    current_sec = "1"
    current_lines: list[str] = []
    chunks: list[LegalChunk] = []

    def _flush() -> None:
        body = " ".join(line.strip() for line in current_lines if line.strip()).strip()
        if not body:
            return
        anchor = f"Part-{current_part}-Sec-{current_sec}"
        digest = hashlib.sha256(f"{doc_id}:{anchor}:{body}".encode()).hexdigest()
        chunks.append(
            LegalChunk(
                chunk_id=f"{doc_id}_{anchor.lower().replace('-', '_')}",
                doc_id=doc_id,
                part=current_part,
                section=current_sec,
                section_anchor=anchor,
                content=body,
                checksum_sha256=digest,
            )
        )

    for line in raw_text.splitlines():
        part_match = _PART_RE.match(line)
        if part_match:
            _flush()
            current_lines = [line]
            current_part = part_match.group(1).upper()
            continue

        sec_match = _SECTION_RE.match(line)
        if sec_match:
            _flush()
            current_lines = [line]
            current_sec = sec_match.group(1)
            continue

        current_lines.append(line)

    _flush()
    return chunks
