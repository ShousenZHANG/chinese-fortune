"""大六壬本命与行年：本命是出生年支，行年男一岁起丙寅顺行、女一岁起壬申逆行，每岁一位；
课里看它们在地盘哪一位、上面加的是天盘哪一神、乘哪一将。

- 起法与例：《选择要略》「男一歲起丙寅順行，女一歲起壬申逆行」，二十三岁男戊子、女庚戌（xuanze:c002:p0094）；
  《六壬大全》夫四十九行年在甲寅、妻三十四在己亥（liuren:c006:p0034）。
- 用法：「日上三傳本命行年六處最𦂳」（liuren:c003:p0038）；「行年在癸巳上見功曹」即看行年那一位上的天盘神
  （liuren:c003:p0102）。

岁数按虚岁：出生那个立春年算一岁，每过一个立春加一岁（与年柱同一换年点）。只给位置，不断吉凶。
"""
from __future__ import annotations

from utils import jiazi_index

STEMS, BRANCHES = '甲乙丙丁戊己庚辛壬癸', '子丑寅卯辰巳午未申酉戌亥'
SOURCES = (
    ('xuanze:c002:p0094', '男一歲起丙寅順行，女一歲起壬申逆行', '行年起法'),
    ('liuren:c006:p0034', '夫年四十九嵗在甲寅落妻年三十四己亥', '六壬大全行年例'),
    ('liuren:c003:p0038', '日上三傳本命行年六處最𦂳', '本命行年要看'),
    ('liuren:c003:p0102', '行年在癸巳上見功曹', '看行年上的天盘神'),
)


def _ganzhi(index: int) -> str:
    return STEMS[index % 10] + BRANCHES[index % 12]


def xingnian(age: int, gender: str) -> str:
    """行年干支：男从丙寅（第 2）顺数，女从壬申（第 8）逆数，一岁一位。"""
    if age < 1:
        raise ValueError('虚岁至少一岁')
    if gender == 'male':
        return _ganzhi(jiazi_index('丙', '寅') + age - 1)
    if gender == 'female':
        return _ganzhi(jiazi_index('壬', '申') - (age - 1))
    raise ValueError('行年要分男女：gender 填 male 或 female')


def _seat(branch: str, tian_pan: dict[str, str], jiang: dict[str, dict]) -> dict:
    general = next((name for name, seat in jiang.items() if seat.get('di_pan') == branch), None)
    return {'di_pan': branch, 'tian_pan': tian_pan.get(branch), 'general': general}


def benming_xingnian(birth_year_ganzhi: str, birth_year: int, cast_year_ganzhi: str, cast_year: int,
                     gender: str, tian_pan: dict[str, str], jiang: dict[str, dict]) -> dict:
    age = cast_year - birth_year + 1
    walk = xingnian(age, gender)
    b = {'ganzhi': birth_year_ganzhi, **_seat(birth_year_ganzhi[1], tian_pan, jiang)}
    w = {'ganzhi': walk, **_seat(walk[1], tian_pan, jiang)}
    out: dict = {'age_xusui': age, 'gender': gender, 'benming': b, 'xingnian': w,
           'sources': [{'passage_id': pid, 'quote': quote, 'use': use} for pid, quote, use in SOURCES],
           'convention': '虚岁按立春换年；行年取干支的地支在地盘的位置，天盘与天将照本课',
           'scope': '只给本命、行年在课里的位置，不断吉凶'}
    out['say'] = (f"本命{birth_year_ganzhi}，{b['di_pan']}上见{b['tian_pan']}" + (f"乘{b['general']}" if b['general'] else '')
                  + f"；{cast_year_ganzhi}年{'男' if gender == 'male' else '女'}命虚岁{age}，行年{walk}，"
                  f"{w['di_pan']}上见{w['tian_pan']}" + (f"乘{w['general']}" if w['general'] else '') + '。')
    return out
