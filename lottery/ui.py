import json
import shutil
import sys
from pathlib import Path

import keyring
from PySide6.QtGui import QIcon
from PySide6.QtCore import QObject, QSettings, QStandardPaths, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QFormLayout, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)

from lottery.ai import chat, chat_stream, parse_prediction, prediction_input
from lottery.core import OfficialClient, Store, backtest, generate, import_csv, statistics, sync
from lottery.trend_ui import TrendView
from lottery.today_ui import TodayPanel
from lottery.awards import check_pending, confirm_batch, save_selection, selections, take_notifications, verify_current_issue, verify_next_issue
from lottery.celebration import Celebration

STYLE = '''
QWidget { background:#f3f0e8; color:#242a26; font-family:"Microsoft YaHei", "PingFang SC", sans-serif; font-size:14px; }
QMainWindow { background:#f3f0e8; }
QFrame#sidebar { background:#183a33; border:0; }
QFrame#sidebar QLabel { background:transparent; color:#e7eee5; }
QFrame#sidebar QPushButton { background:transparent; color:#c6d9cf; text-align:left; padding:13px 18px; border:0; border-radius:9px; font-size:14px; }
QFrame#sidebar QPushButton:hover { background:#285148; color:white; }
QFrame#sidebar QPushButton:checked { background:#d4e4b7; color:#183a33; font-weight:bold; }
QLabel#brand { font-size:26px; font-weight:800; color:#f4f5e8; }
QLabel#kicker { color:#809f8c; font-size:11px; letter-spacing:2px; font-weight:bold; }
QLabel#title { font-size:28px; font-weight:800; color:#203e34; }
QLabel#subtitle { color:#77867b; font-size:13px; }
QFrame#card { background:#fffdf7; border:1px solid #e5e5d9; border-radius:14px; }
QFrame#card QLabel { background:transparent; }
QLabel#cardTitle { color:#334b3f; font-size:16px; font-weight:bold; }
QLabel#big { font-size:32px; font-weight:800; color:#1c4a3a; }
QFrame#card QLabel#redBall { background:#b84d3e; color:white; border-radius:20px; font-size:15px; font-weight:bold; }
QFrame#card QLabel#blueBall { background:#386d91; color:white; border-radius:20px; font-size:15px; font-weight:bold; }
QPushButton { background:#255648; color:#fffdf5; border:0; border-radius:8px; padding:10px 17px; font-weight:bold; }
QPushButton:hover { background:#34715d; }
QPushButton:disabled { background:#bac9bd; color:#f1f2ed; }
QPushButton#secondary { background:#e7ece2; color:#255648; }
QLineEdit, QComboBox, QSpinBox, QTextEdit, QTableWidget { background:#fffdf8; border:1px solid #d9dfd3; border-radius:8px; padding:8px; selection-background-color:#d5e5c9; }
QTableWidget { gridline-color:#eceee5; alternate-background-color:#f7f8f1; }
QHeaderView::section { background:#edf1e8; color:#566a5e; padding:9px; border:0; font-weight:bold; }
QFrame#todayControls { background:#fffdf7; border:1px solid #e5e5d9; border-radius:16px; }
QFrame#todayControls QLabel { background:transparent; }
QFrame#todayBoard { background:#fffdf7; border:1px solid #e5e5d9; border-radius:16px; }
QWidget#ballRow { background:transparent; }
QWidget#ballRow QLabel#rowNumber { background:transparent; }
QLabel#todayCaption { color:#244c3d; font-size:15px; font-weight:bold; }
QLabel#todayCount { color:#b45440; font-size:19px; font-weight:800; }
QLabel#todayPhase, QLabel#rowNumber { color:#8a9a8b; font-size:12px; font-weight:bold; }
QWidget#ballRow QLabel#todayRed { color:white; font-size:17px; font-weight:800; border:1px solid #9e4032; border-radius:21px; background:qradialgradient(cx:0.31, cy:0.24, radius:0.9, fx:0.26, fy:0.18, stop:0 #f5927c, stop:0.38 #cf5b4a, stop:1 #9d3429); }
QWidget#ballRow QLabel#todayBlue { color:white; font-size:17px; font-weight:800; border:1px solid #24516c; border-radius:21px; background:qradialgradient(cx:0.31, cy:0.24, radius:0.9, fx:0.26, fy:0.18, stop:0 #8ec1d9, stop:0.38 #4b86a9, stop:1 #275572); }
QWidget#ballRow QLabel#todayRed[aiAdjusted="true"], QWidget#ballRow QLabel#todayBlue[aiAdjusted="true"] { color:#ffdf59; }
QPushButton#todayStart { border-radius:22px; border:1px solid #1b493b; border-bottom:5px solid #153d32; padding:9px 20px; font-size:17px; background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #477e65, stop:1 #235442); color:white; }
QPushButton#todayStart:hover { background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #599475, stop:1 #2a644c); }
QPushButton#todayStart:pressed { border-bottom:1px solid #153d32; padding-top:13px; }
QPushButton#todayStart:disabled { background:#aebdb2; border:1px solid #a0afa4; color:#ecf0ea; }
QSlider::groove:horizontal { height:5px; background:#d8e1d6; border-radius:2px; }
QSlider::sub-page:horizontal { background:#80a98c; border-radius:2px; }
QSlider::handle:horizontal { background:#255648; border:3px solid #fffdf7; width:18px; margin:-8px 0; border-radius:11px; }
QTextEdit#todayLog { background:#fffdf7; border:1px solid #e5e5d9; border-radius:14px; padding:12px; color:#40574a; }
'''


class Worker(QObject):
    progress = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, job):
        super().__init__()
        self.job = job

    def run(self):
        try:
            self.finished.emit(self.job(self.progress.emit))
        except Exception as exc:
            import requests
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                message = f'服务返回 HTTP {exc.response.status_code}，请检查配置或稍后重试。'
            elif isinstance(exc, requests.RequestException):
                message = '网络请求失败，请检查网络连接、服务地址或稍后重试。'
            else:
                message = str(exc)
            self.failed.emit(message)


class WorkerCallbacks(QObject):
    def __init__(self, owner, done, failed, progress):
        super().__init__(owner)
        self.owner, self.done_callback, self.failed_callback, self.progress_callback = owner, done, failed, progress

    @Slot(object)
    def done(self, result):
        self.done_callback(result)

    @Slot(str)
    def failed(self, message):
        self.failed_callback(message)

    @Slot(str)
    def progress(self, message):
        if self.progress_callback:
            self.progress_callback(message)

    @Slot()
    def cleanup(self):
        self.owner.threads.remove(self.bundle)
        self.deleteLater()


def card():
    box = QFrame()
    box.setObjectName('card')
    layout = QVBoxLayout(box)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(12)
    return box, layout


def label(text, name=None):
    result = QLabel(text)
    if name:
        result.setObjectName(name)
    result.setWordWrap(True)
    return result


def app_data_dir():
    path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(path)


def create_store():
    path = app_data_dir() / 'history.sqlite3'
    path.parent.mkdir(parents=True, exist_ok=True)
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    seed = root / 'data' / 'history.sqlite3'
    if not path.exists() and seed.exists():
        shutil.copy2(seed, path)
    return Store(path)


class MainWindow(QMainWindow):
    def __init__(self, store=None, auto_sync=True):
        super().__init__()
        self.store = store or create_store()
        self.settings = QSettings('LuckyLab', 'Shuangseqiu')
        self.threads = []
        self.sync_verified = False
        self.tickets = []
        self.summary = None
        self.setWindowTitle('吉球 · 双色球数据实验室')
        root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
        self.setWindowIcon(QIcon(str(root / 'assets' / 'jiqiu.png')))
        self.resize(1160, 800)
        self.setMinimumSize(960, 680)
        self.build_ui()
        self.celebration = Celebration(self.centralWidget())
        self.refresh()
        if auto_sync:
            QTimer.singleShot(250, self.start_sync)

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(214)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(20, 32, 20, 24)
        side.addWidget(label('吉 球', 'brand'))
        side.addWidget(label('双色球数据实验室', 'kicker'))
        side.addSpacing(42)
        self.pages = QStackedWidget()
        self.nav = []
        for index, title in enumerate(['今日选号', '历史开奖', '走势图', '选号与回测', 'AI 预测', '模型设置', '选号记录']):
            button = QPushButton(f'{index+1:02d}   {title}')
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self.navigate(i))
            side.addWidget(button)
            self.nav.append(button)
        side.addStretch()
        side.addWidget(label('DATA  /  PLAY  /  EXPLORE', 'kicker'))
        side.addWidget(label('每一次选号，都是一次探索。'))
        shell.addWidget(sidebar)
        shell.addWidget(self.pages, 1)
        self.build_home()
        self.build_history()
        self.build_trends()
        self.build_analysis()
        self.build_ai()
        self.build_settings()
        self.build_records()
        self.navigate(0)

    def page(self, title, subtitle):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(38, 32, 38, 32)
        layout.setSpacing(18)
        layout.addWidget(label(title, 'title'))
        layout.addWidget(label(subtitle, 'subtitle'))
        self.pages.addWidget(widget)
        return layout

    def build_home(self):
        layout = self.page('今日选号', '本地初选后，点击开始将所选历史走势与号码发送给配置的模型。')
        status = QHBoxLayout()
        self.latest_issue = label('暂无开奖记录', 'subtitle')
        status.addWidget(self.latest_issue)
        status.addStretch()
        self.sync_label = label('准备同步', 'subtitle')
        status.addWidget(self.sync_label)
        self.sync_button = QPushButton('同步')
        self.sync_button.setObjectName('secondary')
        self.sync_button.clicked.connect(self.start_sync)
        status.addWidget(self.sync_button)
        layout.addLayout(status)
        self.today = TodayPanel()
        self.today.startRequested.connect(self.start_today)
        layout.addWidget(self.today, 1)
        layout.addWidget(label('红球 01–33 · 蓝球 01–16  |  仅供娱乐，历史走势不代表未来概率', 'subtitle'))

    def build_history(self):
        layout = self.page('历史开奖', '本地记录按开奖日期排序；数据范围以实际同步结果为准。')
        row = QHBoxLayout()
        self.history_info = label('')
        row.addWidget(self.history_info, 1)
        btn = QPushButton('导入 CSV')
        btn.setObjectName('secondary')
        btn.clicked.connect(self.import_file)
        row.addWidget(btn)
        layout.addLayout(row)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['期号', '开奖日期', '红球', '蓝球'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        layout.addWidget(self.table)
        layout.addWidget(label('CSV 列名：code,date,red,blue；红球用英文逗号分隔并放在引号内。', 'subtitle'))

    def build_trends(self):
        layout = self.page('走势图', '参考新浪走势图分类，所有指标由本地开奖记录计算。')
        self.trends = TrendView()
        layout.addWidget(self.trends, 1)

    def build_analysis(self):
        layout = self.page('选号与回测', '选择一种策略，生成号码并与相同注数的随机选号进行历史对照。')
        panel, inner = card()
        row = QHBoxLayout()
        self.strategy = QComboBox()
        self.strategy.addItems(['随机', '热号', '冷号', '混合'])
        self.window = QSpinBox()
        self.window.setRange(1, 500)
        self.window.setValue(30)
        self.window.setSuffix(' 期')
        self.count = QSpinBox()
        self.count.setRange(1, 100)
        self.count.setValue(5)
        self.count.setSuffix(' 注')
        for text, widget in [('策略', self.strategy), ('统计窗口', self.window), ('注数', self.count)]:
            column = QVBoxLayout()
            column.addWidget(label(text))
            column.addWidget(widget)
            row.addLayout(column)
        inner.addLayout(row)
        buttons = QHBoxLayout()
        gen = QPushButton('生成号码')
        gen.clicked.connect(self.generate_tickets)
        test = QPushButton('运行历史回测')
        test.setObjectName('secondary')
        test.clicked.connect(self.run_backtest)
        buttons.addWidget(gen)
        buttons.addWidget(test)
        buttons.addStretch()
        inner.addLayout(buttons)
        layout.addWidget(panel)
        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        self.analysis_text.setPlaceholderText('生成的号码和回测结果将显示在这里。')
        layout.addWidget(self.analysis_text, 1)
        layout.addWidget(label('热号、冷号和遗漏均为历史描述，不意味着下一期出现概率改变。', 'subtitle'))

    def build_ai(self):
        layout = self.page('AI 走势分析', '将选定范围的走势数据交给模型分析，并生成下一期娱乐性候选号码。')
        controls = QHBoxLayout()
        controls.addWidget(label('候选注数'))
        self.ai_count = QSpinBox()
        self.ai_count.setRange(1, 20)
        self.ai_count.setValue(3)
        self.ai_count.setSuffix(' 注')
        controls.addWidget(self.ai_count)
        controls.addStretch()
        preview = QPushButton('查看发送摘要')
        preview.setObjectName('secondary')
        preview.clicked.connect(self.preview_ai)
        controls.addWidget(preview)
        layout.addLayout(controls)
        self.ai_text = QTextEdit()
        self.ai_text.setReadOnly(True)
        self.ai_text.setPlaceholderText('走势范围与“走势图”页面一致。点击查看发送摘要，或发送给模型生成候选号码。')
        layout.addWidget(self.ai_text, 1)
        self.ai_button = QPushButton('分析走势并生成候选号')
        self.ai_button.clicked.connect(self.run_ai)
        layout.addWidget(self.ai_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(label('仅在点击分析后发送所选期数的开奖、走势图指标和已有算法结果；结果仅供娱乐。', 'subtitle'))

    def build_settings(self):
        layout = self.page('模型设置', '兼容 OpenAI Chat Completions 协议；密钥保存在系统凭据管理器。')
        box, inner = card()
        form = QFormLayout()
        form.setSpacing(16)
        self.base = QLineEdit(str(self.settings.value('base', 'https://api.deepseek.com/v1')))
        self.model = QLineEdit(str(self.settings.value('model', 'deepseek-chat')))
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText('输入 API Key；留空则保留已保存密钥')
        form.addRow('Base URL', self.base)
        form.addRow('Model Name', self.model)
        form.addRow('API Key', self.key)
        inner.addLayout(form)
        row = QHBoxLayout()
        save = QPushButton('保存设置')
        save.clicked.connect(self.save_settings)
        test = QPushButton('测试连接')
        test.setObjectName('secondary')
        test.clicked.connect(self.test_connection)
        row.addWidget(save)
        row.addWidget(test)
        row.addStretch()
        inner.addLayout(row)
        layout.addWidget(box)
        layout.addWidget(label('连接测试会发送一条简短请求，可能产生模型调用费用。', 'subtitle'))
        layout.addStretch()

    def build_records(self):
        layout = self.page('选号记录', '保存的最终号码会与基准期之后的下一期开奖核对。')
        self.records_info = label('')
        layout.addWidget(self.records_info)
        self.records_table = QTableWidget(0, 6)
        self.records_table.setHorizontalHeaderLabels(['生成时间', '基准期', '红球', '蓝球', '来源', '核对结果'])
        self.records_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.records_table.horizontalHeader().setStretchLastSection(True)
        self.records_table.verticalHeader().hide()
        self.records_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.records_table.setAlternatingRowColors(True)
        layout.addWidget(self.records_table, 1)
        layout.addWidget(label('程序初选仅作过程记录；最终号码和高级页面生成的号码参与自动核对。', 'subtitle'))

    def navigate(self, index):
        self.pages.setCurrentIndex(index)
        for i, button in enumerate(self.nav):
            button.setChecked(i == index)

    def refresh(self):
        draws = self.store.all()
        self.trends.set_draws(draws)
        self.history_info.setText(f'共 {len(draws)} 期 · ' + (f'{draws[0].code} — {draws[-1].code}' if draws else '暂无数据'))
        if draws:
            latest = draws[-1]
            self.latest_issue.setText(f'最近开奖 {latest.code}  ·  已保存 {len(draws):,} 期')
        self.table.setRowCount(len(draws))
        for row, d in enumerate(reversed(draws)):
            for col, value in enumerate([d.code, d.date, '   '.join(f'{n:02d}' for n in d.red), f'{d.blue:02d}']):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.refresh_records()

    def refresh_records(self):
        records = selections(self.store)
        self.records_info.setText(f'共 {len(records)} 条 · 核对结果以官方开奖为准')
        self.records_table.setRowCount(len(records))
        for i, record in enumerate(records):
            if record['status'] == 'preview':
                result = '预览号码 · 未纳入自动核对'
            elif record['status'] == 'pending':
                result = '等待下一期开奖 / 官方核验'
            else:
                result = f'{record["draw_code"]} · ' + (record['prize'] or '未命中') + f'（{record["red_hits"]}红 {record["blue_hit"]}蓝）'
            values = [record['selected_at'].replace('T', ' '), record['baseline'],
                      ' '.join(f'{n:02d}' for n in record['red']), f'{record["blue"]:02d}', record['source'], result]
            for j, value in enumerate(values):
                self.records_table.setItem(i, j, QTableWidgetItem(value))

    def launch(self, job, done, failed=None, progress=None):
        thread = QThread(self)
        worker = Worker(job)
        callbacks = WorkerCallbacks(self, done, failed or (lambda message: QMessageBox.warning(self, '操作失败', message)), progress)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(callbacks.progress)
        worker.finished.connect(callbacks.done)
        worker.failed.connect(callbacks.failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(callbacks.cleanup)
        callbacks.bundle = (thread, worker, callbacks)
        self.threads.append(callbacks.bundle)
        thread.start()

    def start_sync(self):
        self.sync_verified = False
        self.sync_button.setEnabled(False)
        self.sync_label.setText('正在连接中国福彩网…')
        def job(progress):
            client = OfficialClient()
            sync(self.store, client.page, progress=lambda page, total: progress(f'同步中 · 第 {page} / {total} 页'))
            message = ''
            try:
                check_pending(self.store, lambda baseline, candidate: verify_next_issue(client, baseline, candidate))
            except Exception:
                message = ' · 选号核对暂未完成'
            return client.latest_code, message
        def done(result):
            self.refresh()
            draws = self.store.all()
            self.sync_verified = bool(draws and draws[-1].code == result[0])
            self.sync_button.setEnabled(True)
            message = result[1] if self.sync_verified else ' · 本地最新期与官网不一致，请检查导入数据'
            self.sync_label.setText(f'同步完成 · {self.store.get_meta("last_sync")}' + message)
            wins = take_notifications(self.store)
            if wins:
                self.celebration.show_wins(wins)
        def failed(message):
            self.refresh()
            self.sync_button.setEnabled(True)
            self.sync_label.setText(f'同步未完成，已保留本地数据：{message}')
        self.launch(job, done, failed, self.sync_label.setText)

    def import_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, '导入历史数据', '', 'CSV 文件 (*.csv)')
        if not filename:
            return
        try:
            count = import_csv(self.store, filename)
            self.refresh()
            QMessageBox.information(self, '导入完成', f'已处理 {count} 条记录。')
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, '导入失败', str(exc))

    def start_today(self):
        if self.today.rolling:
            return
        self.today.begin()
        if not self.sync_verified:
            self.today.fail('请先完成官网数据同步，才能确定下一期并保存号码。')
            return
        draws = self.store.all()
        if not draws:
            self.today.fail('没有开奖数据，请先同步或导入历史数据。')
            return
        count = self.today.slider.value()
        window = self.trends.selected_count() or 50
        relevant = draws[-window:]
        local = generate(relevant, '混合', count)
        local_data = {'策略': '混合：3个热号加权、3个随机红球，蓝球随机',
                      '数据范围': [relevant[0].code, relevant[-1].code],
                      '候选号码': [{'红球': list(red), '蓝球': blue} for red, blue in local]}
        baseline = draws[-1].code
        try:
            save_selection(self.store, baseline, [{'red': list(red), 'blue': blue} for red, blue in local], '程序初选', track=False)
            self.refresh_records()
        except Exception:
            self.today.fail('保存程序初选失败，请检查本地数据库。')
            return
        lines = [f'程序初选 · 基于近 {len(relevant)} 期，使用混合策略']
        lines += [f'{i:02d}  ' + ' '.join(f'{n:02d}' for n in red) + f'  +  {blue:02d}'
                  for i, (red, blue) in enumerate(local, 1)]
        self.today.write('\n'.join(lines))
        try:
            base, model, key = self.model_config()
            if not key or not model:
                raise ValueError('请先在“模型设置”填写模型名称和 API Key。')
            summary = prediction_input(draws, window, count, local_data)
        except ValueError as exc:
            self.today.fail(str(exc))
            return
        self.today.phase.setText('AI 分析中')
        self.today.write('正在向配置的模型发送本地初选和所选期数的历史走势。')
        def done(result):
            try:
                parsed = parse_prediction(result, count)
            except ValueError:
                self.today.fail('模型返回的号码或格式无效，请重试。')
                return
            if not self.sync_verified or not self.store.all() or self.store.all()[-1].code != baseline:
                self.today.fail('开奖期数或同步状态已变化，请重新选号。')
                return
            try:
                save_selection(self.store, baseline, parsed['tickets'], 'AI 最终号码')
                self.refresh_records()
            except Exception:
                self.today.fail('保存最终号码失败，请检查本地数据库。')
                return
            self.today.ai_progress = ''
            self.today.write('AI 分析\n' + parsed['analysis'])
            self.today.write('AI 逐注说明\n' + '\n'.join(f'{i:02d}  {item["reason"]}' for i, item in enumerate(parsed['tickets'], 1)))
            self.today.complete(parsed['tickets'], local)
        def job(progress):
            if not verify_current_issue(baseline):
                raise ValueError('官网最新期已变化，请先同步后重新选号。')
            result = chat_stream(base, model, key, summary, progress)
            if not verify_current_issue(baseline):
                raise ValueError('分析期间官网最新期已变化，请先同步后重新选号。')
            return result
        self.launch(job, done,
                    self.today.fail, self.today.set_progress)

    def generate_tickets(self):
        if not self.sync_verified:
            QMessageBox.warning(self, '请先同步', '请先完成官网数据同步，才能确定下一期并保存号码。')
            return
        draws = self.store.all()
        if not draws:
            QMessageBox.warning(self, '暂无数据', '请先同步或导入开奖记录。')
            return
        window = draws[-self.window.value():]
        strategy = self.strategy.currentText()
        self.tickets = generate(window, strategy, self.count.value())
        try:
            batch = save_selection(self.store, draws[-1].code, [{'red': list(red), 'blue': blue} for red, blue in self.tickets], '算法选号', track=False)
            self.refresh_records()
        except Exception:
            QMessageBox.warning(self, '保存失败', '无法保存号码，请检查本地数据库。')
            return
        stat = statistics(window)
        self.summary = {'数据范围': [window[0].code, window[-1].code], '期数': len(window), '策略': strategy,
                        '红球频次': stat['red'], '蓝球频次': stat['blue'],
                        '候选号码': [{'红球': list(red), '蓝球': blue} for red, blue in self.tickets]}
        lines = [f'策略：{strategy}  ·  最近 {len(window)} 期  ·  {len(self.tickets)} 注', '']
        lines += [f'{i:02d}    ' + '   '.join(f'{n:02d}' for n in red) + f'     +  {blue:02d}' for i, (red, blue) in enumerate(self.tickets, 1)]
        self.analysis_text.setPlainText('\n'.join(lines))
        baseline = draws[-1].code
        self.analysis_text.append('\n正在核实官网最新期；核实前号码只作为预览。')
        def confirmed(ok):
            if ok and self.sync_verified and self.store.all() and self.store.all()[-1].code == baseline:
                confirm_batch(self.store, batch)
                self.analysis_text.append('官网期数已核实，号码已保存并纳入下一期核对。')
            else:
                self.analysis_text.append('官网期数已变化，号码仅保存为预览；请先同步后重新选号。')
            self.refresh_records()
        def failed(_):
            self.analysis_text.append('官网期数核实失败，号码仅保存为预览；请稍后同步后重试。')
        self.launch(lambda progress: verify_current_issue(baseline), confirmed, failed)

    def run_backtest(self):
        try:
            draws = self.store.all()
            strategy = self.strategy.currentText()
            window, count = self.window.value(), self.count.value()
            tested = backtest(draws, strategy, window, count)
            baseline = backtest(draws, '随机', window, count, seed=43)
            def line(name, result):
                total = len(result['red_hits'])
                return f'{name}：红球平均命中 {sum(result["red_hits"])/total:.3f} 个 / 注；蓝球命中 {sum(result["blue_hits"])} / {total} 注'
            text = f'\n\n历史回测：{tested["periods"]} 期，每期 {count} 注\n' + line(strategy, tested) + '\n' + line('随机对照', baseline) + '\n理论随机基准：红球平均 36/33 个；蓝球命中概率 1/16。\n固定随机种子，结果会随样本波动；回测不代表未来表现。'
            self.analysis_text.append(text)
            if self.summary:
                self.summary['回测'] = {'策略': strategy, '窗口': window, '期数': tested['periods'], '每期注数': count,
                    '策略红球总命中': sum(tested['red_hits']), '策略蓝球总命中': sum(tested['blue_hits']),
                    '随机红球总命中': sum(baseline['red_hits']), '随机蓝球总命中': sum(baseline['blue_hits'])}
        except ValueError as exc:
            QMessageBox.warning(self, '无法回测', str(exc))

    def save_settings(self):
        try:
            if self.key.text():
                keyring.set_password('球序', 'api_key', self.key.text())
                self.key.clear()
            self.settings.setValue('base', self.base.text().strip())
            self.settings.setValue('model', self.model.text().strip())
            self.settings.sync()
            QMessageBox.information(self, '设置已保存', '模型地址、名称和密钥已保存。')
        except Exception:
            QMessageBox.warning(self, '保存失败', '无法访问系统凭据管理器，密钥未保存。')

    def model_config(self):
        try:
            key = self.key.text() or keyring.get_password('球序', 'api_key') or ''
        except Exception:
            raise ValueError('无法读取系统凭据，请检查系统凭据管理器。') from None
        return self.base.text().strip(), self.model.text().strip(), key

    def test_connection(self):
        try:
            base, model, key = self.model_config()
        except ValueError as exc:
            QMessageBox.warning(self, '连接失败', str(exc))
            return
        self.launch(lambda progress: chat(base, model, key, {'任务': '请回复连接成功'}),
                    lambda _: QMessageBox.information(self, '连接成功', '模型服务已返回有效内容。'))

    def ai_payload(self):
        return prediction_input(self.store.all(), self.trends.selected_count(), self.ai_count.value(), self.summary)

    def preview_ai(self):
        try:
            self.ai_text.setPlainText(json.dumps(self.ai_payload(), ensure_ascii=False, indent=2))
        except ValueError as exc:
            QMessageBox.warning(self, '暂无走势数据', str(exc))

    def run_ai(self):
        if not self.sync_verified:
            QMessageBox.warning(self, '请先同步', '请先完成官网数据同步，才能确定下一期并保存号码。')
            return
        try:
            base, model, key = self.model_config()
            summary = self.ai_payload()
        except ValueError as exc:
            QMessageBox.warning(self, '无法解读', str(exc))
            return
        count = self.ai_count.value()
        baseline = self.store.all()[-1].code
        self.ai_button.setEnabled(False)
        self.ai_text.setPlainText('正在请求模型分析走势并生成候选号码…')
        def done(result):
            try:
                parsed = parse_prediction(result, count)
                if not self.sync_verified or not self.store.all() or self.store.all()[-1].code != baseline:
                    raise ValueError('开奖期数或同步状态已变化，请重新选号')
                save_selection(self.store, baseline, parsed['tickets'], 'AI 预测')
                self.refresh_records()
                lines = ['AI 走势分析', '', parsed['analysis'], '', 'AI 候选号码（仅供娱乐）']
                for i, ticket in enumerate(parsed['tickets'], 1):
                    lines.append(f'{i:02d}    ' + '  '.join(f'{n:02d}' for n in ticket['red']) + f'  +  {ticket["blue"]:02d}')
                    lines.append('       ' + ticket['reason'])
                self.ai_text.setPlainText('\n'.join(lines))
            except Exception as exc:
                self.ai_text.setPlainText(f'{exc}；以下为模型原始响应，请勿作为有效号码：\n\n{result}')
            self.ai_button.setEnabled(True)
        def failed(message):
            self.ai_text.setPlainText(f'解读失败：{message}')
            self.ai_button.setEnabled(True)
        def job(progress):
            if not verify_current_issue(baseline):
                raise ValueError('官网最新期已变化，请先同步后重新选号。')
            result = chat(base, model, key, summary)
            if not verify_current_issue(baseline):
                raise ValueError('分析期间官网最新期已变化，请先同步后重新选号。')
            return result
        self.launch(job, done, failed)

    def closeEvent(self, event):
        if self.threads:
            QMessageBox.information(self, '任务进行中', '请等待当前同步或模型请求完成后再关闭。')
            event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName('LuckyLab')
    app.setApplicationName('Shuangseqiu')
    app.setApplicationDisplayName('吉球')
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    app.setWindowIcon(QIcon(str(root / 'assets' / 'jiqiu.png')))
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
