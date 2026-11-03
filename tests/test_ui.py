import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QThread, QTimer
from lottery.core import Draw, Store
from lottery.ui import MainWindow
from lottery.trends import CHARTS


def test_brand_name_and_window_icon(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(store=Store(tmp_path / 'draws.db'), auto_sync=False)
    assert window.windowTitle() == '吉球 · 双色球数据实验室'
    assert not window.windowIcon().isNull()
    assert window.findChild(__import__('PySide6.QtWidgets', fromlist=['QLabel']).QLabel, 'brand').text().replace(' ', '') == '吉球'
    window.close()


def test_desktop_can_show_history_and_generate_numbers(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    store = Store(tmp_path / 'draws.db')
    store.save([Draw('2024001', '2024-01-01', (1, 2, 3, 4, 5, 6), 7)])
    window = MainWindow(store=store, auto_sync=False)
    window.sync_verified = True
    monkeypatch.setattr('lottery.ui.verify_current_issue', lambda code: True)
    window.show()
    app.processEvents()
    assert window.table.rowCount() == 1
    window.generate_tickets()
    assert len(window.tickets) == 5
    assert window.summary['数据范围'] == ['2024001', '2024001']
    while window.threads:
        app.processEvents()
    window.close()


def test_worker_completion_callback_runs_on_ui_thread(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(store=Store(tmp_path / 'draws.db'), auto_sync=False)
    loop = QEventLoop()
    called = []
    def done(result):
        called.append(QThread.currentThread() == app.thread())
        loop.quit()
    window.launch(lambda progress: 1, done)
    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    assert called == [True]
    while window.threads:
        app.processEvents()
    window.close()


def test_trend_page_switches_chart_and_uses_prior_history(tmp_path):
    app = QApplication.instance() or QApplication([])
    store = Store(tmp_path / 'draws.db')
    store.save([Draw('2024001', '2024-01-02', (1, 2, 3, 4, 5, 6), 7),
                Draw('2024002', '2024-01-04', (2, 3, 4, 5, 6, 7), 8)])
    window = MainWindow(store=store, auto_sync=False)
    assert window.trends.chart.count() == len(CHARTS)
    assert window.trends.table.rowCount() == 2
    window.trends.chart.setCurrentText('蓝球走势')
    assert window.trends.table.columnCount() >= 18
    window.trends.chart.setCurrentText('周二走势')
    assert window.trends.table.rowCount() == 1
    window.close()


def test_ai_prediction_displays_validated_model_ticket(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    store = Store(tmp_path / 'draws.db')
    store.save([Draw('2024001', '2024-01-02', (1, 2, 3, 4, 5, 6), 7)])
    window = MainWindow(store=store, auto_sync=False)
    window.ai_count.setValue(1)
    window.sync_verified = True
    monkeypatch.setattr('lottery.ui.verify_current_issue', lambda code: True)
    monkeypatch.setattr(window, 'model_config', lambda: ('https://example.com/v1', 'model', 'key'))
    monkeypatch.setattr('lottery.ui.chat', lambda *args: '{"analysis":"历史描述", "tickets":[{"red":[1,2,3,4,5,6],"blue":7,"reason":"娱乐选号"}]}')
    window.run_ai()
    loop = QEventLoop()
    def check():
        if not window.threads:
            loop.quit()
        else:
            QTimer.singleShot(10, check)
    QTimer.singleShot(10, check)
    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    assert 'AI 候选号码' in window.ai_text.toPlainText()
    assert '01  02  03  04  05  06  +  07' in window.ai_text.toPlainText()
    window.close()


def test_invalid_ai_output_is_not_presented_as_prediction(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    store = Store(tmp_path / 'draws.db')
    store.save([Draw('2024001', '2024-01-02', (1, 2, 3, 4, 5, 6), 7)])
    window = MainWindow(store=store, auto_sync=False)
    window.ai_count.setValue(1)
    window.sync_verified = True
    monkeypatch.setattr('lottery.ui.verify_current_issue', lambda code: True)
    monkeypatch.setattr(window, 'model_config', lambda: ('https://example.com/v1', 'model', 'key'))
    monkeypatch.setattr('lottery.ui.chat', lambda *args: '{"analysis":"x","tickets":[{"red":[1,1,3,4,5,6],"blue":7,"reason":"x"}]}')
    window.run_ai()
    loop = QEventLoop()
    def check():
        if not window.threads:
            loop.quit()
        else:
            QTimer.singleShot(10, check)
    QTimer.singleShot(10, check)
    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    assert '请勿作为有效号码' in window.ai_text.toPlainText()
    assert 'AI 候选号码（仅供娱乐）' not in window.ai_text.toPlainText()
    window.close()
