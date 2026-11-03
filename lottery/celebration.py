import math
import random
import sys
import time
from collections import Counter
from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, QRectF, QTimer, Qt, QUrl
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget
from PySide6.QtMultimedia import QSoundEffect


class Celebration(QWidget):
    def __init__(self, parent, audio=True):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        parent.installEventFilter(self)
        self.anim = QTimer(self)
        self.anim.setInterval(33)
        self.anim.timeout.connect(self.update)
        self.close_timer = QTimer(self)
        self.close_timer.setSingleShot(True)
        self.close_timer.setInterval(5000)
        self.close_timer.timeout.connect(self.finish)
        self.sound = None
        if audio:
            path = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / 'assets' / 'celebration.wav'
            if path.exists():
                self.sound = QSoundEffect(self)
                self.sound.setSource(QUrl.fromLocalFile(str(path)))
                self.sound.setVolume(0.65)
        self.particles = []
        self.title = ''
        self.subtitle = ''
        self.hide()

    def eventFilter(self, watched, event):
        if watched is self.parent() and event.type() == QEvent.Type.Resize:
            self.setGeometry(self.parent().rect())
        return False

    def show_wins(self, wins):
        if not wins:
            return
        counts = Counter(item['prize'] for item in wins)
        order = ['一等奖','二等奖','三等奖','四等奖','五等奖','六等奖','福运奖']
        first = next(name for name in order if name in counts)
        self.title = '恭喜！号码命中' + first
        self.subtitle = '  ·  '.join(f'{name} {counts[name]} 注' for name in order if counts[name])
        issues = sorted({item['draw_code'] for item in wins})
        self.issue_text = '开奖期号：' + '、'.join(issues)
        rng = random.Random()
        self.particles = [(rng.random(), rng.uniform(-1.1, 0.05), rng.uniform(0.28, 0.66),
                           rng.uniform(16, 37), rng.uniform(-25, 25), rng.random()*6.28) for _ in range(35)]
        self.started = time.monotonic()
        self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()
        self.anim.start()
        self.close_timer.start()
        if self.sound:
            self.sound.play()

    def finish(self):
        self.anim.stop()
        self.close_timer.stop()
        if self.sound:
            self.sound.stop()
        self.hide()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(18, 31, 24, 210))
        elapsed = time.monotonic() - self.started
        for x, start, speed, size, tilt, phase in self.particles:
            y = ((start + elapsed * speed) % 1.5 - 0.15) * h
            xpos = x*w + math.sin(elapsed*2 + phase)*16
            p.save()
            p.translate(xpos, y)
            p.rotate(tilt + math.sin(elapsed*3 + phase)*12)
            self.draw_ingot(p, size)
            p.restore()
        p.setPen(QColor('#fff2b8'))
        font = QFont('Microsoft YaHei', max(22, min(42, w//22)))
        font.setBold(True)
        p.setFont(font)
        p.drawText(QRectF(20, h*0.34, w-40, 80), Qt.AlignmentFlag.AlignCenter, self.title)
        p.setPen(QColor('#fff9de'))
        p.setFont(QFont('Microsoft YaHei', 16))
        p.drawText(QRectF(20, h*0.34+78, w-40, 35), Qt.AlignmentFlag.AlignCenter, self.subtitle)
        p.setFont(QFont('Microsoft YaHei', 11))
        p.drawText(QRectF(20, h*0.34+120, w-40, 28), Qt.AlignmentFlag.AlignCenter, self.issue_text)
        p.drawText(QRectF(20, h*0.34+150, w-40, 28), Qt.AlignmentFlag.AlignCenter, '如已购买对应彩票，请以官方公告和彩票凭证核实。')
        p.end()

    @staticmethod
    def draw_ingot(p, size):
        gold = QLinearGradient(0, -size*0.45, 0, size*0.45)
        gold.setColorAt(0, QColor('#fff09e'))
        gold.setColorAt(0.42, QColor('#f4c343'))
        gold.setColorAt(1, QColor('#b77110'))
        path = QPainterPath()
        path.moveTo(-size, -size*0.15)
        path.cubicTo(-size*0.72, size*0.10, -size*0.50, size*0.23, 0, size*0.20)
        path.cubicTo(size*0.50, size*0.23, size*0.72, size*0.10, size, -size*0.15)
        path.cubicTo(size*0.86, size*0.55, size*0.62, size*0.64, 0, size*0.66)
        path.cubicTo(-size*0.62, size*0.64, -size*0.86, size*0.55, -size, -size*0.15)
        p.setPen(QPen(QColor('#9e6719'), 1))
        p.setBrush(gold)
        p.drawPath(path)
        p.setBrush(QColor('#ffe384'))
        p.drawEllipse(QRectF(-size*0.45, -size*0.08, size*0.9, size*0.30))
