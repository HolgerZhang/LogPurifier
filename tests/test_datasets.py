"""Unit tests for the dataset registry: Thunderbird/Spirit line parsing and HDFS sessions."""

from logpurifier.datasets import (
    ALL_DATASETS,
    default_data_path,
    get_line_spec,
    is_session_dataset,
)
from logpurifier.parsing import load_hdfs_sessions, parse_lines

# Real Thunderbird lines (Label "-" = normal)
TB_LINES = [
    "- 1131523501 2005.11.09 aadmin1 Nov 10 00:05:01 src@aadmin1 in.tftpd[14620]: tftp: client does not accept options",
    "- 1131524071 2005.11.09 tbird-admin1 Nov 10 00:14:31 local@tbird-admin1 postfix/postdrop[10896]: warning: unable to look up public/pickup: No such file or directory",
]

# Real Spirit lines (same format; "R_HDA_NR" is an alert tag => anomaly)
SPIRIT_LINES = [
    "- 1104566400 2005.01.01 sadmin1 Jan 1 00:00:00 sadmin1/sadmin1 CROND[30483]: (root) CMD (/home/x/bin/grab_myrinet_info)",
    "R_HDA_NR 1104566407 2005.01.01 sadmin1 Jan 1 00:00:07 sadmin1/sadmin1 kernel: hda: drive not ready for command",
]


def test_registry_membership():
    assert ALL_DATASETS == ["BGL", "Thunderbird", "Spirit", "HDFS"]
    assert is_session_dataset("HDFS")
    assert not is_session_dataset("BGL")


def test_default_data_path():
    assert default_data_path("BGL") == "data/BGL/BGL.log"
    assert default_data_path("Thunderbird") == "data/Thunderbird/Thunderbird.log"
    assert default_data_path("Spirit") == "data/Spirit/spirit2"
    assert default_data_path("HDFS") == "data/HDFS/HDFS.log"


def test_thunderbird_parse_label_timestamp_content():
    entries = parse_lines(TB_LINES, get_line_spec("Thunderbird"))
    assert len(entries) == 2
    assert [e.is_anomaly for e in entries] == [False, False]
    assert entries[0].timestamp == 1131523501.0


def test_spirit_parse_alert_tag_is_anomaly():
    entries = parse_lines(SPIRIT_LINES, get_line_spec("Spirit"))
    assert len(entries) == 2
    assert [e.is_anomaly for e in entries] == [False, True]  # "-" normal, "R_HDA_NR" alert
    assert entries[1].timestamp == 1104566407.0


def test_hdfs_sessions_group_by_block(tmp_path):
    log = tmp_path / "HDFS.log"
    log.write_text(
        "081109 203615 148 INFO dfs.DataNode: Receiving block blk_1 src: /1.2.3.4\n"
        "081109 203616 149 INFO dfs.DataNode: Receiving block blk_2 src: /1.2.3.5\n"
        "081109 203617 150 INFO dfs.DataNode: PacketResponder blk_1 terminating\n"
        "081109 203618 151 INFO dfs.DataNode: PacketResponder blk_2 terminating\n"
    )
    label = tmp_path / "anomaly_label.csv"
    label.write_text("BlockId,Label\nblk_1,Normal\nblk_2,Anomaly\n")

    seqs, labels = load_hdfs_sessions(str(log), str(label))
    assert len(seqs) == 2          # two blocks -> two sessions
    assert all(len(s) == 2 for s in seqs)
    assert sum(labels) == 1        # blk_2 is anomalous


def test_hdfs_unlabeled_block_defaults_normal(tmp_path):
    log = tmp_path / "HDFS.log"
    log.write_text("081109 203615 148 INFO dfs.DataNode: Receiving block blk_9 src: /1.2.3.4\n")
    label = tmp_path / "anomaly_label.csv"
    label.write_text("BlockId,Label\nblk_1,Normal\n")  # blk_9 absent
    seqs, labels = load_hdfs_sessions(str(log), str(label))
    assert len(seqs) == 1 and labels == [0]


def test_hdfs_pipeline_end_to_end(tmp_path):
    """run_pipeline dispatches HDFS to the session path (no window) and yields results."""
    from logpurifier.pipeline import run_pipeline

    lines, label_rows = [], ["BlockId,Label"]
    for b in range(12):
        blk = f"blk_{b}"
        lines.append(f"081109 2036{b:02d} 148 INFO dfs.DataNode: Receiving block {blk} src: /1.2.3.4")
        lines.append(f"081109 2037{b:02d} 149 INFO dfs.DataNode: PacketResponder {blk} terminating")
        label_rows.append(f"{blk},{'Anomaly' if b >= 10 else 'Normal'}")  # 10 normal, 2 anomaly
    (tmp_path / "HDFS.log").write_text("\n".join(lines) + "\n")
    (tmp_path / "anomaly_label.csv").write_text("\n".join(label_rows) + "\n")

    results, _ = run_pipeline(
        data_path=str(tmp_path / "HDFS.log"),
        dataset="HDFS",
        label_path=str(tmp_path / "anomaly_label.csv"),
        models=["OCSVM"],
        oov_min_count=1,
        artifacts_dir=str(tmp_path / "art"),
        run_id="test",
    )
    variants = {(r.model, r.variant) for r in results}
    assert ("OCSVM", "org") in variants and ("OCSVM", "cleaned") in variants
    assert (tmp_path / "art" / "HDFS" / "test" / "sessions_all.npz").exists()
