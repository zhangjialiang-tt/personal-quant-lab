# Personal Quant Lab

面向中国交易所 ETF、日线级、Long Only、中低频策略的可验证 / 可复现 / 可审计量化研究平台。

> 核心能力不是证明策略有效，而是**尽可能可靠地识别哪些策略不值得投入真实资金**。

## 安装

需求：Python 3.11+，[uv](https://github.com/astral-sh/uv)。

```bash
uv sync --all-extras --group dev
```

可选数据源（Tushare token 走环境变量 `TUSHARE_TOKEN`，仅占位符配置，严禁落盘真实值）：

```bash
uv sync --all-extras --group dev
```

## 命令

```bash
uv run pql --help          # 子命令组：data / experiment / registry / validate / risk / paper / gate / review
uv run pytest -q           # 全量离线测试
uv run ruff check src tests
```

## 目录

```
config/                 # 市场规则 / 标的元数据 / 成本模型 / 验证门槛
data/                   # raw(snapshot 缓存) / snapshots(不可变研究证据) / processed / metadata(溯源，git 跟踪)
src/pql/                # 主包：schemas / lifecycle / cli + data / signals / backtest / validation / risk / portfolio / execution / review
strategies/             # 策略 spec YAML
experiments/            # EXP-XXXX：manifest.yaml + runs/RUN-XXXX/
research/hypotheses/    # 研究假设
reports/                # 报告输出（gitignore）
tests/                  # 离线测试
strategy_registry.yaml  # 策略生命周期注册表
experiment_registry.parquet  # 派生索引（pql registry rebuild 重建）
```

## 设计原则

- Hypothesis Before Code：策略先定义假设，再允许实现。
- Point-in-Time First：区分 event/available/signal/decision/execution 时间，禁止未来函数。
- Execution Must Be Realistic：明确何时出信号、何时成交、何价成交、成本多少。
- Out-of-Sample Is Consumable：Holdout 一次性研究资源，Candidate Freeze 后经 `HoldoutGuard` 一次性消费。
- Every Experiment Is Evidence：失败实验不删除，全部进 Experiment → Run Ledger。
- AI Accelerates Research, Not Approval：实盘批准权保留给人。