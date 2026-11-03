import csv
import random
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import requests

SOURCE = 'https://www.cwl.gov.cn/ygkj/wqkjgg/'
API = 'https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice'


@dataclass(frozen=True)
class Draw:
    code: str
    date: str
    red: tuple[int, ...]
    blue: int

    def __post_init__(self):
        if not self.code.isdigit() or len(self.code) != 7:
            raise ValueError('期号必须是 7 位数字')
        date.fromisoformat(self.date)
        if len(self.red) != 6 or len(set(self.red)) != 6 or any(not 1 <= n <= 33 for n in self.red):
            raise ValueError('红球必须是 6 个不重复的 1–33 号码')
        if not 1 <= self.blue <= 16:
            raise ValueError('蓝球必须在 1–16 之间')
        object.__setattr__(self, 'red', tuple(sorted(self.red)))


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS draws (code TEXT PRIMARY KEY, date TEXT NOT NULL, red TEXT NOT NULL, blue INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.path)

    def save(self, draws):
        with self.connect() as db:
            db.executemany('INSERT INTO draws VALUES (?, ?, ?, ?) ON CONFLICT(code) DO UPDATE SET date=excluded.date, red=excluded.red, blue=excluded.blue WHERE date!=excluded.date OR red!=excluded.red OR blue!=excluded.blue',
                           [(d.code, d.date, ','.join(map(str, d.red)), d.blue) for d in draws])

    def all(self):
        with self.connect() as db:
            rows = db.execute('SELECT code, date, red, blue FROM draws ORDER BY date, code').fetchall()
        return [Draw(code, day, tuple(map(int, red.split(','))), blue) for code, day, red, blue in rows]

    def get_meta(self, key):
        with self.connect() as db:
            row = db.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key, value):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO metadata VALUES (?, ?)', (key, value))


class OfficialClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0', 'Referer': SOURCE})
        response = self.session.get(SOURCE, timeout=20)
        response.raise_for_status()

    def page(self, page):
        response = self.session.get(API, params={'name': 'ssq', 'issueCount': '', 'pageNo': page,
                                                'pageSize': 100, 'systemType': 'PC'}, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data.get('state') != 0 or not isinstance(data.get('result'), list) or not data.get('pageNum'):
            raise ValueError('福彩接口未返回有效数据')
        draws = [Draw(str(row['code']), row['date'][:10], tuple(map(int, row['red'].split(','))), int(row['blue']))
                 for row in data['result']]
        if not draws:
            raise ValueError('福彩接口返回空页，无法确认同步完整')
        if page == 1:
            self.latest_code = draws[0].code
        return draws, int(data['pageNum'])


def sync(store, fetch_page, full=False, progress=None):
    known = {d.code for d in store.all()}
    full = full or store.get_meta('full_sync') != 'complete' or not known
    if full:
        store.set_meta('full_sync', 'partial')
    page = 1
    while True:
        draws, pages = fetch_page(page)
        if not draws or pages < page:
            raise ValueError('接口分页不完整')
        store.save(draws)
        if progress:
            progress(page, pages)
        if page >= pages or (not full and any(d.code in known for d in draws)):
            break
        page += 1
    if full:
        store.set_meta('full_sync', 'complete')
    store.set_meta('last_sync', __import__('datetime').datetime.now().isoformat(timespec='seconds'))


def import_csv(store, path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    draws = []
    for row in rows:
        try:
            draws.append(Draw(row['code'].strip(), row['date'].strip(), tuple(int(x.strip()) for x in row['red'].split(',')), int(row['blue'])))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f'CSV 第 {len(draws)+2} 行无效：{exc}') from exc
    if not draws:
        raise ValueError('CSV 没有数据')
    store.save(draws)
    return len(draws)


def statistics(draws):
    red = Counter(n for draw in draws for n in draw.red)
    blue = Counter(draw.blue for draw in draws)
    return {'count': len(draws), 'red': {n: red[n] for n in range(1, 34)}, 'blue': {n: blue[n] for n in range(1, 17)}}


def generate(draws, strategy, count, rng=None):
    if strategy not in ('随机', '热号', '冷号', '混合') or not 1 <= count <= 100:
        raise ValueError('选号参数无效')
    rng = rng or random.Random()
    stats = statistics(draws)
    def choose(pool, frequencies, mode):
        if mode == '随机':
            weights = [1] * len(pool)
        elif mode == '热号':
            weights = [frequencies[n] + 1 for n in pool]
        else:
            maximum = max(frequencies.values(), default=0)
            weights = [maximum - frequencies[n] + 1 for n in pool]
        return rng.choices(pool, weights=weights, k=1)[0]
    tickets = []
    for _ in range(count):
        remaining = list(range(1, 34))
        red = []
        for i in range(6):
            mode = ('热号' if i < 3 else '随机') if strategy == '混合' else strategy
            n = choose(remaining, stats['red'], mode)
            red.append(n)
            remaining.remove(n)
        blue = choose(list(range(1, 17)), stats['blue'], '随机' if strategy == '混合' else strategy)
        tickets.append((tuple(sorted(red)), blue))
    return tickets


def backtest(draws, strategy, window=30, count=1, seed=42, periods=100):
    if window < 1 or len(draws) <= window:
        raise ValueError('历史数据不足以进行回测')
    rng = random.Random(seed)
    red_hits, blue_hits = [], []
    for i in range(max(window, len(draws) - periods), len(draws)):
        for red, blue in generate(draws[i-window:i], strategy, count, rng):
            red_hits.append(len(set(red) & set(draws[i].red)))
            blue_hits.append(int(blue == draws[i].blue))
    return {'red_hits': red_hits, 'blue_hits': blue_hits, 'periods': len(red_hits) // count}
