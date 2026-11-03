import pytest
from lottery.core import Draw, Store
from lottery.awards import prize_for, save_selection, check_pending, take_notifications, parse_special_award


DRAW = Draw('2024002', '2024-01-04', (1, 2, 3, 4, 5, 6), 7)


@pytest.mark.parametrize(('red', 'blue', 'expected'), [
    ([1,2,3,4,5,6],7,'一等奖'), ([1,2,3,4,5,6],8,'二等奖'),
    ([1,2,3,4,5,10],7,'三等奖'), ([1,2,3,4,5,10],8,'四等奖'),
    ([1,2,3,4,10,11],7,'四等奖'), ([1,2,3,4,10,11],8,'五等奖'),
    ([1,2,3,10,11,12],7,'五等奖'), ([1,2,10,11,12,13],7,'六等奖'),
    ([10,11,12,13,14,15],7,'六等奖'), ([1,2,10,11,12,13],8,None),
])
def test_official_regular_prize_priority(red, blue, expected):
    assert prize_for(red, blue, DRAW, False) == expected


def test_fuyun_only_when_verified_active():
    red = [1,2,3,10,11,12]
    assert prize_for(red, 8, DRAW, True) == '福运奖'
    assert prize_for(red, 8, DRAW, False) is None
    assert prize_for(red, 8, DRAW, None) == '待确认福运奖'


def test_fuyun_requires_the_official_prize_table():
    base = '<html><p>2024002</p><table><tr><th>奖级</th><th>中奖注数</th></tr><tr><td>一等奖</td></tr><tr><td>六等奖</td></tr>{}</table></html>'
    assert parse_special_award(base.format('<tr><td>福运奖</td><td>3</td><td>5</td></tr>'), '2024002') is True
    assert parse_special_award(base.format(''), '2024002') is False
    assert parse_special_award('<p>2024002 福运奖</p>', '2024002') is None
    assert parse_special_award(base.format(''), '2024003') is None


def test_saved_ticket_waits_for_next_official_draw_and_notifies_once(tmp_path):
    store = Store(tmp_path / 'test.db')
    previous = Draw('2024001','2024-01-02',(10,11,12,13,14,15),2)
    store.save([previous])
    save_selection(store, previous.code, [{'red':[1,2,3,4,5,6], 'blue':7}], 'AI')
    assert len(check_pending(store, lambda baseline, candidate: (DRAW, False))) == 0
    store.save([DRAW])
    check_pending(store, lambda baseline, candidate: (DRAW, False))
    rows = take_notifications(store)
    assert len(rows) == 1 and rows[0]['prize'] == '一等奖' and rows[0]['draw_code'] == '2024002'
    assert take_notifications(store) == []
    check_pending(store, lambda baseline, candidate: (DRAW, False))
    assert take_notifications(store) == []


def test_missing_or_unverified_next_draw_stays_pending(tmp_path):
    store = Store(tmp_path / 'test.db')
    previous = Draw('2024001','2024-01-02',(10,11,12,13,14,15),2)
    later = Draw('2024003','2024-01-07',(1,2,3,4,5,6),7)
    store.save([previous, later])
    save_selection(store, previous.code, [{'red':[1,2,3,4,5,6], 'blue':7}], 'AI')
    check_pending(store, lambda baseline, candidate: None)
    assert take_notifications(store) == []
    with store.connect() as db:
        assert db.execute('SELECT status FROM selections').fetchone()[0] == 'pending'


def test_fuyun_waits_until_official_announcement_known(tmp_path):
    store = Store(tmp_path / 'test.db')
    previous = Draw('2024001','2024-01-02',(10,11,12,13,14,15),2)
    store.save([previous, DRAW])
    save_selection(store, previous.code, [{'red':[1,2,3,10,11,12], 'blue':8}], 'AI')
    check_pending(store, lambda baseline, candidate: (DRAW, None))
    assert take_notifications(store) == []
    check_pending(store, lambda baseline, candidate: (DRAW, True))
    assert take_notifications(store)[0]['prize'] == '福运奖'


def test_preview_is_persisted_but_never_triggers_a_win(tmp_path):
    path = tmp_path / 'test.db'
    store = Store(path)
    store.save([Draw('2024001','2024-01-02',(10,11,12,13,14,15),2), DRAW])
    save_selection(store, '2024001', [{'red':[1,2,3,4,5,6], 'blue':7}], '程序初选', track=False)
    reopened = Store(path)
    check_pending(reopened, lambda baseline, candidate: (DRAW, False))
    assert take_notifications(reopened) == []
    with reopened.connect() as db:
        assert db.execute('SELECT status FROM selections').fetchone()[0] == 'preview'
