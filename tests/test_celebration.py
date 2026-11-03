import os
import wave
from pathlib import Path
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication, QWidget
from lottery.celebration import Celebration
from lottery.core import Draw, Store
from lottery.awards import save_selection, selections
from lottery.ui import MainWindow
from PySide6.QtCore import QEventLoop, QTimer


def test_celebration_is_timed_and_mentions_actual_prize():
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    parent.resize(800, 600)
    parent.show()
    overlay = Celebration(parent, audio=False)
    overlay.show_wins([{'prize': '六等奖', 'draw_code':'2024002'}])
    app.processEvents()
    assert overlay.isVisible()
    assert overlay.close_timer.interval() == 5000
    assert '六等奖' in overlay.title
    overlay.close_timer.timeout.emit()
    assert not overlay.isVisible()
    parent.close()


def test_celebration_audio_is_nonempty_and_five_seconds():
    path = Path(__file__).resolve().parents[1] / 'assets' / 'celebration.wav'
    with wave.open(str(path), 'rb') as sound:
        assert 4.9 <= sound.getnframes() / sound.getframerate() <= 5.0
        assert any(sound.readframes(sound.getnframes()))


def test_sync_checks_saved_numbers_and_announces_only_once(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    store = Store(tmp_path / 'history.sqlite3')
    a = Draw('2024001', '2024-01-02', (10,11,12,13,14,15), 2)
    b = Draw('2024002', '2024-01-04', (1,2,3,4,5,6), 7)
    store.save([a])
    store.set_meta('full_sync', 'complete')
    save_selection(store, a.code, [{'red':[1,2,3,4,5,6], 'blue':7}], 'AI')
    class Client:
        def page(self, page):
            self.latest_code = b.code
            return [b, a], 1
    monkeypatch.setattr('lottery.ui.OfficialClient', Client)
    monkeypatch.setattr('lottery.ui.verify_next_issue', lambda client, baseline, candidate: (b, False))
    window = MainWindow(store, auto_sync=False)
    announcements = []
    monkeypatch.setattr(window.celebration, 'show_wins', lambda wins: announcements.extend(wins))
    def run_sync():
        loop = QEventLoop()
        window.start_sync()
        def check():
            if not window.threads: loop.quit()
            else: QTimer.singleShot(10, check)
        QTimer.singleShot(10, check)
        QTimer.singleShot(5000, loop.quit)
        loop.exec()
    run_sync()
    assert window.sync_verified
    assert len(announcements) == 1 and announcements[0]['prize'] == '一等奖'
    assert selections(store)[0]['draw_code'] == b.code
    run_sync()
    assert len(announcements) == 1
    window.close()
