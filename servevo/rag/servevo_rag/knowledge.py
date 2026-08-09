"""知识读取：references/*.md → 结构化块（source 文件名 + 行号 + 标题）。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class KnowledgeChunk:
    content: str
    source: str          # 文件名，如 warranty-policy.md
    section: str = ""    # 小节标题（## …）
    line_start: int = 0
    score: float = 0.0
    overlap: float = 0.0  # query 词在 chunk 中的覆盖率（真实质量信号，供质量门使用）

    def to_dict(self) -> dict[str, object]:
        return {"content": self.content, "source": self.source, "section": self.section,
                "score": self.score, "overlap": self.overlap}


_HEADING_RE = re.compile(r"^#{2,4}\s+(.+)$")


def load_knowledge(refs_dir: str | Path) -> list[KnowledgeChunk]:
    """读取目录下所有 .md，按 ## 级小节切块。"""
    root = Path(refs_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"知识目录不存在: {root}")
    chunks: list[KnowledgeChunk] = []
    for md in sorted(root.glob("*.md")):
        lines = md.read_text(encoding="utf-8").splitlines()
        cur_section = ""
        cur_start = 1
        buf: list[str] = []
        for idx, line in enumerate(lines, start=1):
            m = _HEADING_RE.match(line.strip())
            if m:
                if buf:
                    chunks.append(KnowledgeChunk(content="\n".join(buf).strip(), source=md.name, section=cur_section, line_start=cur_start))
                cur_section = m.group(1).strip()
                cur_start = idx
                buf = [line.strip()]
            else:
                buf.append(line.rstrip())
        if buf:
            chunks.append(KnowledgeChunk(content="\n".join(buf).strip(), source=md.name, section=cur_section, line_start=cur_start))
    return [c for c in chunks if c.content]