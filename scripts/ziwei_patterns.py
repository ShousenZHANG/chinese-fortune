"""紫微: 格局判定, 条件照《紫微斗数全书》原文.

《全书》卷一 p0153-p0156 有一份格局清单, 每格一句定义 (如「金灿光辉 太阳单守，
命在午宫是也」); 卷一「论X格」(p0098-p0111) 与卷三诸星分论 (c003:p0120 起) 另给
成格条件和加减注 (如「机月同梁作吏人  命在寅申方论……凶杀空劫化忌为下格」)。
每个格在 SPECS 里记出处段号和原句, 判定函数把原文条件拆成三组:
required 成格必须满足的、bonus 原文说更好的、breaking 原文说减力或破格的。
转录查不到的现代通行格标 modern_convention, 不说成原书格局。

按定义永远凑不齐的格不收 (金舆扶驾要日月夹紫微、财印夹禄要梁相夹禄, 按安星
规则太阳不与紫微相邻、天梁天相永远相邻), 免得看起来像「从不出现」的漏判。
马头带剑卷一作「马有刃」也凑不齐, 改用卷三的定义, 见 _ma_tou_dai_jian。
亮度一律按七级表判庙旺陷, 与 --brightness 选哪张表显示无关。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from utils import DIZHI
from ziwei_brightness import seven_level

LUCKY = ('左辅', '右弼', '文昌', '文曲', '天魁', '天钺')
SHA4 = ('擎羊', '陀罗', '火星', '铃星')
KONG_JIE = ('地空', '地劫')
KONG_WANG = ('旬空', '截路', '空亡', '截空')
BRIGHT = ('庙', '旺')
FOUR_TOMBS = '辰戌丑未'

Result = tuple[list[str], list[str], list[str]]


@dataclass(frozen=True)
class Chart:
    ming: str
    shen: str
    stars: dict[str, frozenset[str]]
    mains: dict[str, tuple[str, ...]]
    names: dict[str, str]
    sihua: dict[str, str]
    year_stem: str

    def at(self, star: str) -> str | None:
        return next((b for b in DIZHI if star in self.stars[b]), None)

    def has(self, branch: str, *stars: str) -> bool:
        return all(s in self.stars[branch] for s in stars)

    def sfsz(self, branch: str | None = None) -> list[str]:
        i = DIZHI.index(branch or self.ming)
        return [DIZHI[(i + k) % 12] for k in (0, 6, 4, 8)]

    def sfsz_stars(self, branch: str | None = None) -> set[str]:
        return set().union(*(self.stars[b] for b in self.sfsz(branch)))

    def jia_by(self, a: str, b: str, branch: str | None = None) -> bool:
        i = DIZHI.index(branch or self.ming)
        prev, nxt = self.stars[DIZHI[(i - 1) % 12]], self.stars[DIZHI[(i + 1) % 12]]
        return (a in prev and b in nxt) or (b in prev and a in nxt)

    def kong(self, branch: str) -> list[str]:
        return [s for s in KONG_WANG if s in self.stars[branch]]

    def lucky(self, branches: list[str]) -> list[str]:
        good = LUCKY + ('禄存',) + tuple(self.sihua.get(k, '') for k in ('禄', '权', '科'))
        return sorted({s for b in branches for s in self.stars[b] if s and s in good})

    def level(self, star: str) -> str | None:
        branch = self.at(star)
        return seven_level(star, branch) if branch else None

    def hua(self, kind: str) -> str | None:
        return self.sihua.get(kind)


def _need(*conds: tuple[bool, str]) -> list[str] | None:
    return [text for ok, text in conds] if all(ok for ok, _ in conds) else None


def _done(req: list[str] | None, bonus: list[str] | None = None,
          breaking: list[str] | None = None) -> Result | None:
    return None if req is None else (req, bonus or [], breaking or [])


def _opt(*conds: tuple[bool, str]) -> list[str]:
    return [text for ok, text in conds if ok]


def _sha(stars: set[str] | frozenset[str], names: tuple[str, ...] = SHA4 + KONG_JIE) -> list[str]:
    return [s for s in names if s in stars]


# --- 卷一格局清单 (c001:p0153-p0155) -------------------------------------------

def _ri_yue_zhao_bi(c: Chart) -> Result | None:
    home = c.names['田宅宫']
    req = _need((c.has(home, '太阳', '太阴'), f'太阳太阴同在田宅宫（{home}）'))
    return _done(req, _opt((home in FOUR_TOMBS, '田宅在墓库（原文：喜居墓库）')))


def _jin_can_guang_hui(c: Chart) -> Result | None:
    req = _need((c.ming == '午', '命宫在午'), (c.mains[c.ming] == ('太阳',), '太阳单守命宫'))
    return _done(req)


def _ri_yue_jia_ming(c: Chart) -> Result | None:
    req = _need((c.jia_by('太阳', '太阴'), '太阳太阴分居命宫前后'))
    if not req:
        return None
    good, empty = c.lucky([c.ming]), c.kong(c.ming)
    return (req, _opt((bool(good), f'命宫有吉星（{"、".join(good)}）')),
            _opt((bool(empty), f'命宫坐空亡（{"、".join(empty)}；原文：不坐空亡）')))


def _ri_chu_fu_sang(c: Chart) -> Result | None:
    seat = '命宫' if c.ming == '卯' else '官禄宫' if c.names['官禄宫'] == '卯' else None
    req = _need((c.at('太阳') == '卯' and seat is not None, f'太阳在卯守{seat}'))
    return _done(req)


def _yue_lang_tian_men(c: Chart) -> Result | None:
    req = _need((c.ming == '亥' and '太阴' in c.mains[c.ming], '太阴在亥守命'))
    return _done(req)


def _yue_sheng_cang_hai(c: Chart) -> Result | None:
    req = _need((c.names['田宅宫'] == '子' and c.at('太阴') == '子', '太阴在子守田宅'))
    return _done(req)


def _fu_bi_gong_zhu(c: Chart) -> Result | None:
    gong = {'左辅', '右弼'} <= c.sfsz_stars() - c.stars[c.ming]
    jia = c.jia_by('左辅', '右弼')
    req = _need(('紫微' in c.mains[c.ming], '紫微守命'),
                (gong or jia, '左辅右弼' + ('拱命（三方四正）' if gong else '夹命')))
    return _done(req)


def _jun_chen_qing_hui(c: Chart) -> Result | None:
    req = _need((c.has(c.ming, '紫微', '左辅', '右弼'), '紫微左辅右弼同守命宫'))
    if not req:
        return None
    met = [s for s in ('天相', '武曲', '太阴') if s in c.sfsz_stars()]
    return req, _opt((bool(met), f'更会{"、".join(met)}（原文：更会相武阴妙上）')), []


def _zuo_gui_xiang_gui(c: Chart) -> Result | None:
    here = [s for s in ('天魁', '天钺') if s in c.stars[c.ming]]
    other = {'天魁': '天钺', '天钺': '天魁'}
    req = _need((len(here) == 1 and other[here[0]] in c.sfsz_stars() if here else False,
                 '天魁天钺一坐命宫、一在三方四正拱照'))
    return _done(req)


def _ma_tou_dai_jian(c: Chart) -> Result | None:
    # 卷一 p0154 定义作「马有刃」(天马擎羊同宫), 但天马只落寅申巳亥、擎羊不落这四宫,
    # 同宫凑不出来; 取卷三 c003:p0155 的读法: 擎羊在午守命 (午为马)。
    req = _need((c.ming == '午' and '擎羊' in c.stars[c.ming], '擎羊在午守命'))
    good = c.lucky(c.sfsz())
    return _done(req, _opt((len(good) >= 2, f'吉多（{"、".join(good)}；原注：吉多勿论）')))


def _xing_qiu_jia_yin(c: Chart) -> Result | None:
    seat = '命宫' if c.has(c.ming, '天刑', '廉贞') else '身宫' if c.has(c.shen, '天刑', '廉贞') else None
    req = _need((seat is not None, f'天刑廉贞同临{seat}'))
    return _done(req)


def _tan_huo_xiang_feng(c: Chart) -> Result | None:
    req = _need((c.has(c.ming, '贪狼', '火星'), '贪狼火星同守命宫'),
                (c.level('贪狼') in BRIGHT and c.level('火星') in BRIGHT,
                 f'二星庙旺（贪狼{c.level("贪狼")}、火星{c.level("火星")}）'))
    return _done(req)


def _wu_qu_shou_yuan(c: Chart) -> Result | None:
    req = _need((c.ming == '卯' and '武曲' in c.mains[c.ming], '武曲在卯守命'))
    return _done(req)


def _quan_lu_sheng_feng(c: Chart) -> Result | None:
    lu, quan = c.hua('禄'), c.hua('权')
    both = bool(lu and quan) and c.has(c.ming, lu or '', quan or '')
    req = _need((both, f'生年化禄（{lu}）化权（{quan}）同守命宫'),
                (both and c.level(lu or '') in BRIGHT and c.level(quan or '') in BRIGHT,
                 '二星庙旺（原文：陷不是）'))
    return _done(req)


def _yang_ren_ru_miao(c: Chart) -> Result | None:
    good = c.lucky(c.sfsz())
    req = _need(('擎羊' in c.stars[c.ming] and c.ming in FOUR_TOMBS, '擎羊在辰戌丑未守命'),
                (bool(good), f'遇吉（三方四正见{"、".join(good)}）'))
    return _done(req)


def _sheng_bu_feng_shi(c: Chart) -> Result | None:
    empty = c.kong(c.ming)
    req = _need(('廉贞' in c.mains[c.ming], '廉贞守命'), (bool(empty), f'命宫坐空亡（{"、".join(empty)}）'))
    return _done(req)


def _lu_feng_liang_sha(c: Chart) -> Result | None:
    empty, kj = c.kong(c.ming), _sha(c.sfsz_stars(), KONG_JIE)
    req = _need(('禄存' in c.stars[c.ming] and bool(empty), f'禄存守命而坐空亡（{"、".join(empty)}）'),
                (bool(kj), f'又逢{"、".join(kj)}'))
    return _done(req)


def _cai_yu_qiu_chou(c: Chart) -> Result | None:
    split = (('武曲' in c.mains[c.ming] and '廉贞' in c.mains[c.shen])
             or ('廉贞' in c.mains[c.ming] and '武曲' in c.mains[c.shen]))
    req = _need((split, '武曲廉贞分守命宫身宫'))
    return _done(req)


def _yi_sheng_gu_pin(c: Chart) -> Result | None:
    req = _need(('破军' in c.mains[c.ming] and c.level('破军') == '陷', '破军守命落陷'))
    return _done(req)


def _jun_zi_zai_ye(c: Chart) -> Result | None:
    hits = [f'{s}在{"命宫" if b == c.ming else "身宫"}' for b in dict.fromkeys((c.ming, c.shen))
            for s in SHA4 if s in c.stars[b] and seven_level(s, b) == '陷']
    req = _need((bool(hits), '四煞守身命而落陷（' + '、'.join(hits) + '）'))
    return _done(req)


# --- 卷一论X格 (c001:p0098-p0111) ----------------------------------------------

def _dui_mian_chao_dou(c: Chart) -> Result | None:
    move = c.names['迁移宫']
    req = _need((move in '子午' and '禄存' in c.stars[move], f'禄存在迁移宫（{move}）'))
    return _done(req)


def _jian_wen_wu(c: Chart) -> Result | None:
    seats = c.stars[c.ming] | c.stars[c.shen]
    req = _need(({'文曲', '武曲'} <= seats, '文曲武曲在身命'))
    if not req:
        return None
    bad = _sha(c.stars[c.ming], SHA4) + (['破军'] if '破军' in c.mains[c.ming] else [])
    return req, [], _opt((bool(bad), f'命宫有{"、".join(bad)}（诗：更值命宫无杀破）'))


def _shi_zhong_yin_yu(c: Chart) -> Result | None:
    req = _need((c.ming in '子午' and '巨门' in c.mains[c.ming], '巨门在子午守命'))
    if not req:
        return None
    hua = [c.hua(k) for k in ('科', '权', '禄') if c.hua(k) in c.sfsz_stars()]
    return req, _opt((bool(hua), f'三方四正见化科权禄（{"、".join(h for h in hua if h)}）'),
                     (c.year_stem in '辛癸', f'{c.year_stem}年生（卷三：辛癸人上格）'),
                     (c.year_stem in '丁己', f'{c.year_stem}年生（卷三：丁己人次之）')), []


def _huo_gui(c: Chart) -> Result | None:
    seat = next((n for n, b in (('命宫', c.ming), ('身宫', c.shen)) if {'贪狼', '火星'} <= c.sfsz_stars(b)), None)
    req = _need((seat is not None, f'贪狼火星同在{seat}三方四正'))
    if not req:
        return None
    bad = _sha(c.sfsz_stars(), ('擎羊', '陀罗', '铃星') + KONG_JIE)
    return req, [], _opt((bool(bad), f'三方见{"、".join(bad)}（诗：三方倘若无凶杀）'))


# --- 卷三诸星分论 (c003:p0120 起) ----------------------------------------------

def _tan_huo_ling_si_mu(c: Chart) -> Result | None:
    fire = [s for s in ('火星', '铃星') if s in c.sfsz_stars()]
    req = _need(('贪狼' in c.mains[c.ming] and c.ming in FOUR_TOMBS, '贪狼在辰戌丑未守命'),
                (bool(fire), f'{"、".join(fire)}守照'))
    return _done(req, _opt((c.ming in '辰戌', '命在辰戌（原注：辰戌宫佳）')))


def _fu_xiang_chao_yuan(c: Chart) -> Result | None:
    # 天相永远在天府后四位, 两星必同在一个三方; 「朝垣」取二星都从命宫以外的三方来朝。
    req = _need(({'天府', '天相'} <= c.sfsz_stars() - c.stars[c.ming], '天府天相从三方四正朝命（不坐命宫）'))
    upper = c.ming in '寅申' and {c.at('天府'), c.at('天相')} <= {c.names['财帛宫'], c.names['官禄宫']}
    return _done(req, _opt((upper, '命在寅申、府相在财帛官禄（原注：上格）')))


def _ji_yue_tong_liang(c: Chart) -> Result | None:
    req = _need((c.ming in '寅申', '命在寅申'),
                ({'天机', '太阴', '天同', '天梁'} <= c.sfsz_stars(), '天机太阴天同天梁齐会三方四正'))
    if not req:
        return None
    bad = _sha(c.sfsz_stars()) + ([f'化忌（{c.hua("忌")}）'] if c.hua('忌') in c.sfsz_stars() else [])
    return req, [], _opt((bool(bad), f'三方见{"、".join(bad)}（原注：凶杀空劫化忌为下格）'))


def _ming_zhu_chu_hai(c: Chart) -> Result | None:
    req = _need((c.ming == '未', '命宫在未'), (c.at('太阳') == '卯' and c.at('太阴') == '亥', '太阳在卯、太阴在亥'))
    return _done(req)


def _ri_yue_tong_gong(c: Chart) -> Result | None:
    seat = next((n for n, b in (('命宫', c.ming), ('身宫', c.shen)) if c.has(b, '太阳', '太阴')), None)
    req = _need((seat is not None, f'太阳太阴同守{seat}（丑未）'))
    if not req:
        return None
    good = c.lucky(c.sfsz())
    return req, _opt((bool(good), f'三方四正见{"、".join(good)}')), _opt((not good, '三方无吉（原文：反为凶）'))


def _chang_qu_jia_ming(c: Chart) -> Result | None:
    req = _need((c.jia_by('文昌', '文曲'), '文昌文曲分居命宫前后'))
    good = c.lucky([c.ming])
    return _done(req, _opt((bool(good), f'命宫有吉星（{"、".join(good)}；原注：吉多方论此为贵）')))


def _kui_yue_jia_ming(c: Chart) -> Result | None:
    req = _need((c.jia_by('天魁', '天钺'), '天魁天钺分居命宫前后'))
    return _done(req)


def _zuo_you_jia_ming(c: Chart) -> Result | None:
    req = _need((c.jia_by('左辅', '右弼'), '左辅右弼分居命宫前后'))
    return _done(req)


def _yang_tuo_jia_ji(c: Chart) -> Result | None:
    ji = c.hua('忌')
    req = _need((bool(ji) and ji in c.stars[c.ming], f'生年化忌（{ji}）坐命'),
                (c.jia_by('擎羊', '陀罗'), '擎羊陀罗分居命宫前后'))
    return _done(req)


def _huo_ling_jia_ming(c: Chart) -> Result | None:
    req = _need((c.jia_by('火星', '铃星'), '火星铃星分居命宫前后'))
    if not req:
        return None
    good, ji = c.lucky([c.ming]), c.hua('忌')
    return (req, _opt((bool(good), f'命宫有吉星（{"、".join(good)}；原注：吉多尚可）')),
            _opt((bool(ji) and ji in c.stars[c.ming], f'命宫坐化忌（{ji}；原注：惟夹忌）')))


def _xiong_su_chao_yuan(c: Chart) -> Result | None:
    req = _need((c.ming in '申未' and '廉贞' in c.mains[c.ming], '廉贞在申未守命'))
    if not req:
        return None
    bad = _sha(c.sfsz_stars(), SHA4)
    return req, [], _opt((bool(bad), f'三方见{"、".join(bad)}（原注：加杀平常）'))


def _lu_ma_jiao_chi(c: Chart) -> Result | None:
    seat = next((b for b in c.sfsz() if c.has(b, '禄存', '天马')), None)
    req = _need((seat is not None, f'禄存天马同宫（{seat}）在命宫三方四正'))
    if not req or seat is None:
        return None
    bad = [s for s in ('擎羊', '火星') + KONG_WANG if s in c.stars[seat]]
    return req, [], _opt((bool(bad), f'同宫见{"、".join(bad)}（卷三：忌见杀羊火截路空亡）'))


def _ke_quan_lu_he(c: Chart) -> Result | None:
    hua = [c.hua(k) for k in ('科', '权', '禄')]
    req = _need((all(h and h in c.sfsz_stars() for h in hua), f'生年化科权禄（{"、".join(h or "" for h in hua)}）齐会三方四正'))
    return _done(req)


def _shuang_lu(c: Chart) -> Result | None:
    lu = c.hua('禄')
    req = _need((bool(lu) and c.has(c.ming, '禄存', lu or ''), f'禄存与生年化禄（{lu}）同守命宫'))
    if not req:
        return None
    kj = _sha(c.sfsz_stars(), KONG_JIE)
    return req, [], _opt((bool(kj), f'遇{"、".join(kj)}，即两重华盖（ziwei:c001:p0155）'))


def _qi_sha_chao_dou(c: Chart) -> Result | None:
    req = _need((c.ming in '寅申子午' and '七杀' in c.mains[c.ming], '七杀在寅申子午守命'))
    return _done(req)


def _zi_fu_tong_gong(c: Chart) -> Result | None:
    req = _need((c.has(c.ming, '紫微', '天府'), '紫微天府同守命宫'))
    return _done(req)


def _tan_wu_tong_xing(c: Chart) -> Result | None:
    req = _need((c.has(c.ming, '武曲', '贪狼'), '武曲贪狼同守命宫'))
    return _done(req)


# --- 现代通行 (所选转录未载) -----------------------------------------------------

def _yang_liang_chang_lu(c: Chart) -> Result | None:
    seen = c.sfsz_stars()
    req = _need(({'太阳', '天梁', '文昌'} <= seen, '太阳天梁文昌会于三方四正'),
                ('禄存' in seen or c.hua('禄') in seen, '并见禄存或生年化禄'))
    return _done(req)


def _sha_po_lang(c: Chart) -> Result | None:
    req = _need(({'七杀', '破军', '贪狼'} <= c.sfsz_stars(), '七杀破军贪狼会于三方四正'))
    return _done(req)


def _kong_jie_jia_ming(c: Chart) -> Result | None:
    req = _need((c.jia_by('地空', '地劫'), '地空地劫分居命宫前后'))
    return _done(req)


Spec = tuple[str, str, Optional[str], Optional[str], Callable[[Chart], Optional[Result]]]
QUANSHU, MODERN = 'quanshu_definition', 'modern_convention'
# (名称, 出处类别, passage id, 原句, 判定)
SPECS: tuple[Spec, ...] = (
    ('日月照璧', QUANSHU, 'ziwei:c001:p0153', '日月照璧 日月临田宅宫是也，喜居墓库', _ri_yue_zhao_bi),
    ('金灿光辉', QUANSHU, 'ziwei:c001:p0153', '金灿光辉 太阳单守，命在午宫是也', _jin_can_guang_hui),
    ('日月夹命', QUANSHU, 'ziwei:c001:p0154', '日月夹命 不坐空亡遇逢本宫有吉星是也', _ri_yue_jia_ming),
    ('日出扶桑', QUANSHU, 'ziwei:c001:p0154', '日出扶桑 日在卯守命是也，守官禄宫亦然', _ri_chu_fu_sang),
    ('月朗天门', QUANSHU, 'ziwei:c001:p0154', '月落亥宫 月在亥守命是也，又名月朗天门', _yue_lang_tian_men),
    ('月生沧海', QUANSHU, 'ziwei:c001:p0154', '月生沧海 月在子宫守田宅是也', _yue_sheng_cang_hai),
    ('辅弼拱主', QUANSHU, 'ziwei:c001:p0154', '辅弼拱主 紫微守命二星来拱是也，夹之亦然', _fu_bi_gong_zhu),
    ('君臣庆会', QUANSHU, 'ziwei:c001:p0154', '君臣庆会 紫微左右同守命是也，更会相武阴妙上', _jun_chen_qing_hui),
    ('坐贵向贵', QUANSHU, 'ziwei:c001:p0154', '坐贵向贵 谓魁钺在命迭相坐拱是也', _zuo_gui_xiang_gui),
    ('马头带剑', QUANSHU, 'ziwei:c003:p0155', '擎羊子午卯酉非夭折而刑伤  午凶卯次之。子酉又次之，马头带剑，吉多勿论',
     _ma_tou_dai_jian),
    ('刑囚夹印', QUANSHU, 'ziwei:c001:p0154', '刑囚夹印 天刑廉贞同临身命主武勇之人', _xing_qiu_jia_yin),
    ('贪火相逢', QUANSHU, 'ziwei:c001:p0154', '贪火相逢 谓二星守命同居庙旺是也', _tan_huo_xiang_feng),
    ('武曲守垣', QUANSHU, 'ziwei:c001:p0154', '武曲守垣 武守命卯宫是也，余不是', _wu_qu_shou_yuan),
    ('权禄生逢', QUANSHU, 'ziwei:c001:p0154', '权禄生逢 二星守命庙旺是也，陷不是', _quan_lu_sheng_feng),
    ('羊刃入庙', QUANSHU, 'ziwei:c001:p0154', '羊刃入庙 辰戍丑未守命遇吉是也', _yang_ren_ru_miao),
    ('生不逢时', QUANSHU, 'ziwei:c001:p0155', '生不逢时 命坐空亡逢廉贞是也', _sheng_bu_feng_shi),
    ('禄逢两杀', QUANSHU, 'ziwei:c001:p0155', '禄逢两杀 禄坐空亡又逢空劫杀星是也', _lu_feng_liang_sha),
    ('财与囚仇', QUANSHU, 'ziwei:c001:p0155', '财与囚仇 武贞同守身命是也', _cai_yu_qiu_chou),
    ('一生孤贫', QUANSHU, 'ziwei:c001:p0155', '一生孤贫 谓破守命星陷地是也', _yi_sheng_gu_pin),
    ('君子在野', QUANSHU, 'ziwei:c001:p0155', '君子在野 谓四杀守身命而言临陷地是也', _jun_zi_zai_ye),
    ('对面朝斗', QUANSHU, 'ziwei:c001:p0098', '论对面朝斗格 子午宫逢禄存是也', _dui_mian_chao_dou),
    ('兼文武', QUANSHU, 'ziwei:c001:p0104', '论兼文武格 文曲武曲在身命是也', _jian_wen_wu),
    ('石中隐玉', QUANSHU, 'ziwei:c001:p0108', '论石中隐玉格 命在子午逢巨门是也', _shi_zhong_yin_yu),
    ('火贵格', QUANSHU, 'ziwei:c001:p0110', '论贪狼遇火名为火贵格 三合照身命是也', _huo_gui),
    ('贪狼遇火铃于四墓', QUANSHU, 'ziwei:c003:p0145', '贪狼遇铃火四墓宫豪富家资侯伯贵', _tan_huo_ling_si_mu),
    ('府相朝垣', QUANSHU, 'ziwei:c003:p0121', '府相朝垣千锺食禄  命寅申，府相在财帛宫，禄官朝者，上格别宫次之',
     _fu_xiang_chao_yuan),
    ('机月同梁', QUANSHU, 'ziwei:c003:p0129', '机月同梁作吏人  命在寅申方论', _ji_yue_tong_liang),
    ('明珠出海', QUANSHU, 'ziwei:c003:p0135', '日卯月亥安命未宫多折桂', _ming_zhu_chu_hai),
    ('日月同宫', QUANSHU, 'ziwei:c003:p0135', '日月命身居丑末三方无吉反为凶', _ri_yue_tong_gong),
    ('昌曲夹命', QUANSHU, 'ziwei:c003:p0141', '昌曲夹命最为奇  假若命在丑宫，文昌在寅，文曲在子是也', _chang_qu_jia_ming),
    ('魁钺夹命', QUANSHU, 'ziwei:c003:p0165', '魁钺夹命为奇格  如命安在辰宫，魁在卯，钺在巳宫是也', _kui_yue_jia_ming),
    ('左右夹命', QUANSHU, 'ziwei:c003:p0168', '左右夹命为贵格  如安命在丑宫，左辅在子宫，右弼在寅宫', _zuo_you_jia_ming),
    ('羊陀夹忌', QUANSHU, 'ziwei:c003:p0155', '羊陀夹忌为败局  假如安命在申宫，又逢忌星，羊在酉陀在未夹之', _yang_tuo_jia_ji),
    ('火铃夹命', QUANSHU, 'ziwei:c003:p0160', '火铃夹命为败局  如命安寅申，火星在丑，铃星在卯', _huo_ling_jia_ming),
    ('雄宿朝元', QUANSHU, 'ziwei:c003:p0147', '廉贞申未宫无杀富贵声扬播远名  雄宿朝元格，加杀平常', _xiong_su_chao_yuan),
    ('禄马交驰', QUANSHU, 'ziwei:c001:p0064', '与禄存同宫，谓之禄马交驰', _lu_ma_jiao_chi),
    ('科权禄合', QUANSHU, 'ziwei:c003:p0174', '科权禄合富贵双全', _ke_quan_lu_he),
    ('双禄守命', QUANSHU, 'ziwei:c003:p0170', '双禄守命吕后专权', _shuang_lu),
    ('七杀朝斗', QUANSHU, 'ziwei:c003:p0151', '七杀寅申子午一生爵禄荣昌  为七杀朝斗格', _qi_sha_chao_dou),
    ('紫府同宫', QUANSHU, 'ziwei:c001:p0095', '紫府同宫终身福厚', _zi_fu_tong_gong),
    ('贪武同行', QUANSHU, 'ziwei:c001:p0095', '贪武同行威镇边夷', _tan_wu_tong_xing),
    ('阳梁昌禄', MODERN, None, None, _yang_liang_chang_lu),
    ('杀破狼', MODERN, None, None, _sha_po_lang),
    ('空劫夹命', MODERN, None, None, _kong_jie_jia_ming),
)


def detect_patterns(*, ming_branch: str, shen_branch: str, branch_to_main_stars: dict[str, list[str]],
                    branch_to_all_stars: dict[str, list[str]], palaces: list[dict], sihua: dict[str, str],
                    year_stem: str) -> list[dict]:
    chart = Chart(ming=ming_branch, shen=shen_branch,
                  stars={b: frozenset(branch_to_all_stars.get(b, [])) for b in DIZHI},
                  mains={b: tuple(branch_to_main_stars.get(b, [])) for b in DIZHI},
                  names={p['name']: p['branch'] for p in palaces}, sihua=dict(sihua), year_stem=year_stem)
    out: list[dict] = []
    for name, source, passage_id, quote, judge in SPECS:
        result = judge(chart)
        if result is None:
            continue
        required, bonus, breaking = result
        out.append({'name': name, 'source_status': source, 'passage_id': passage_id, 'quote': quote,
                    'required': required, 'bonus': bonus, 'breaking': breaking,
                    'evidence': '；'.join(required)})
    return out
