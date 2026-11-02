"""功能表、SKILL、路由、MCP、CLI 五处入口互相对得上；任何一处漏了就失败。"""
import ast
import re
from pathlib import Path

import fortune_rules
import mcp_server
from build_skill import SCRIPT_EXCLUDE
from classical_search import get_passage

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/chinese-fortune/scripts'
SKILL_DIR = ROOT / 'skills/chinese-fortune'
SKILL = (SKILL_DIR / 'SKILL.md').read_text(encoding='utf-8')
REFERENCES = {p.name: p.read_text(encoding='utf-8') for p in (ROOT / 'skills/chinese-fortune/references').glob('*.md')}
ROUTER = (SCRIPTS / 'question_router.py').read_text(encoding='utf-8')


def runtime_entry_points() -> set[str]:
    names = set()
    for path in SCRIPTS.glob('*.py'):
        if path.name in SCRIPT_EXCLUDE or path.name == 'utils.py':
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        if any(isinstance(node, ast.FunctionDef) and node.name == 'main' for node in tree.body):
            names.add(path.name)
    return names


def test_every_runtime_cli_is_documented_for_the_host():
    docs = SKILL + ''.join(REFERENCES.values())
    hidden = {'mcp_server.py'}  # 由宿主配置启动，不是回答流程里的命令
    missing = sorted(name for name in runtime_entry_points() - hidden if name not in docs)
    assert not missing, f'SKILL.md 与 references 都没提到: {missing}'


def test_every_runtime_cli_is_reachable_over_mcp():
    dedicated = {spec['script'] for spec in mcp_server.TOOLS.values() if spec['script']}
    reachable = dedicated | set(mcp_server.runnable_scripts())
    # 写个人档案、预测记录须在能显示写入内容的宿主里经用户明确同意，故意不经 MCP。
    missing = sorted(runtime_entry_points() - reachable - {'mcp_server.py'} - mcp_server.PERSONAL_DATA)
    assert not missing, f'MCP 既无专用工具也不能 run_script: {missing}'


def test_mcp_never_runs_maintenance_tools_and_its_tools_point_at_real_scripts():
    maintenance = {name for name in SCRIPT_EXCLUDE if name.endswith('.py')}
    assert maintenance <= mcp_server.EXCLUDED
    assert not maintenance & set(mcp_server.runnable_scripts())
    for name, spec in mcp_server.TOOLS.items():
        if spec['script']:
            assert (SCRIPTS / spec['script']).is_file(), name
            assert spec['script'] in runtime_entry_points() | {'doctor.py'}, name


def test_router_names_only_shipped_scripts_and_existing_references():
    scripts = set(re.findall(r"scripts/([a-z_]+\.py)", ROUTER))
    scripts |= set(re.findall(r"'([a-z_]+\.py)'", ROUTER))
    assert scripts, 'router no longer names any script?'
    for name in scripts:
        assert (SCRIPTS / name).is_file() and name not in SCRIPT_EXCLUDE, name
    for ref in set(re.findall(r"references/([0-9a-z\-]+\.md)", ROUTER)) | set(re.findall(r"'([0-9]{2}-[a-z\-]+\.md)'", ROUTER)):
        assert ref in REFERENCES, ref


def test_router_method_references_mention_their_scripts():
    from question_router import _named_methods
    every = '八字 紫微 梅花 六爻 周易 奇门 大六壬 塔罗 奇门择时'
    for method in _named_methods(every):
        reference = method['reference'].removeprefix('references/')
        script = method['script'].removeprefix('scripts/')
        assert script in REFERENCES[reference] or script in SKILL, (method['method'], script, reference)


def test_skill_links_resolve():
    for target in re.findall(r'\]\(((?:references|docs)/[^)#]+)', SKILL):
        assert (SKILL_DIR / target).is_file(), target
    for name in re.findall(r'scripts/([a-z_]+\.py)', SKILL):
        assert (SCRIPTS / name).is_file() and name not in SCRIPT_EXCLUDE, name


def test_capability_table_points_at_real_passages_and_references():
    for row in fortune_rules.capabilities():
        ref = row.get('ranking_reference')
        if ref:
            assert (SKILL_DIR / ref).is_file(), (row['scenario'], ref)
        authority = row.get('authority') or {}
        for key in ('method_passage_id', 'passage_id'):
            if authority.get(key):
                assert get_passage(authority[key])['text'], (row['scenario'], authority[key])
