import asyncio
from dataclasses import dataclass
from json import load
from pathlib import Path
from shutil import rmtree
from urllib.error import HTTPError
from urllib.request import URLopener, urlretrieve

URLopener.version = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0"


async def get_commit_hash_from_registry():
    url = "https://github.com/nonebot/registry"
    cmd = f"git ls-remote {url} -b results"
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    return stdout.decode().split()[0]


def load_plugins_from_registry(commit: str):
    url = f"https://raw.githubusercontent.com/nonebot/registry/{commit}/plugins.json"
    resp = urlretrieve(url)
    with open(resp[0], "r", encoding="utf-8") as f:
        return load(f)


@dataclass
class Plugin:
    data: dict

    def __post_init__(self):
        self.module_name: str = self.data.get("module_name")
        self.project_link: str = self.data.get("project_link")
        self.name: str = self.data.get("name")
        self.desc: str = self.data.get("desc")
        self.author: str = self.data.get("author")
        self.homepage: str = self.data.get("homepage")

        self.pypi_version: str = None
        self.git_hash: str = None

        self.created_from_pypi = False
        self.created_from_git = False
        self.booted_from_pypi = False
        self.booted_from_git = False

        self.folder_name = f"test-{self.module_name}"
        self.folder_path = Path("tests") / self.folder_name
        self.folder_path.mkdir(parents=True, exist_ok=True)

        self.new_from_pypi = False
        self.new_from_git = False

    def clear(self):
        for p in self.folder_path.iterdir():
            if p.is_dir():
                rmtree(p)
            else:
                p.unlink()

    def unlink(self):
        rmtree(self.folder_path)


def get_runtime_version_latest():
    url = f"https://pypi.org/pypi/nonebot2/json"
    resp = urlretrieve(url)
    with open(resp[0], "r", encoding="utf-8") as f:
        return load(f)["info"]["version"]


def get_pypi_version(plugin: Plugin):
    url = f"https://pypi.org/pypi/{plugin.module_name}/json"
    try:
        resp = urlretrieve(url)
        with open(resp[0], "r", encoding="utf-8") as f:
            plugin.pypi_version = load(f)["info"]["version"]
    except HTTPError as e:
        if e.code == 404:
            return
        raise


async def get_git_head_hash(plugin: Plugin):
    cmd = f"git ls-remote {plugin.homepage} -b HEAD"
    proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate()
    if stdout:
        plugin.git_hash = stdout.decode().split()[0]


RUN = """from nonebot import init, load_plugin
init()
exit(0 if load_plugin("{name}") else 1)
"""


async def pdm_create_project_from_pypi(plugin: Plugin):
    cmd = f"cd {plugin.folder_path} && pdm init --non-interactive && pdm add {plugin.module_name}"
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        await asyncio.wait_for(proc.communicate(), 300)
    except asyncio.TimeoutError:
        proc.terminate()
        print("从 PyPI 创建项目超时")
        return
    manifest = plugin.folder_path.joinpath("pdm.lock")
    if not manifest.exists():
        return
    if f'name = "{plugin.project_link}"' in manifest.read_text("utf-8"):
        plugin.created_from_pypi = True


async def pdm_create_project_from_git(plugin: Plugin):
    cmd = f"cd {plugin.folder_path} && pdm init --non-interactive && pdm add git+{plugin.homepage}"
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        await asyncio.wait_for(proc.communicate(), 300)
    except asyncio.TimeoutError:
        proc.terminate()
        print("从 Git 创建项目超时")
        return
    manifest = plugin.folder_path.joinpath("pdm.lock")
    if not manifest.exists():
        return
    if f'git = "{plugin.homepage}"' in manifest.read_text("utf-8"):
        plugin.created_from_git = True


async def pdm_run_project_from_pypi(plugin: Plugin, data: dict):
    plugin.folder_path.joinpath(".env.prod").write_bytes(
        Path(".env.prod.example").read_bytes()
    )
    plugin.folder_path.joinpath("run.py").write_text(
        RUN.format(name=plugin.module_name)
    )
    cmd = f"cd {plugin.folder_path} && pdm run python run.py"
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), 30)
    except asyncio.TimeoutError:
        proc.terminate()
        data["stderr_pypi"] = "从 PyPI 项目运行超时"
        print(data["stderr_pypi"])
        return
    if proc.returncode == 0:
        plugin.booted_from_pypi = True
        data.pop("stderr_pypi", None)
    else:
        data["stderr_pypi"] = stderr.decode().strip()
        if not data["stderr_pypi"]:
            data["stderr_pypi"] = stdout.decode().strip()
        print(data["stderr_pypi"])


async def pdm_run_project_from_git(plugin: Plugin, data: dict):
    plugin.folder_path.joinpath(".env.prod").write_bytes(
        Path(".env.prod.example").read_bytes()
    )
    plugin.folder_path.joinpath("run.py").write_text(
        RUN.format(name=plugin.module_name)
    )
    cmd = f"cd {plugin.folder_path} && pdm run python run.py"
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), 30)
    except asyncio.TimeoutError:
        proc.terminate()
        data["stderr_git"] = "从 Git 项目运行超时"
        print(data["stderr_git"])
        return
    if proc.returncode == 0:
        plugin.booted_from_git = True
        data.pop("stderr_git", None)
    else:
        data["stderr_git"] = stderr.decode().strip()
        if not data["stderr_git"]:
            data["stderr_git"] = stdout.decode().strip()
        print(data["stderr_git"])


async def git_add(filepath: Path):
    await (await asyncio.create_subprocess_shell(f"git add {filepath}")).communicate()


async def commit_changes():
    await (
        await asyncio.create_subprocess_shell(
            "git config user.name Lancercmd && git config user.email lancercmd@gmail.com"
        )
    ).communicate()
    cmd = "git commit -m '✅ Update state'"
    proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE)
    stdout, _ = await proc.communicate()
    if "nothing to commit" in stdout.decode():
        return
    await (await asyncio.create_subprocess_shell("git push")).communicate()


if __name__ == "__main__":
    exit(2)
