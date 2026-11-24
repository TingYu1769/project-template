# 实验仓库规范

这份规范约定用本模板建的每个实验项目怎么组织代码、配置、数据和运行结果，调 LLM API 的 agent 实验和 GPU 训练都适用。它要保证两件事：

- 任何一个结果都能追到产生它的代码版本和完整配置。
- 重跑、换机器、几个月后回头查，都不靠记忆。

本仓库就是按这份规范搭好的可运行骨架，包名 `expkit`；`tools/new_project.sh` 用它新建项目。

## 新建项目

```bash
bash tools/new_project.sh my-project ~/work     # 建在 ~/work/my-project/，父目录默认是当前目录
cd ~/work/my-project && make test
```

脚本依次做这几件事：

1. 用 `git archive` 导出模板当前 commit 的文件，不带 `tools/`、`LICENSE`
2. 把包名 `expkit` 换成 `my_project`
3. `git init`、`uv sync`，提交第一个 commit，提交信息里记下模板的 commit

每个实验项目是一个独立的 git 仓库。

## 原则

**1. 五类东西分开放。** 它们的生命周期不同，混在一起就分不清哪些能改、哪些能删。

| 类别 | 位置 | 进 git | 规则 |
|---|---|---|---|
| 代码 | `src/<pkg>/`、`scripts/`、`tests/` | 是 | 随时修改；不写死路径和超参 |
| 配置 | `configs/` | 是 | 一个实验定义写定后，不再改变它的含义 |
| 数据 | `data/` | 否 | `raw/` 只读；`processed/` 必须能由脚本重建 |
| 运行输出 | `outputs/` | 否 | 每次运行一个目录，写完不改，失败的也保留 |
| 结论 | `docs/`、`reports/` | 是 | 体积小；报告由脚本从运行输出生成 |

**2. 每次运行都新建一个目录，永不覆盖。** 路径是 `outputs/<实验名>/<YYYYMMDD-HHMMSS>[_<label>]_<4位随机十六进制>/`，`label` 可选，只描述同一实验下的变体。目录已存在就直接报错。

**3. 运行目录自带复现信息。** 每个目录里存这些东西：

- 合并后的完整配置 `config.yaml`
- `manifest.json`，内容有：
  - git commit、有无未提交改动、未跟踪的文件
  - 命令行和覆盖项、seed
  - 主机、Python 版本、GPU、`uv.lock` 的 sha256
  - 起止时间和状态
- 未提交改动的完整 diff `git.diff`

正式结论只用 commit 干净的运行。

**4. 实验定义写成文件。**

- 每个实验写成一个文件 `configs/experiments/E<三位编号>_<名称>.yaml`，文件名就是实验名。
- 换 seed、调一个参数这类小改动用命令行覆盖，manifest 会记录下来。
- 不用 `sed` 改 YAML，也不靠拼长命令行定义实验。

**5. 原始输出和汇总分两步。**

- 实验只负责写原始记录：`metrics.jsonl`、`samples.jsonl`、`results.json`。
- 汇总表和图由 `report` 命令或 `scripts/` 从 `outputs/` 生成，不手抄数字。
- 汇总逻辑改了，也不用重跑实验。

**6. 每个实验在登记表里有一行。** `docs/experiments.md` 把问题或假设、配置、运行目录、结论连在一起。实验编号只增不复用。换模型、换数据、换评测协议，就开新编号。

**7. 写文件经得起中断。**

- JSON 先写临时文件，再原子替换。
- 过程记录用 JSONL 追加，每行写完就 fsync。
- 进程被杀时，已经写下的记录不会损坏。

**8. 上游代码单独存放。**

- 拷进来的第三方代码放在 `third_party/<name>/`，旁边放一份 `PROVENANCE.json`，写明来源仓库、commit 和本地改动。
- 复现论文时，另在 `docs/` 里列出和原实现不同的地方。

**9. 调 LLM 的项目再加三条。** 模板没有内置这部分，需要时在 `src/<pkg>/llm.py` 里实现。

- **响应缓存**：放在 `cache/llm.sqlite`，缓存键是完整请求的 sha256。请求里要包括：
  - 带日期的模型快照名，不用别名
  - messages、temperature、max_tokens、tools、seed
  - 采样序号，否则 best-of-N 会塌成同一个回答

  缓存不设过期时间。厂商的 prompt caching 只省钱和省延迟，不能替代这层缓存。
- **轨迹**：每条样本或 episode 在 `samples.jsonl` 里写一行，包括：
  - id、输入、输出、工具调用、reward
  - token 数、费用
  - `error` 字段

  基础设施故障和模型答错分开记。中断后续跑时，跳过已完成的 id。
- **费用和 prompt**：
  - 每次调用的 token 数和费用都要记下，汇总到 `results.json`。
  - prompt 模板放在 `prompts/` 下进 git，调用时记录 prompt 的哈希。

## 目录结构

```
<project>/
├── README.md            目标、安装、怎么跑、结果在哪
├── AGENTS.md            AI 助手的工作约定；CLAUDE.md 用 @AGENTS.md 导入它
├── pyproject.toml       uv 管理，src 布局
├── uv.lock              进 git
├── .python-version  .gitignore  .env.example      .env 不进 git
├── Makefile             setup / test / smoke / lint / report
├── src/<pkg>/
│   ├── config.py        YAML 加载：extends 继承、点号覆盖、RunSpec 校验
│   ├── run.py           运行目录、manifest、原子写入
│   ├── report.py        汇总一个实验的全部运行
│   ├── cli.py           唯一入口：run / report
│   └── experiment.py    实验入口函数 (cfg, run) -> dict，按需拆成 data/ envs/ agents/ eval/ 等模块
├── configs/
│   ├── base.yaml        默认值
│   ├── <group>/*.yaml   可组合的部件，例如 model/、env/，用 extends: [a, b] 组合
│   ├── experiments/     一个文件一个实验：E001_pi-estimate.yaml，文件名就是实验名
│   ├── debug/           调试叠加层：smoke.yaml，叠上去的运行写到 outputs/_debug/
│   └── local.yaml       本机设置，例如把 output_root 指到别的盘；不进 git
├── scripts/             批量运行、下载数据、画图；只调用 src/，不复制逻辑
├── notebooks/           探索用，01-explore-xxx.ipynb；结论要搬进 src/ 或 reports/
├── tests/               按被测模块一一对应：test_config.py、test_run.py…；test_experiments.py 检查每个实验配置都能解析
├── docs/                设计文档、experiments.md 登记表
├── reports/             E001_pi-estimate.md、E001_pi-estimate_runs.md、figures/
├── third_party/         按需：拷进来的上游代码 + PROVENANCE.json
├── data/                不进 git，只有 data/README.md 进；raw/ 只读，processed/ 可重建
├── cache/               不进 git，删掉也能重建
└── outputs/             不进 git，只增不改
    └── <实验名>/<YYYYMMDD-HHMMSS>[_<label>]_<4hex>/
        ├── config.yaml      合并后的完整配置
        ├── manifest.json    见下表
        ├── git.diff         有未提交改动时才生成
        ├── run.log
        ├── metrics.jsonl    过程指标：{"step", "time", ...}
        ├── samples.jsonl    逐样本或逐 episode 的记录
        ├── results.json     最终指标
        └── artifacts/       checkpoint、视频、生成的数据
```

## manifest.json 字段

| 字段 | 含义 |
|---|---|
| `schema_version` | manifest 格式版本，目前是 1 |
| `run_id`、`experiment`、`exp_id` | 运行目录名、实验名（如 `E001_pi-estimate`）、实验编号（如 `E001`） |
| `label`、`debug` | 变体描述（可为空）；是否调试运行 |
| `seed`、`entry` | 随机种子；实验入口 `模块:函数` |
| `status` | `running` / `success` / `failed` / `interrupted` |
| `started_at`、`ended_at`、`duration_s` | 带时区的 ISO 时间，耗时以秒计 |
| `argv`、`cwd` | 完整命令行和工作目录 |
| `config_paths`、`overrides`、`config_sha256` | 实验配置和叠加层文件、命令行覆盖项、合并后配置的哈希 |
| `git` | `commit`、`branch`、`dirty`、`untracked`、`diff_file` |
| `env` | `python`、`executable`、`platform`、`host`、`uv_lock_sha256`、`cuda_visible_devices`、`gpus` |
| `error` | 失败时的 traceback |

运行目录里的 manifest 和原始记录，是"这个数字从哪来"的唯一凭据。登记表和报告引用的都是运行目录名。

## 命名

- **项目名**：小写字母，用连字符连接，例如 `my-project`。包名把连字符换成下划线，即 `my_project`。
- **实验名**：`E<三位编号>_<名称>`，例如 `E001_pi-estimate`。编号从 `E001` 开始，只增不复用；名称小写、用连字符连接。冒烟和调试用 `configs/debug/` 叠加层，不占编号。`tests/test_experiments.py` 会检查命名。
- **运行目录**：时间戳精确到秒，按名字排序大致就是时间顺序。末尾的 4 位随机十六进制数，用来避免同一秒启动的两次运行撞名。
- **notebook**：`两位序号-用途-描述.ipynb`，例如 `03-explore-failure-cases.ipynb`。

## 按规模裁剪

- **最小可用**：`README.md`、`src/`、`configs/`、`outputs/`、一个冒烟测试。用不到的目录直接删掉。
- **按需添加**：

| 需要 | 加什么 |
|---|---|
| 数据要在多台机器之间同步 | DVC，或 Hugging Face datasets 仓库 |
| 依赖和主环境冲突 | `environments/<name>/`（独立的 uv 项目）或 `docker/<name>/Dockerfile` |
| 参数扫描 | `scripts/sweep_E00x.sh`，循环调用 `run` 并传入不同的覆盖项，每个组合各算一次运行 |
| 多个进程写同一份结果 | 每个进程用自己的运行目录；确实要共享时用 SQLite，参考 vla-evaluation-harness 的 `recording.py` |

## 参考来源

这份规范来自 2026-10-03 对以下项目的调研。

| 项目 | 借鉴了什么 | 没有借鉴什么 |
|---|---|---|
| [allenai/vla-evaluation-harness](https://github.com/allenai/vla-evaluation-harness) | 可安装的 `src/` 包加一个薄 CLI；YAML 用 `extends` 继承（`src/vla_eval/cli/config_loader.py`）；结果里写入 config、seed 和带 git hash 的版本号；原始结果不进 git，挑出的结果和带结论的报告一起提交（`docs/reproductions/`）；每个完整配置配一个冒烟配置 | 结果平铺在 `./results`，文件名不带 run id，重跑会静默覆盖；`experiments/` 里用 `sed` 改 YAML 的脚本，已有 7 处引用路径失效；每个 benchmark 一个 Docker 镜像、leaderboard、PyPI 发布，对个人研究太重 |
| 作者的一个论文复现工程 | 原子写入和 JSONL 追加（`run.py` 由它改写）；单一入口 `run.sh`；`UPSTREAM.json`、`PROVENANCE.json`；`docs/reproduction.md` 的偏差对照表 | 输出默认写到仓库外 |
| 作者的一个自我改进实验工程 | `manifest.json` 里的配置哈希、版本、候选 id 和父候选 id；attempt id 不复用；`docs/` 按章节编号 | `data/` 根目录散落约 20 个 `.log` 文件 |
| lightning-hydra-template、Hydra | `configs/experiment/` 一个文件一个实验；输出目录带时间戳；保存合并后的配置和覆盖项 | 没有用 Hydra 本身，它的规则多，出错难排查 |
| lm-evaluation-harness、Inspect AI、SWE-agent、OpenHands | 结果 JSON 带 git hash 和任务版本；逐样本 JSONL；按完整请求缓存 LLM 响应；出错的样本也写进记录 | Inspect 的缓存默认 1 周过期，研究里不该过期 |
| Cookiecutter Data Science v2、Good Research Code Handbook | `data/raw` 只读；`src/` 是可安装的包；notebook 编号命名 | — |
| Sacred、W&B | 每次运行记录 git commit、dirty 标记、diff、依赖和主机信息 | 外部追踪服务；需要可视化时再接 |

外部链接：

- <https://cookiecutter-data-science.drivendata.org/>
- <https://github.com/ashleve/lightning-hydra-template>
- <https://hydra.cc/docs/tutorials/basic/running_your_app/working_directory/>
- <https://goodresearch.dev/setup.html>
- <https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/interface.md>
- <https://inspect.aisi.org.uk/eval-logs.html>
- <https://inspect.aisi.org.uk/caching.html>
- <https://swe-agent.com/latest/usage/trajectories/>
- <https://docs.openhands.dev/openhands/usage/developers/evaluation-harness>
- <https://sacred.readthedocs.io/en/stable/observers.html>
