"""奇门定局可选超神接气置闰：《遁甲演义》万历二十六至二十九年的实例逐条复算（真实历日）。"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from classical_search import get_passage
from qimen_dingju import ZHIRUN_SOURCES, determine_ju_zhirun, zhirun_term

SKILL = Path(__file__).resolve().parents[1] / 'skills/chinese-fortune'


def test_quotes_are_in_their_passages():
    for pid, quote, _ in ZHIRUN_SOURCES:
        assert quote in get_passage(pid)['text'], pid


@pytest.mark.parametrize('day,term,mode', [
    # dunjia:c001:p0015「超至十月二十七己夘日超用大雪……已過十一日合當置閏也十三甲午日疊作大雪節此名閏竒」
    (date(1598, 11, 25), '大雪', '超神'),
    (date(1598, 12, 10), '大雪', '闰奇'),
    # 「萬厯二十七年己亥五月十七甲子日子時正交小暑節此名正授竒」
    (date(1599, 7, 8), '小暑', '正授'),
    # 「八月初三己夘日符頭已到初四秋分乃符先到而節氣後到又當超用」
    (date(1599, 9, 21), '秋分', '超神'),
    # 「辛丑四月二十七甲午日超用芒種五月初七甲辰日丑時交芒種節已超過十日」，其后置闰
    (date(1601, 5, 28), '芒种', '超神'),
    (date(1601, 6, 12), '芒种', '闰奇'),
])
def test_the_wanli_examples(day, term, mode):
    row = zhirun_term(day)
    assert (row['term'], row['mode'], row['yuan']) == (term, mode, '上元'), row


def test_eight_days_ahead_at_mangzhong_is_not_enough_to_insert():
    # 万历二十六年芒种：符头比交节早八日，书中一路超到大雪才置闰。
    row = zhirun_term(date(1598, 5, 29))
    assert row['term'] == '芒种' and row['chao_days'] == 8
    assert zhirun_term(date(1598, 6, 13))['term'] == '夏至'


def test_every_term_gets_fifteen_days_and_only_mangzhong_daxue_repeat():
    seen, last = [], None
    day = date(2020, 1, 1)
    while day < date(2026, 12, 31):
        row = zhirun_term(day)
        if row['yuan_start'] != last:
            seen.append((row['term'], row['mode']))
            last = row['yuan_start']
        day = date.fromordinal(day.toordinal() + 5)
    assert {term for term, mode in seen if mode == '闰奇'} <= {'芒种', '大雪'}
    assert any(mode == '闰奇' for _, mode in seen)


def _run(*args):
    return subprocess.run([sys.executable, '-X', 'utf8', 'scripts/qimen_cast.py', '--date', '2026-06-20',
                           '--time', '10:00', *args], cwd=SKILL, capture_output=True, text=True, encoding='utf-8')


def test_cli_offers_zhirun_beside_the_default():
    run = _run
    default, zhirun = json.loads(run().stdout), json.loads(run('--ju-method', 'zhirun').stdout)
    assert default['ok'] and zhirun['ok']
    context = zhirun['method_profile']['solar_term']
    assert context['method'] == 'zhirun' and context['mode'] in ('超神', '接气', '正授', '闰奇')
    assert zhirun['method_profile']['ding_ju'] == 'zhirun' and '置闰' in zhirun['method_profile']['intercalation']
    assert default['method_profile']['intercalation'] == 'none'
    assert determine_ju_zhirun(date(2026, 6, 20))[3]['mode'] in ('超神', '接气', '正授', '闰奇')
