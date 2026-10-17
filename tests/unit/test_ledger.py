import json

from athanor.ledger import GENESIS_HASH, LedgerWriter, read_ledger, verify_ledger


def _write(path, n=4):
    w = LedgerWriter(str(path))
    for i in range(n):
        w.append({"id": f"c{i}", "verdict": "APPROVE", "h7": 0.8 + i / 100})
    return w


def test_chain_links_and_verifies(tmp_path):
    p = tmp_path / "ledger.jsonl"
    w = _write(p)
    rows = read_ledger(str(p))
    assert rows[0]["prev_hash"] == GENESIS_HASH
    assert all(rows[i]["prev_hash"] == rows[i - 1]["row_hash"] for i in range(1, len(rows)))
    res = verify_ledger(str(p))
    assert res.ok and res.rows == 4 and res.head == w.head


def _rewrite(p, rows):
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_detects_edit(tmp_path):
    p = tmp_path / "ledger.jsonl"
    _write(p)
    rows = read_ledger(str(p))
    rows[2]["verdict"] = "REJECT"
    _rewrite(p, rows)
    res = verify_ledger(str(p))
    assert not res.ok and res.first_bad_seq == 2


def test_detects_deletion_and_reorder(tmp_path):
    p = tmp_path / "ledger.jsonl"
    _write(p)
    rows = read_ledger(str(p))
    _rewrite(p, rows[:1] + rows[2:])
    assert verify_ledger(str(p)).first_bad_seq == 1
    _rewrite(p, [rows[1], rows[0]] + rows[2:])
    assert verify_ledger(str(p)).first_bad_seq == 0


def test_reserved_fields_rejected(tmp_path):
    w = LedgerWriter(str(tmp_path / "l.jsonl"))
    try:
        w.append({"row_hash": "x"})
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_unreadable_ledger(tmp_path):
    res = verify_ledger(str(tmp_path / "missing.jsonl"))
    assert not res.ok
