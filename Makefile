# 常用命令。项目根目录有 .env 时自动加载其中的环境变量（API key 等）。
ENV_FILE := $(wildcard .env)
RUN := uv run $(if $(ENV_FILE),--env-file .env)
EXP ?= E001

.PHONY: setup test smoke lint report

setup:  # 安装依赖（含 dev 组）
	uv sync

test:   # 单元测试 + 冒烟测试
	$(RUN) pytest -q

smoke:  # 示例实验叠加冒烟层跑一次，输出写到 outputs/_debug/
	$(RUN) expkit run -c configs/experiments/E001_pi-estimate.yaml -c configs/debug/smoke.yaml

lint:
	$(RUN) ruff check src tests

report: # 汇总某个实验的全部运行，写到 reports/<实验名>_runs.md：make report EXP=E001
	$(RUN) expkit report $(EXP) --save
