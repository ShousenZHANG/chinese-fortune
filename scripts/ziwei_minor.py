"""紫微杂曜补全: 月系 / 日系 / 时系 / 年系 30 颗.

与 ziwei_stars.place_miscellaneous_stars 的 9 颗 (天马 红鸾 天喜 孤辰 寡宿 天哭
天虚 龙池 凤阁) 合起来, 覆盖 iztro 默认盘面的全部杂曜。安法凡《全书》卷二有诀者
照诀, 并在 SOURCES 记 passage id; 诀中未载者取 iztro 默认表, 记为「通行表」。
所有下标为子起 (子=0), 与 utils.DIZHI 一致。
"""
from __future__ import annotations

from utils import DIZHI, TIANGAN, hour_branch_index

# 《全书》p0067 转录作「月德星从子上起子」, 照此月德永远与太岁同宫, 与天德
# (酉起) 的写法不成对; iztro 及各家安星表均为巳宫起子。取巳, 不取转录。
# 天德/月德原诀「顺数至流年太岁」是流年星, 本命盘按生年太岁安, 同 iztro。
NOTE = ("杂曜 39 颗: 9 颗旧有 + 30 颗补全。《全书》有诀者照诀; 月德取巳宫起子"
        "(所引转录作子宫, 与天德不成对); 天德/月德原为流年星, 本命盘按生年太岁安; "
        "截路空亡原诀为一星占两宫, 此处按 iztro 拆作截路(阳支)、空亡(阴支)。")

SOURCES: dict[str, str] = {
    "天刑": "ziwei:c002:p0046", "天姚": "ziwei:c002:p0046",
    "三台": "ziwei:c002:p0047", "八座": "ziwei:c002:p0047",
    "台辅": "ziwei:c002:p0053", "封诰": "ziwei:c002:p0055",
    "天德": "ziwei:c002:p0067", "月德": "ziwei:c002:p0067",
    "年解": "ziwei:c002:p0068",
    "天哭": "ziwei:c002:p0049", "天虚": "ziwei:c002:p0049",
    "龙池": "ziwei:c002:p0051", "凤阁": "ziwei:c002:p0051",
    "截路": "ziwei:c002:p0073", "空亡": "ziwei:c002:p0073", "截空": "ziwei:c002:p0073",
    "天伤": "ziwei:c002:p0040", "天使": "ziwei:c002:p0040",
}
COMMON_TABLE = "通行表"

_JIE_SHEN = "申戌子寅辰午"          # 月解神, 每两月一位
_YIN_SHA = "寅子戌申午辰"
_TIAN_YUE = "戌巳辰寅未卯亥未寅午戌寅"
_TIAN_WU = "巳申寅亥"
_TIAN_CHU = "巳午子巳午申寅午酉亥"   # 按年干 甲..癸
_TIAN_GUAN = "未辰巳寅卯酉亥酉戌午"
_TIAN_FU = "酉申子亥卯寅午巳午巳"
_JIE_LU = "申午辰寅子"               # 甲己 乙庚 丙辛 丁壬 戊癸
_KONG_WANG = "酉未巳卯丑"
# 截空单星: 甲乙丙丁戊取对子中的阳支, 己庚辛壬癸取阴支; 占验派戊癸改取戌亥。表取自
# Renhuai123/ziwei-doushu school-tables.generated.ts JK_ARR1 / JK_ARR3 (MIT)。
_JIE_KONG_SINGLE = "申午辰寅子酉未巳卯丑"
_JIE_KONG_ZHANYAN = "申午辰寅戌酉未巳卯亥"
_PO_SUI = "巳丑酉"
_FEI_LIAN = "申酉戌巳午未寅卯辰亥子丑"
_HUA_GAI_XIAN_CHI = {"寅午戌": ("戌", "卯"), "申子辰": ("辰", "酉"),
                     "巳酉丑": ("丑", "午"), "亥卯未": ("未", "子")}


def _at(index: int) -> str:
    return DIZHI[index % 12]


def _idx(branch: str) -> int:
    return DIZHI.index(branch)


def xun_kong(year_stem: str, year_branch: str) -> str:
    """生年旬中空亡的两支里, 取与年支同阴阳的一支。"""
    yb = _idx(year_branch)
    first = yb - TIANGAN.index(year_stem) + 10
    return _at(first if first % 2 == yb % 2 else first + 1)


def _jie_kong(stem_index: int, school: str) -> dict[str, str]:
    if school == "split":
        return {"截路": _JIE_LU[stem_index % 5], "空亡": _KONG_WANG[stem_index % 5]}
    table = _JIE_KONG_SINGLE if school == "single" else _JIE_KONG_ZHANYAN
    return {"截空": table[stem_index]}


def _shang_shi(ming: int, gender: str, year_branch: int, school: str) -> dict[str, str]:
    """天伤在奴仆宫 (命宫逆数第 8 宫), 天使在疾厄宫 (第 6 宫)。
    中州派 (iztro JS algorithm=zhongzhou): 阴男阳女两星对调。"""
    shang, shi = _at(ming - 7), _at(ming - 5)
    if school == "zhongzhou" and (year_branch % 2 == 0) != (gender == "male"):
        shang, shi = shi, shang
    return {"天伤": shang, "天使": shi}


def place_minor_stars(*, year_stem: str, year_branch: str, lunar_month: int, lunar_day: int,
                      hour: int, ming_branch: str, shen_branch: str, lucky: dict[str, str],
                      gender: str = "male", tianshi: str = "default",
                      jie_kong: str = "split") -> dict[str, str]:
    """补全杂曜的地支. lunar_month 为闰月处理后的有效月, lucky 为六吉位置."""
    m0, d0, t = lunar_month - 1, lunar_day - 1, hour_branch_index(hour)
    yb, ys = _idx(year_branch), TIANGAN.index(year_stem)
    mg = _idx(ming_branch)
    hua_gai, xian_chi = next(v for k, v in _HUA_GAI_XIAN_CHI.items() if year_branch in k)
    return {
        # 月系
        "天姚": _at(1 + m0), "天刑": _at(9 + m0),
        "解神": _JIE_SHEN[m0 // 2], "阴煞": _YIN_SHA[m0 % 6],
        "天月": _TIAN_YUE[m0], "天巫": _TIAN_WU[m0 % 4],
        # 日系
        "三台": _at(_idx(lucky["左辅"]) + d0), "八座": _at(_idx(lucky["右弼"]) - d0),
        "恩光": _at(_idx(lucky["文昌"]) + d0 - 1), "天贵": _at(_idx(lucky["文曲"]) + d0 - 1),
        # 时系
        "台辅": _at(6 + t), "封诰": _at(2 + t),
        # 年系
        "华盖": hua_gai, "咸池": xian_chi,
        "天才": _at(mg + yb), "天寿": _at(_idx(shen_branch) + yb),
        "天厨": _TIAN_CHU[ys], "天官": _TIAN_GUAN[ys], "天福": _TIAN_FU[ys],
        "破碎": _PO_SUI[yb % 3], "蜚廉": _FEI_LIAN[yb],
        "天德": _at(9 + yb), "月德": _at(5 + yb), "天空": _at(yb + 1),
        **_jie_kong(ys, jie_kong),
        "旬空": xun_kong(year_stem, year_branch), "年解": _at(10 - yb),
        **_shang_shi(mg, gender, yb, tianshi),
    }


def sources_for(stars: dict[str, str]) -> dict[str, list[str]]:
    """{passage id or 通行表: [stars]}, grouped so the basis stays short."""
    grouped: dict[str, list[str]] = {}
    for name in stars:
        grouped.setdefault(SOURCES.get(name, COMMON_TABLE), []).append(name)
    return grouped
