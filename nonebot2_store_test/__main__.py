"""
Author       : Lancercmd
Date         : 2022-01-21 12:09:00
LastEditors  : Lancercmd
LastEditTime : 2023-01-23 16:32:06
Description  : None
GitHub       : https://github.com/Lancercmd
"""
from asyncio import create_subprocess_shell, run, subprocess
from copy import deepcopy
from getopt import getopt
from dataclasses import dataclass, field
from json import dumps, loads
from os import system
from pathlib import Path
from shutil import rmtree
from sys import argv, platform
from typing import Optional

from requests import get

COMMIT = "master"
HOME = Path("workflow") / COMMIT
ENV = HOME.parent / "env"
LOCAL = HOME.parent / "history.json"
RUNNER = """from nonebot import init, load_plugin

init()
valid = load_plugin("{}")
if not valid:
    exit(1)
else:
    exit(0)
"""


@dataclass
class Report:
    branch: str
    passed: dict = field(default_factory=dict)
    error_while_running: dict = field(default_factory=dict)
    error_while_creating: dict = field(default_factory=dict)


@dataclass
class Module:
    branch: str
    module_name: str
    project_link: str
    display_name: str
    homepage: str

    def __post_init__(self):
        self.path_pypi = HOME / f"test-{self.module_name}"
        self.path_git = HOME / f"test-{self.module_name}-git"
        self.pypi_version = None
        self._pypi_create = False
        self._pypi_run = False
        self._pypi_skip = False
        self.git_hash = None
        self._git_create = False
        self._git_run = False
        self._git_skip = False


class Operator:
    def __init__(self, argv: list[str]) -> None:
        self.branch = COMMIT
        self.difficulty = 0
        self.specific_module = None
        self._commit = True
        opts, args = getopt(
            argv[1:],
            "d:s:l:n",
            ["difficulty=", "specific-module=", "--limit=", "no-commit"],
        )
        if args:
            self.branch = args[0]
            self.reconstant()
        for opt, arg in opts:
            if opt in ("-d", "--difficulty"):
                self.difficulty = int(arg)
                print()
                print("Difficulty:", self.difficulty)
            elif opt in ("-s", "--specific-module"):
                self.specific_module = arg
                print()
                print(f'Specific module: "{self.specific_module}"')
            elif opt in ("-l", "--limit"):
                self._limit = int(arg)
                print()
                print(
                    f"Limit: Test up to {self._limit}",
                    "plugin." if self._limit == 1 else "plugins.",
                )
            elif opt in ("-n", "--no-commit"):
                self._commit = False
                print()
                print("No commit when finish.")
        print()
        print("Make sure running with utf-8 encoding.")

    def reconstant(self) -> None:
        global COMMIT, HOME, ENV, LOCAL
        COMMIT = self.branch
        HOME = Path("workflow") / COMMIT
        Operator.vacuum()
        ENV = HOME.parent / "env"
        LOCAL = HOME.parent / "history.json"

    @staticmethod
    def vacuum(module: Module = None) -> None:
        if module:
            rmtree(module.path_pypi, ignore_errors=True)
            rmtree(module.path_git, ignore_errors=True)
        else:
            rmtree(HOME, ignore_errors=True)

    @staticmethod
    def load_json_data_from_url(branch: str) -> dict:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36"
        }
        url = f"https://raw.githubusercontent.com/nonebot/nonebot2/{branch}/website/static/plugins.json"
        r = get(url, headers=headers)
        return loads(r.text)

    @staticmethod
    def load_json_data_from_path(path: Path) -> dict:
        if path.exists():
            try:
                with path.open(encoding="utf-8") as f:
                    return loads(f.read())
            except ValueError:
                return {}
        else:
            return {}

    @staticmethod
    async def get_head_hash(git: str) -> Optional[str]:
        proc = await create_subprocess_shell(
            f"git ls-remote {git} HEAD", stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        code = proc.returncode
        if not code:
            _hash = stdout.decode().strip().split()[0]
            return _hash[:7]
        else:
            print(stderr.decode().lstrip())
            return None

    @staticmethod
    def get_pypi_latest(pypi: str) -> Optional[str]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36"
        }
        url = f"https://pypi.org/pypi/{pypi}/json"
        r = get(url, headers=headers)
        if r.status_code == 200:
            data = loads(r.text)
            return data["info"]["version"]
        else:
            return None

    def check_upstream_update(self) -> None:
        _latest = Operator.get_pypi_latest("nonebot2")
        if _latest != self.local.get("_runtime_latest", None):
            if not self.local:
                self.local = {"_runtime_latest": _latest}
            elif not "_runtime_latest" in self.local:
                _li = [[x, y] for x, y in self.local.items()]
                _li.insert(0, ["_runtime_latest", _latest])
                self.local = {x: y for x, y in _li}
            else:
                self.local["_runtime_latest"] = _latest
            self.save_local()
        self._runtime_latest = _latest

    async def checkout_branch(self) -> None:
        _default = ["master", "main"]
        if self.branch.startswith(tuple(_default)):
            self._master = True
            self.branch = await Operator.get_head_hash(
                "https://github.com/nonebot/nonebot2.git"
            )
            self.reconstant()
        self.data = Operator.load_json_data_from_url(self.branch)
        self.local = Operator.load_json_data_from_path(LOCAL)
        self.check_upstream_update()
        self.report = Report(self.branch)
        self._max_length = 0

    async def compare_versions(self, module: Module) -> None:
        print()
        if not self.local.get(module.project_link):
            self.local[module.project_link] = {}
        local: dict = self.local.get(module.project_link)
        _pypi = Operator.get_pypi_latest(module.project_link)
        module.pypi_version = _pypi
        _git = await Operator.get_head_hash(module.homepage)
        module.git_hash = _git
        if (
            local.get("_runtime_latest", None) != self._runtime_latest
            or local.get("_rerun_flag", None)
            or self.specific_module is not None
        ):
            return
        module._pypi_skip = _pypi == local.get("pypi_version", None)
        if module._pypi_skip:
            module._pypi_create = local.get("pypi_create", False)
            module._pypi_run = local.get("pypi_run", False)
        module._git_skip = _git == local.get("git_hash", None)
        if module._git_skip:
            module._git_create = local.get("git_create", False)
            module._git_run = local.get("git_run", False)
        if module._pypi_skip and module._git_skip:
            print(f"{module.project_link} is up to date.")

    def update_local(self, module: Module) -> None:
        local = self.local.get(module.project_link)
        _local = deepcopy(local)
        if not local:
            local.update(
                {"_runtime_latest": self._runtime_latest, "first_seen": module.branch}
            )
        elif not "_runtime_latest" in local:
            _li = [[x, y] for x, y in local.items()]
            _li.insert(0, ["_runtime_latest", local.get("_runtime_latest", None)])
            local = {x: y for x, y in _li}
        local.update(
            {
                "_runtime_latest": self._runtime_latest,
                "module_name": module.module_name,
                "project_link": module.project_link,
                "display_name": module.display_name,
                "homepage": module.homepage,
                "pypi_version": module.pypi_version,
                "pypi_create": module._pypi_create,
                "pypi_run": module._pypi_run,
                "git_hash": module.git_hash,
                "git_create": module._git_create,
                "git_run": module._git_run,
                "last_seen": module.branch,
            }
        )
        local.pop("_rerun_flag", None)
        if hash(str(local)) != hash(str(_local)):
            self.local[module.project_link] = local
            self.save_local()

    def save_local(self) -> None:
        with LOCAL.open("w", encoding="utf-8") as f:
            f.write(dumps(self.local, ensure_ascii=False, indent=4))

    async def commit_changes(self) -> None:
        print()
        await (
            await create_subprocess_shell(
                "git config user.name Lancercmd && git config user.email lancercmd@gmail.com"
            )
        ).communicate()
        _proc = await create_subprocess_shell(
            f'git add {LOCAL.resolve()} && git commit -m "✅ Update {LOCAL.name}"',
            stdout=subprocess.PIPE,
        )
        _stdout, _ = await _proc.communicate()
        if "nothing to commit" in _stdout.decode():
            return
        await (await create_subprocess_shell("git push")).communicate()

    async def copy_env_file(self, _path: Path) -> None:
        await (
            await create_subprocess_shell(
                f"cd {_path.resolve()} && {'copy' if platform == 'win32' else 'cp'} {ENV.resolve()} {str((_path / '.env.prod').resolve())} > NUL"
            )
        ).communicate()

    async def create_poetry_project_from_pypi(self, module: Module) -> None:
        _path = module.path_pypi
        if not _path.exists():
            proc = await create_subprocess_shell(
                f"poetry new {_path.resolve()} && cd {_path.resolve()} && poetry add {module.project_link} && poetry run python -m pip install -U pip {module.project_link}",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            failed = "Error" in stdout.decode() or \
                "Error" in stderr.decode() or \
                "fatal" in stdout.decode() or \
                "fatal" in stderr.decode()
            if not failed:
                print(f"Created project {module.module_name} from PyPI peacefully.")
                module._pypi_create = True
                await self.copy_env_file(_path)
        else:
            print(f"Project {module.module_name} already exists.")
            module._pypi_create = True

    async def create_poetry_project_from_git(self, module: Module) -> None:
        _path = module.path_git
        if not _path.exists():
            _proc = await create_subprocess_shell(
                f"poetry new {_path.resolve()} && cd {_path.resolve()} && poetry env use python && poetry env info --path",
                stdout=subprocess.PIPE,
            )
            _stdout, _ = await _proc.communicate()
            _venv = _stdout.decode().strip().splitlines()[-1]

            # Remove existing git virtualenv to create a new one.
            if platform == "win32":
                system(f'rmdir "{_venv}" /s /q')
            else:
                system(f"rm -rdf {_venv}")

            proc = await create_subprocess_shell(
                f"cd {_path.resolve()} && poetry run python -m pip install git+{module.homepage}",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if not "ERROR" in stderr.decode():
                print(f"Created project {module.module_name} from Git peacefully.")
                module._git_create = True
                await self.copy_env_file(_path)
        else:
            print(f"Project {module.module_name} already exists.")
            module._git_create = True

    async def create_poetry_project(self, module: Module) -> None:
        await self.create_poetry_project_from_pypi(
            module
        ) if not module._pypi_skip else ...
        await self.create_poetry_project_from_git(
            module
        ) if not module._git_skip else ...
        if (not module._pypi_skip and not module._pypi_create) and (
            not module._git_skip and not module._git_create
        ):
            Operator.vacuum(module)
            print(f"Error while creating project: {module.module_name}")

    async def run_poetry_project_from_pypi(self, module: Module) -> None:
        _path = module.path_pypi
        if _path.exists():
            with open(_path / "runner.py", "w") as f:
                f.write(RUNNER.format(module.module_name))
            proc = await create_subprocess_shell(
                f"cd {_path.resolve()} && poetry run python runner.py",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            code = proc.returncode
            if not code:
                print(f"Run project {module.module_name} from PyPI peacefully.")
            else:
                print(f"Error while running project {module.module_name} from PyPI:")
                _err = stderr.decode().strip()
                if len(_err.splitlines()) > 1:
                    for i in _err.splitlines():
                        print(f"    {i}")
                elif not _err:
                    print(stdout.decode().strip())
                else:
                    print(_err)
            module._pypi_run = not code
        else:
            print(f"Project {module.module_name} does not exist.")

    async def run_poetry_project_from_git(self, module: Module) -> None:
        _path = module.path_git
        if _path.exists():
            with open(_path / "runner.py", "w") as f:
                f.write(RUNNER.format(module.module_name))
            proc = await create_subprocess_shell(
                f"cd {_path.resolve()} && poetry run python runner.py",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            code = proc.returncode
            if not code:
                print(f"Run project {module.module_name} from Git peacefully.")
            else:
                print(f"Error while running project {module.module_name} from Git:")
                _err = stderr.decode().strip()
                if len(_err.splitlines()) > 1:
                    for i in _err.splitlines():
                        print(f"    {i}")
                elif not _err:
                    print(stdout.decode().strip())
                else:
                    print(_err)
            module._git_run = not code
        else:
            print(f"Project {module.module_name} does not exist.")

    async def run_poetry_project(self, module: Module) -> None:
        await self.run_poetry_project_from_pypi(
            module
        ) if not module._pypi_skip and module._pypi_create else ...
        await self.run_poetry_project_from_git(
            module
        ) if not module._git_skip and module._git_create else ...

    async def dependency_declaration_test(self) -> None:
        _passed = self.report.passed
        _error_while_running = self.report.error_while_running
        _error_while_creating = self.report.error_while_creating
        for i in self.data:
            module = Module(
                self.branch,
                i["module_name"],
                i["project_link"],
                i["name"],
                i["homepage"],
            )
            if self.specific_module:
                if self.specific_module not in module.module_name:
                    continue
            if self._max_length < len(module.module_name):
                self._max_length = len(module.module_name)
            await self.compare_versions(module)
            if not module._pypi_skip & module._git_skip:
                if hasattr(self, "_limit"):
                    if self._limit == 0:
                        break
                    self._limit -= 1
            await self.create_poetry_project(module)
            if module._pypi_create or module._git_create:
                await self.run_poetry_project(module)
                if module._pypi_run or module._git_run:
                    _passed[module.module_name] = {
                        "display_name": module.display_name,
                        "pypi": module._pypi_run,
                        "git": module._git_run,
                    }
                else:
                    _error_while_running[module.module_name] = {
                        "display_name": module.display_name,
                        "pypi": module._pypi_run,
                        "git": module._git_run,
                    }
            else:
                _error_while_creating[module.module_name] = {
                    "display_name": module.display_name,
                    "pypi": module._pypi_create,
                    "git": module._git_create,
                }
            self.update_local(module)

    async def perform_a_test(self) -> None:
        await self.checkout_branch()
        await self.dependency_declaration_test()
        self.output_report()
        await self.commit_changes() if self._commit else ...

    def output_report(self) -> None:
        _passed = self.report.passed
        _error_while_running = self.report.error_while_running
        _error_while_creating = self.report.error_while_creating
        print()
        print("=" * 80)
        print()
        if hasattr(self, "_limit"):
            if not self._limit:
                print("Limit reached.")
                print()
        print("Runtime latest:", self._runtime_latest)
        print()
        if _passed:
            print("Passed:")
            for i in _passed:
                _name = _passed[i]["display_name"]
                _pypi = "✅" if _passed[i]["pypi"] else "❌"
                _git = "✅" if _passed[i]["git"] else "❌"
                print(
                    f"    {i}{' ' * (self._max_length - len(i))}    PyPI: {_pypi}    Git: {_git}    {_name}"
                )
            print()
        if _error_while_running:
            print("Error while running:")
            for i in _error_while_running:
                _name = _error_while_running[i]["display_name"]
                _pypi = "✅" if _error_while_running[i]["pypi"] else "❌"
                _git = "✅" if _error_while_running[i]["git"] else "❌"
                print(
                    f"    {i}{' ' * (self._max_length - len(i))}    PyPI: {_pypi}    Git: {_git}    {_name}"
                )
            print()
        if _error_while_creating:
            print("Error while creating:")
            for i in _error_while_creating:
                _name = _error_while_creating[i]["display_name"]
                _pypi = "✅" if _error_while_creating[i]["pypi"] else "❌"
                _git = "✅" if _error_while_creating[i]["git"] else "❌"
                print(
                    f"    {i}{' ' * (self._max_length - len(i))}    PyPI: {_pypi}    Git: {_git}    {_name}"
                )
            print()
        print("=" * 80)


if __name__ == "__main__":
    try:
        op = Operator(argv)
        run(op.perform_a_test())
    except KeyboardInterrupt:
        print("\nExit by user.")
    except Exception as e:
        print(f"\nError: {e}")
