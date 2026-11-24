# AGENTS.md

本文件约定 AI 助手在这个项目里怎么工作。项目结构见 `README.md`，完整规范见 `docs/conventions.md`。

## 项目信息（作者填写）

- 研究问题：TODO
- 预算：TODO，例如单次运行 API 花费不超过 $5，GPU 不超过 2 小时
- 当前阶段：TODO，例如"探索阶段，只跑 E001–E003"

## 不能做的事

- 不修改、不删除 `outputs/` 下已有的运行目录，失败的运行也保留。
- 不修改 `data/raw/`。
- 已经有运行的实验配置，不改变它的含义。换模型、换数据、换评测协议时，新建 `configs/experiments/E<新编号>_<描述>.yaml`，并在 `docs/experiments.md` 登记一行。
- 不编造、不手抄结果数字。报告里的每个数字都来自 `outputs/` 下的文件，并注明运行目录名。
- 不把 API key 写进配置、代码、日志或提交记录。密钥只放在 `.env`。
- 付费 API 调用、GPU 训练、预计超过 10 分钟或超出上面预算的运行，先向作者报告预计的调用次数、花费和时长，得到确认再启动。
- 作者没有要求时，不执行 git commit、push，也不改写 git 历史。

## 跑实验

1. 先跑 `make test`，需要时再跑 `make smoke`，确认流水线是通的。冒烟和调试运行用 `configs/debug/` 叠加层，不新建实验编号。
2. 正式运行只用 `uv run expkit run -c configs/experiments/<文件> [key=value ...]`。小改动用命令行覆盖，不用 `sed` 改 YAML，也不写绕开 `run` 命令、把结果存到别处的一次性脚本。
3. 正式运行前看一眼 `git status`。有未提交改动时告诉作者，由作者决定是否提交；带改动的运行只算探索结果。
4. 跑完向作者报告：实验编号和名称（如"E001（pi-estimate）"）、运行目录名、`manifest.json` 里的 `status`、`results.json` 的关键指标、commit 是否干净。失败的运行同样报告，附上 `error` 的最后几行。
5. 汇总多次运行用 `make report EXP=<编号>`，不手工拼表。

## 写代码

- 核心逻辑放在 `src/expkit/`。`scripts/` 和 notebook 只调用它，不复制逻辑。
- 路径和超参从 `cfg` 读取，不写死在代码里。新增的配置项先在 `configs/base.yaml` 里加上默认值。
- 新的实验入口写成 `def name(cfg, run) -> dict`：过程用 `run.log_metrics()`、`run.log_sample()` 记录，大文件写进 `run.artifacts`，返回值会写进 `results.json`。
- 写 JSON 用 `expkit.run.write_json`，追加记录用 `expkit.run.append_jsonl`，不直接用 `open(..., "w")` 写结果文件。
- 加依赖用 `uv add <包名>`，不用 `pip install`。
- 改完代码跑 `make test` 和 `make lint`。测试会检查每个实验配置都能解析、入口函数都存在。
- 代码注释和 docstring 用英文；`docs/`、`reports/` 和 README 用中文。

## 调用 LLM 时

- 所有调用都走同一个客户端模块，例如 `src/expkit/llm.py`，在那里统一做缓存、重试和 token、费用记录。
- 模型写带日期的快照名，不用 `latest` 这类别名。
- 每条样本或 episode 在 `samples.jsonl` 里写一行，带 `error` 字段，基础设施故障和模型答错分开记。
