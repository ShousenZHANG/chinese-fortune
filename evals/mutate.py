"""变异测试 — 衡量测试套件**能不能抓到 bug**, 而不只是「有多少条测试」。

2100+ 条测试听起来很多, 但两轮独立审计各自实测出同一件事: 把关键常量或判断标签
改坏, 套件照样全绿。取样后的存活率是 **77%** —— 也就是说四分之三的人为缺陷不会
被发现。举几个当时活下来的:

- meihua_cast 体用关系的 「用生体(吉)」 与 「体生用(耗体)」 整体对调 -> 全绿
- name_analyze 外格公式 +1 改成 +2 -> 全绿
- liuyao_cast 乾宫纳甲 子寅辰 改成 子寅午 -> 全绿 (纳甲决定每一爻地支, 进而决定
  六亲/世应/旺衰/空亡, 即整个断卦层)
- assets/64hex.json 第 3、4 卦的卦辞对调 -> 全绿

覆盖率对此完全无感: liuyao_cast 行覆盖 88.8%, 却没有任何断言检查排出来的爻装了
什么 —— 「覆盖率高而无 oracle」的干净样本。

用法:
    python evals/mutate.py                 # 全部变异, 打印存活清单
    python evals/mutate.py --max-survivors 3
    python evals/mutate.py --only meihua   # 只跑名字含 meihua 的

每个变异独立施加、跑指定测试文件、无论成败都还原。任何一次异常退出也会还原
(try/finally), 且退出前校验文件字节与备份一致。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Mutation:
    """一处人为缺陷。``tests`` 留空表示跑全量套件 (慢, 仅用于兜底)。"""

    name: str
    path: str
    old: str
    new: str
    why: str                      # 这个值错了会让用户看到什么
    tests: list[str] = field(default_factory=list)


MUTATIONS: list[Mutation] = [
    # --- 语义标签: 结论的方向, 不是查表 ---------------------------------- #
    Mutation(
        "meihua:体用吉凶对调", "scripts/meihua_cast.py",
        'return "用生体 (吉)"', 'return "体生用 (耗体)"',
        "梅花唯一的判断性输出, 会被直接叙述给用户: 吉断说成耗体",
        ["tests/test_engines.py", "tests/test_subcommands.py"],
    ),
    Mutation(
        "meihua:休囚对调", "scripts/meihua_cast.py",
        'return "休"', 'return "囚"',
        "体卦旺衰差一级, 而 §5.3 权重表按「季节囚死 -3」计分",
        ["tests/test_engines.py"],
    ),
    # --- 公式 ------------------------------------------------------------ #
    Mutation(
        "name:外格公式", "scripts/name_analyze.py",
        "wai = (total - ren) + 1", "wai = (total - ren) + 2",
        "外格数字错 -> 81 数理查错行 -> 吉凶断语整条错, 且会进 summary",
        ["tests/test_name_analyze.py", "tests/test_subcommands.py"],
    ),
    # --- 查表: 每一条都驱动下游整层判断 ---------------------------------- #
    Mutation(
        "liuyao:乾宫纳甲", "scripts/liuyao_cast.py",
        '["子", "寅", "辰"]', '["子", "寅", "午"]',
        "纳甲定每爻地支 -> 六亲/世应/旺衰/空亡 全错, 即整个断卦层",
        ["tests/test_subcommands.py", "tests/test_engines.py"],
    ),
    Mutation(
        "ziwei:辛干天魁", "scripts/ziwei_stars.py",
        '    "辛": "午",\n}', '    "辛": "寅",\n}',
        "六吉去二: 每张辛年盘的天魁天钺互换 (占全部命盘 10%)",
        ["tests/test_differential_ziwei.py", "tests/test_engines.py"],
    ),
    Mutation(
        "ziwei:七杀亮度", "scripts/ziwei_stars.py",
        '"七杀": {"子": "旺", "丑": "庙", "寅": "庙", "卯": "旺", "辰": "庙",',
        '"七杀": {"子": "旺", "丑": "庙", "寅": "庙", "卯": "旺", "辰": "陷",',
        "reader-facing: 告诉用户他的七杀落陷, 而卷二说那是入庙",
        ["tests/test_engines.py", "tests/test_reference_consistency.py"],
    ),
    Mutation(
        "meihua:四季月归属", "scripts/meihua_cast.py",
        '4: "土", 7: "土", 10: "土", 1: "土",',
        '4: "木", 7: "火", 10: "金", 1: "水",',
        "96 格旺衰里 32 格变号; 艮/坤 体卦重新变成永远不可能旺",
        ["tests/test_engines.py", "tests/test_subcommands.py"],
    ),
    Mutation(
        # 注意: 只把 getYearShengXiaoByLiChun 换成 getYearShengXiao 是**语义等价**的
        # (年中取值时两 API 在 1950-2050 零分歧 —— 这正是本实现选择年中取值的理由),
        # 那样的变异不构成缺陷。真正的缺陷是取样日: 回到硬编码的 2月5日。
        "zodiac:取样日回到2月5日", "scripts/zodiac_compat.py",
        "mid = Solar.fromYmdHms(year, 6, 1, 12, 0, 0).getLunar()",
        "mid = Solar.fromYmdHms(year, 2, 5, 12, 0, 0).getLunar()",
        "1950-2050 的 49 年返回上一年生肖 —— 这是最高频的那条路由",
        ["tests/test_convert_zodiac.py"],
    ),
    Mutation(
        "bazi:旺衰月令不对称", "scripts/bazi_strength.py",
        '"旺": 0.45, "相": 0.22, "休": -0.10, "囚": -0.30, "死": -0.45,',
        '"旺": 0.45, "相": 0.30, "休": 0.10, "囚": 0.00, "死": -0.10,',
        "旺衰偏向旺侧 -> 用神取反 -> 大运流年吉凶/方位/颜色/行业全部反号",
        ["tests/test_bazi_integration.py"],
    ),
    Mutation(
        "bazi:旺衰通根只加不减", "scripts/bazi_strength.py",
        "+ (rooted - 2) * 0.15", "+ rooted * 0.05",
        "无根不扣分 -> 身弱近乎不可达 -> 用神取反, 整份批断极性错",
        ["tests/test_bazi_integration.py"],
    ),
    Mutation(
        "bazi:时辰边界", "scripts/utils.py",
        "def hour_branch_index(hour: int) -> int:",
        "def hour_branch_index(hour: int) -> int:\n    hour = (hour + 1) % 24",
        "整副时柱错位一辰, 连带 时柱十神/大运起点",
        ["tests/test_utils.py", "tests/test_bazi_integration.py",
         "tests/test_differential_ziwei.py"],
    ),
    Mutation(
        "bazi:化气格条件", "scripts/bazi_geju.py",
        "if rooted > 0:\n                continue                       # 有根不化",
        "if False:\n                continue                       # 有根不化",
        "化气格滥发 -> 格局标签错 -> 「事业天花板和人生主轴」判错",
        ["tests/test_bazi_integration.py"],
    ),
    Mutation(
        "bazi:司令分野", "scripts/bazi_tables.py",
        '"巳": [("戊", 7), ("庚", 7), ("丙", 16)],',
        '"巳": [("戊", 7), ("庚", 10), ("丙", 13)],',
        "司令是必出字段, 分野错则当令藏干错, 旺衰与取用的依据整体偏移",
        ["tests/test_bazi_integration.py"],
    ),
    Mutation(
        "bazi:扶抑来历标注", "scripts/bazi_strength.py",
        "[取舍规则出自本实现, 古籍未定二者优先级]", "",
        "自创规则以古籍权威的口吻输出 —— SKILL.md:34「凡古籍无据者不妄断」要禁的",
        ["tests/test_bazi_integration.py"],
    ),
    Mutation(
        "huangli:建除倾向表", "scripts/huangli_query.py",
        '"满": {"yi": ["嫁娶", "开市", "入宅", "祈福"], "ji": ["动土", "安葬"]},',
        '"满": {"yi": ["动土", "安葬"], "ji": ["嫁娶", "开市", "入宅", "祈福"]},',
        "择日是唯一让用户做不可逆决策(婚期/搬迁/安葬)的输出, 宜忌对调即误导现实行动",
        ["tests/test_reference_consistency.py", "tests/test_huangli_oracle.py"],
    ),
    Mutation(
        "huangli:冲突不再暴露", "scripts/huangli_query.py",
        '"jian_chu_conflicts": conflicts,', '"jian_chu_conflicts": {},',
        "通书结论与建除倾向的分歧被藏起来, 读者以为看到的就是建除的结论",
        ["tests/test_huangli_oracle.py"],
    ),
    Mutation(
        "liuyao:六神起点", "scripts/liuyao_cast.py",
        '"甲": "青龙", "乙": "青龙",', '"甲": "朱雀", "乙": "朱雀",',
        "六神起于日干; 起点错则六爻的青龙白虎全部错位, 断卦的吉凶意象整体偏移",
        ["tests/test_liuyao_oracle.py"],
    ),
    Mutation(
        "qimen:值使退化为值符", "scripts/qimen_cast.py",
        "zhi_shi_palace = DIZHI_TO_PALACE.get(hour_branch, shi_gan_palace)",
        "zhi_shi_palace = shi_gan_palace",
        "值使是八门盘独立的枢; 退化成值符副本后整张八门盘失去独立信息",
        ["tests/test_qimen_liuren_oracle.py"],
    ),
    Mutation(
        "liuren:伏吟不用刑", "scripts/liuren_cast.py",
        "mo = _xing_or_chong(zhong)", "mo = tian_pan[zhong]",
        "伏吟时天地盘各居本位, 末传恒等于中传 —— 三传退化成两传",
        ["tests/test_qimen_liuren_oracle.py"],
    ),
    Mutation(
        "liuren:反吟不用驿马", "scripts/liuren_cast.py",
        "    chu = YI_MA[ri_zhi]", "    chu = tian_pan[ri_zhi]",
        "反吟时天盘逐位相冲, 末传恒等于初传 —— 三传退化成两传",
        ["tests/test_qimen_liuren_oracle.py"],
    ),
    Mutation(
        "xiaoliuren:起宫公式", "scripts/xiaoliuren_cast.py",
        "day_index = (month_index + day - 1) % 6",
        "day_index = (month_index + day) % 6",
        "整套小六壬结论错位一宫 —— 吉凶直接反号 (大安吉 vs 留连平)",
        ["tests/test_subcommands.py"],
    ),
    Mutation(
        "skill:自化来历标注", "references/02-ziwei.md",
        "**《紫微斗数全书》全书三卷检索无「自化」二字**", "自化见于本门",
        "自化是飞星派概念, 《全书》无此说; 不注来历即借古籍名义讲别家的话",
        ["tests/test_interpretation_coverage.py"],
    ),
    Mutation(
        "skill:五格来历标注", "scripts/name_analyze.py",
        '"classical_basis": "无 —— 非中土古法, 《三命通会》等古籍均无此说",',
        '"classical_basis": "见《三命通会》",',
        "五格系近代日本熊崎式, 冒充古籍即违反 SKILL.md:54 的明令",
        ["tests/test_interpretation_coverage.py"],
    ),
    Mutation(
        "assets:卦辞对调", "assets/64hex.json",
        '"judgment": "元亨,利贞。勿用有攸往,利建侯。"',
        '"judgment": "亨。匪我求童蒙,童蒙求我。"',
        "周易/六爻 交付给用户的解读文本本身错了",
        ["tests/test_subcommands.py"],
    ),
    Mutation(
        "assets:64hex binary", "assets/64hex.json",
        '"binary": "110111"', '"binary": "011111"',
        "小畜 的编码读成夬 —— 随发布包分发, Claude 直接读得到",
        ["tests/test_subcommands.py"],
    ),
    Mutation(
        "bazi:调候用神", "assets/tiaohou.json",
        '"primary_yongshen": [\n        "甲"\n      ]',
        '"primary_yongshen": [\n        "丙"\n      ]',
        "用神决定大运流年吉凶/方位/颜色/行业, 一格错则整份批断反号",
        ["tests/test_bazi_integration.py"],
    ),
]


def apply(m: Mutation) -> bool:
    p = ROOT / m.path
    text = p.read_text(encoding="utf-8")
    if text.count(m.old) < 1:
        return False
    p.write_text(text.replace(m.old, m.new, 1), encoding="utf-8", newline="")
    return True


def run_tests(m: Mutation) -> bool:
    """True = 套件抓到了 (至少一条测试红)。"""
    targets = m.tests or ["tests/"]
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "pytest", *targets, "-q", "-x",
         "--no-header", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=900,
    )
    return proc.returncode != 0


_BASELINE_CACHE: dict[tuple[str, ...], bool] = {}


def baseline_is_green(m: Mutation) -> bool:
    """变异**之前**这批测试必须是绿的。

    否则一条因无关原因报错的测试 (比如我自己写坏了一个 zip strict 参数) 会让
    每一个变异都被算成「抓到」—— 得分虚高, 而门禁看起来还是满分。这是本工具
    最容易骗到自己的地方, 实际已经发生过一次。

    同一组测试目标只跑一次基线并缓存 —— 二十个变异里多数共用同几组目标, 不缓存
    的话整轮耗时翻倍。
    """
    key = tuple(m.tests or ["tests/"])
    if key not in _BASELINE_CACHE:
        _BASELINE_CACHE[key] = not run_tests(m)
    return _BASELINE_CACHE[key]


class _Lock:
    """进程级互斥。

    本工具会临时改坏源文件再还原。两个实例并发跑时会互相踩踏 —— 甲刚把文件改坏,
    乙就把这个坏值当成基线备份下来, 之后乙「还原」的其实是甲的变异。实际发生过
    一次: 并发的两轮让全量套件冒出三个与改动无关的失败, 且 git status 时红时绿。
    """

    path = ROOT / ".mutate.lock"

    def __enter__(self):
        if self.path.exists():
            sys.exit(
                f"FATAL: 另一个 mutate.py 正在运行 ({self.path})。\n"
                "并发会互相踩踏源文件。等它跑完, 或确认无进程后删掉该文件。")
        self.path.write_text(str(os.getpid()), encoding="utf-8")
        return self

    def __exit__(self, *exc):
        self.path.unlink(missing_ok=True)
        return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--max-survivors", type=int, default=0,
                    help="允许存活的变异数上限 (默认 0)")
    ap.add_argument("--only", default=None, help="只跑名字含该子串的变异")
    args = ap.parse_args(argv)

    todo = [m for m in MUTATIONS if not args.only or args.only in m.name]
    if not todo:
        print(f"没有匹配 {args.only!r} 的变异")
        return 2

    survivors, skipped, broken = [], [], []
    print(f"施加 {len(todo)} 处变异\n" + "=" * 64)
    lock = _Lock().__enter__()
    for m in todo:
        p = ROOT / m.path
        backup = p.read_bytes()
        try:
            if not baseline_is_green(m):
                broken.append(m)
                print(f"[BROKEN] {m.name} — 变异前这批测试就是红的, 结果不可信")
                continue
            if not apply(m):
                skipped.append(m)
                print(f"[SKIP  ] {m.name} — 目标文本已不存在, 变异需更新")
                continue
            caught = run_tests(m)
        finally:
            p.write_bytes(backup)
            assert p.read_bytes() == backup, f"还原失败: {m.path}"
        if caught:
            print(f"[CAUGHT] {m.name}")
        else:
            survivors.append(m)
            print(f"[SURVIVED] {m.name}\n           后果: {m.why}")

    lock.__exit__()
    tested = len(todo) - len(skipped) - len(broken)
    score = (tested - len(survivors)) / tested * 100 if tested else 0.0
    print("=" * 64)
    print(f"变异得分 {score:.0f}%  ({tested - len(survivors)}/{tested} 被抓到)")
    if skipped:
        print(f"跳过 {len(skipped)} 处 (目标文本已变), 需更新: "
              f"{[m.name for m in skipped]}")
    if broken:
        print(f"基线已红 {len(broken)} 处, 这些变异的结果无意义: "
              f"{[m.name for m in broken]}")
    if survivors:
        print("\n存活 —— 这些缺陷现在能进主干而无人察觉:")
        for m in survivors:
            print(f"  - {m.name} ({m.path})\n      {m.why}")

    # 跳过的变异等同于失去覆盖, 计入失败。
    if len(survivors) > args.max_survivors or skipped or broken:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
