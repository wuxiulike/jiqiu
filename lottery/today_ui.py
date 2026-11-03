import time
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QRectF, QUrl
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QPushButton, QSlider, QTextEdit, QVBoxLayout, QWidget)
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtMultimedia import QSoundEffect


class Stamp(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(154, 154)
        policy = self.sizePolicy()
        policy.setRetainSizeWhenHidden(True)
        self.setSizePolicy(policy)
        self.timer = QTimer(self)
        self.timer.setInterval(25)
        self.timer.timeout.connect(self.animate)
        self.started = 0
        self.hide()

    def reveal(self):
        self.started = time.monotonic()
        self.show()
        self.timer.start()
        self.update()

    def animate(self):
        if time.monotonic() - self.started >= 0.35:
            self.timer.stop()
        self.update()

    def paintEvent(self, event):
        elapsed = min(1.0, (time.monotonic() - self.started) / 0.35)
        scale = 1.18 - 0.18 * (1 - (1 - elapsed) ** 3)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(min(1, elapsed * 3))
        p.translate(self.width() / 2, self.height() / 2)
        p.rotate(-11)
        p.scale(scale, scale)
        color = QColor('#b9473b')
        p.setPen(QPen(color, 4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(-56, -56, 112, 112), 8, 8)
        p.setPen(QPen(color, 1.2))
        p.drawRoundedRect(QRectF(-49, -49, 98, 98), 4, 4)
        font = QFont('KaiTi', 30)
        font.setBold(True)
        p.setFont(font)
        p.setPen(color)
        p.drawText(QRectF(-48, -47, 96, 94), Qt.AlignmentFlag.AlignCenter, '吉号\n已选')
        p.end()


def make_sound(parent, filename, volume, loop=False):
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    sound = QSoundEffect(parent)
    sound.setSource(QUrl.fromLocalFile(str(root / 'assets' / filename)))
    sound.setVolume(volume)
    if loop:
        sound.setLoopCount(QSoundEffect.Infinite.value)
    return sound


class TodayPanel(QWidget):
    startRequested = Signal()

    def __init__(self):
        super().__init__()
        self.ball_rows = []
        self.rolling = False
        self.is_finished = False
        self.minimum_roll_ms = 1500
        self.target = None
        self.settled = 0
        self.ticks = 0
        self.messages = []
        self.ai_progress = ''
        self.adjusted = []
        self.rolling_sound = make_sound(self, 'rolling.wav', 0.45, loop=True)
        self.finish_sound = make_sound(self, 'complete.wav', 0.7)
        self.timer = QTimer(self)
        self.timer.setInterval(70)
        self.timer.timeout.connect(self.tick)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        controls = QFrame()
        controls.setObjectName('todayControls')
        row = QHBoxLayout(controls)
        row.setContentsMargins(20, 15, 20, 15)
        row.setSpacing(15)
        left = QVBoxLayout()
        left.setSpacing(5)
        caption = QLabel('今天想选几注？')
        caption.setObjectName('todayCaption')
        left.addWidget(caption)
        slider_row = QHBoxLayout()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 5)
        self.slider.setValue(1)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.setTickInterval(1)
        slider_row.addWidget(self.slider, 1)
        self.count_label = QLabel('1 注')
        self.count_label.setObjectName('todayCount')
        self.count_label.setFixedWidth(54)
        slider_row.addWidget(self.count_label)
        left.addLayout(slider_row)
        row.addLayout(left, 1)
        self.start_button = QPushButton('开始选号  ✦')
        self.start_button.setObjectName('todayStart')
        self.start_button.setMinimumSize(155, 58)
        shadow = QGraphicsDropShadowEffect(self.start_button)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(28, 77, 55, 95))
        self.start_button.setGraphicsEffect(shadow)
        row.addWidget(self.start_button)
        layout.addWidget(controls)

        self.board = QFrame()
        self.board.setObjectName('todayBoard')
        board_row = QHBoxLayout(self.board)
        board_row.setContentsMargins(18, 10, 18, 10)
        rows_holder = QWidget()
        rows_holder.setObjectName('ballRow')
        rows_holder.setMaximumWidth(445)
        self.board_layout = QVBoxLayout(rows_holder)
        self.board_layout.setContentsMargins(0, 0, 0, 0)
        self.board_layout.setSpacing(5)
        board_row.addWidget(rows_holder)
        stamp_holder = QWidget()
        stamp_holder.setObjectName('ballRow')
        stamp_layout = QHBoxLayout(stamp_holder)
        stamp_layout.setContentsMargins(0, 0, 0, 0)
        stamp_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stamp = Stamp()
        stamp_layout.addWidget(self.stamp)
        board_row.addWidget(stamp_holder, 1)
        layout.addWidget(self.board)

        log_title = QHBoxLayout()
        title = QLabel('选号对话')
        title.setObjectName('todayCaption')
        log_title.addWidget(title)
        self.phase = QLabel('等待开始')
        self.phase.setObjectName('todayPhase')
        log_title.addWidget(self.phase)
        self.legend = QLabel('黄色数字：AI 调整')
        self.legend.setObjectName('todayPhase')
        self.legend.hide()
        log_title.addWidget(self.legend)
        log_title.addStretch()
        layout.addLayout(log_title)
        self.log = QTextEdit()
        self.log.setObjectName('todayLog')
        self.log.setReadOnly(True)
        self.log.setPlaceholderText('程序先生成初选号码，再由模型结合历史走势分析。默认使用近 50 期，可在“走势图”调整。')
        layout.addWidget(self.log, 1)
        self.slider.valueChanged.connect(self.reset_rows)
        self.start_button.clicked.connect(self.startRequested.emit)
        self.reset_rows(1)

    def reset_rows(self, count):
        self.count_label.setText(f'{count} 注')
        self.stamp.hide()
        self.stamp.timer.stop()
        self.legend.hide()
        self.phase.setText('等待开始')
        self.messages = []
        self.ai_progress = ''
        self.render_log()
        while self.board_layout.count():
            item = self.board_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.ball_rows = []
        for i in range(count):
            holder = QWidget()
            holder.setObjectName('ballRow')
            row = QHBoxLayout(holder)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            number = QLabel(f'{i+1:02d}')
            number.setObjectName('rowNumber')
            number.setFixedWidth(30)
            row.addWidget(number)
            balls = []
            for j in range(7):
                ball = QLabel('?')
                ball.setObjectName('todayBlue' if j == 6 else 'todayRed')
                ball.setProperty('aiAdjusted', False)
                ball.setFixedSize(42, 42)
                ball.setAlignment(Qt.AlignmentFlag.AlignCenter)
                if j == 6:
                    row.addSpacing(9)
                row.addWidget(ball)
                balls.append(ball)
            row.addStretch()
            self.board_layout.addWidget(holder)
            self.ball_rows.append(balls)

    def write(self, text):
        self.messages.append(text)
        self.render_log()

    def render_log(self):
        text = '\n\n'.join(self.messages)
        if self.ai_progress:
            text += '\n\nAI 分析\n' + self.ai_progress
        self.log.setPlainText(text)
        bar = self.log.verticalScrollBar()
        bar.setValue(bar.maximum())

    def set_progress(self, text):
        self.ai_progress = text
        self.render_log()

    def begin(self):
        self.rolling_sound.stop()
        self.finish_sound.stop()
        self.stamp.hide()
        self.stamp.timer.stop()
        self.legend.hide()
        self.reset_rows(self.slider.value())
        self.messages = []
        self.ai_progress = ''
        self.render_log()
        self.rolling = True
        self.is_finished = False
        self.target = None
        self.settled = 0
        self.ticks = 0
        self.started = time.monotonic()
        self.phase.setText('程序初选中')
        self.start_button.setEnabled(False)
        self.slider.setEnabled(False)
        QTimer.singleShot(300, self.start_wheel)

    def start_wheel(self):
        if self.rolling and not self.timer.isActive():
            self.timer.start()
            self.rolling_sound.play()

    def tick(self):
        if not self.rolling:
            return
        self.ticks += 1
        balls = [ball for row in self.ball_rows for ball in row]
        for i, ball in enumerate(balls):
            if i < self.settled:
                continue
            maximum = 16 if i % 7 == 6 else 33
            ball.setText(f'{((self.ticks - 1) % maximum) + 1:02d}')
        if self.target and (time.monotonic() - self.started) * 1000 >= self.minimum_roll_ms:
            values = [number for ticket in self.target for number in ticket['red'] + [ticket['blue']]]
            ball = balls[self.settled]
            ball.setText(f'{values[self.settled]:02d}')
            ball.setProperty('aiAdjusted', self.adjusted[self.settled])
            ball.style().unpolish(ball)
            ball.style().polish(ball)
            ball.update()
            self.settled += 1
            if self.settled == len(balls):
                self.timer.stop()
                self.rolling_sound.stop()
                self.finish_sound.play()
                self.stamp.reveal()
                if any(self.adjusted):
                    self.legend.show()
                self.rolling = False
                self.is_finished = True
                self.phase.setText('分析完成 · 仅供娱乐')
                self.start_button.setEnabled(True)
                self.slider.setEnabled(True)

    def complete(self, tickets, initial):
        self.target = tickets
        self.adjusted = []
        for ticket, (original_red, original_blue) in zip(tickets, initial):
            self.adjusted.extend(number not in original_red for number in ticket['red'])
            self.adjusted.append(ticket['blue'] != original_blue)
        self.phase.setText('结果揭晓中')

    def fail(self, message):
        self.timer.stop()
        self.rolling_sound.stop()
        self.stamp.hide()
        self.stamp.timer.stop()
        self.legend.hide()
        self.rolling = False
        self.is_finished = True
        self.target = None
        for row in self.ball_rows:
            for ball in row:
                ball.setText('?')
        self.phase.setText('AI 未完成')
        self.ai_progress = ''
        self.write('AI 未完成 · ' + message + '\n上方号码未揭晓；程序初选见上方记录。')
        self.start_button.setEnabled(True)
        self.slider.setEnabled(True)
