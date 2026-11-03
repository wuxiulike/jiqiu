from collections import Counter
from datetime import date

CHARTS = ['基本走势', '红球走势', '蓝球走势', '连号走势', '重号走势', '周二走势', '周四走势', '周日走势',
          '红球大小', '红球奇偶', '红球质合', '红球012路', '和值走势', 'AC值走势', '区间走势', '跨度走势',
          '尾数分布', '和尾走势', '红球遗漏', '蓝球遗漏', '和值遗漏']
LOTTERY_PRIMES = {1, 2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}


def gap_between(previous, current):
    py, pn = int(previous[:4]), int(previous[4:])
    cy, cn = int(current[:4]), int(current[4:])
    return (cy == py and cn != pn + 1) or (cy != py and (cy != py + 1 or cn != 1))


def trend_rows(draws):
    red_omission = {i: None for i in range(1, 34)}
    blue_omission = {i: None for i in range(1, 17)}
    sum_omission = {i: None for i in range(21, 184)}
    result = []
    previous = None
    for draw in draws:
        gap = previous is not None and gap_between(previous.code, draw.code)
        if gap:
            red_omission = dict.fromkeys(red_omission)
            blue_omission = dict.fromkeys(blue_omission)
            sum_omission = dict.fromkeys(sum_omission)
        total = sum(draw.red)
        for data, present in ((red_omission, set(draw.red)), (blue_omission, {draw.blue}), (sum_omission, {total})):
            for n, value in data.items():
                data[n] = 0 if n in present else (value + 1 if value is not None else None)
        reds = draw.red
        consecutive = sorted({n for a, b in zip(reds, reds[1:]) if b == a + 1 for n in (a, b)})
        different = {b - a for i, a in enumerate(reds) for b in reds[i+1:]}
        result.append({'code': draw.code, 'date': draw.date, 'weekday': date.fromisoformat(draw.date).weekday(),
            'red': list(reds), 'blue': draw.blue, 'sum': total, 'sum_tail': total % 10,
            'span': reds[-1] - reds[0], 'ac': len(different) - 5, 'consecutive': consecutive,
            'repeat': sorted(set(reds) & set(previous.red)) if previous is not None and not gap else None,
            'large_small': [sum(n >= 17 for n in reds), sum(n <= 16 for n in reds)],
            'odd_even': [sum(n % 2 == 1 for n in reds), sum(n % 2 == 0 for n in reds)],
            'prime_composite': [sum(n in LOTTERY_PRIMES for n in reds), sum(n not in LOTTERY_PRIMES for n in reds)],
            'mod3': [sum(n % 3 == i for n in reds) for i in range(3)],
            'zones': [sum(lo <= n <= hi for n in reds) for lo, hi in ((1, 11), (12, 22), (23, 33))],
            'tails': [sum(n % 10 == i for n in reds) for i in range(10)], 'gap': gap,
            'red_omission': red_omission.copy(), 'blue_omission': blue_omission.copy(),
            'sum_omission': sum_omission.copy()})
        previous = draw
    return result


def make_summary(draws, window):
    if not draws or window < 1:
        raise ValueError('没有足够的开奖数据')
    rows = trend_rows(draws)
    selected = rows[-window:]
    red_counts = Counter(n for row in selected for n in row['red'])
    blue_counts = Counter(row['blue'] for row in selected)
    last = selected[-1]
    return {'数据来源': '本地开奖记录（福彩同步或手工导入；未逐条区分）',
        '数据范围': [selected[0]['code'], last['code']], '期数': len(selected),
        '存在缺期': any(row['gap'] for row in rows),
        '边界说明': '未见过的号码遗漏未知；跨年最后一期的完整性未独立核验。',
        '红球频次': {f'{n:02d}': red_counts[n] for n in range(1, 34)},
        '蓝球频次': {f'{n:02d}': blue_counts[n] for n in range(1, 17)},
        '红球遗漏': {f'{n:02d}': last['red_omission'][n] for n in range(1, 34)},
        '蓝球遗漏': {f'{n:02d}': last['blue_omission'][n] for n in range(1, 17)},
        '和值遗漏': {str(n): last['sum_omission'][n] for n in range(21, 184)},
        '口径': {'大小': '小01-16，大17-33', '分区': '01-11、12-22、23-33',
                 '质合': '彩票口径将01归质；数学上1不是质数', '遗漏': '该号码上次出现后的本地连续开奖期数，null表示未知'},
        '逐期走势': [{key: row[key] for key in ('code', 'date', 'red', 'blue', 'sum', 'sum_tail', 'span', 'ac',
                     'consecutive', 'repeat', 'large_small', 'odd_even', 'prime_composite', 'mod3', 'zones', 'tails', 'gap')}
                     for row in selected]}
