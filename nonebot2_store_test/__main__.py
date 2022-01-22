'''
Author       : Lancercmd
Date         : 2022-01-21 12:09:00
LastEditors  : Lancercmd
LastEditTime : 2022-01-22 22:55:44
Description  : None
GitHub       : https://github.com/Lancercmd
'''
from asyncio import create_subprocess_shell, run, subprocess
from json import loads
from os import system
from pathlib import Path
from shutil import rmtree

from requests import get

COMMIT = "10733e7"
HOME = Path("workflow") / COMMIT


def load_json_data_from_url(branch: str) -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36"
    }
    url = f"https://raw.githubusercontent.com/nonebot/nonebot2/{branch}/website/static/plugins.json"
    r = get(url, headers=headers)
    return loads(r.text)


def vacuum(project_name: str = None) -> None:
    if project_name:
        rmtree(HOME / f"test-{project_name}", ignore_errors=True)
        rmtree(HOME / f"test-{project_name}-git", ignore_errors=True)
    else:
        rmtree(HOME, ignore_errors=True)


async def create_poetry_project_from_pypi(project_name: str, pypi_name: str) -> bool:
    _path = HOME / f"test-{project_name}"
    if not _path.exists():
        proc = await create_subprocess_shell(
            f"poetry new {_path.resolve()} && cd {_path.resolve()} && poetry add {pypi_name}",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if not stderr:
            print(f"Created project {project_name} from PyPI peacefully.")
        return not stderr
    else:
        print(f"Project {project_name} already exists.")
        return True


async def create_poetry_project_from_git(project_name: str, git_path: str) -> bool:
    _path = HOME / f"test-{project_name}-git"
    if not _path.exists():
        _proc = await create_subprocess_shell(
            f"poetry new {_path.resolve()} && cd {_path.resolve()} && poetry env use python && poetry env info --path",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _stdout, _stderr = await _proc.communicate()
        _venv = _stdout.decode().strip().splitlines()[-1]

        # Remove existing git virtualenv to create a new one.
        system(f'rmdir "{_venv}" /s /q')

        proc = await create_subprocess_shell(
            f"cd {_path.resolve()} && poetry add git+{git_path}",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if not stderr:
            print(f"Created project {project_name} from Git peacefully.")
        return not stderr
    else:
        print(f"Project {project_name} already exists.")
        return True


async def create_poetry_project(project_name: str, pypi_name: str, git_path: str) -> tuple[bool]:
    print()
    _pypi = await create_poetry_project_from_pypi(project_name, pypi_name)
    if _pypi:
        _git = await create_poetry_project_from_git(project_name, git_path)
    else:
        _git = await create_poetry_project_from_git(project_name, git_path)
        if not _git:
            vacuum(project_name)
            print(f"Error while creating project: {project_name}")
    return _pypi, _git


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


async def run_poetry_project_from_pypi(project_name: str) -> bool:
    _path = HOME / f"test-{project_name}"
    if _path.exists():
        with open(_path / "runner.py", "w") as f:
            f.write(RUNNER.format(project_name))
        proc = await create_subprocess_shell(
            f"cd {_path.resolve()} && poetry run python runner.py",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        code = proc.returncode
        if not code:
            print(f"Run project {project_name} from PyPI peacefully.")
        else:
            print(f"Error while running project {project_name} from PyPI:")
            _err = stderr.decode().strip()
            if len(_err.splitlines()) > 1:
                for i in _err.splitlines():
                    print(f"    {i}")
            elif not _err:
                print(stdout.decode().strip())
            else:
                print(_err)
        return not code
    else:
        print(f"Project {project_name} does not exist.")
        return False


async def run_poetry_project_from_git(project_name: str) -> bool:
    _path = HOME / f"test-{project_name}-git"
    if _path.exists():
        with open(_path / "runner.py", "w") as f:
            f.write(RUNNER.format(project_name))
        proc = await create_subprocess_shell(
            f"cd {_path.resolve()} && poetry run python runner.py",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        code = proc.returncode
        if not code:
            print(f"Run project {project_name} from Git peacefully.")
        else:
            print(f"Error while running project {project_name} from Git:")
            _err = stderr.decode().strip()
            if len(_err.splitlines()) > 1:
                for i in _err.splitlines():
                    print(f"    {i}")
            elif not _err:
                print(stdout.decode().strip())
            else:
                print(_err)
        return not code
    else:
        print(f"Project {project_name} does not exist.")
        return False


async def run_poetry_project(project_name: str) -> tuple[bool]:
    _pypi = await run_poetry_project_from_pypi(project_name)
    _git = await run_poetry_project_from_git(project_name)
    return _pypi, _git


async def perform_poetry_test(branch: str) -> None:
    data = load_json_data_from_url(branch)
    _passed = {}
    _error_while_running = {}
    _error_while_creating = {}
    _max_length = 0
    for i in data:
        _module_name = i["module_name"]
        if _max_length < len(_module_name):
            _max_length = len(_module_name)
        _project_link = i["project_link"]
        _name = i["name"]
        _homepage = i["homepage"]
        _cpypi, _cgit = await create_poetry_project(_module_name, _project_link, _homepage)
        if _cpypi or _cgit:
            _rpypi, _rgit = await run_poetry_project(_module_name)
            if _rpypi or _rgit:
                _passed[_module_name] = {
                    "name": _name, "pypi": _rpypi, "git": _rgit
                }
            else:
                _error_while_running[_module_name] = {
                    "name": _name, "pypi": _rpypi, "git": _rgit
                }
        else:
            _error_while_creating[_module_name] = {
                "name": _name, "pypi": _cpypi, "git": _cgit
            }
    print()
    print("=" * 80)
    print()
    if _passed:
        print("Passed:")
        for i in _passed:
            _name = _passed[i]["name"]
            _pypi = "✅" if _passed[i]["pypi"] else "❌"
            _git = "✅" if _passed[i]["git"] else "❌"
            print(
                f"    {i}{' ' * (_max_length - len(i))}    PyPI: {_pypi}    Git: {_git}    {_name}"
            )
        print()
    if _error_while_running:
        print("Error while running:")
        for i in _error_while_running:
            _name = _error_while_running[i]["name"]
            _pypi = "✅" if _error_while_running[i]["pypi"] else "❌"
            _git = "✅" if _error_while_running[i]["git"] else "❌"
            print(
                f"    {i}{' ' * (_max_length - len(i))}    PyPI: {_pypi}    Git: {_git}    {_name}"
            )
        print()
    if _error_while_creating:
        print("Error while creating:")
        for i in _error_while_creating:
            _name = _error_while_creating[i]["name"]
            _pypi = "✅" if _error_while_creating[i]["pypi"] else "❌"
            _git = "✅" if _error_while_creating[i]["git"] else "❌"
            print(
                f"    {i}{' ' * (_max_length - len(i))}    PyPI: {_pypi}    Git: {_git}    {_name}"
            )
        print()
    print("=" * 80)


if __name__ == "__main__":
    try:
        print("Make sure running with utf-8 encoding.")
        vacuum()
        run(perform_poetry_test(COMMIT))
    except KeyboardInterrupt:
        print("\nExit by user.")
    except Exception as e:
        print(f"\nError: {e}")
    # vacuum()
