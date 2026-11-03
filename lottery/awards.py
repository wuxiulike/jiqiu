from datetime import datetime
import json
from html.parser import HTMLParser

from lottery.core import Draw


class _PrizeTables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.current = []
        self.tables = []

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.in_table = True
            self.current = []

    def handle_data(self, data):
        if self.in_table and data.strip():
            self.current.append(data.strip())

    def handle_endtag(self, tag):
        if tag == 'table' and self.in_table:
            self.tables.append(self.current)
            self.in_table = False


def parse_special_award(html, code):
    if code not in html:
        return None
    parser = _PrizeTables()
    parser.feed(html)
    for cells in parser.tables:
        if '一等奖' in cells and '六等奖' in cells:
            return '福运奖' in cells
    return None


def verify_next_issue(client, baseline, candidate):
    response = client.session.get('https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice',
        params={'name':'ssq', 'issueCount':'', 'issueStart':baseline, 'issueEnd':candidate,
                'pageNo':1, 'pageSize':30, 'systemType':'PC'}, timeout=30)
    response.raise_for_status()
    data = response.json()
    rows = data.get('result')
    if data.get('state') != 0 or data.get('total') != 2 or not isinstance(rows, list) or {row.get('code') for row in rows} != {baseline, candidate}:
        return None
    row = next(item for item in rows if item['code'] == candidate)
    draw = Draw(candidate, row['date'][:10], tuple(map(int, row['red'].split(','))), int(row['blue']))
    special = None
    link = row.get('detailsLink', '')
    if isinstance(link, str) and link.startswith('/c/'):
        try:
            detail = client.session.get('https://www.cwl.gov.cn' + link, timeout=20)
            detail.raise_for_status()
            detail.encoding = 'utf-8'
            special = parse_special_award(detail.text, candidate)
        except Exception:
            special = None
    return draw, special


def ensure_tables(store):
    with store.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT, batch TEXT NOT NULL, baseline TEXT NOT NULL,
            selected_at TEXT NOT NULL, red TEXT NOT NULL, blue INTEGER NOT NULL, source TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', draw_code TEXT, red_hits INTEGER,
            blue_hit INTEGER, prize TEXT, notified INTEGER NOT NULL DEFAULT 0)''')


def prize_for(red, blue, draw, special):
    matches = len(set(red) & set(draw.red))
    blue_match = blue == draw.blue
    if matches == 6:
        return '一等奖' if blue_match else '二等奖'
    if matches == 5:
        return '三等奖' if blue_match else '四等奖'
    if matches == 4:
        return '四等奖' if blue_match else '五等奖'
    if matches == 3 and blue_match:
        return '五等奖'
    if blue_match:
        return '六等奖'
    if matches == 3:
        return '福运奖' if special is True else (None if special is False else '待确认福运奖')
    return None


def save_selection(store, baseline, tickets, source, track=True):
    ensure_tables(store)
    if not isinstance(baseline, str) or len(baseline) != 7 or not baseline.isdigit() or not tickets:
        raise ValueError('无法确定选号对应的基准期')
    rows = []
    for ticket in tickets:
        draw = Draw(baseline, '2000-01-01', tuple(ticket['red']), ticket['blue'])
        rows.append((json.dumps(draw.red), draw.blue))
    from uuid import uuid4
    batch = uuid4().hex
    selected_at = datetime.now().isoformat(timespec='seconds')
    with store.connect() as db:
        db.executemany('INSERT INTO selections (batch,baseline,selected_at,red,blue,source,status) VALUES (?,?,?,?,?,?,?)',
                       [(batch, baseline, selected_at, red, blue, source, 'pending' if track else 'preview') for red, blue in rows])
    return batch


def confirm_batch(store, batch):
    with store.connect() as db:
        db.execute("UPDATE selections SET status='pending' WHERE batch=? AND status='preview'", (batch,))


def verify_current_issue(baseline):
    from lottery.core import OfficialClient
    client = OfficialClient()
    draws, _ = client.page(1)
    return bool(draws and draws[0].code == baseline)


def check_pending(store, verify):
    ensure_tables(store)
    with store.connect() as db:
        pending = db.execute("SELECT id,baseline,red,blue FROM selections WHERE status='pending' ORDER BY id").fetchall()
    draws = store.all()
    by_baseline = {}
    updated = []
    for id_, baseline, red_text, blue in pending:
        candidate = next((d for d in draws if d.code > baseline), None)
        if candidate is None:
            continue
        pair = (baseline, candidate.code)
        if pair not in by_baseline:
            by_baseline[pair] = verify(baseline, candidate.code)
        verified = by_baseline[pair]
        if verified is None:
            continue
        official, special = verified
        if official.code != candidate.code:
            continue
        red = json.loads(red_text)
        prize = prize_for(red, blue, official, special)
        if prize == '待确认福运奖':
            continue
        hits = len(set(red) & set(official.red))
        with store.connect() as db:
            db.execute("UPDATE selections SET status='checked',draw_code=?,red_hits=?,blue_hit=?,prize=? WHERE id=? AND status='pending'",
                       (official.code, hits, int(blue == official.blue), prize, id_))
        updated.append(id_)
    return updated


def take_notifications(store):
    ensure_tables(store)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        rows = db.execute("SELECT id,draw_code,red,blue,prize FROM selections WHERE status='checked' AND prize IS NOT NULL AND notified=0 ORDER BY id").fetchall()
        db.executemany('UPDATE selections SET notified=1 WHERE id=?', [(row[0],) for row in rows])
    return [{'id': id_, 'draw_code': code, 'red': json.loads(red), 'blue': blue, 'prize': prize}
            for id_, code, red, blue, prize in rows]


def selections(store):
    ensure_tables(store)
    with store.connect() as db:
        rows = db.execute('SELECT selected_at,baseline,red,blue,source,status,draw_code,red_hits,blue_hit,prize FROM selections ORDER BY id DESC').fetchall()
    return [{'selected_at': at, 'baseline': base, 'red': json.loads(red), 'blue': blue, 'source': source,
             'status': status, 'draw_code': draw, 'red_hits': rh, 'blue_hit': bh, 'prize': prize}
            for at, base, red, blue, source, status, draw, rh, bh, prize in rows]
