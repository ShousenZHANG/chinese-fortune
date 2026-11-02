"""出生地解析: 省名前缀、同名区县、未收录时的近似候选.

cities_cn.json 只收地级市, 名字互不重复; 同名麻烦出在区县: 「朝阳」可以是北京
朝阳区也可以是辽宁朝阳市, 旧逻辑不声不响地取了后者。这里先剥省名前缀, 再查同名
区县表; 仍有多个候选就交回调用方, 由用户指明省份。区县的经纬度一律借所属地级市
在表里的值 (同城区县相差不到 0.3°, 约 1 分钟真太阳时), 不另填数字。
"""
from __future__ import annotations

import difflib

from utils import _load_city_index, lookup_city

# 同名区县 -> [(所属地级市在表里的名字, 完整名称)]。只收同名的或常被直接说出的区县。
DISTRICTS: dict[str, list[tuple[str, str]]] = {
    '朝阳': [('北京', '北京市朝阳区'), ('朝阳', '辽宁省朝阳市')],
    '通州': [('北京', '北京市通州区'), ('南通', '江苏省南通市通州区')],
    '鼓楼': [('南京', '江苏省南京市鼓楼区'), ('福州', '福建省福州市鼓楼区'), ('徐州', '江苏省徐州市鼓楼区'),
             ('开封', '河南省开封市鼓楼区')],
    '长安': [('西安', '陕西省西安市长安区'), ('石家庄', '河北省石家庄市长安区')],
    '和平': [('天津', '天津市和平区'), ('沈阳', '辽宁省沈阳市和平区')],
    '普陀': [('上海', '上海市普陀区'), ('舟山', '浙江省舟山市普陀区')],
    '江北': [('重庆', '重庆市江北区'), ('宁波', '浙江省宁波市江北区')],
    '宝山': [('上海', '上海市宝山区'), ('双鸭山', '黑龙江省双鸭山市宝山区')],
    '白云': [('广州', '广东省广州市白云区'), ('贵阳', '贵州省贵阳市白云区')],
    '西湖': [('杭州', '浙江省杭州市西湖区'), ('南昌', '江西省南昌市西湖区')],
    '新华': [('石家庄', '河北省石家庄市新华区'), ('沧州', '河北省沧州市新华区'), ('平顶山', '河南省平顶山市新华区')],
    '城关': [('拉萨', '西藏拉萨市城关区'), ('兰州', '甘肃省兰州市城关区')],
    '海淀': [('北京', '北京市海淀区')],
    '浦东': [('上海', '上海市浦东新区')],
}
SUFFIXES = ('新区', '区', '县')


def _strip_province(text: str, provinces: set[str]) -> tuple[str | None, str]:
    for province in sorted(provinces, key=len, reverse=True):
        for prefix in (province + '省', province + '市', province + '自治区', province):
            if text.startswith(prefix) and len(text) > len(prefix):
                return province, text[len(prefix):]
    return None, text


def _district_key(text: str) -> str:
    for suffix in SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix) + 1:
            return text[:-len(suffix)]
    return text


def resolve(name: str) -> tuple[dict | None, list[dict]]:
    """(row, candidates): a row when the place is clear; otherwise the candidates to choose from."""
    index = _load_city_index()
    provinces = {row['province'] for row in index.values()}
    province, rest = _strip_province(name.strip(), provinces)
    rest = rest.removeprefix('市')
    for key, entries in DISTRICTS.items():      # 「南京鼓楼区」: the parent city named before the district
        for parent, label in entries:
            tail = rest[len(parent):].removeprefix('市') if rest.startswith(parent) else ''
            if tail and _district_key(tail) == key:
                row = lookup_city(parent)
                if row and (province is None or row['province'] == province):
                    return {**row, 'name': label, 'resolved_via': row['name']}, []
    choices = []
    for parent, label in DISTRICTS.get(_district_key(rest), []):
        row = lookup_city(parent)
        if row and (province is None or row['province'] == province):
            choices.append({**row, 'name': label, 'resolved_via': row['name']})
    if len(choices) == 1:
        return choices[0], []
    if len(choices) > 1:
        return None, choices
    row = lookup_city(rest) or lookup_city(_district_key(rest))
    if row and (province is None or row['province'] == province):
        return row, []
    near = difflib.get_close_matches(rest, list(index), n=5, cutoff=0.5)
    return None, [{**index[k], 'suggested_for': name} for k in dict.fromkeys(near)]


def describe(candidates: list[dict]) -> str:
    return '；'.join(f"{c['name']}（{c['province']}，东经{c['lon']}°）" for c in candidates)
