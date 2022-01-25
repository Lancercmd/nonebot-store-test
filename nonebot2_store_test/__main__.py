'''
Author       : Lancercmd
Date         : 2022-01-21 12:09:00
LastEditors  : Lancercmd
LastEditTime : 2022-01-26 01:01:46
Description  : None
GitHub       : https://github.com/Lancercmd
'''
from asyncio import create_subprocess_shell, run, subprocess
from dataclasses import dataclass, field
from json import loads
from os import system
from pathlib import Path
from shutil import rmtree
from sys import platform

from requests import get

COMMIT = "ebd45dc"
HOME = Path("workflow") / COMMIT
RUNNER = """from nonebot import get_driver, init, load_plugin

init()
driver = get_driver()

try:
    from nonebot.adapters.onebot.v11 import Adapter as OneBot_V11_Adapter

    driver.register_adapter(OneBot_V11_Adapter)
except ImportError:
    try:
        from nonebot.adapters.cqhttp import Bot as OneBot_V11_Bot

        driver.register_adapter("cqhttp", OneBot_V11_Bot)
    except ImportError:
        pass
except Exception as e:
    pass

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
        self._create = {"pypi": False, "git": False}
        self._run = {"pypi": False, "git": False}


class Operator:
    def __init__(self, branch: str, *, difficulty: int = 0, specific_modules: str = None) -> None:
        self.branch = branch
        self.difficulty = difficulty
        self.specific_modules = specific_modules
        self.data = Operator.load_json_data_from_url(self.branch)
        self.report = Report(self.branch)
        self._max_length = 0
        print("Make sure running with utf-8 encoding.")

    @staticmethod
    def load_json_data_from_url(branch: str) -> dict:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36"
        }
        url = f"https://raw.githubusercontent.com/nonebot/nonebot2/{branch}/website/static/plugins.json"
        r = get(url, headers=headers)
        return loads(r.text)

    @staticmethod
    def vacuum(module: Module = None) -> None:
        if module:
            rmtree(module.path_pypi, ignore_errors=True)
            rmtree(module.path_git, ignore_errors=True)
        else:
            rmtree(HOME, ignore_errors=True)

    async def create_poetry_project_from_pypi(self, module: Module) -> None:
        _path = module.path_pypi
        if not _path.exists():
            proc = await create_subprocess_shell(
                f"poetry new {_path.resolve()} && cd {_path.resolve()} && poetry add {module.project_link} && poetry run python -m pip install -U {module.project_link}",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if not stderr:
                print(
                    f"Created project {module.module_name} from PyPI peacefully."
                )
            module._create["pypi"] = not stderr
        else:
            print(f"Project {module.module_name} already exists.")
            module._create["pypi"] = True

    async def create_poetry_project_from_git(self, module: Module) -> None:
        _path = module.path_git
        if not _path.exists():
            _proc = await create_subprocess_shell(
                f"poetry new {_path.resolve()} && cd {_path.resolve()} && poetry env use python && poetry env info --path",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            _stdout, _stderr = await _proc.communicate()
            _venv = _stdout.decode().strip().splitlines()[-1]

            # Remove existing git virtualenv to create a new one.
            if platform == "win32":
                system(f'rmdir "{_venv}" /s /q')
            else:
                system(f"rm -rdf {_venv}")

            proc = await create_subprocess_shell(
                f"cd {_path.resolve()} && poetry run python -m pip install git+{module.homepage}",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if not "ERROR" in stderr.decode():
                print(
                    f"Created project {module.module_name} from Git peacefully."
                )
            module._create["git"] = not "ERROR" in stderr.decode()
        else:
            print(f"Project {module.module_name} already exists.")
            module._create["git"] = True

    async def create_poetry_project(self, module: Module) -> None:
        print()
        await self.create_poetry_project_from_pypi(module)
        if module._create["pypi"]:
            await self.create_poetry_project_from_git(module)
        else:
            await self.create_poetry_project_from_git(module)
            if not module._create["git"]:
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
                stderr=subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            code = proc.returncode
            if not code:
                print(
                    f"Run project {module.module_name} from PyPI peacefully."
                )
            else:
                print(
                    f"Error while running project {module.module_name} from PyPI:"
                )
                _err = stderr.decode().strip()
                if len(_err.splitlines()) > 1:
                    for i in _err.splitlines():
                        print(f"    {i}")
                elif not _err:
                    print(stdout.decode().strip())
                else:
                    print(_err)
            module._run["pypi"] = not code
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
                stderr=subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            code = proc.returncode
            if not code:
                print(f"Run project {module.module_name} from Git peacefully.")
            else:
                print(
                    f"Error while running project {module.module_name} from Git:"
                )
                _err = stderr.decode().strip()
                if len(_err.splitlines()) > 1:
                    for i in _err.splitlines():
                        print(f"    {i}")
                elif not _err:
                    print(stdout.decode().strip())
                else:
                    print(_err)
            module._run["git"] = not code
        else:
            print(f"Project {module.module_name} does not exist.")

    async def run_poetry_project(self, module: Module) -> None:
        # if module._create["pypi"]:
        await self.run_poetry_project_from_pypi(module) if module._create["pypi"] else ...
        # if module._create["git"]:
        await self.run_poetry_project_from_git(module) if module._create["git"] else ...

    async def dependency_declaration_test(self) -> None:
        _passed = self.report.passed
        _error_while_running = self.report.error_while_running
        _error_while_creating = self.report.error_while_creating
        for i in self.data:
            module = Module(
                self.branch, i["module_name"], i["project_link"], i["name"], i["homepage"]
            )
            if self.specific_modules:
                if self.specific_modules not in module.module_name:
                    continue
            if self._max_length < len(module.module_name):
                self._max_length = len(module.module_name)
            await self.create_poetry_project(module)
            if module._create["pypi"] or module._create["git"]:
                await self.run_poetry_project(module)
                if module._run["pypi"] or module._run["git"]:
                    _passed[module.module_name] = {
                        "display_name": module.display_name,
                        "pypi": module._run["pypi"],
                        "git": module._run["git"]
                    }
                else:
                    _error_while_running[module.module_name] = {
                        "display_name": module.display_name,
                        "pypi": module._run["pypi"],
                        "git": module._run["git"]
                    }
            else:
                _error_while_creating[module.module_name] = {
                    "display_name": module.display_name,
                    "pypi": module._create["pypi"],
                    "git": module._create["git"]
                }

    async def perform_a_test(self) -> None:
        Operator.vacuum()
        await self.dependency_declaration_test()
        self.output_report()

    def output_report(self) -> None:
        _passed = self.report.passed
        _error_while_running = self.report.error_while_running
        _error_while_creating = self.report.error_while_creating
        print()
        print("=" * 80)
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
        op = Operator(COMMIT)
        run(op.perform_a_test())
    except KeyboardInterrupt:
        print("\nExit by user.")
    except Exception as e:
        print(f"\nError: {e}")
