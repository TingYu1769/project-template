# expkit

TODO：用一两句话写清这个项目要回答什么问题、用什么方法、在什么数据或环境上做。

目录和运行记录遵循 `docs/conventions.md` 的实验仓库规范。AI 助手的工作约定写在 `AGENTS.md`，`CLAUDE.md` 导入它。

## 快速开始

```bash
make setup                 # 安装依赖
cp .env.example .env       # 需要 API key 时填写
make test                  # 单元测试和冒烟测试
make smoke                 # 示例实验叠加冒烟层跑一次，结果写到 outputs/_debug/
```

## 跑实验

`configs/experiments/` 下的每个文件定义一个实验，文件名就是实验名：`E<三位编号>_<名称>.yaml`，例如 `E001_pi-estimate.yaml`。编号用来认，名称给人看，提到实验时两者一起写。

```bash
uv run expkit run -c configs/experiments/E001_pi-estimate.yaml
uv run expkit run -c configs/experiments/E001_pi-estimate.yaml run.label=seed1 run.seed=1
uv run expkit run -c configs/experiments/E001_pi-estimate.yaml -c configs/debug/smoke.yaml
```

- 命令行的 `key.sub=value` 覆盖配置里已有的键。键不存在会报错，确实要新增时写 `+key.sub=value`。
- 每次运行都新建一个目录，不会覆盖旧结果。
- `run.label` 可选，只描述同一实验下的变体，会出现在运行目录名里。
- 多个 `-c` 按顺序合并。`configs/debug/` 下是调试叠加层，叠上去的运行写到 `outputs/_debug/`，不占实验编号。
- 配置的合并顺序：`extends` 的父配置 → 实验配置 → 叠加层 → `configs/local.yaml` → 命令行覆盖。

汇总一个实验的全部运行：

```bash
make report EXP=E001       # 编号或全名都行；表格同时写到 reports/E001_pi-estimate_runs.md
```

## 目录

| 目录 | 放什么 | 进 git |
|---|---|---|
| `src/expkit/` | 核心代码：`config.py` 加载配置，`run.py` 管理运行目录，`cli.py` 是入口，`experiment.py` 是示例实验 | 是 |
| `configs/` | `base.yaml` 是默认值，`experiments/` 每个文件一个实验，`debug/` 是调试叠加层，`local.yaml` 写本机设置 | `local.yaml` 除外 |
| `scripts/` | 批量运行、下载数据、画图的脚本，只调用 `src/` 里的代码 | 是 |
| `notebooks/` | 探索用，命名为 `01-explore-xxx.ipynb` | 是 |
| `tests/` | 单元测试和冒烟测试 | 是 |
| `docs/` | 设计文档和实验登记表 `experiments.md` | 是 |
| `reports/` | 结论报告和图，由脚本从 `outputs/` 生成 | 是 |
| `data/` | 数据，来源写在 `data/README.md` | 否 |
| `outputs/` | 运行输出，每次运行一个目录 | 否 |
| `cache/` | 删掉也能重建的缓存 | 否 |

## 一次运行留下什么

```
outputs/<实验名>/<YYYYMMDD-HHMMSS>[_<label>]_<4位随机十六进制>/
├── config.yaml      合并后的完整配置
├── manifest.json    git commit、有无未提交改动、命令行、seed、主机、uv.lock 哈希、起止时间、状态
├── git.diff         运行时未提交的改动，没有改动就不生成
├── run.log          日志
├── metrics.jsonl    过程指标，由 run.log_metrics() 写入
├── samples.jsonl    逐样本或逐 episode 的记录，由 run.log_sample() 写入
├── results.json     最终指标，即实验入口函数的返回值
└── artifacts/       checkpoint、视频、生成的数据等大文件
```

运行出错时目录照样保留，`manifest.json` 里 `status` 为 `failed`，`error` 字段存着 traceback。

## 新增实验入口

1. 在 `src/expkit/` 下写一个函数 `def my_exp(cfg, run) -> dict`。
2. 函数里用 `run.log_metrics()`、`run.log_sample()` 记录过程，大文件写进 `run.artifacts`，返回的字典会写进 `results.json`。
3. 在实验配置里设 `run.entry: expkit.my_module:my_exp`。
4. 在 `docs/experiments.md` 登记一行。
