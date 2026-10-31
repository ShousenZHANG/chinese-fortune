"""长生、博士、将前、岁前 four sets of twelve gods on the natal palaces.

Mainstream charts (iztro, Renhuai's ziwei-doushu) print all four on every
palace; this chart printed none. 长生十二神 follows 《紫微斗数全书》卷二
for its starting branches (ziwei:c002:p0057: 火局寅、木局亥、水局申、金局巳、土局申); the
direction is the modern 阳男阴女顺、阴男阳女逆, which differs from p0056's literal
男顺女逆, and the output says so. The transcription does not state the 博士, 将前 or 岁前
rules; those follow the common convention (博士随禄存起, 将前按年支三合起将星,
岁前从年支起岁建) and are labelled as such. They are labels on palaces, not
verdicts.
"""
from __future__ import annotations

from utils import DIZHI

CHANGSHENG = ('长生', '沐浴', '冠带', '临官', '帝旺', '衰', '病', '死', '墓', '绝', '胎', '养')
BOSHI = ('博士', '力士', '青龙', '小耗', '将军', '奏书', '飞廉', '喜神', '病符', '大耗', '伏兵', '官府')
JIANGQIAN = ('将星', '攀鞍', '岁驿', '息神', '华盖', '劫煞', '灾煞', '天煞', '指背', '咸池', '月煞', '亡神')
SUIQIAN = ('岁建', '晦气', '丧门', '贯索', '官符', '小耗', '大耗', '龙德', '白虎', '天德', '吊客', '病符')
# 五行局 number -> branch where 长生 starts (全书卷二).
CHANGSHENG_START = {2: '申', 3: '亥', 4: '巳', 5: '申', 6: '寅'}
# 将星 by the year branch's 三合 group: 寅午戌午、申子辰子、巳酉丑酉、亥卯未卯.
JIANGXING = {'寅': '午', '午': '午', '戌': '午', '申': '子', '子': '子', '辰': '子',
             '巳': '酉', '酉': '酉', '丑': '酉', '亥': '卯', '卯': '卯', '未': '卯'}
SOURCES = {'changsheng': '起点出自 ziwei:c002:p0057，原文：「火局命寅起长生。木局命亥起长生。水局命申起长生。金局命巳起长生。'
                         '土局命申起长生。」顺逆按现代通行的阳男阴女顺、阴男阳女逆（与 iztro 一致），与 ziwei:c002:p0056 原文'
                         '「男命顺数、女命逆数」不同；引用时只引这两句原文，不要把概括加引号',
           'boshi': '现代通行口径（随禄存起，阳男阴女顺、阴男阳女逆）；所选《全书》转录未载',
           'jiangqian': '现代通行口径（按年支三合起将星，顺行）；所选《全书》转录未载',
           'suiqian': '现代通行口径（从年支起岁建，顺行）；转录 ziwei:c002:p0061 只载丧门、吊客、白虎、官府的相对位置'}


def _forward(gender: str, year_branch: str) -> bool:
    """阳男阴女顺行、阴男阳女逆行; 阳支 are the even-indexed branches from 子."""
    yang = DIZHI.index(year_branch) % 2 == 0
    return yang == (gender == 'male')


def _place(names: tuple[str, ...], start: str, forward: bool) -> dict[str, str]:
    base = DIZHI.index(start)
    step = 1 if forward else -1
    return {DIZHI[(base + step * i) % 12]: name for i, name in enumerate(names)}


def twelve_gods(*, ju_number: int, gender: str, year_branch: str, lu_cun_branch: str) -> dict[str, dict[str, str]]:
    """{set: {palace branch: god}} for the four sets."""
    forward = _forward(gender, year_branch)
    return {
        'changsheng': _place(CHANGSHENG, CHANGSHENG_START[ju_number], forward),
        'boshi': _place(BOSHI, lu_cun_branch, forward),
        'jiangqian': _place(JIANGQIAN, JIANGXING[year_branch], True),
        'suiqian': _place(SUIQIAN, year_branch, True),
    }
