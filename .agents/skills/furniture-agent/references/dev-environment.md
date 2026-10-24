# 开发环境（uv + fnm + text-to-cad）

本仓库是 text-to-cad 的**消费者**，不是它的开发工作区。CAD 运行时用 `.venv` 里安装的 **cadgen 轮子**（自带 `_runtime`），不要把 `external/text-to-cad/packages/cadgen/src` 插到 `PYTHONPATH`。checkout 里的 `_runtime/` 是 gitignore 的，没有打包过的源码树不能当运行时。

版本钉在子模块 Skill 上，不要在本仓库 `pyproject.toml` 再写一份：

- 子模块：`external/text-to-cad/VERSION`
- Python pin：`external/text-to-cad/skills/cad/SKILL.md` 启动行里的 `cadgen==…`，与 `VERSION` 相同。本仓库不再复写版本号。`skills/cad/requirements.txt` 和 `cadgen[snapshot]` 额外依赖都已经没有了，Playwright 跟在 `cadgen` 本体里。
- cadgen 要求 Python `>=3.11`；本仓库用 **Python 3.12** + **uv** 管解释器与 `.venv`，**fnm** 管 Node。技能自己的 `uvx --python 3.13` 是给智能体宿主单独装一份用的，家具 CAD 不走那条。

Node 不是 CAD 运行时依赖。`cadgen viewer`、STEP 生成、snapshot 都走轮子里的 `_runtime`。只有要在 checkout 里改 cadgen / Viewer 源码并自己 bundle 时才需要 Node。

## 从零建 `.venv`

在仓库根目录、PowerShell：

```powershell
git submodule update --init --recursive external/text-to-cad

if (Test-Path .venv) { Remove-Item -Recurse -Force .venv }

uv python install 3.12
uv sync --python 3.12
$version = (Get-Content -Raw external/text-to-cad/VERSION).Trim()
uv pip install "cadgen==$version"
.\.venv\Scripts\python.exe -m playwright install chromium
```

需要科学分析依赖时再加上：

```powershell
uv sync --python 3.12 --extra furniture-analysis
$version = (Get-Content -Raw external/text-to-cad/VERSION).Trim()
uv pip install "cadgen==$version"
```

`uv sync` 会重写 `.venv` 里 pyproject 锁定的包，**不会**带上 cadgen。每次 `uv sync` 之后都要再跑一遍上面的 `uv pip install "cadgen==$version"`。

## 核对已经对齐

```powershell
.\.venv\Scripts\python.exe -m cadgen.cli doctor external/text-to-cad/skills/cad
.\.venv\Scripts\python.exe -c @"
import cadgen, importlib.metadata as m
from pathlib import Path
root = Path(cadgen.__file__).resolve().parent
print('cadgen', m.version('cadgen'))
print('file', cadgen.__file__)
print('runtime', (root / '_runtime').is_dir())
"@
```

合格结果：

- `cadgen doctor` 报的版本等于 `external/text-to-cad/VERSION`，且 pin 匹配 `skills/cad/SKILL.md` 里的 `cadgen==`
- `file` 在 `.venv\Lib\site-packages\cadgen\` 下，**不在** `external\text-to-cad\`
- `runtime` 为 `True`

子模块升级后（pin 变了），删掉旧 `.venv` 按「从零建」重来，或至少重跑 `uv pip install "cadgen==$version"`（`$version` 来自 `VERSION`）。cadgen 的 freshness gate **不跟踪 cadgen 版本**，升级后清一次缓存，避免旧 tree 被当成 current：

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\.cache\cadgen" -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Directory -Filter .cadgen-store temp, generated -ErrorAction SilentlyContinue |
  Remove-Item -Recurse -Force
```

## 跑测试

布局阶段维护时，只跑 [布局运行时映射](../../../../domain/stages/layout-plan/references/runtime-map.md) 的「维护时跑哪几个测试」里这次改动碰到的行。下面不带 `-p` 的命令是整库回归。

在仓库根目录、PowerShell：

```powershell
.\.venv\Scripts\python.exe domain\stages\cad-generated\scripts\run_tests.py
```

入口在 `run_tests.py`，用标准库 `unittest`，不需要额外安装。它调 `runtime_paths.bootstrap_runtime_paths()` 装好阶段包和独立 AI 模块，再发现六阶段中现有的 `scripts/tests/` 与 `domain/modules/ai/tests/` 下的全部测试。包括布局阶段的位置稳定性与脱墙旋转回归。原命令与 `-p` 用法不变。加 `-v` 会列出每个未失败用例。

合格结果是最后一行 `ran <总数>, failed 0, errored 0, skipped 0`。退出码 0 表示全绿。

测试会建临时目录并往 `store/`、`temp/` 写文件，所以要在一个可写工作区里跑；**报 `PermissionError` 或 `FileNotFoundError` 都是运行环境不允许写文件，不是代码缺陷**——先确认工作区可写，再判断测试是否真的红了。

已知环境限制：在 DSH 的 Windows 写入限制沙箱（`workspace-write`）下，`tempfile` 建出的临时目录会被拒绝访问，表现是一整片 `PermissionError`，涉及约 37 个用例。原因是沙箱给受限进程的新建对象补的那个 capability ACE，会被 `chmod` 重写 DACL 时抹掉，而 `tempfile.mkdtemp()` 恰好用 `mode=0o700`（唯一触发值；`0o755`/`0o750`/`0o711`/`0o777` 都正常）。这与本仓库代码无关，普通机器上是全绿；换更宽的权限预设即可绕开。

本仓库测试按 `unittest` 写，不依赖 pytest。只想跑单个文件时加 `-p`：

```powershell
.\.venv\Scripts\python.exe domain\stages\cad-generated\scripts\run_tests.py -p test_panel_rule_contracts.py
```

## fnm / Node（可选）

日常跑家具 CAD **不用** Node。需要改 Viewer 或从 checkout 打 `_runtime` 时：

```powershell
fnm install 22
fnm use 22
node -v
```

bundle 脚本是 bash，Windows 用 Git Bash，不要用 PowerShell 直接跑 `.sh`：

```bash
cd external/text-to-cad
bash scripts/bundle/bundle.sh
```

`bundle.sh` 把 `_runtime` 打进 `packages/cadgen`。Node 构建用 `packages/core`，Viewer 用 `apps/web`，CAD 应用页用 `apps/mcp`。

只有这条路径才适合 editable 安装：

```powershell
uv pip install -e "external/text-to-cad/packages/cadgen"
```

未 bundle 就 editable，mesh / snapshot / `cadgen viewer` 会找不到 `_runtime`。家具主路径不要走 editable。

## Windows：Smart App Control

`import build123d` / `cadgen` 若报 `DLL load failed while importing OCP`，是 Windows 11 Smart App Control 拦了未签名的 OCC 原生模块，不是 venv 装错。`cadgen doctor` 会点名。关法：设置 → 隐私和安全性 → Windows 安全中心 → 应用和浏览器控制 → Smart App Control。没有按应用豁免。

## CAD 桥怎么用这个环境

`CadBridge` 用仓库 `.venv` 的解释器执行 `python <model>.py --json`（可加 `--force`）。解释器里的 cadgen 必须是上面装上的轮子。不要把 checkout 源码插到 `PYTHONPATH`。
