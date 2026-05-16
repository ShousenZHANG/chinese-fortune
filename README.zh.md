# Chinese Fortune · 中国传统命理占卜 Claude 技能

> 五术大全 · Claude Skill · 20+ 方法 · MIT 协议
> [English](README.md) · [快速开始](#快速开始) · [覆盖方法](#覆盖方法) · [安全护栏](#安全护栏)

一个面向 Claude Code / Claude Agent SDK 的综合性技能包，把中国传统命理占卜的完整体系 (**五术：山·医·命·相·卜**) 装进单一可导航的 skill。覆盖 **20+ 种传统方法**，外加生肖、西方占星、塔罗、解梦等相邻实践。

定位是**文化研习与个人内省**，不替代医疗、法律、金融决策。

---

## 亮点

- **20+ 占卜体系**：八字四柱、紫微斗数、周易 (64 卦全文)、六爻、梅花易数、奇门遁甲、大六壬、小六壬、风水 (八宅 / 玄空 / 形势派)、面相、手相、测字、黄历择日、起名、合婚、解梦、生肖、星座、塔罗，以及扩展矩阵覆盖太乙、铁板、称骨、河洛、七政四余、灵签、杯筊等
- **生产级架构**：渐进披露 (123 行 SKILL.md 路由 → 23 份参考文档 → 11 个 Python 脚本 → 11 份 JSON 资产)
- **真实计算**：`lunar_python` 处理公农历换算、24 节气、60 甲子、真太阳时；`random.SystemRandom` 保证占卜随机性
- **严格红线**：硬编码安全边界 (不预测死亡、不诊断疾病、不指点投资、不诅咒他人、不归罪家人、危机自动转介)
- **自我验证**：`evals/run_checks.py` 强制校验 frontmatter 合规、脚本 JSON 输出完整、参考文档覆盖、发布清洁度
- **15,907 行 / 906 KB**

---

## 快速开始

### 1. 安装 skill

```bash
# 克隆
git clone https://github.com/<你的账号>/chinese-fortune.git
cd chinese-fortune

# 复制到 Claude 用户 skill 目录
cp -r . ~/.claude/skills/chinese-fortune

# 装 Python 依赖 (八字 / 农历 / 黄历 需要)
pip install lunar_python
```

### 2. 在 Claude 里使用

打开新 Claude Code 会话，直接说人话：

```text
我 1990 年 5 月 10 日下午 2 点 30 分出生的男性，北京。详细批一下八字。
```

```text
帮我用铜钱起一卦，问要不要跳槽。
```

```text
2026 年 6 月想搬家，我属龙，哪几天合适？
```

skill 自动识别中文或英文请求触发，无需手动调用。

### 3. 命令行直接跑 (不进 Claude 也行)

每个脚本输出结构化 JSON 到 stdout：

```bash
python scripts/bazi_calc.py --year 1990 --month 5 --day 10 \
  --hour 14 --minute 30 --gender male --longitude 116.4

python scripts/yijing_cast.py coins --question "要不要接 offer"

python scripts/huangli_query.py --date 2026-06-15

python scripts/zodiac_compat.py compat --a 虎 --b 猴

python scripts/tarot_draw.py three --seed 42
```

完整参数：`python scripts/<名>.py --help`。

---

## 覆盖方法

### 命 · 命理推演
| 方法 | 触发词 | 参考文档 | 脚本 |
|---|---|---|---|
| 八字四柱 | "八字" / "排盘" / 生辰 | [01-bazi.md](references/01-bazi.md) | `bazi_calc.py` |
| 紫微斗数 | "紫微" / "命宫" | [02-ziwei.md](references/02-ziwei.md) | `ziwei_calc.py` |
| 称骨算命 | "称骨" / "几两几钱" | [21-extended-methods.md](references/21-extended-methods.md) | — |
| 河洛理数 | "河洛" / "先天数" | [21-extended-methods.md](references/21-extended-methods.md) | — |
| 七政四余 | "七政" / "果老星宗" | [21-extended-methods.md](references/21-extended-methods.md) | — |

### 卜 · 占卜起卦
| 方法 | 触发词 | 参考文档 | 脚本 |
|---|---|---|---|
| 周易 64 卦 | "起卦" / "周易" / "易经" | [03-yijing.md](references/03-yijing.md) + [64hex-full.md](references/64hex-full.md) | `yijing_cast.py` |
| 六爻 | "六爻" / "摇卦" / "金钱卦" | [04-liuyao.md](references/04-liuyao.md) | `liuyao_cast.py` |
| 梅花易数 | "梅花" / "心易" | [05-meihua.md](references/05-meihua.md) | `meihua_cast.py` |
| 奇门遁甲 | "奇门" / "八门九星" | [06-qimen.md](references/06-qimen.md) | — |
| 大六壬 | "六壬" / "三传四课" | [07-daliuren.md](references/07-daliuren.md) | — |
| 小六壬 | "小六壬" / "大安留连" | [21-extended-methods.md](references/21-extended-methods.md) | `xiaoliuren_cast.py` |
| 太乙神数 | "太乙" / "国运" | [21-extended-methods.md](references/21-extended-methods.md) | — |
| 灵签 | "观音签" / "签文" | [21-extended-methods.md](references/21-extended-methods.md) | — |
| 杯筊 | "圣杯" / "笑杯" / "阴杯" | [21-extended-methods.md](references/21-extended-methods.md) | — |

### 相 · 相术与风水
| 方法 | 触发词 | 参考文档 |
|---|---|---|
| 风水 (八宅 / 玄空 / 形势) | "风水" / "阳宅" / "玄空飞星" | [08-fengshui.md](references/08-fengshui.md) |
| 面相 | "面相" / "脸相" / "痣相" | [09-mianxiang.md](references/09-mianxiang.md) |
| 手相 | "手相" / "掌纹" / "生命线" | [10-shouxiang.md](references/10-shouxiang.md) |
| 测字 | "测字" / "拆字" | [11-cezi.md](references/11-cezi.md) |

### 实用术数
| 方法 | 触发词 | 参考文档 | 脚本 |
|---|---|---|---|
| 黄历择日 | "黄历" / "择日" / "宜搬家" | [12-huangli.md](references/12-huangli.md) | `huangli_query.py` |
| 起名改名 | "起名" / "改名" / "公司名" | [13-qiming.md](references/13-qiming.md) | `name_analyze.py` |
| 合婚配对 | "合婚" / "我俩合不合" | [14-hehun.md](references/14-hehun.md) | `zodiac_compat.py` |
| 解梦 | "解梦" / "梦见" | [15-jiemeng.md](references/15-jiemeng.md) | — |
| 生肖 | "属相" / "本命年" / "太岁" | [16-shengxiao.md](references/16-shengxiao.md) | `zodiac_compat.py` |
| 西方星座 | "星座" / "太阳星座" / "上升" | [17-xingzuo.md](references/17-xingzuo.md) | — |
| 塔罗 | "塔罗" / "抽牌" | [18-tarot.md](references/18-tarot.md) | `tarot_draw.py` |

### 基础与参考
| 主题 | 文档 |
|---|---|
| 阴阳、五行、天干地支、60 甲子、八卦、24 节气 | [00-foundations.md](references/00-foundations.md) |
| 神煞详表 (吉神 16 + 凶煞 19) | [19-shensha.md](references/19-shensha.md) |
| 免责声明与伦理边界 | [20-disclaimer.md](references/20-disclaimer.md) |
| 扩展术数矩阵 | [21-extended-methods.md](references/21-extended-methods.md) |
| 64 卦全文 (卦辞 + 大象 + 384 爻辞) | [64hex-full.md](references/64hex-full.md) |

---

## 目录结构

```
chinese-fortune/
├── SKILL.md                # 123 行路由，含 frontmatter 触发描述
├── agents/openai.yaml      # OpenAI 兼容运行时元数据
├── references/             # 23 份 markdown，约 11,540 行
│   ├── 00-foundations.md   # 阴阳五行 / 干支 / 八卦
│   ├── 01-bazi.md          # 八字：排盘步骤、十神、大运
│   ├── 02-ziwei.md         # 紫微：12 宫、14 主星、四化
│   ├── 03-yijing.md        # 周易理论与 6 种起卦法
│   ├── 04-liuyao.md        # 六爻：八宫、六亲、六神、纳甲
│   ├── 05-meihua.md        # 梅花：体用、季节旺衰、外应
│   ├── 06-qimen.md         # 奇门：9 宫、8 门、9 星、8 神
│   ├── 07-daliuren.md      # 六壬：四课三传、12 天将
│   ├── 08-fengshui.md      # 八宅 + 玄空 + 形势 + 24 山
│   ├── 09-mianxiang.md     # 面相：三停、五官、十二宫
│   ├── 10-shouxiang.md     # 手相：五大主线、八卦在手
│   ├── 11-cezi.md          # 测字：拆字、添减、经典案例
│   ├── 12-huangli.md       # 黄历：12 建除、28 宿、10 类择日
│   ├── 13-qiming.md        # 起名：五格、81 数理、三才
│   ├── 14-hehun.md         # 合婚：12×12 生肖、八字六要点
│   ├── 15-jiemeng.md       # 解梦：6 类梦境、约 80 意象
│   ├── 16-shengxiao.md     # 12 生肖详解 + 太岁
│   ├── 17-xingzuo.md       # 12 星座 + 四元素 + 三模式
│   ├── 18-tarot.md         # 78 牌 + 7 种牌阵
│   ├── 19-shensha.md       # 神煞详表
│   ├── 20-disclaimer.md    # 红线 + 伦理 + 危机转介
│   ├── 21-extended-methods.md  # 14 种冷门方法覆盖矩阵
│   └── 64hex-full.md       # 64 卦全文 (王弼通行本)
├── scripts/                # 11 个 Python 脚本 + utils.py
│   ├── bazi_calc.py        # 八字完整排盘 + 十神 + 神煞 + 大运
│   ├── ziwei_calc.py       # 紫微骨架：宫位、主星、四化
│   ├── yijing_cast.py      # 周易：4 种起卦、本/互/变卦
│   ├── liuyao_cast.py      # 六爻完整：八宫、纳甲、六亲、六神
│   ├── meihua_cast.py      # 梅花：体用关系、季节旺衰
│   ├── xiaoliuren_cast.py  # 小六壬快占 (无依赖)
│   ├── huangli_query.py    # 当日黄历
│   ├── lunar_convert.py    # 公历↔农历 + 节气
│   ├── name_analyze.py     # 五格 + 81 数理 + 三才
│   ├── zodiac_compat.py    # 12×12 合婚 + 太岁
│   ├── tarot_draw.py       # 5 种牌阵 + 78 张完整牌组
│   └── utils.py            # 共享常量、十神算法、真太阳时
├── assets/                 # 11 份 JSON 查询表 (211 KB)
│   ├── ganzhi.json         # 10 干 + 12 支 + 60 甲子 + 纳音
│   ├── wuxing.json         # 五行生克 + 旺相休囚死
│   ├── bagua.json          # 8 卦象 + 属性
│   ├── 64hex.json          # 64 卦 (王弼通行本)
│   ├── ziwei_stars.json    # 紫微 14 主星 + 12 辅星 + 四化
│   ├── shensha.json        # 16 吉神 + 19 凶煞
│   ├── 24jieqi.json        # 24 节气
│   ├── tarot78.json        # 22 大阿尔卡纳 + 56 小阿尔卡纳
│   ├── jiemeng.json        # 约 80 个梦境意象 (传统 + 心理)
│   ├── name_bihua.json     # 2,594 字康熙笔画
│   └── name_shuli.json     # 81 数理详表
└── evals/
    ├── evals.json          # 12 个测试用例
    └── run_checks.py       # 4 项发布就绪检查
```

---

## 安全护栏

skill **拒绝**以下请求 (见 [20-disclaimer.md](references/20-disclaimer.md))：

- 预测死亡时间
- 具体医疗诊断 (转介医生)
- 具体法律决断 (转介律师)
- 具体金融操作 (转介持牌理财顾问)
- 诅咒、伤害他人
- 把命主家人指为不幸来源
- 收取费用或法事钱
- 推销"化解物品"
- 政治选举预测

skill **始终**：

- 把读盘表述为文化研习和模式洞察，**不**做决定论预言
- 出读盘时附简短免责声明
- 监测自伤 / 急性焦虑等信号，立即转介危机资源 (24h 心理热线 400-161-9995)

---

## 验收

发布或改动前跑发布检查：

```bash
PYTHONDONTWRITEBYTECODE=1 python -X utf8 evals/run_checks.py
```

预期输出：

```
ok check_skill_metadata
ok check_core_scripts
ok check_reference_coverage
ok check_release_cleanliness
```

校验项：
1. SKILL.md frontmatter 严格只有 `name` + `description`，description ≤ 1024 字符，9 个必备触发词齐全
2. 11 个核心脚本全部输出有效非错误 JSON
3. 所有路由参考文档存在
4. 发布版无 `TODO` / `TBD` / `placeholder` / `__pycache__`

---

## 贡献

见 [CONTRIBUTING.md](CONTRIBUTING.md)。欢迎以下 PR：

- 加深参考文档 (尤其紫微星曜细节、玄空飞星具体盘式、解梦词条扩充)
- 新方法 (目前奇门 / 大六壬 / 太乙暂无脚本)
- 翻译 (目前仅简体中文，欢迎繁體中文 + English 翻译)
- 扩充 `evals/evals.json` 测试用例

提交前请跑 `evals/run_checks.py`。

---

## 协议

[MIT](LICENSE) — 个人、学术、商用均免费。No warranty。

---

## 鸣谢

- 经典出处：《周易》《滴天髓》《三命通会》《渊海子平》《紫微斗数全书》《卜筮正宗》《梅花易数》《奇门遁甲秘笈大全》《六壬大全》《葬书》《麻衣相法》《钦定协纪辨方书》
- Python 农历库：[`6tail/lunar-python`](https://github.com/6tail/lunar-python)
- 作为 [Claude Skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) 构建，兼容 Claude Code、Claude Agent SDK 及任何兼容运行时

---

## 免责声明

本软件基于中国传统命理学说提供**文化与教育参考**，**不**替代医疗、法律、心理、金融专业建议。命理是概率性模式洞察，不是决定性预言。请理性使用。
