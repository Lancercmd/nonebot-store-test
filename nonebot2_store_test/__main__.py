'''
Author       : Lancercmd
Date         : 2022-01-21 12:09:00
LastEditors  : Lancercmd
LastEditTime : 2022-01-21 22:18:00
Description  : None
GitHub       : https://github.com/Lancercmd
'''
from asyncio import create_subprocess_shell, run, subprocess
from json import loads
from pathlib import Path
from shutil import rmtree

from requests import get

COMMIT = "10733e7"


def load_json_data_from_url(branch: str) -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36"
    }
    url = f"https://raw.githubusercontent.com/nonebot/nonebot2/{branch}/website/static/plugins.json"
    r = get(url, headers=headers)
    return loads(r.text)


async def create_poetry_project(project_name: str) -> bool:
    _path = Path("workflow") / COMMIT / f"test-{project_name}"
    if not _path.exists():
        proc = await create_subprocess_shell(
            f"poetry new {_path.resolve()} && cd {_path.resolve()} && poetry add {project_name.replace('_', '-')}",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        print("")
        if not stderr:
            print(f"Created project {project_name} peacefully.")
        else:
            print(f"Error while creating project: {project_name}")
        return not stderr
    else:
        print(f"Project {project_name} already exists.")
        return True

RUNNER = """from nonebot import get_driver, init, load_plugin

init()
driver = get_driver()

try:
    from nonebot.adapters.onebot.v11 import Adapter as OneBot_V11_Adapter

    driver.register_adapter(OneBot_V11_Adapter)
except ImportError:
    try:
        from nonebot.adapters.cqhttp import Bot as OneBot_V11_Bot

        driver.register_adapter('cqhttp', OneBot_V11_Bot)
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


async def run_poetry_project(project_name: str) -> bool:
    _path = Path("workflow") / COMMIT / f"test-{project_name}"
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
            print(f"Run project {project_name} peacefully.")
        else:
            print(f"Error while running project {project_name}:")
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


async def perform_poetry_test(branch: str) -> None:
    data = load_json_data_from_url(branch)
    report = [[], [], []]
    for i in data:
        latest = await create_poetry_project(i["module_name"])
        if latest:
            finish = await run_poetry_project(i["module_name"])
            if finish:
                report[0].append(i["module_name"])
            else:
                report[1].append(i["module_name"])
        else:
            report[2].append(i["module_name"])
    print()
    print("=" * 80)
    print("")
    if report[0]:
        print("Passed:")
        for i in report[0]:
            print(f"    {i}")
        print("")
    if report[1]:
        print("Error while running:")
        for i in report[1]:
            print(f"    {i}")
        print("")
    if report[2]:
        print("Error while creating:")
        for i in report[2]:
            print(f"    {i}")
        print("")
    print("=" * 80)


if __name__ == "__main__":
    try:
        print("Make sure running with utf-8 encoding.")
        rmtree(Path("workflow") / COMMIT, ignore_errors=True)
        run(perform_poetry_test(COMMIT))
    except KeyboardInterrupt:
        print("\nExit by user.")
    except Exception as e:
        print(f"\nError: {e}")
    rmtree(Path("workflow") / COMMIT, ignore_errors=True)
