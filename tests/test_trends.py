from lottery.core import Draw
from lottery.trends import trend_rows, make_summary, CHARTS


def d(code, day, red, blue):
    return Draw(code, day, tuple(red), blue)


def test_features_and_preceding_draw():
    draws = [d('2024001', '2024-01-02', [1, 2, 3, 11, 22, 33], 3),
             d('2024002', '2024-01-04', [2, 3, 4, 12, 24, 32], 5)]
    row = trend_rows(draws)[-1]
    assert row['sum'] == 77
    assert row['span'] == 30
    assert row['consecutive'] == [2, 3, 4]
    assert row['repeat'] == [2, 3]
    assert row['odd_even'] == [1, 5]
    assert row['large_small'] == [2, 4]
    assert row['prime_composite'] == [2, 4]
    assert row['zones'] == [3, 1, 2]
    assert row['mod3'] == [3, 1, 2]
    assert row['ac'] == len({abs(a-b) for a in draws[-1].red for b in draws[-1].red if a > b}) - 5


def test_omission_known_from_before_window_and_unknown_at_history_start():
    draws = [d('2024001', '2024-01-02', [1, 2, 3, 4, 5, 6], 1),
             d('2024002', '2024-01-04', [2, 3, 4, 5, 6, 7], 2),
             d('2024003', '2024-01-07', [2, 3, 4, 5, 6, 8], 3)]
    rows = trend_rows(draws)
    assert rows[0]['red_omission'][8] is None
    assert rows[-1]['red_omission'][1] == 2
    summary = make_summary(draws, 1)
    assert summary['期数'] == 1
    assert summary['红球遗漏']['01'] == 2
    assert summary['和值遗漏']['21'] == 2
    assert summary['数据范围'] == ['2024003', '2024003']


def test_gap_invalidates_omissions_and_repeat():
    draws = [d('2024001', '2024-01-02', [1, 2, 3, 4, 5, 6], 1),
             d('2024003', '2024-01-07', [2, 3, 4, 5, 6, 7], 3)]
    row = trend_rows(draws)[-1]
    assert row['gap'] is True
    assert row['repeat'] is None
    assert row['red_omission'][1] is None
    assert make_summary(draws, 1)['存在缺期'] is True


def test_includes_all_sina_chart_types():
    assert len(CHARTS) == 21
    assert {'基本走势', '红球遗漏', '蓝球遗漏', '和值遗漏', '周日走势'} <= set(CHARTS)


def test_sina_public_2026121_sum_and_ac_example():
    # 新浪公开走势图第 2026121 期：和值 109，AC 值 8。
    row = trend_rows([d('2026121', '2026-10-22', [2, 7, 20, 24, 26, 30], 2)])[0]
    assert (row['sum'], row['ac'], row['prime_composite']) == (109, 8, [2, 4])
