import random
import pytest

from lottery.core import Draw, Store, generate, backtest, sync, import_csv


def make_draw(code, red=(1, 2, 3, 4, 5, 6), blue=1):
    return Draw(str(code), '2024-01-01', tuple(red), blue)


def test_draw_rejects_duplicate_or_out_of_range_numbers():
    with pytest.raises(ValueError):
        make_draw(1, (1, 1, 2, 3, 4, 5))
    with pytest.raises(ValueError):
        make_draw(1, blue=17)


def test_store_deduplicates_and_reports_range(tmp_path):
    store = Store(tmp_path / 'draws.db')
    store.save([make_draw(2024001), make_draw(2024002)])
    store.save([make_draw(2024001)])
    assert [d.code for d in store.all()] == ['2024001', '2024002']


def test_sync_saves_pages_and_resume_after_failure(tmp_path):
    store = Store(tmp_path / 'draws.db')
    pages = {1: ([make_draw(2024003)], 3), 2: ([make_draw(2024002)], 3), 3: ([make_draw(2024001)], 3)}
    def broken(page):
        if page == 2:
            raise RuntimeError('network')
        return pages[page]
    with pytest.raises(RuntimeError):
        sync(store, broken, full=True)
    assert [d.code for d in store.all()] == ['2024003']
    sync(store, pages.__getitem__, full=True)
    assert len(store.all()) == 3


def test_incremental_sync_does_not_stop_on_overlap_until_known_baseline(tmp_path):
    store = Store(tmp_path / 'draws.db')
    store.save([make_draw(2024001)])
    store.set_meta('full_sync', 'complete')
    pages = {1: ([make_draw(2024003)], 2), 2: ([make_draw(2024002), make_draw(2024001)], 2)}
    sync(store, pages.__getitem__)
    assert len(store.all()) == 3


def test_failed_csv_import_does_not_save_partial_data(tmp_path):
    store = Store(tmp_path / 'draws.db')
    path = tmp_path / 'bad.csv'
    path.write_text('code,date,red,blue\n2024001,2024-01-01,"1,2,3,4,5,6",1\n2024002,2024-01-02,"1,1,2,3,4,5",2\n', encoding='utf-8')
    with pytest.raises(ValueError):
        import_csv(store, path)
    assert store.all() == []


@pytest.mark.parametrize('strategy', ['随机', '热号', '冷号', '混合'])
def test_generated_tickets_are_valid(strategy):
    tickets = generate([make_draw(2024001)], strategy, 20, random.Random(5))
    assert len(tickets) == 20
    for red, blue in tickets:
        assert len(red) == len(set(red)) == 6
        assert all(1 <= n <= 33 for n in red)
        assert 1 <= blue <= 16


def test_backtest_does_not_use_future_draws():
    draws = [make_draw(2024000 + i, blue=i % 16 + 1) for i in range(1, 8)]
    first = backtest(draws[:6], '热号', window=2, count=1, seed=9)
    second = backtest(draws, '热号', window=2, count=1, seed=9)
    assert first['red_hits'] == second['red_hits'][:len(first['red_hits'])]
    assert first['blue_hits'] == second['blue_hits'][:len(first['blue_hits'])]
