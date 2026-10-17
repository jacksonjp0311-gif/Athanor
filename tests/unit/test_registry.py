from athanor.experiments.registry import validate_config


def test_validate_config_accepts_defaults():
    out = validate_config({})
    assert out['threshold_h7'] == 0.70
    assert out['dphi_mode'] == 'l2'


def test_validate_config_rejects_invalid_bounds():
    try:
        validate_config({'threshold_h7': 1.2})
    except ValueError as exc:
        assert 'threshold_h7' in str(exc)
    else:
        raise AssertionError('Expected ValueError for threshold_h7')


def test_validate_config_rejects_mode():
    try:
        validate_config({'dphi_mode': 'bad'})
    except ValueError as exc:
        assert 'dphi_mode' in str(exc)
    else:
        raise AssertionError('Expected ValueError for dphi_mode')


import pytest
from athanor.experiments.registry import load_config


def test_refine_floor_must_not_exceed_threshold():
    with pytest.raises(ValueError, match='refine_floor'):
        validate_config({'threshold_h7': 0.6, 'refine_floor': 0.7})


def test_governor_knobs_have_defaults():
    out = validate_config({})
    assert out['refine_floor'] == 0.50
    assert out['telemetry_noise'] == 0.02
    assert out['proposer_sigma'] == 0.12
    assert out['proposer_step_cap'] == 0.50


def test_run_tag_rejects_paths():
    with pytest.raises(ValueError, match='run.tag'):
        validate_config({'run': {'tag': '../escape'}})


def test_inherits_deep_merges_nested_sections(tmp_path):
    (tmp_path / 'base.yaml').write_text('archive:\n  bins: [8, 8]\n  novelty_eps: 0.05\n')
    (tmp_path / 'child.yaml').write_text('inherits: base.yaml\narchive:\n  bins: [4, 4]\n')
    cfg = load_config(str(tmp_path / 'child.yaml'))
    assert cfg['archive']['bins'] == [4, 4]
    assert cfg['archive']['novelty_eps'] == 0.05  # previously lost by shallow update
    assert 'inherits' not in cfg


def test_inherits_cycle_detected(tmp_path):
    (tmp_path / 'a.yaml').write_text('inherits: b.yaml\n')
    (tmp_path / 'b.yaml').write_text('inherits: a.yaml\n')
    with pytest.raises(ValueError, match='cycle'):
        load_config(str(tmp_path / 'a.yaml'))
