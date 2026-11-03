import pytest
from lottery.ai import chat, normalize_base_url


def test_base_url_supports_v1_and_full_endpoint():
    assert normalize_base_url('https://example.com/v1/') == 'https://example.com/v1/chat/completions'
    assert normalize_base_url('https://example.com/v1/chat/completions') == 'https://example.com/v1/chat/completions'


def test_chat_sends_grounded_summary_and_reads_answer():
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'choices': [{'message': {'content': '结果仅供娱乐'}}]}
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()
    result = chat('https://example.com/v1', 'model', 'secret', {'期数': 10}, post=post)
    assert result == '结果仅供娱乐'
    assert calls[0][1]['json']['messages'][1]['content'].find('10') >= 0
    assert '独立' in calls[0][1]['json']['messages'][0]['content']


def test_invalid_model_response_is_reported():
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'choices': []}
    with pytest.raises(ValueError):
        chat('https://example.com/v1', 'model', 'secret', {}, post=lambda *a, **k: Response())
