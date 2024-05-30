import asyncio
from getopt import getopt
from json import dumps, loads
from pathlib import Path
from shutil import rmtree
from sys import argv

from utils import (
    Plugin,
    commit_changes,
    get_commit_hash_from_registry,
    get_git_head_hash,
    get_pypi_version,
    get_runtime_version_latest,
    git_add,
    load_plugins_from_registry,
    pdm_create_project_from_git,
    pdm_create_project_from_pypi,
    pdm_run_project_from_git,
    pdm_run_project_from_pypi,
)

opts, args = getopt(argv[1:], "l:", ["limit=", "no-commit"])
limit = 0
no_commit = False
for opt, arg in opts:
    if opt in ("-l", "--limit"):
        if not arg.isdigit():
            print("limit 必须是数字")
            exit(1)
        limit = int(arg)
    elif opt == "--no-commit":
        print("不提交测试结果")
        no_commit = True
print("从 nonebot/registry 获取提交哈希")
commit = asyncio.run(get_commit_hash_from_registry())
print("从 nonebot/registry 获取插件列表")
plugins: list[dict] = load_plugins_from_registry(commit)
STATE = Path("state.json")
state: dict[str, str | dict] = {}
if STATE.exists():
    print("加载历史记录")
    state = loads(STATE.read_bytes())
modified = False
print("正在检查更新 nonebot2")
version = get_runtime_version_latest()
VER_KEY = "__nonebot2.version__"
if not state.get(VER_KEY):
    modified = True
elif version != state.get(VER_KEY):
    print(f"nonebot2 {state.get(VER_KEY)} -> {version}")
    modified = True
state[VER_KEY] = state.get(VER_KEY) or version
for data in plugins:
    plugin = Plugin(data)
    if not state.get(plugin.project_link):
        state[plugin.project_link] = {}
    print("正在检查更新", plugin.module_name)
    get_pypi_version(plugin)
    plugin.new_from_pypi = plugin.pypi_version and (
        not state.get(plugin.project_link)
        or plugin.pypi_version != state[plugin.project_link].get("pypi_version")
    )
    if plugin.pypi_version != state[plugin.project_link].get("pypi_version"):
        print(
            plugin.module_name,
            "PyPI:",
            state[plugin.project_link].get("pypi_version"),
            "->",
            plugin.pypi_version,
        )
    asyncio.run(get_git_head_hash(plugin))
    plugin.new_from_git = plugin.git_hash and (
        not state.get(plugin.project_link)
        or plugin.git_hash != state[plugin.project_link].get("git_hash")
    )
    if plugin.git_hash != state[plugin.project_link].get("git_hash"):
        print(
            plugin.module_name,
            "Git: ",
            state[plugin.project_link].get("git_hash"),
            "->",
            plugin.git_hash,
        )
    d = {
        VER_KEY: state[plugin.project_link].get(VER_KEY) or version,
        "first_seen": state[plugin.project_link].get("first_seen") or commit,
        "module_name": plugin.module_name,
        "project_link": plugin.project_link,
        "display_name": plugin.name.strip(),
        "desc": plugin.desc,
        "author": plugin.author,
        "homepage": plugin.homepage,
        "pypi_version": plugin.pypi_version,
        "pypi_create": state[plugin.project_link].get("pypi_create") or False,
        "pypi_run": state[plugin.project_link].get("pypi_run") or False,
        "git_hash": plugin.git_hash,
        "git_create": state[plugin.project_link].get("git_create") or False,
        "git_run": state[plugin.project_link].get("git_run") or False,
        "last_seen": commit,
        "stderr_pypi": state[plugin.project_link].get("stderr_pypi"),
        "stderr_git": state[plugin.project_link].get("stderr_git"),
    }
    if version != state[plugin.project_link].get(VER_KEY) or (
        plugin.pypi_version and plugin.new_from_pypi
    ):
        modified = True
        asyncio.run(pdm_create_project_from_pypi(plugin))
        if plugin.created_from_pypi:
            d["pypi_create"] = True
            asyncio.run(pdm_run_project_from_pypi(plugin, d))
            if plugin.booted_from_pypi:
                d["pypi_run"] = True
            plugin.clear()
    if version != state[plugin.project_link].get(VER_KEY) or (
        plugin.git_hash and plugin.new_from_git
    ):
        modified = True
        asyncio.run(pdm_create_project_from_git(plugin))
        if plugin.created_from_git:
            d["git_create"] = True
            asyncio.run(pdm_run_project_from_git(plugin, d))
            if plugin.booted_from_git:
                d["git_run"] = True
            plugin.clear()
    plugin.unlink()
    if not d.get("stderr_pypi"):
        d.pop("stderr_pypi", None)
    if not d.get("stderr_git"):
        d.pop("stderr_git", None)
    state[plugin.project_link] = d
    if plugin.new_from_pypi or plugin.new_from_git:
        limit -= 1
        if not limit:
            break
if modified:
    print("保存历史记录")
    STATE.write_bytes(dumps(state, ensure_ascii=False, indent="\t").encode())
print("生成测试报告")
RESULTS = Path("RESULTS.md")
P = "✅"
F = "❌"
p, r, c = [], [], []
for k, v in state.items():
    if k == VER_KEY:
        continue
    if v[VER_KEY] != version:
        continue
    if v["pypi_run"] or v["git_run"]:
        p.append(k)
    elif v["pypi_create"] or v["git_create"]:
        r.append(k)
    else:
        c.append(k)
s = ""
if not limit:
    s += "已达到限制，结束测试。\n\n"
s += f"`nonebot2 == {version}`\n"
if p:
    s += f"## {P} 满足基础可靠性\n"
    for i in p:
        s += (
            f"- `{state[i]['module_name']}` {state[i]['display_name']}\n"
            + "  - `PyPI "
            + (P if state[i]["pypi_run"] else F)
            + "` `Git "
            + (P if state[i]["git_run"] else F)
            + "`\n"
        )
if r:
    s += f"\n## {F} 运行时错误\n"
    for i in r:
        s += (
            f"- `{state[i]['module_name']}` {state[i]['display_name']}\n"
            + "  - `PyPI "
            + (P if state[i]["pypi_run"] else F)
            + "` `Git "
            + (P if state[i]["git_run"] else F)
            + "`\n"
        )
if c:
    s += f"\n## {F} 创建时错误\n"
    for i in c:
        s += (
            f"- `{state[i]['module_name']}` {state[i]['display_name']}\n"
            + "  - `PyPI "
            + (P if state[i]["pypi_run"] else F)
            + "` `Git "
            + (P if state[i]["git_run"] else F)
            + "`\n"
        )
RESULTS.write_text(s, encoding="utf-8")
if not no_commit:
    print("提交测试结果")
    asyncio.run(git_add(RESULTS))
    asyncio.run(git_add(STATE))
    asyncio.run(commit_changes())
    rmtree("__pycache__")
