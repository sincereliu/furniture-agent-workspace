# 开发环境（uv + fnm + text-to-cad）

本仓库是 text-to-cad 的**消费者**，不是它的开发工作区。CAD 运行时用 `.venv` 里安装的 **cadgen 轮子**（自带 `_runtime`），不要把 `external/text-to-cad/packages/cadgen/src` 插到 `PYTHONPATH`。checkout 里的 `_runtime/` 是 gitignore 的，没有打包过的源码树不能当运行时。

版本钉在子模块 Skill 上，不要在本仓库 `pyproject.toml` 再写一份：

- 子模块：`external/text-to-cad/VERSION`
- Python pin：`external/text-to-cad/skills/cad/requirements.txt`（里面的 `cadgen[snapshot]==…` 由子模块 `VERSION` 决定，本仓库不再复写版本号）
- cadgen 要求 Python `>=3.11`；本仓库用 **Python 3.12** + **uv** 管解释器与 `.venv`，**fnm** 管 Node。

Node 不是 CAD 运行时依赖。`cadgen viewer`、STEP 生成、snapshot 都走轮子里的 `_runtime`。只有要在 checkout 里改 cadgen / Viewer 源码并自己 bundle 时才需要 Node。

## 从零建 `.venv`

在仓库根目录、PowerShell：

```powershell
git submodule update --init --recursive external/text-to-cad

if (Test-Path .venv) { Remove-Item -Recurse -Force .venv }

uv python install 3.12
uv sync --python 3.12
uv pip install -r external/text-to-cad/skills/cad/requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

需要科学分析依赖时再加上：

```powershell
uv sync --python 3.12 --extra furniture-analysis
uv pip install -r external/text-to-cad/skills/cad/requirements.txt
```

`uv sync` 会重写 `.venv` 里 pyproject 锁定的包，**不会**带上 cadgen。每次 `uv sync` 之后都要再跑一遍上面的 `uv pip install -r .../cad/requirements.txt`。

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

- `cadgen doctor` 报的版本等于 `external/text-to-cad/VERSION`，且 pin 匹配 `skills/cad/requirements.txt`
- `file` 在 `.venv\Lib\site-packages\cadgen\` 下，**不在** `external\text-to-cad\`
- `runtime` 为 `True`

子模块升级后（pin 变了），删掉旧 `.venv` 按「从零建」重来，或至少重跑 `uv pip install -r external/text-to-cad/skills/cad/requirements.txt`。cadgen 的 freshness gate **不跟踪 cadgen 版本**，升级后清一次缓存，避免旧 tree 被当成 current：

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\.cache\cadgen" -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Directory -Filter .cadgen-store temp, generated -ErrorAction SilentlyContinue |
  Remove-Item -Recurse -Force
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
npm --prefix packages/cadgen-js install
npm --prefix apps/viewer install
bash scripts/bundle/bundle.sh
```

只有这条路径才适合 editable 安装：

```powershell
uv pip install -e "external/text-to-cad/packages/cadgen[snapshot]"
```

未 bundle 就 editable，mesh / snapshot / `cadgen viewer` 会找不到 `_runtime`。家具主路径不要走 editable。

## Windows：Smart App Control

`import build123d` / `cadgen` 若报 `DLL load failed while importing OCP`，是 Windows 11 Smart App Control 拦了未签名的 OCC 原生模块，不是 venv 装错。`cadgen doctor` 会点名。关法：设置 → 隐私和安全性 → Windows 安全中心 → 应用和浏览器控制 → Smart App Control。没有按应用豁免。

## CAD 桥怎么用这个环境

`CadBridge` 用仓库 `.venv` 的解释器执行 `python <model>.py --json`（可加 `--force`）。解释器里的 cadgen 必须是上面装上的轮子。不要把 checkout 源码插到 `PYTHONPATH`。
