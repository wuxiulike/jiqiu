import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer
from lottery.ai import chat_stream
from lottery.core import Draw, Store
from lottery.ui import MainWindow


def test_chat_stream_accumulates_real_model_content_and_progress():
    chunks = ['{"analysis":"基于', '历史走势",', '"tickets":[]}']
    class Response:
        encoding = None
        def raise_for_status(self): pass
        def iter_lines(self, decode_unicode=False):
            for chunk in chunks:
                yield 'data: ' + json.dumps({'choices': [{'delta': {'content': chunk}}]}, ensure_ascii=False)
            yield 'data: [DONE]'
        def close(self): pass
    calls, progress = [], []
    def post(url, **kw):
        calls.append(kw)
        return Response()
    result = chat_stream('https://example.com/v1', 'model', 'secret', {'x': 1}, progress.append, post=post)
    assert result == ''.join(chunks)
    assert '历史走势' in progress[-1]
    assert calls[0]['json']['stream'] is True


def test_chat_stream_rejects_incomplete_or_filtered_stream():
    class Response:
        encoding = None
        def __init__(self, event): self.event = event
        def raise_for_status(self): pass
        def iter_lines(self, decode_unicode=False):
            yield 'data: ' + json.dumps(self.event)
            yield 'data: [DONE]'
        def close(self): pass
    event = {'choices': [{'delta': {'content': '{}'}, 'finish_reason': 'content_filter'}]}
    with pytest.raises(ValueError):
        chat_stream('https://example.com/v1', 'm', 'key', {}, lambda x: None, post=lambda *a, **k: Response(event))


def test_chat_stream_reads_real_sse_from_local_server():
    seen = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            seen.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.end_headers()
            for part in ['{"analysis":"中文', '走势","tickets":[]}']:
                payload = json.dumps({'choices':[{'delta':{'content':part}}]}, ensure_ascii=False)
                self.wfile.write(('data: ' + payload + '\n\n').encode('utf-8'))
            self.wfile.write(b'data: [DONE]\n\n')
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        progress = []
        result = chat_stream(f'http://127.0.0.1:{server.server_port}/v1', 'model', 'key', {'候选号码':[1]}, progress.append)
        assert json.loads(result)['analysis'] == '中文走势'
        assert progress[-1] == '中文走势'
        assert seen[0]['stream'] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_home_initial_balls_and_slider(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(Store(tmp_path / 'db.sqlite3'), auto_sync=False)
    assert window.today.slider.minimum() == 1 and window.today.slider.maximum() == 5
    window.today.slider.setValue(3)
    assert len(window.today.ball_rows) == 3
    assert all(ball.text() == '?' for row in window.today.ball_rows for ball in row)
    window.today.begin()
    window.today.tick()
    assert [ball.text() for ball in window.today.ball_rows[0]] == ['01'] * 7
    for _ in range(16): window.today.tick()
    assert window.today.ball_rows[0][0].text() == '17'
    assert window.today.ball_rows[0][6].text() == '01'
    window.today.fail('test')
    window.close()


def test_home_local_generation_then_model_result(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    store = Store(tmp_path / 'db.sqlite3')
    store.save([Draw('2024001', '2024-01-02', (1,2,3,4,5,6), 7)])
    window = MainWindow(store, auto_sync=False)
    window.sync_verified = True
    window.today.slider.setValue(1)
    monkeypatch.setattr(window, 'model_config', lambda: ('https://example.com/v1', 'm', 'key'))
    monkeypatch.setattr('lottery.ui.verify_current_issue', lambda code: True)
    captured = []
    def stream(base, model, key, summary, progress):
        captured.append(summary)
        progress('基于历史进行分析。')
        return json.dumps({'analysis':'基于历史进行分析。','tickets':[{'red':[2,4,6,8,10,12],'blue':9,'reason':'仅供娱乐'}]}, ensure_ascii=False)
    monkeypatch.setattr('lottery.ui.chat_stream', stream)
    window.today.minimum_roll_ms = 0
    window.start_today()
    loop = QEventLoop()
    def check():
        if window.today.is_finished and not window.threads: loop.quit()
        else: QTimer.singleShot(20, check)
    QTimer.singleShot(20, check)
    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    assert captured[0]['程序算法结果']['候选号码']
    assert len(captured[0]['逐期走势']) == 1
    assert [b.text() for b in window.today.ball_rows[0]] == ['02','04','06','08','10','12','09']
    assert '基于历史进行分析' in window.today.log.toPlainText()
    assert '程序初选' in window.today.log.toPlainText()
    from lottery.awards import selections
    assert [s['status'] for s in selections(store)] == ['pending', 'preview']
    window.close()


def test_home_refuses_model_call_if_official_issue_has_changed(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    store = Store(tmp_path / 'db.sqlite3')
    store.save([Draw('2024001', '2024-01-02', (1,2,3,4,5,6), 7)])
    window = MainWindow(store, auto_sync=False)
    window.sync_verified = True
    monkeypatch.setattr(window, 'model_config', lambda: ('https://example.com/v1', 'm', 'key'))
    monkeypatch.setattr('lottery.ui.verify_current_issue', lambda code: False)
    called = []
    monkeypatch.setattr('lottery.ui.chat_stream', lambda *args: called.append(True))
    window.start_today()
    loop = QEventLoop()
    def check():
        if not window.threads: loop.quit()
        else: QTimer.singleShot(10, check)
    QTimer.singleShot(10, check)
    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    assert called == []
    assert '最新期已变化' in window.today.log.toPlainText()
    from lottery.awards import selections
    assert all(s['status'] == 'preview' for s in selections(store))
    window.close()


def test_home_does_not_save_final_if_issue_changes_during_ai(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    store = Store(tmp_path / 'db.sqlite3')
    store.save([Draw('2024001', '2024-01-02', (1,2,3,4,5,6), 7)])
    window = MainWindow(store, auto_sync=False)
    window.sync_verified = True
    monkeypatch.setattr(window, 'model_config', lambda: ('https://example.com/v1', 'm', 'key'))
    outcomes = iter([True, False])
    monkeypatch.setattr('lottery.ui.verify_current_issue', lambda code: next(outcomes))
    monkeypatch.setattr('lottery.ui.chat_stream', lambda *args: '{"analysis":"x","tickets":[{"red":[1,2,3,4,5,6],"blue":7,"reason":"x"}]}')
    window.start_today()
    loop = QEventLoop()
    def check():
        if not window.threads: loop.quit()
        else: QTimer.singleShot(10, check)
    QTimer.singleShot(10, check)
    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    assert '分析期间官网最新期已变化' in window.today.log.toPlainText()
    from lottery.awards import selections
    assert all(s['status'] == 'preview' for s in selections(store))
    window.close()


def test_home_model_failure_stops_and_discloses_unfinished_ai(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    store = Store(tmp_path / 'db.sqlite3')
    store.save([Draw('2024001', '2024-01-02', (1,2,3,4,5,6), 7)])
    window = MainWindow(store, auto_sync=False)
    window.sync_verified = True
    monkeypatch.setattr(window, 'model_config', lambda: ('https://example.com/v1', 'm', ''))
    window.start_today()
    assert not window.today.rolling
    assert all(b.text() == '?' for b in window.today.ball_rows[0])
    assert 'AI 未完成' in window.today.log.toPlainText()
    assert '程序初选' in window.today.log.toPlainText()
    window.close()
