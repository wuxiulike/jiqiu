import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtWidgets import QApplication
from lottery.today_ui import TodayPanel


class Sound:
    def __init__(self): self.plays = 0; self.stops = 0
    def play(self): self.plays += 1
    def stop(self): self.stops += 1


def test_highlights_only_numbers_changed_by_ai():
    app = QApplication.instance() or QApplication([])
    panel = TodayPanel()
    panel.minimum_roll_ms = 0
    panel.begin()
    assert panel.stamp.isHidden()
    initial = [((1, 3, 5, 7, 9, 11), 6)]
    final = [{'red': [1, 3, 5, 7, 9, 12], 'blue': 8}]
    panel.complete(final, initial)
    for _ in range(7): panel.tick()
    assert [bool(b.property('aiAdjusted')) for b in panel.ball_rows[0]] == [False, False, False, False, False, True, True]
    assert not panel.stamp.isHidden()
    panel.slider.setValue(2)
    assert panel.stamp.isHidden()
    assert panel.legend.isHidden()
    assert all(b.text() == '?' for row in panel.ball_rows for b in row)
    panel.begin()
    assert panel.stamp.isHidden()
    assert all(not b.property('aiAdjusted') for b in panel.ball_rows[0])
    panel.fail('cancel')


def test_same_red_numbers_in_different_order_are_not_adjustments():
    app = QApplication.instance() or QApplication([])
    panel = TodayPanel()
    panel.minimum_roll_ms = 0
    panel.begin()
    panel.complete([{'red':[1,3,5,7,9,11], 'blue':6}], [((11, 9, 7, 5, 3, 1), 6)])
    for _ in range(7): panel.tick()
    assert all(not b.property('aiAdjusted') for b in panel.ball_rows[0])


def test_sound_lifecycle_success_and_failure():
    app = QApplication.instance() or QApplication([])
    panel = TodayPanel()
    panel.rolling_sound, panel.finish_sound = Sound(), Sound()
    panel.minimum_roll_ms = 0
    panel.begin()
    panel.start_wheel()
    assert panel.rolling_sound.plays == 1
    panel.complete([{'red':[1,2,3,4,5,6], 'blue':7}], [((1,2,3,4,5,6),7)])
    for _ in range(7): panel.tick()
    assert panel.rolling_sound.stops >= 1
    assert panel.finish_sound.plays == 1
    panel.begin()
    panel.start_wheel()
    panel.fail('test')
    assert panel.rolling_sound.stops >= 2
    assert panel.finish_sound.plays == 1
    assert panel.stamp.isHidden()
