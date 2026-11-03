from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QHeaderView, QLabel, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from lottery.trends import CHARTS, trend_rows


class Sparkline(QWidget):
    def __init__(self):
        super().__init__()
        self.values = []
        self.setMinimumHeight(145)
        self.setMaximumHeight(180)

    def paintEvent(self, event):
        if not self.values:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        left, right, top, bottom = 38, w - 15, 15, h - 28
        lo, hi = min(self.values), max(self.values)
        span = max(hi - lo, 1)
        p.setPen(QPen(QColor('#d9e2d7'), 1))
        for i in range(3):
            y = top + (bottom-top)*i/2
            p.drawLine(QPointF(left, y), QPointF(right, y))
        p.setPen(QColor('#78867c'))
        p.drawText(1, top + 7, str(hi))
        p.drawText(1, bottom + 4, str(lo))
        p.setPen(QPen(QColor('#b84d3e'), 2))
        points = [QPointF(left + i*(right-left)/max(len(self.values)-1, 1),
                          bottom - (value-lo)*(bottom-top)/span) for i, value in enumerate(self.values)]
        for a, b in zip(points, points[1:]):
            p.drawLine(a, b)
        if len(points) == 1:
            p.drawEllipse(points[0], 3, 3)
        p.setPen(QColor('#78867c'))
        p.drawText(left, h-5, '较早')
        p.drawText(right-28, h-5, '最近')
        p.end()


class TrendView(QWidget):
    def __init__(self):
        super().__init__()
        self.draws = []
        self.rows = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        controls = QHBoxLayout()
        controls.addWidget(QLabel('走势图'))
        self.chart = QComboBox()
        self.chart.addItems(CHARTS)
        controls.addWidget(self.chart, 1)
        controls.addWidget(QLabel('范围'))
        self.window = QComboBox()
        self.window.addItem('近 30 期', 30)
        self.window.addItem('近 50 期', 50)
        self.window.addItem('近 100 期', 100)
        self.window.addItem('全部', 0)
        self.window.setCurrentIndex(1)
        controls.addWidget(self.window)
        layout.addLayout(controls)
        self.info = QLabel()
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        self.plot = Sparkline()
        layout.addWidget(self.plot)
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)
        self.chart.currentIndexChanged.connect(self.render)
        self.window.currentIndexChanged.connect(self.render)
        self.render()

    def set_draws(self, draws):
        self.draws = draws
        self.rows = trend_rows(draws)
        self.render()

    def selected_count(self):
        return self.window.currentData() or len(self.rows)

    def render(self):
        name = self.chart.currentText()
        rows = self.rows[-self.selected_count():] if self.rows else []
        weekdays = {'周二走势': 1, '周四走势': 3, '周日走势': 6}
        if name in weekdays:
            rows = [row for row in rows if row['weekday'] == weekdays[name]]
        self.info.setText((f'{rows[0]["code"]} — {rows[-1]["code"]} · 显示 {len(rows)} 期' if rows else '暂无符合条件的开奖记录')
                          + '  ·  遗漏“?”为未知；缺期后重新计算。质合按彩票口径将 01 归质。')
        matrix_types = {'基本走势', '红球走势', '蓝球走势', '红球遗漏', '蓝球遗漏',
                        '连号走势', '重号走势', '周二走势', '周四走势', '周日走势'}
        scalar_types = {'和值走势': 'sum', 'AC值走势': 'ac', '跨度走势': 'span', '和尾走势': 'sum_tail', '和值遗漏': 'sum'}
        self.plot.values = [r[scalar_types[name]] for r in rows] if name in scalar_types and name != '和值遗漏' else []
        self.plot.setVisible(bool(self.plot.values))
        self.plot.update()
        if name in matrix_types:
            show_red = name not in ('蓝球走势', '蓝球遗漏')
            show_blue = name in ('基本走势', '蓝球走势', '蓝球遗漏')
            columns = [('r', n) for n in range(1, 34)] if show_red else []
            if show_blue:
                columns += [('b', n) for n in range(1, 17)]
            headers = ['期号', '日期'] + [f'{"红" if kind == "r" else "蓝"}{n:02d}' for kind, n in columns]
            values = []
            for row in reversed(rows):
                cells = []
                for kind, n in columns:
                    red = kind == 'r'
                    if name == '连号走势':
                        hit = n in row['consecutive']
                    elif name == '重号走势':
                        hit = row['repeat'] is not None and n in row['repeat']
                    else:
                        hit = n in row['red'] if red else n == row['blue']
                    omission = row['red_omission' if red else 'blue_omission'][n]
                    content = f'{n:02d}' if hit else ('?' if omission is None or (name == '重号走势' and row['repeat'] is None) else str(omission))
                    cells.append((content, '#b84d3e' if red else '#386d91') if hit else (content, None))
                values.append([(row['code'], None), (row['date'], None)] + cells)
        else:
            headers = ['期号', '日期', '红球', '蓝球', '指标']
            values = []
            for row in reversed(rows):
                field = {'红球大小': ('large_small', '大:小'), '红球奇偶': ('odd_even', '奇:偶'),
                         '红球质合': ('prime_composite', '质:合'), '红球012路': ('mod3', '0:1:2'),
                         '区间走势': ('zones', '一区:二区:三区'), '尾数分布': ('tails', '尾0–9')}.get(name)
                if field:
                    indicator = field[1] + '  ' + ':'.join(map(str, row[field[0]]))
                else:
                    value = row[scalar_types[name]]
                    indicator = str(value)
                    if name == '和值遗漏':
                        indicator += f'（上次出现后的间隔：{self.previous_sum_omission(row)}）'
                values.append([(row['code'], None), (row['date'], None),
                    (' '.join(f'{n:02d}' for n in row['red']), None), (f'{row["blue"]:02d}', '#386d91'), (indicator, None)])
        self.table.clear()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(values))
        for i, row in enumerate(values):
            for j, (text, color) in enumerate(row):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if color:
                    item.setBackground(QColor(color))
                    item.setForeground(QColor('white'))
                self.table.setItem(i, j, item)

    def previous_sum_omission(self, row):
        index = next((i for i, item in enumerate(self.rows) if item['code'] == row['code']), 0)
        if index == 0 or row['gap']:
            return '?'
        value = self.rows[index-1]['sum_omission'][row['sum']]
        return '?' if value is None else str(value)
