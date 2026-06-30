"""Log parsing: Drain3 turns raw lines into (timestamp, template_id, is_anomaly).

Per paper Section IV-C, Drain extracts templates; each line's cluster_id is its TemplateId.
Line-level datasets share parse_lines (regex from datasets.LineDatasetSpec); HDFS uses
load_hdfs_sessions (block_id grouping + label csv).
"""

from __future__ import annotations

import re

import pandas as pd
from dataclasses import dataclass

from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

from .datasets import LineDatasetSpec, get_line_spec
from .logging_config import logger

# Backward-compatible alias (regex now lives in datasets.py)
from .datasets import BGL_REGEX as BGL_LOG_REGEX  # noqa: E402,F401

_BLOCK_RE = re.compile(r"blk_-?\d+")


@dataclass
class ParsedEntry:
    timestamp: float        # Unix seconds, used for time-window segmentation
    template_id: int        # Drain3 cluster_id
    is_anomaly: bool        # set from the dataset's label field


def _new_template_miner() -> TemplateMiner:
    """Create an in-memory Drain3 TemplateMiner."""
    return TemplateMiner(config=TemplateMinerConfig())


def parse_lines(
    lines, spec: LineDatasetSpec, miner: TemplateMiner | None = None, log_every: int = 500_000
) -> list[ParsedEntry]:
    """Parse line-level dataset lines via spec.regex. Label != "-" marks an anomaly."""
    if miner is None:
        miner = _new_template_miner()
    entries: list[ParsedEntry] = []
    skipped = 0
    for i, line in enumerate(lines):
        line = line.rstrip("\n")
        if not line.strip():
            continue
        m = spec.regex.match(line)
        if m is None:
            skipped += 1
            continue
        result = miner.add_log_message(m.group("Content"))
        entries.append(
            ParsedEntry(
                timestamp=float(m.group("Timestamp")),
                template_id=int(result["cluster_id"]),
                is_anomaly=(m.group("Label") != "-"),
            )
        )
        if log_every and (i + 1) % log_every == 0:
            logger.info(
                "[{}] parsing: {} lines read, {} valid, {} templates",
                spec.name, i + 1, len(entries), len(miner.drain.clusters),
            )
    if skipped:
        logger.warning("[{}] parsing skipped {} non-matching lines", spec.name, skipped)
    logger.info(
        "[{}] parsing done: {} entries, {} templates",
        spec.name, len(entries), len(miner.drain.clusters),
    )
    return entries


def parse_line_file(
    path: str, dataset: str, max_lines: int = 0, miner: TemplateMiner | None = None
) -> list[ParsedEntry]:
    """Parse a line-level dataset file. max_lines=0 means the whole file."""
    spec = get_line_spec(dataset)

    def _iter():
        with open(path, encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if max_lines and i >= max_lines:
                    break
                yield line

    return parse_lines(_iter(), spec, miner=miner)


def parse_bgl_file(
    path: str, max_lines: int = 0, miner: TemplateMiner | None = None
) -> list[ParsedEntry]:
    """Backward-compatible BGL parser."""
    return parse_line_file(path, "BGL", max_lines=max_lines, miner=miner)


def load_hdfs_sessions(
    log_path: str, label_path: str, max_lines: int = 0, miner: TemplateMiner | None = None
) -> tuple[list[list[int]], list[int]]:
    """Parse HDFS into per-block_id template sequences with labels from anomaly_label.csv.

    HDFS line format: <Date> <Time> <Pid> <Level> <Component>: <Content>. block_ids are
    extracted from Content; a line may belong to several blocks. Label "Anomaly" -> 1.
    """
    if miner is None:
        miner = _new_template_miner()
    hdfs_re = re.compile(
        r"^(?P<Date>\S+)\s+(?P<Time>\S+)\s+(?P<Pid>\S+)\s+"
        r"(?P<Level>\S+)\s+(?P<Component>\S+?):\s+(?P<Content>.*)$"
    )
    sessions: dict[str, list[int]] = {}
    skipped = 0
    with open(log_path, encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            if max_lines and i >= max_lines:
                break
            line = line.rstrip("\n")
            if not line.strip():
                continue
            m = hdfs_re.match(line)
            if m is None:
                skipped += 1
                continue
            content = m.group("Content")
            tid = int(miner.add_log_message(content)["cluster_id"])
            for blk in set(_BLOCK_RE.findall(content)):
                sessions.setdefault(blk, []).append(tid)
            if (i + 1) % 500_000 == 0:
                logger.info(
                    "[HDFS] parsing: {} lines read, {} blocks, {} templates",
                    i + 1, len(sessions), len(miner.drain.clusters),
                )
    if skipped:
        logger.warning("[HDFS] parsing skipped {} non-matching lines", skipped)

    label_df = pd.read_csv(label_path)
    label_map = {
        str(b): (1 if str(lbl).strip().lower() == "anomaly" else 0)
        for b, lbl in zip(label_df["BlockId"], label_df["Label"])
    }
    block_ids = list(sessions.keys())
    sequences = [sessions[b] for b in block_ids]
    labels = [label_map.get(b, 0) for b in block_ids]
    logger.info(
        "[HDFS] sessions: {} blocks, {} anomalous, {} templates",
        len(sequences), sum(labels), len(miner.drain.clusters),
    )
    return sequences, labels


def parse_structured(records) -> list[ParsedEntry]:
    """Build ParsedEntry from (timestamp, template_id, is_anomaly) tuples (for tests)."""
    return [
        ParsedEntry(timestamp=float(ts), template_id=int(tid), is_anomaly=bool(anom))
        for ts, tid, anom in records
    ]
