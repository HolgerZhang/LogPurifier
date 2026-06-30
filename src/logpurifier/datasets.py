"""Dataset registry.

Two dataset families (see specs/04-datasets.md):
- Line-level + time window: BGL / Thunderbird / Spirit. First column Label ("-"=normal),
  second column Unix-second Timestamp, trailing Content. Described by a LineDatasetSpec.
- Session-labeled: HDFS v1. Grouped by block_id with labels from a separate csv; handled
  by a dedicated loader (see parsing.load_hdfs_sessions). No time window.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LineDatasetSpec:
    """A line-level dataset whose regex captures Label / Timestamp / Content groups."""

    name: str
    regex: re.Pattern


# BGL: <Label> <Timestamp> <Date> <Node> <Time> <NodeRepeat> <Type> <Component> <Level> <Content>
BGL_REGEX = re.compile(
    r"^(?P<Label>\S+)\s+(?P<Timestamp>\d+)\s+(?P<Date>\S+)\s+"
    r"(?P<Node>\S+)\s+(?P<Time>\S+)\s+(?P<NodeRepeat>\S+)\s+(?P<Type>\S+)\s+"
    r"(?P<Component>\S+)\s+(?P<Level>\S+)\s+(?P<Content>.*)$"
)

# Thunderbird and Spirit share the same format:
# <Label> <Timestamp> <Date> <User> <Month> <Day> <Time> <Location> <Content>
TB_SPIRIT_REGEX = re.compile(
    r"^(?P<Label>\S+)\s+(?P<Timestamp>\d+)\s+(?P<Date>\S+)\s+(?P<User>\S+)\s+"
    r"(?P<Month>\S+)\s+(?P<Day>\S+)\s+(?P<Time>\S+)\s+(?P<Location>\S+)\s+(?P<Content>.*)$"
)

LINE_SPECS: dict[str, LineDatasetSpec] = {
    "BGL": LineDatasetSpec("BGL", BGL_REGEX),
    "Thunderbird": LineDatasetSpec("Thunderbird", TB_SPIRIT_REGEX),
    "Spirit": LineDatasetSpec("Spirit", TB_SPIRIT_REGEX),
}

SESSION_DATASETS = {"HDFS"}

ALL_DATASETS = list(LINE_SPECS) + sorted(SESSION_DATASETS)

# Default log file name per dataset (under data/<name>/); used when --data-path is omitted.
DEFAULT_LOG_FILE = {
    "BGL": "BGL.log",
    "Thunderbird": "Thunderbird.log",
    "Spirit": "spirit2",
    "HDFS": "HDFS.log",
}
HDFS_LABEL_FILE = "anomaly_label.csv"


def is_session_dataset(name: str) -> bool:
    return name in SESSION_DATASETS


def get_line_spec(name: str) -> LineDatasetSpec:
    if name not in LINE_SPECS:
        raise ValueError(f"unknown line dataset {name!r}; available: {list(LINE_SPECS)}")
    return LINE_SPECS[name]


def default_data_path(name: str) -> str:
    return f"data/{name}/{DEFAULT_LOG_FILE.get(name, name + '.log')}"


def default_label_path(name: str) -> str:
    return f"data/{name}/{HDFS_LABEL_FILE}"
