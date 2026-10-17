from athanor.utils.logging import log_jsonl


def test_log_jsonl_writes_real_newlines(tmp_path):
    p = tmp_path / "x.jsonl"
    log_jsonl(str(p), {"a": 1})
    log_jsonl(str(p), {"a": 2})
    assert p.read_text().splitlines() == ['{"a": 1}', '{"a": 2}']
