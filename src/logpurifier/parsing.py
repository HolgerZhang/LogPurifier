"""Log parsing: Drain3 turns raw lines into (timestamp, template_id, is_anomaly).

Per paper Section IV-C, Drain extracts templates; each line's cluster_id is its TemplateId.
The BGL line-format regex follows event-purger (epurger/parser.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

from .logging_config import logger


@dataclass
class ParsedEntry:
    timestamp: float        # Unix seconds, used for time-window segmentation
    template_id: int        # Drain3 cluster_id
    is_anomaly: bool        # set from the dataset's label field


# BGL line format:
# <Label> <Timestamp> <Date> <Node> <Time> <NodeRepeat> <Type> <Component> <Level> <Content>
BGL_LOG_REGEX = re.compile(
    r"^(?P<Label>\S+)\s+(?P<Timestamp>\d+)\s+(?P<Date>\S+)\s+"
    r"(?P<Node>\S+)\s+(?P<Time>\S+)\s+(?P<NodeRepeat>\S+)\s+(?P<Type>\S+)\s+"
    r"(?P<Component>\S+)\s+(?P<Level>\S+)\s+(?P<Content>.*)$"
)


def _new_template_miner() -> TemplateMiner:
    """Create an in-memory Drain3 TemplateMiner."""
    return TemplateMiner(config=TemplateMinerConfig())


def parse_bgl_file(
    path: str, max_lines: int = 0, miner: TemplateMiner | None = None
) -> list[ParsedEntry]:
    """Parse a BGL log file. max_lines=0 means the whole file."""
    def _iter():
        with open(path, encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if max_lines and i >= max_lines:
                    break
                yield line

    return parse_bgl_lines(_iter(), miner=miner)


def parse_bgl_lines(
    lines, miner: TemplateMiner | None = None, log_every: int = 500_000
) -> list[ParsedEntry]:
    """Parse BGL-style lines. Label != "-" marks an anomalous line. Logs progress."""
    if miner is None:
        miner = _new_template_miner()
    entries: list[ParsedEntry] = []
    skipped = 0
    for i, line in enumerate(lines):
        line = line.rstrip("\n")
        if not line.strip():
            continue
        m = BGL_LOG_REGEX.match(line)
        if m is None:
            skipped += 1
            continue
        content = m.group("Content")
        result = miner.add_log_message(content)
        entries.append(
            ParsedEntry(
                timestamp=float(m.group("Timestamp")),
                template_id=int(result["cluster_id"]),
                is_anomaly=(m.group("Label") != "-"),
            )
        )
        if log_every and (i + 1) % log_every == 0:
            logger.info(
                "parsing: {} lines read, {} valid, {} templates",
                i + 1, len(entries), len(miner.drain.clusters),
            )
    if skipped:
        logger.warning("parsing skipped {} non-matching lines", skipped)
    logger.info("parsing done: {} entries, {} templates", len(entries), len(miner.drain.clusters))
    return entries


def parse_structured(records) -> list[ParsedEntry]:
    """Build ParsedEntry from (timestamp, template_id, is_anomaly) tuples (for tests)."""
    return [
        ParsedEntry(timestamp=float(ts), template_id=int(tid), is_anomaly=bool(anom))
        for ts, tid, anom in records
    ]
