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
