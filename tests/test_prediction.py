import pytest
from lottery.ai import parse_prediction, SYSTEM_PROMPT, prediction_input
from lottery.core import Draw


def test_model_prediction_accepts_json_fence_and_formats_valid_tickets():
    text = '```json\n{"analysis":"历史描述", "tickets":[{"red":[1,2,3,4,5,6],"blue":7,"reason":"随机选择"}]}\n```'
    result = parse_prediction(text, 1)
    assert result['tickets'][0]['red'] == [1, 2, 3, 4, 5, 6]
    assert result['tickets'][0]['blue'] == 7
    assert '独立' in SYSTEM_PROMPT


@pytest.mark.parametrize('text', [
    '{"analysis":"x","tickets":[{"red":[1,1,3,4,5,6],"blue":7,"reason":"x"}]}',
    '{"analysis":"x","tickets":[{"red":[1,2,3,4,5,34],"blue":7,"reason":"x"}]}',
    '{"analysis":"x","tickets":[{"red":[1,2,3,4,5,6],"blue":17,"reason":"x"}]}',
    '{"analysis":"x","tickets":[]}',
    'not json',
])
def test_invalid_predictions_are_rejected(text):
    with pytest.raises(ValueError):
        parse_prediction(text, 1)


def test_prediction_input_carries_recent_draws_and_separates_local_tickets():
    draws = [Draw('2024001', '2024-01-02', (1, 2, 3, 4, 5, 6), 7)]
    summary = prediction_input(draws, 50, 2, {'候选号码': ['local']})
    assert summary['期数'] == 1
    assert summary['候选注数'] == 2
    assert summary['逐期走势'][0]['blue'] == 7
    assert summary['程序算法结果']['候选号码'] == ['local']
