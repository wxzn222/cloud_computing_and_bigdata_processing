# Windows 环境准备与启动检查

请同学们使用自己的笔记本完成安装与预检，再进入实验 01。手册使用 Windows 11 x64、Python 3.12 和 CPU，基础任务在本机 Python 环境中运行。选择模型路径前应完成本机校验，设备运行过慢或内存不足时改做同分基础路径。本文所有命令均为 **PowerShell**，不是 CMD，也不是 WSL 中的 Bash。

## 1. 先认识路径、终端和解释器

将课程包解压到 `C:\BDP`。资源管理器进入该目录，应能同时看到 `README.md`、`coursekit`、`requirements.lock.txt` 和八个实验目录。如果外面多套了一层 `BDP\BDP`，真正工作目录是能看到这些文件的内层目录。

开始菜单搜索 PowerShell 并打开，普通用户权限即可。输入：

```powershell
Set-Location C:\BDP
Get-Location
Get-ChildItem
```

第一条切换当前工作目录；第二条应显示 `C:\BDP`；第三条列出文件。路径只是本手册约定，如果实际路径不同，修改 `Set-Location` 后所有相对路径仍可使用。含空格的路径要加引号，例如 `Set-Location 'D:\My Courses\BDP'`。

各章用 Git 的 `diff --no-index` 保存本人改动，因此也需安装 Git for Windows。请从 [Git 官方页面](https://git-scm.com/downloads/win)取得安装器，并按下载页面提供的信息核对来源。安装后重开 PowerShell，运行 `git --version`。`git diff --no-index` 比较两个本地文件，有差异时退出码为 1，这是它的正常约定，不表示文件比较失败。代码编辑器可用已有的 VS Code 或其他能保存 UTF-8 的文本编辑器。

复制代码块时不包含前后的三个反引号。出现 `PS C:\BDP>` 之类终端提示符时也不应复制。不要把 Python 代码直接当 PowerShell 命令执行。

## 2. 安装 Python 3.12 并创建独立环境

请从 [Python 官方 Windows 下载页面](https://www.python.org/downloads/windows/) 取得安装器。安装时启用 Python Launcher；若已安装 3.12，不要重复安装。补丁版本不同通常不影响命令形式，但仍应运行本节预检和后续实验检查，以实际结果为准。

```powershell
py -0p
py -3.12 --version
```

`py` 是 Windows 上选择 Python 版本的启动器，`-3.12` 指定所需大/小版本。`py -0p` 显示已安装解释器及其路径。如果提示找不到命令，先关闭终端再重开；仍失败，检查安装器是否安装 Launcher。不要把系统中的其他 Python 删除来解决版本选择问题。

创建课程专属虚拟环境：

```powershell
Set-Location C:\BDP
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe --version
```

`-m venv` 运行 Python 自带的环境创建模块；`.venv` 是目录名。后面的命令显式使用该环境的解释器，因此不需要执行 `Activate.ps1`，也不需要放宽全局 PowerShell 执行策略。八个实验共用这个环境，不需要每次新建。

## 3. 安装、锁定和核对依赖

```powershell
$env:PYTHONUTF8 = '1'
$coursePyPI = 'https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple'
.\.venv\Scripts\python.exe -m pip install --index-url $coursePyPI -r requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw '依赖安装失败，请先处理上方第一条错误' }
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import duckdb, pyarrow, dask, distributed, moto, numpy, fastapi; print('BASE_IMPORT_OK')"
```

环境变量 `PYTHONUTF8` 使 Python 在终端/文件默认处理时使用 UTF-8；关闭窗口后本次设置失效，可在新窗口重设。文件读写代码仍显式声明 UTF-8。`pip install -r` 按锁文件逐项安装，包括间接依赖；`pip check` 检查包之间的版本要求；最后一条只做导入预检。导入成功不代表后续八个实验已经运行。

依赖文件分为三个用途：`requirements.lock.txt` 是原生 Windows 基线；`requirements-models.lock.txt` 在基线上增加嵌入模型依赖；`requirements.container.txt` 供 Linux 容器构建，剔除了 Windows 专有包。两个 Windows 锁文件固定版本，但没有内嵌 wheel 哈希，因此版本相同只说明包版本一致，并不证明安装文件逐字节相同。安装时使用一个明确的镜像源，不混用 `extra-index-url`；若单独升级某个包，应重新执行 `pip check` 和受影响实验。

首次依赖安装耗时受网络影响。测量算法或模型耗时时，请排除下载和安装时间。

### 使用离线 wheel 包

请在自己的 Windows x64 / Python 3.12 笔记本能联网时执行下列命令，保存离线安装所需的依赖包；已有缓存和清单的同学可以直接从下一段校验命令开始：

```powershell
Set-Location C:\BDP
New-Item -ItemType Directory -Force wheelhouse | Out-Null
$coursePyPI = 'https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple'
.\.venv\Scripts\python.exe -m pip download --index-url $coursePyPI -r requirements-models.lock.txt -d wheelhouse
.\.venv\Scripts\python.exe scripts\artifact_manifest.py create .\wheelhouse .\wheelhouse-manifest.json
```

取得 `wheelhouse` 与 `wheelhouse-manifest.json` 后，先校验再安装：

```powershell
.\.venv\Scripts\python.exe scripts\artifact_manifest.py verify .\wheelhouse .\wheelhouse-manifest.json
.\.venv\Scripts\python.exe -m pip install --no-index --find-links .\wheelhouse -r requirements.lock.txt
```

`--no-index` 禁止联网搜索，`--find-links` 指向本地包目录。校验失败时不要继续安装，应重新取得离线包并再次核对。Windows wheel 不能直接用于 Linux 容器。wheel 包只包含 Python 程序依赖，不包含 BGE 模型权重或 Ollama 模型。没有离线包时，可按本节前面的清华 PyPI 命令安装；模型路径还需把依赖文件换成 `requirements-models.lock.txt`。

## 4. 建立个人身份与数据

```powershell
$studentId = Read-Host '请输入本人学号'
.\.venv\Scripts\python.exe -m coursekit identity --student-id $studentId --lab 01 --stage start
.\.venv\Scripts\python.exe -m coursekit seed --rows 20000
```

输入本人学号并保留前导零。`student.json` 记录本人学号，不应写手机号或身份证号。按 [学号与提交验收](学号与提交验收.md) 运行、取证和提交；所有评分截图原生显示学号、实验/项目号和 run_id，与真实结果同屏。主要 CLI 自动生成证据 HTML，独立命令用 capture。身份缺失、UNREGISTERED 或不一致须退回补证；机器核对身份后仍须授课老师逐张复核截图。身份码和哈希都不具备防伪能力，学习成果还需结合改动 diff 与现场说明验收。

`seed` 用固定随机种子 42 生成虚构推理事件、政策资料和评价题。默认 20,102 行，其中合法唯一事件 20,000 条、完全重复 100 条、非法 2 条。相同参数重复运行不会改变内容；如原始事件已被修改或更换规模，程序会拒绝覆盖，以免丢失证据。

生成的数据保存在本人笔记本的课程目录中。规则文档中的 CPU 配额、保留时间等是虚构题设，用于练习检索、版本比较和权限核验。

## 5. 可选模型对照的环境准备

选择模型对照的同学，请先完成实验 01—04，再按实验 05 的步骤依次运行词法基线和构建语义索引。模型权重通过下方下载命令单独准备，也可使用已取得且能通过 manifest 校验的离线目录。

如果已准备 `wheelhouse` 离线包，使用以下两条命令安装模型依赖：

```powershell
.\.venv\Scripts\python.exe scripts\artifact_manifest.py verify .\wheelhouse .\wheelhouse-manifest.json
.\.venv\Scripts\python.exe -m pip install --no-index --find-links .\wheelhouse -r requirements-models.lock.txt
```

如果没有 `wheelhouse`，通过清华 PyPI 镜像在线安装：

```powershell
$coursePyPI = 'https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple'
.\.venv\Scripts\python.exe -m pip install --index-url $coursePyPI -r requirements-models.lock.txt
.\.venv\Scripts\python.exe -m pip check
```

嵌入模型固定为 `BAAI/bge-small-zh-v1.5`，用于在 CPU 上观察中文语义检索。如果已准备离线模型目录，只需校验本地文件；没有离线目录时，可通过下一步从国内 ModelScope 准备。

在可访问国内 ModelScope 的网络中执行以下命令，可得到不依赖账户缓存路径的普通文件目录。脚本逐文件核对版本、字节数和 SHA256，只允许 `modelscope.cn` 及其子域；域名不符合要求时会停止并保留错误，不会改走其他下载源：

```powershell
.\.venv\Scripts\python.exe scripts\prepare_embedding.py
Get-Content -LiteralPath .\models\embedding-manifest.json -Encoding UTF8
```

脚本只下载运行所需的配置、分词器和约 96 MB 的 safetensors 权重。`models\embedding-manifest.json` 记录固定来源版本、每个文件的大小和 SHA256；`--verify-only` 会逐项核对，无需在报告中手抄整串散列。

模型目录准备好后，在完成 01—04 且准备进行实验 05 的语义对照时执行：

```powershell
.\.venv\Scripts\python.exe scripts\prepare_embedding.py --verify-only
$env:BDP_EMBED_MODEL = (Resolve-Path .\models\bge-small-zh-v1.5).Path
$env:HF_HUB_OFFLINE = '1'
.\.venv\Scripts\python.exe -m coursekit lab05 --mode semantic
```

此时直接从本地目录加载。报告中的本地模型 revision 是该目录的内容散列，并与 `models\embedding-manifest.json` 中的上游提交信息一起记录。恢复共同词法基线时：

```powershell
Remove-Item Env:HF_HUB_OFFLINE -ErrorAction SilentlyContinue
Remove-Item Env:BDP_EMBED_MODEL -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m coursekit lab05 --mode lexical
```

这些 `Remove-Item Env:` 命令只移除当前终端的环境变量，不删除模型文件。语义实验读取已校验的本地目录，不需要连接 Hugging Face。离线运行需分别准备 Python wheel、BGE 普通目录和 Ollama 模型；三者用途不同。

先从 [Ollama 官方 Windows 下载页](https://ollama.com/download/windows) 安装，并重新打开 PowerShell。如果官方下载在当前网络不可用，可使用已经取得的官方离线安装文件，先按随包清单校验；暂时无法完成安装时可改走同分的基础路径。默认生成模型文件为 `Qwen3.5-0.8B-Q8_0.gguf`，大小约 834 MB。没有离线 GGUF 时，以下命令从国内 ModelScope 下载，并把固定来源版本、字节数和 SHA256 写入 `models\generation-manifest.json`：

```powershell
.\.venv\Scripts\python.exe scripts\prepare_generation.py prepare
```

准备得到或从离线包取得 `models\qwen35` 与 `models\generation-manifest.json` 后，执行：

```powershell
ollama --version
.\.venv\Scripts\python.exe scripts\prepare_generation.py verify
.\.venv\Scripts\python.exe scripts\prepare_generation.py import-ollama
ollama list
$env:BDP_OLLAMA_MODEL = 'bdp-qwen35:0.8b-q8_0'
Invoke-RestMethod -Uri http://127.0.0.1:11434/api/tags
```

`prepare_generation.py` 从固定的 ModelScope 来源下载模型，并核对文件清单。脚本在导入前再次检查 GGUF 和 Modelfile，使用自定义 tag，避免连接 Ollama Registry。该 GGUF 是社区转换制品，不等于 Ollama 官方 tag 或 digest。默认请求关闭 thinking，使用 CPU、2线程、上下文2048、最多输出256 token；代码不会自动启用 GPU。模型文件大小和真正运行时内存不同，还需给运行时、KV cache 和 Windows 留出空间。Ollama 应用通常在安装后运行；如本地接口无法连接，先打开 Ollama，再检查端口，不能把文件导入完成当作服务已可用。

此课程的小模型可能生成错误引用、遗漏条件或错误回答，这些都是实验 06 应保留和分析的观察。课程评价不要求小模型必然优于摘录基线。

新开 PowerShell 后，在**当前将执行语义查询或启动服务的终端**重新设置以下变量，再运行模型命令。另一窗口的设置不会自动传入已经启动的进程；先完成模型文件校验。

```powershell
$env:PYTHONUTF8 = '1'
$env:BDP_EMBED_MODEL = (Resolve-Path .\models\bge-small-zh-v1.5).Path
$env:HF_HUB_OFFLINE = '1'
$env:BDP_OLLAMA_MODEL = 'bdp-qwen35:0.8b-q8_0'
```

## 6. 两个终端与 HTTP 服务

实验 07 用到一个持续运行的服务进程。终端 A 启动后会一直停留在服务日志，这是正常现象；用终端 B 发请求。

终端 A（在完成 01–06 后）：

```powershell
Set-Location C:\BDP
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m uvicorn coursekit.service:app --host 127.0.0.1 --port 8000
```

终端 B：

```powershell
Set-Location C:\BDP
$env:PYTHONUTF8 = '1'
Invoke-RestMethod -Uri http://127.0.0.1:8000/health
.\.venv\Scripts\python.exe -m coursekit lab07 --requests 20
```

`127.0.0.1` 是本机回环地址。服务代码中的 `role` 仅用于模拟权限，没有用户身份认证；实验服务应保持本机监听。完成实验，在终端 A 按 `Ctrl+C` 即可正常停止。

## 7. 可选容器实验的环境准备

容器化是实验 07 的可选部署对照。同学们先在自己的笔记本上用原生 Python 完成 HTTP 实验；本机已具备可用 Docker Desktop 时，再开展容器练习。准备前阅读 [Docker Desktop Windows 系统要求](https://docs.docker.com/desktop/setup/install/windows-install/)，核对本机后端、虚拟化条件与安装许可。

`Dockerfile` 描述镜像，`compose.yaml` 描述端口、数据挂载、CPU/内存限制和健康检查。Windows 上使用 Docker 的 Linux 容器后端运行该镜像，请区分宿主机、容器后端和容器内进程。

```powershell
docker version
docker compose version
docker compose config --quiet
```

`docker version` 必须同时显示 Client 和 Server 才说明引擎可用；仅有 Client 不够。`compose config` 只验证配置能否解析，不会构建镜像、启动服务或证明功能正常。具体构建、停止原生服务以释放 8000 端口、挂载数据和验收步骤见实验 07。

## 8. 独立数据根与恢复顺序

需要规模对照时，保持代码目录不变，在新终端为一次实验新建独立数据根；不要覆盖已有默认数据。下面生成新的唯一目录名，并登记这次实验的本人身份：

```powershell
$isolatedRoot = Join-Path (Get-Location) ('outputs\scale-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $isolatedRoot | Out-Null
$env:BDP_ROOT = $isolatedRoot
$studentId = Read-Host '请输入本人学号'
.\.venv\Scripts\python.exe -m coursekit identity --student-id $studentId --lab 03 --stage scale-start
.\.venv\Scripts\python.exe -m coursekit seed --rows 40000
.\.venv\Scripts\python.exe -m coursekit lab01
.\.venv\Scripts\python.exe -m coursekit lab02
.\.venv\Scripts\python.exe -m coursekit lab03 --workers 2 --partitions 8
Remove-Item Env:BDP_ROOT
```

记录 `$isolatedRoot` 的真实值；移除变量后回到默认数据根，不删除刚生成的证据。若要把这组对照计入实验 03，另用 `capture --lab 03` 记录对应命令、原始结果与配置。跨窗口运行时必须设置同一数据根并重新核对身份。课程可执行附件通过 `coursekit.common` 读取 `BDP_ROOT`，与主命令使用相同的数据、输出和身份目录；请在启动附件的终端设置该变量。复制到 `submissions` 的练习脚本也沿用这一约定，不混用两份数据。

### 高发问题与恢复顺序

| 现象 | 原因定位 | 操作 |
|---|---|---|
| `No module named coursekit` | 当前目录不对 | 用 `Get-Location`、`Get-ChildItem coursekit` 检查项目根目录 |
| `No module named duckdb` 等 | 用了错误解释器或装包失败 | 请使用 `.\.venv\Scripts\python.exe`，再安装锁文件 |
| 中文乱码 | PowerShell 显示或 Python 流编码不一致 | 新终端设置 `$env:PYTHONUTF8='1'`；读取文件用 `Get-Content -Encoding UTF8` |
| 原始数据拒绝覆盖 | 本次规模或内容与已有证据不同 | 保留旧数据，按本节新建独立数据根进行规模对照 |
| 下载超时/证书错误 | 网络、代理或系统证书配置 | 记录首个错误；有本人准备的离线缓存时核对清单后使用，否则稍后重试国内源；不要关闭 TLS 校验 |
| `WinError 10048` / 地址已使用 | 同一端口已有服务 | 回原终端 `Ctrl+C` 停止本人服务；先 `Get-NetTCPConnection -LocalPort 8000` 检查，不能盲杀其他进程 |
| 索引过期返回 409 | 文档或实验 04 快照已改变 | 重建 lab05，完成 lab06 dev，重新 freeze 后运行 test，再做 lab07/08；已看过 test 时将重跑标记为回归检查，不要手改 manifest |
| `PermissionError` 位于 pytest 临时目录 | 当前账户对系统临时测试目录无权限 | 用下方新建的项目内测试目录，不要提权删除他人临时目录 |
| Docker 无法连接 LinuxEngine | Docker Desktop 引擎未启动 | 在本机打开 Docker Desktop，等待引擎就绪并检查 Server；暂不可用时完成原生路径 |

需要进一步核验代码时，可执行针对性测试：

```powershell
New-Item -ItemType Directory -Force outputs | Out-Null
$testRun = Join-Path (Get-Location) ('outputs\pytest-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp $testRun
```

每次使用新的目录保留测试过程，避免碰到其他课程的系统临时目录。正式实验成绩依据每次实验的独立任务、原始运行证据和解释；通过这里的代码测试不能代替完成报告。
