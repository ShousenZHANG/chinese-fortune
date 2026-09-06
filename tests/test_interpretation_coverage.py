"""引擎输出的每个术语, references/ 里都必须查得到解读依据。

这是 P3 的门禁。缺口不是「少一个标签」—— 一个 Claude 查不到规则的字段, 它要么
漏报, 要么**照着字面自由发挥**, 而输出的权威外观 (确定性引擎 + 古籍署名) 会让
用户以为那是古籍的说法。

修前实测缺口 (5 个引擎共 7 个词):
- 全合/半合/全会/半会 —— bazi 的 interactions 用它们标注三合三会的到场程度,
  而 references 只写了「三合」「三会」, 没有区分全/半, 更没说半合力弱
- 月德合 —— 月德 有 12 处, 其合 0 处; 而它是独立的一路神煞
- 自化 / 自化忌 / 自化科 —— **全库 0 处**。而且它根本不是《全书》的概念:
  三卷检索无此二字, 是飞星派后起之说。本仓库星曜安法以《全书》为纲, 唯此一项
  出自另一系 —— 不写清来历就等于借古籍的名义讲别家的话。

门禁本身不判断解读对不对 (那需要人), 只保证「引擎说出口的词, 文档里有」。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

try:
    import lunar_python  # noqa: F401
    HAS_LUNAR = True
except ImportError:
    HAS_LUNAR = False

pytestmark = pytest.mark.skipif(not HAS_LUNAR, reason="lunar_python not installed")

# 每个引擎跑一张有代表性的盘。术语是否出现取决于具体盘, 所以这里取多张。
CASES = [
    ("bazi", "bazi_calc.py", ["--year", 1990, "--month", 5, "--day", 10,
                              "--hour", 14, "--gender", "male"]),
    ("bazi", "bazi_calc.py", ["--year", 1984, "--month", 2, "--day", 4,
                              "--hour", 3, "--gender", "female"]),
    ("ziwei", "ziwei_calc.py", ["--year", 1990, "--month", 5, "--day", 10,
                                "--hour", 14, "--gender", "male"]),
    ("ziwei", "ziwei_calc.py", ["--year", 2001, "--month", 9, "--day", 21,
                                "--hour", 6, "--gender", "female"]),
    ("liuyao", "liuyao_cast.py", ["coins", "--seed", 7,
                                  "--date", "2026-06-01", "--time", "10:00"]),
    ("qimen", "qimen_cast.py", ["--date", "2026-06-01", "--time", "14:30"]),
    ("liuren", "liuren_cast.py", ["--date", "2026-06-01", "--time", "14:30",
                                  "--question", "x"]),
    ("meihua", "meihua_cast.py", ["--datetime", "2026-06-01T13:05", "time"]),
    ("huangli", "huangli_query.py", ["--date", "2026-06-01"]),
    ("xiaoliuren", "xiaoliuren_cast.py", ["lunar", "--month", 3, "--day", 15,
                                          "--hour-branch", "午"]),
]

# 豁免必须逐条写明理由 —— 一句「太通用了」不算。
EXEMPT: dict[str, str] = {
    "年支三合": "复合标注:「年支」+「三合」, 两半各自有据",
    "月支三合": "复合标注:「月支」+「三合」, 两半各自有据",
    "日支三合": "复合标注:「日支」+「三合」, 两半各自有据",
    "时支三合": "复合标注:「时支」+「三合」, 两半各自有据",
    "日柱旬空": "复合标注:「日柱」+「旬空」, 旬空 在 01-bazi.md 有 8 处",
    "年柱旬空": "复合标注:「年柱」+「旬空」, 旬空 在 01-bazi.md 有 8 处",
    "男命戌亥": "孤辰寡宿 的性别分野标注; 孤辰/寡宿 本身在 19-shensha.md 有据",
    "女命辰巳": "孤辰寡宿 的性别分野标注; 孤辰/寡宿 本身在 19-shensha.md 有据",
    "通根": "命理通用词, 01-bazi.md 正文多处使用 (非表格术语, 逐字匹配不到)",
}

# 整类豁免 —— 逐词写不现实, 但类别本身必须在文档里交代出处与解读原则。
# 每条给一个正则和一句「这一类在哪儿交代过」。
EXEMPT_PATTERNS: list[tuple[str, str, str]] = [
    (r"^(?:初[一二三四五六七八九十]|廿[一二三四五六七八九]?|三十|十[一二三四五六七八九]?)$",
     "农历日期数字如初三和廿五，仅是日期显示，不是待解释的术数条件",
     ""),
    (r"^[一二三四五六七八九十零〇]{2,5}$",
     "汉字数字 (农历日期如「一九八四」「廿三」), 不是术语",
     ""),
]


def _run(script: str, args) -> dict:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc.returncode == 0, f"{script}: {proc.stderr[-300:]}"
    return json.loads(proc.stdout)


def _terms(obj, out: set) -> None:
    """输出里所有 2-5 字的纯中文字符串值 —— 星名/神煞/格局/关系等术语。"""
    if isinstance(obj, dict):
        for v in obj.values():
            _terms(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _terms(v, out)
    elif isinstance(obj, str) and 2 <= len(obj) <= 5 and re.fullmatch(r"[一-鿿]+", obj):
        out.add(obj)


@pytest.fixture(scope="module")
def corpus() -> str:
    parts = [p.read_text(encoding="utf-8") for p in (ROOT / "references").glob("*.md")]
    parts.append((ROOT / "SKILL.md").read_text(encoding="utf-8"))
    return "\n".join(parts)


@pytest.mark.parametrize("name,script,args", CASES,
                         ids=[f"{c[0]}:{i}" for i, c in enumerate(CASES)])
def test_every_emitted_term_has_a_documented_rule(name, script, args, corpus):
    d = _run(script, args)
    terms: set = set()
    _terms(d, terms)
    assert terms, f"{script} 没有可检验的术语输出"

    def exempt_by_pattern(term: str) -> bool:
        return any(re.fullmatch(pat, term) for pat, _, _ in EXEMPT_PATTERNS)

    missing = sorted(t for t in terms
                     if t not in corpus and t not in EXEMPT and not exempt_by_pattern(t))
    assert not missing, (
        f"{name} 输出了 references/ 与 SKILL.md 都查不到的词: {missing}\n"
        "这些是 Claude 只能自由发挥的地方 —— 要么补文档, 要么把它们连同理由"
        "写进本文件的 EXEMPT。")


def test_exemptions_all_carry_a_reason():
    """豁免名单是欠账簿, 不是抑制器 —— 每条都要能独立读懂。"""
    assert EXEMPT, "豁免为空反而可疑 —— 复合词总是有的"
    for term, why in EXEMPT.items():
        assert len(why) >= 12, f"{term} 的豁免理由太空泛: {why!r}"
        assert "同上" not in why, f"{term}: 「同上」不算理由, 每条要能单独读懂"
    for pat, why, _ in EXEMPT_PATTERNS:
        assert len(why) >= 12, f"{pat} 的豁免理由太空泛: {why!r}"


def test_huangli_vocabulary_categories_are_documented(corpus):
    """黄历的 宜忌词表 (84 条)、时辰十二神、二十八宿全称 三组词不出自本仓库任何
    一张表 —— 它们来自 lunar_python 的通书词汇。逐条写进文档不现实, 但**类别**
    必须交代出处与解读原则, 否则 Claude 拿到「造车器」「斋醮」只能自行演绎。
    """
    md = (ROOT / "references" / "12-huangli.md").read_text(encoding="utf-8")
    assert "lunar_python" in md, "宜忌词表的来源未交代"
    assert "照字面转述" in md, "缺少解读原则 —— 不要替这些词编造吉凶推演"
    for shen in ("青龙", "明堂", "金匮", "天刑", "天牢", "勾陈"):
        assert shen in md, f"时辰十二神 {shen} 未列"
    assert "两套体系" in md, "必须说明时辰十二神与十二建除不是一回事"
    assert "七政" in md and "禽" in md, "二十八宿全称的构成未说明"


def test_zihua_declares_it_is_not_from_the_classic(corpus):
    """Disclose the adopted flying-transformation concept without claiming a
    new exhaustive search of every edition of the classic."""
    md = (ROOT / "references" / "02-ziwei.md").read_text(encoding="utf-8")
    assert "自化" in md, "引擎输出自化, 文档却没有它"
    seg = md.split("自化")[0][-400:] + md[md.index("自化"):md.index("自化") + 1200]
    assert "飞星派" in seg or "飞星" in seg, "必须说明它属飞星派"
    assert "未给出独立核定" in seg, "必须说明自化解释条款尚未核定"


def test_every_routing_trigger_is_reachable_from_the_description():
    """路由表每一行的触发词, 至少要有一个出现在 SKILL.md 的 description 里。

    description 决定这个 skill 会不会被唤起; 触发词不在其中的路由行, 成本天天挂在
    常驻文件里, 而用户问到时根本加载不到本 skill。修前有三行如此:
    「神煞/桃花/驿马/天乙贵人」(指向 19-shensha.md, 570 行)、
    「五行/天干地支/阴阳/八卦(理论)」(00-foundations.md, 366 行)、
    「随机寻访/今日探索点/…/QRNG 探索」。
    """
    md = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    desc = re.search(r"^description: (.*)$", md, re.M).group(1)

    # 只看路由表: 行内含 references/xx.md 链接的那些
    unreachable = []
    for line in md.splitlines():
        if not line.startswith("|") or "references/" not in line:
            continue
        trigger = line.split("|")[1].strip()
        words = [w.strip(" *`") for w in re.split(r"[/、()（）]", trigger)
                 if w.strip(" *`")]
        if words and not any(w in desc for w in words):
            unreachable.append(trigger)
    assert not unreachable, (
        f"这些路由行的触发词一个都不在 description 里, 用户问到时唤不起本 skill: "
        f"{unreachable}")


def test_skill_md_documents_the_json_contract():
    """引擎造了一套自限标志 (reliable / missing_in_table / *_granularity /
    boundary / hour_known), 而 Claude 可读的文档面从前**零提及** —— 标志造好了
    却没有任何文字要求它去看, 于是 Claude 照着 summary 讲, 而 summary 本身不带
    保留。
    """
    md = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for field in ("`ok`", "reliable", "missing_in_table", "boundary",
                  "hour_known", "_granularity", "exit code"):
        assert field in md, f"SKILL.md 未交代 {field}"
    # Do not lock a particular English slogan: real error handling is covered
    # by the CLI tests, while these names make limits discoverable.


def test_payload_switches_are_documented_where_claude_can_see_them():
    """六个裁剪开关此前在 SKILL.md + references + README + agents 里零提及 ——
    杠杆造好了没接线。且开关本身造在了不占体积的地方: ziwei 的
    twelve_palaces + da_xian 合占载荷 81.5%, 而原有两个开关只覆盖 3.5%,
    实测裁剪只省 0.3%。
    """
    md = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    # Method-specific flags can live on the routed page; keep them out of the
    # default BaZi prompt while ensuring users can actually find them.
    assert "references/02-ziwei.md" in md
    md += (ROOT / "references/02-ziwei.md").read_text(encoding="utf-8")
    for flag in ("--no-shensha", "--no-geju", "--no-yongshen",
                 "--brief-palaces", "--no-da-xian", "--as-of-year"):
        assert flag in md, f"SKILL.md 未提及 {flag}"


@pytest.mark.parametrize("flags,max_ratio", [
    (["--brief-palaces"], 0.60),
    (["--no-da-xian"], 0.80),
    (["--no-da-xian", "--brief-palaces", "--no-patterns", "--no-sihua"], 0.35),
])
def test_ziwei_switches_actually_cut_the_payload(flags, max_ratio):
    """开关必须真的省体积 —— 否则文档里的百分比是空话。"""
    base = ["--year", 1990, "--month", 5, "--day", 10, "--hour", 14,
            "--gender", "male"]
    full = len(json.dumps(_run("ziwei_calc.py", base), ensure_ascii=False))
    cut = len(json.dumps(_run("ziwei_calc.py", base + flags), ensure_ascii=False))
    assert cut / full < max_ratio, (
        f"{flags}: 裁剪后仍占 {cut/full:.0%}, 应低于 {max_ratio:.0%}")
    # 裁剪不得改变仍然输出的字段的值
    kept = _run("ziwei_calc.py", base + flags)
    orig = _run("ziwei_calc.py", base)
    assert kept["ming_gong"] == orig["ming_gong"]
    assert kept["wuxing_ju"] == orig["wuxing_ju"]


def test_name_analyze_declares_it_has_no_classical_basis():
    """SKILL.md:54 明令五格「无古籍 —— 系近代日本熊崎健翁所创, 非中土古法;
    须如实标注其来历与争议, 不作古籍权威引用」。

    而输出此前一个 note/source/boundary 字段都没有 —— 只能指望 Claude 记得去读
    13-qiming.md 末尾那一句。同项目的 liuren_cast / xiaoliuren_cast 都在 JSON 里
    带 boundary 自我限定, 唯独这里没有。起名场景的用户多半是给新生儿取名, 而
    81 数理会发「沦落天涯, 失意烦闷, 因缘薄弱, 家庭难圆」这类宿命式凶断。
    """
    d = _run("name_analyze.py", ["--name", "张子涵"])
    src = d["source"]
    assert "熊崎" in src["origin"]
    assert src["disputed"] is True
    assert "无" in src["classical_basis"]
    assert "不可作命定之论" in src["caveat"]
    assert d["boundary"] and "勿单凭数理" in d["boundary"]

    # 旧表分类保留作诊断数据, 但事件断语已移除, 不进入用户结论。
    assert all(g["label_kind"] == "legacy_numerology_category"
               and g["personal_verdict"] is None and "comment" not in g
               for g in d["five_grids"].values())
    assert "凶" not in d["summary"]
