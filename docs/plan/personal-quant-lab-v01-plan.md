# Personal Quant Lab v0.1 执行计划

## Context

按 `docs/proposal/1.md` 从零构建 v0.1：面向中国交易所 ETF、日线级、Long Only、中低频策略的可验证/可复现/可审计量化研究平台。仓库当前为空（仅 README + 提案）。终态 = 提案 §25 的 16 条验收标准全部可演示：不可变数据快照、自动质量检查、Signal/Execution 时间契约、Control 策略回测、两个 ETF 策略、全量实验注册、可复现、参数/时间稳定性、成本压力、Kill Tests、AI Reviewer/Challenger 审查包、模拟运行 + 每日对账、状态变化可追溯。

环境事实（本会话已验证）：Python 3.11 + uv 已安装；PyPI 上 vectorbt 1.1.0（要求 `python>=3.11,<3.15`、`numpy>=2.4.6`、`pandas>=3.0.3,<4`、`numba>=0.66`）；vectorbt 文档确认 `vbt.Portfolio.from_signals(close=..., entries=..., exits=..., fees=..., slippage=..., freq=...)`，且明确要求基于收盘价的信号必须 shift 一栏（`signals.vbt.fshift(1)`）再成交——这就是本计划的 T+1 执行机制。

## 全局决策（所有里程碑引用，不得重开）

### D1 包与工程结构

- uv 管理项目，`pyproject.toml` 用 hatchling 后端；可导入包名 `pql`，src 布局；控制台命令 `pql = "pql.cli:main"`。
- `requires-python = ">=3.11,<3.15"`。
- 依赖（下限固定，`uv.lock` 提交进 git）：
    ```
    dependencies = [
        "numpy>=2.4.6", "pandas>=3.0.3,<4", "vectorbt>=1.1.0,<2",
        "scipy>=1.15", "statsmodels>=0.14", "matplotlib>=3.9",
        "plotly>=5.24", "pyyaml>=6.0", "pyarrow>=17",
    ]
    [project.optional-dependencies]
    data = ["akshare>=1.18", "tushare>=1.4.29"]
    [dependency-groups]
    dev = ["pytest>=8", "pytest-cov>=5", "ruff>=0.6"]
    ```
- 目录树（M1 一次建齐）：
    ```
    ai/{researcher_prompt.md,reviewer_prompt.md,challenger_prompt.md}
    config/markets/cn_etf_2026.yaml
    config/instruments/<symbol>.yaml
    config/costs/cn_etf_2026.yaml
    config/validation_gates.yaml
    data/{raw,snapshots,processed,paper}/          # 全部 gitignore
    data/metadata/                                  # git 跟踪（溯源记录）
    src/pql/{cli,schemas,lifecycle,timing}.py
    src/pql/data/{adapters,calendar,snapshot,quality,dataset}.py
    src/pql/signals/
    src/pql/backtest/{api,engine,costs,metrics}.py
    src/pql/registry/{experiments,budget,holdout}.py
    src/pql/validation/{pipeline,walkforward,robustness,regimes,stress,bootstrap,kill,overfitting,gates}.py
    src/pql/risk/rules.py
    src/pql/portfolio/target.py
    src/pql/execution/{orders,paper,reconcile}.py
    src/pql/review/bundle.py
    strategies/                  # 策略 spec YAML（git 跟踪）
    experiments/                 # EXP-XXXX 目录：manifest.yaml + results（git 跟踪）
    research/hypotheses/
    reports/                     # gitignore
    tests/
    strategy_registry.yaml
    experiment_registry.parquet  # 派生索引，由 pql registry rebuild 生成
    ```
- CLI：单一 argparse 入口 `src/pql/cli.py`，子命令组 `data / experiment / registry / validate / risk / paper / gate / review`。禁止引入 click/typer。

### D2 时间契约（提案 §6.3/§6.4 的实现）

`src/pql/timing.py`：

```python
@dataclass(frozen=True)
class TimingContract:
    signal_time: str = "T_close"   # 信号只用 ≤T 收盘数据
    decision_time: str = "T_close" # 决策时点
    execution_bar: int = 1         # T+N 成交，v0.1 默认 1（压力测试可 2）
    execution_price: str = "close" # close|open
```

不变式：`data_available_time ≤ signal_time ≤ decision_time < execution_time`。vectorbt 实现：entries/exits 经 `vbt.signals.fshift(execution_bar)` 后，用 `execution_price` 对应序列成交。`execution_bar == 0` 视为未来函数，校验器必须拒绝。

### D3 成本模型（提案 §16.6 的基线）

`config/costs/cn_etf_2026.yaml`，版本 id `cn-etf-cost-2026-v1`：

```yaml
version: cn-etf-cost-2026-v1
fee_rate: 0.0003 # 单边佣金比例
stamp_duty: 0.0 # ETF 免印花税
slippage: 0.001 # 单边滑点比例
```

v0.1 成本模型 = 比例佣金 + slippage，**不含最低佣金**（方案 A：初始资金 100 万、中低频 ETF 下单，min_fee=5 CNY 相对整单佣金可忽略；待执行引擎支持逐笔 `max(order_value*fee_rate, min_fee)` 时再引入，两种都在 metric 报告声明所用口径）。`run_backtest` 生产路径拒绝 `fee_rate <= 0`（抛 `CostModelError`）；引擎单元测试允许显式 `ZeroCostFixture(fee_rate=0)` 且不触发成本政策（成本政策不侵入数学引擎单元测试）。压力倍数 [1, 2, 3] 只乘 `fee_rate` 与 `slippage`。

### D4 市场规则与标的元数据

`config/markets/cn_etf_2026.yaml`（版本 id `cn-etf-2026-v1`）：lot_size=100、price_tick 按标的、`trading_calendar` 指向快照内日历、默认 benchmark `510300`。
每个标的一个 `config/instruments/<symbol>.yaml`，字段（提案 §14）：

```yaml
symbol: "518880"
exchange: SSE
asset_type: ETF
underlying_type: GOLD # INDEX|BOND|GOLD|CROSS_BORDER
currency: CNY
lot_size: 100
tick_size: 0.001
same_day_sell: true # 黄金/债券/跨境/货币 ETF=true；股票指数 ETF=false
listed_date: "2013-07-29" # 首次上市交易日（构建时从数据源核实）
```

v0.1 初始 universe（固定）：`510300`（沪深300）、`510500`（中证500）、`518880`（黄金）、`511010`（国债）。数据拉取起始日 `2013-01-01`；研究窗口从四个标的共同有数据的第一个交易日开始。**证券代码一律用字符串**，canonical 形式 `510300.SH`（含交易所后缀，避免日后 159915.SZ 需推断交易所）；内部统一 `symbol: "510300.SH"`，配置文件与 CLI 入参接受 `510300` 简写并显式解析到 `.SH`/`.SZ`。

### D5 数据快照约定

- 快照版本命名 `market-YYYYMMDD-vN`（同日重复构建递增 N）。
- 快照目录 `data/snapshots/<version>/`：`prices.parquet`（长表：`date, symbol, open, high, low, close, volume, amount, close_adj`；`close_adj` 为前复权研究价）、`calendar.parquet`（全部 A 股交易日）、`manifest.json`（source、download_time、dataset_version、每文件 sha256、adjustment 说明、schema_version=1）。
- 快照不可变 = **snapshot ID + manifest + sha256 + verify-on-read + no-overwrite**。`snapshot.py` 写入完成即对所有文件去除写权限（Windows 用 `os.chmod` 去写位，仅作防误操作）；`DatasetView.load()` 默认重新校验每个文件 sha256，不一致抛 `SnapshotIntegrityError`（chmod 不是安全边界，checksum 才是）。重建同版本 = 报错退出，不允许覆盖。
- Raw 与 Snapshot 分离：原始下载落 `data/raw/`（可删缓存），快照是研究证据（提案 §12）。
- Holdout 切分规则（确定性）：快照构建后，`holdout_start = 数据最后完整年份的前一年的 1 月 1 日`（例：数据到 2026-08，则 holdout = 2025-01-01 起，IS = 之前全部）。具体日期写入策略 spec 冻结，此后不得随数据更新漂移。
- Holdout 访问审计：任何读取 holdout 区间数据的调用必须走 `pql.registry.holdout.HoldoutGuard.holdout_slice()`。**Guard 的硬前置条件 = Candidate 已冻结**（spec hash + code commit + param set + validation config 全部锁定，见 D6/M6），未冻结 → 抛 `HoldoutError` 拒绝访问。**fail-closed 顺序**：先检查 `status != UNUSED` 则拒绝 → **原子持久化 `consumed=true` + `fsync()`**（写 `holdout_status: {consumed, consumed_at, candidate_hash}` 与 `holdout_access.log` JSONL）→ **之后才返回 holdout 数据**。`consumed=true` 必须在数据离开 Guard 之前落盘；异常采用 fail-closed，不允许回滚为 unused——宁可崩溃浪费一次，不可偷偷多获得一次。**消费不可逆**：此后任何 signal / parameter / universe / execution / cost 变更必须新建策略版本，原 holdout 不得重置为"未使用"。

### D6 策略 Schema 与生命周期

`src/pql/schemas.py` 用 frozen dataclass + YAML 双向序列化（`load_spec(path) -> StrategySpec`、`dump_spec`）。StrategySpec 字段：

```yaml
# strategies/<name>.yaml
name: etf_trend_v1
hypothesis: "……（先于代码的假设陈述）"
universe: ["510300", "510500", "518880", "511010"] # 全字符串，规范形式见 D4
benchmark: "510300"
signal: { kind: trend_ma, ma_period: 200 }
rebalance: daily # daily|weekly|monthly
risk: { max_positions: 2 }
dataset_version: market-20260808-v1
market_rule_version: cn-etf-2026-v1
cost_model_version: cn-etf-cost-2026-v1
timing: { execution_bar: 1, execution_price: close }
windows:
    in_sample: ["2013-07-29", "2024-12-31"]
    holdout: ["2025-01-01", "2026-08-07"] # 按 D5 规则在 M2 后填入真实日期
param_grid: { ma_period: [150, 180, 200, 220, 250] } # 冻结搜索范围
research_budget:
    max_total_selection_runs: 50 # 每个 SELECT run 消耗一次预算（与 DSR 的 selection_key 同源，A6）
    max_variants_per_param: { ma_period: 20 }
    holdout_access: { allowed: false }
seed: 42
```

生命周期状态机 `src/pql/lifecycle.py`：状态 `IDEA→SPECIFIED→RESEARCH→CANDIDATE→VALIDATED→PAPER→LIVE`，另有 `LIVE⇄SUSPENDED`、任意→`RETIRED`。合法迁移表硬编码；非法迁移抛 `LifecycleError`。每次迁移向 `strategy_registry.yaml` 的 `history` 追加 `{from, to, time, reason, evidence, approver}`，并向 `reports/audit.log`（JSONL，gitignore）追加同内容。**`RESEARCH→CANDIDATE` 迁移执行 Candidate Freeze**：锁定 spec hash、code commit、param set、validation config（`gate_version`）+ **版本化配置哈希**（`cost_config_sha256`、`market_rule_sha256`、`instrument_sha256`、`uv_lock_sha256`），写入 registry 的 `candidate_freeze`；此后变更任一冻结项必须新建策略版本（`_v2`）。**versioned config 文件一旦被任一实验引用，禁止原地修改**（防止 version id 不变而内容被改）。`strategy_registry.yaml` 结构：

```yaml
strategies:
    - id: etf_trend_v1
      state: RESEARCH
      created: "2026-08-08T10:00:00"
      history:
          [
              {
                  from: IDEA,
                  to: SPECIFIED,
                  time: "...",
                  reason: "...",
                  evidence: "strategies/etf_trend_v1.yaml",
                  approver: zhangjl,
              },
          ]
```

### D7 实验 Schema 与注册（提案 §10）

**冻结数据模型：`Strategy → Experiment → Run`**（二级，Experiment 不再是单次运行的别名）。`experiments/EXP-NNNN/`（NNNN = 现有最大编号+1，4 位补零）结构：

```
experiments/EXP-NNNN/
    manifest.yaml            # 研究问题、experiment config、decision
    runs/
        RUN-00001/
            run.yaml         # run_kind、selection_key、parameters、dataset_version、timing、result
            equity.parquet
            orders.parquet
            metrics.json
        RUN-00002/ ...
```

- **Experiment** 保存：研究问题、experiment config、decision（PENDING|ACCEPTED|REJECTED + reason）。
- **Run** 保存：具体参数、数据版本、结果、`run_kind`、`selection_key`（D7 下一条）。所有运行都写入 Run/Trial Ledger。CLI 一致化：`pql experiment create`（建 EXP）→ `pql experiment run --exp EXP-NNNN --params ...`（加 Run）→ `pql experiment decide --exp EXP-NNNN ...`（M4）。首次 `pql experiment run --strategy X` 自动建首个 EXP，后续必须显式 `--exp`——**禁止一次 run 就隐式建一个新 EXP**。
- `manifest.yaml`：experiment_id、strategy、parameters、dataset_version、market_rule_version、cost_model_version、**gate_version**（D9）、code_commit（`git rev-parse HEAD`）、code_dirty（bool）、**git_diff.patch + git_diff_sha256**（code_dirty=true 时必须保存完整 diff，否则拒绝写 manifest）、config_sha256（spec+gates 文件内容哈希）、seed、依赖版本（vectorbt/pandas/numpy）、timing（D2 全字段）、result（D8 指标全集）、decision、reason、created。
- **RunKind 与 selection_key**：每个 Run 必须有 `run_kind`（`SELECT` / `EVALUATE` / `STRESS` / `DIAGNOSTIC` / `FINAL_HOLDOUT`）与 `selection_key`（参与选择的参数组合去重键，如 `{momentum_days:120, ma_filter:200, top_k:2}`）。**Run/Trial Ledger**：所有运行都写入 ledger（含 run 元数据、`visible_to_researcher`），但 **`effective_trial_count = COUNT(DISTINCT selection_key across strategy lineage)`**——只有 `run_kind=SELECT` 且参与策略/参数选择的独立候选配置计入。bootstrap 每次、cost/execution stress 每变体、kill 每变体、walk-forward 每段、regime 每片、final holdout **都不直接加 N**（它们是对已选定配置的统计估计/诊断，不是从候选里挑选赢家）。walk-forward 的 N = 各 test 段评估过的 DISTINCT 配置并集（5 fold × 配置{60,120,180} → N=3，不是 15）。strategy lineage = 该策略的全部版本（含 `_vN`），N 取并集，防止 v2 重试同参数系统性低估。该计数与 Research Budget 计数器（A6）共用同一口径，DSR 的试验数 N 用它，而非 EXP 目录数（见 M6）。
- **dirty 代码规则**：RESEARCH 阶段允许 dirty，但 manifest 必须存 `git_diff.patch`；`CANDIDATE`/`VALIDATED` 强制 `code_dirty == false`，否则 Promotion Gate 拒绝（M7）。
- 失败实验不得删除；`decision`/`reason` 由 `pql experiment decide --exp EXP-NNNN --decision REJECTED --reason ...` 填写。
- `experiment_registry.parquet` 是派生索引：`pql registry rebuild` 扫描 `experiments/*/manifest.yaml` 重新生成（pandas → pyarrow 写 parquet）。manifest 是唯一事实来源。

### D8 指标定义（`src/pql/backtest/metrics.py`，全部基于日频）

年化因子 252。`cagr = (end/start)^(252/n_days) - 1`；`sharpe = mean(daily_ret)/std(daily_ret, ddof=1)*sqrt(252)`（rf=0）；`max_drawdown`（负值）；`calmar = cagr/|max_drawdown|`；`turnover` = 单边成交额/组合净值 的日均；`exposure` = 持仓市值/净值 日均；`n_trades`；`win_rate`。所有实验的 `result` 字段必须是这组指标的完整 dict。

### D9 验证门槛默认值（`config/validation_gates.yaml`）

```yaml
version: gates-2026-v1
candidate: # RESEARCH -> CANDIDATE（全部不需要 holdout 的证伪项，禁读 holdout）
    min_is_sharpe: 0.5
    max_drawdown_floor: -0.35
    walkforward_min_segment_sharpe_frac: 0.5 # ≥50% 的 test 段 sharpe>0
    param_stability_min_frac: 0.5 # 网格中 sharpe ≥ 0.5*best 的点占比
    time_windows_min_pos_cagr_frac: 0.5
    cost_2x_min_sharpe: 0.0
    exec_stress_max_drawdown_floor: -0.45 # T+2 与 open 价变体
    bootstrap_sharpe_p05_min: -0.3
    deflated_sharpe_min: 0.95
    max_kill_families_killed: 2 # 按 Kill Test Family 判定（M6）
    require_code_clean: true # CANDIDATE/VALIDATED 必须 code_dirty==false
final: # `pql validate final`（Candidate Freeze 后最后一道验证，只消费 holdout）
    holdout_min_sharpe: 0.0
validated: # CANDIDATE -> VALIDATED = candidate 全 PASS 且 final(holdout) 通过；无额外统计门槛
paper: # VALIDATED -> PAPER 准入门槛见 D12
    min_trading_days: 40
    min_rebalance_cycles: 3
    min_sim_orders: 10
    max_unreconciled: 0
    max_silent_failures: 0
```

所有阈值只存在于该文件；代码只读不硬编码。**这些是 Promotion Policy，不是统计学真理，PASS Gate ≠ 策略已被证明有效**（D7 每个实验记录 `gate_version`；策略进入 RESEARCH 时 gate_version 冻结，改门槛须新建 policy version）。**流程顺序**：`development validation（candidate 门槛全部证伪）→ candidate 全 PASS → Candidate Freeze → validate final（只跑 holdout）→ VALIDATED`——stress/bootstrap/DSR/kill 全在 Freeze 前完成，holdout 是真正最后一道验证。

### D10 回测引擎接口（提案 §15）

`src/pql/backtest/api.py`，唯一公开入口（策略层禁止直接 import vectorbt）：

```python
def run_backtest(
    intent: TradingIntent,          # SignalIntent | TargetWeightIntent
    universe: list[str],
    execution_model: TimingContract,
    cost_model: CostModel,          # 从 costs yaml 加载的 dataclass
    portfolio_config: PortfolioConfig,  # init_cash=1_000_000、max_positions、权重方式 equal
    dataset: DatasetView,           # 见 M2
) -> BacktestResult                 # equity/orders/metrics + run_meta（含 vectorbt 版本、参数哈希）
```

`TradingIntent = SignalIntent | TargetWeightIntent`，按类型路由到不同 vectorbt 调用：

- **SignalIntent**（entries/exits bool 序列，用于 Trend / Buy&Hold）→ `vbt.Portfolio.from_signals`：信号先 `fshift(execution_model.execution_bar)`，`price` 取 close 或 open 序列，`fees=cost_model.fee_rate`、`slippage=cost_model.slippage`、`init_cash`、`freq="D"`，`direction="longonly"`。
- **TargetWeightIntent**（目标权重序列，用于 Rotation / Allocation）→ `vbt.Portfolio.from_orders`，**必须固定**：`size_type='targetpercent'`、`cash_sharing=True`、`call_seq='auto'`（先卖后买，否则现金不足）、`val_price=<执行 bar 前收 close.fshift(1)>`、`group_by=True`、信号同样 `fshift(execution_bar)`。**val_price 语义钉死 = Execution Revaluation（方案 B）**：目标权重在 T 决定，成交前按执行 bar 前收重算股数（`execution_bar=1` 时 val_price=T 收盘；`execution_bar=2` 时 val_price=T+1 收盘）。这与 Decision Locked（A：固定用 T 收盘估值，成交延迟不重算数量）不同，报告必须注明所用模式，避免 execution-delay stress 同时改了成交日和数量估值而解释不干净。

成本不含最低佣金（D3）；框架把 `fees`/`slippage` 真实传入 vectorbt，使净值直接反映成本。此接口面向 `SignalIntent | TargetWeightIntent` 双态，后续风险平价 / 多资产配置 / 多策略组合无需重写契约。

## Approach

里程碑按顺序执行（M1→M7），每个里程碑结束 tree 可构建、测试全绿、git 提交一次（实验记录需要 code_commit，提交是本项目的功能需求）。

### M1 项目骨架 + 研究契约（提案 Week 1）

1. 写 `.gitignore`（`data/raw/ data/snapshots/ data/processed/ data/paper/ reports/ __pycache__/ *.pyc .venv/ experiment_registry.parquet`；注意 `!data/metadata/` 保留跟踪）、`pyproject.toml`（D1）、更新 `README.md`（安装/命令/目录说明）。
2. 建 D1 全部目录与 `src/pql/__init__.py` 等空包骨架；`uv sync --all-extras` 必须成功（验证依赖可解析）。
3. 实现 `src/pql/schemas.py`：`StrategySpec`、`CostModel`、`PortfolioConfig`、`BacktestResult` dataclass + `load_spec/dump_spec/load_cost_model`；字段与 D6/D3 完全一致。未知 YAML 键 = 报错（防止 spec 漂移）。
4. 实现 `src/pql/lifecycle.py`：状态枚举、合法迁移表、`transition(registry_path, strategy_id, to, reason, evidence, approver)` 写 registry + audit log（D6）。
5. 写 `config/markets/cn_etf_2026.yaml`、四个 `config/instruments/*.yaml`（D4，`listed_date` 此刻填提案已知值，M2 用真实数据核实并修正）、`config/costs/cn_etf_2026.yaml`（D3）、`config/validation_gates.yaml`（D9）。
6. 初始化 `strategy_registry.yaml`（空 strategies 列表）。
7. 测试 `tests/test_schemas.py`（YAML 往返、未知键报错）、`tests/test_lifecycle.py`（合法/非法迁移、history 追加内容断言）。

**M1 验证**：`uv run pytest tests/test_schemas.py tests/test_lifecycle.py -q` 全绿；`uv run pql --help` 打印子命令列表（CLI 骨架可先只注册 `--help` 占位）。

### M2 数据 Snapshot 系统（提案 Week 2）

依赖 M1。数据源以 akshare 为主（无 token）；tushare 为可选适配器（token 走环境变量 `TUSHARE_TOKEN`，代码与文档一律用占位符 `<YOUR_TUSHARE_TOKEN>`，严禁落盘真实值）。

1. `src/pql/data/adapters.py`：两个 Provider 抽象——`fetch_raw_bars(symbol, start, end) -> DataFrame`（open/high/low/close/volume/amount，raw 价）与 `fetch_research_prices(symbol, start, end)`（前复权研究序列）。**Provider 内部实现可不同**：Tushare 用 `pro.fund_daily` + `pro.fund_adj` 因子合成；akshare 用 `adjust="" / "qfq"` 直接返回 raw / qfq 行情。akshare 接口名实现时用 `python -c "import akshare as ak; print([x for x in dir(ak) if 'etf' in x.lower()])"` 现场确认（`unverified — confirm first`），不强制所有 provider 实现统一 Adjust Factor API。**单位归一化契约**（Canonical Schema）：`price: CNY/share, volume: shares, amount: CNY`——provider 内部完成转换（如 Tushare `vol=手`→×100、`amount=千元`→×1000），manifest 记 `source_units / normalized_units / conversion`。异常统一抛 `DataAdapterError`。
2. `src/pql/data/calendar.py`：`CalendarAdapter` 多源（ExchangeCalendar 优先 / TushareTradeCalendar / AkShareCalendar），运行时确认可用且最新；快照构建要求 **`calendar_end >= snapshot_end`**，否则拒绝构建（除非 `--allow-calendar-gap` 且记录 warning）。存 `calendar.parquet`。
3. `src/pql/data/snapshot.py`：`pql data snapshot --source akshare --symbols 510300,510500,518880,511010 --start 2013-01-01 [--name market-YYYYMMDD-vN]`：下载→落 `data/raw/`→质量检查→写 `data/snapshots/<version>/`（prices/calendar/manifest.json，D5）→去写权限。同名版本已存在→exit 1。
4. `src/pql/data/quality.py` 质量检查（全部在快照前运行，失败即中止并输出具体行）：日期单调且属于交易日历；OHLC 关系 `low≤open/close≤high`；price>0；volume≥0；重复行；单标的缺失交易日比例 >5% 告警、>20% 中止；前复权价与 raw 价比值跳变 >15%（除权除息日外）标记告警。
5. `src/pql/data/dataset.py`：`DatasetView`（`load(version, universe, start, end)`），加载时**默认重新校验快照 checksum**（不一致抛 `SnapshotIntegrityError`，D5），提供 `.research_frame()`（IS 区间、close_adj 用于信号）、`.execution_frame()`（raw close/open 用于成交）、`HoldoutGuard.holdout_slice()`（D5 冻结前置 + 一次性消费审计）。`DatasetView` 是 D10 `run_backtest` 的唯一数据入口。
6. 测试（离线）：`tests/fixtures/make_fixture.py` 生成确定性合成 OHLC（固定 seed 的正则价格+噪声，10 个标的日×4 symbol 风格），`tests/test_quality.py`（每类脏数据构造一条反例断言被拦截）、`tests/test_snapshot.py`（用 monkeypatch 替换 adapter 为 fixture，断言 manifest/checksum/只读/重名拒绝）。

**M2 验证**：离线 `uv run pytest tests/test_quality.py tests/test_snapshot.py -q` 全绿；联网手工跑一次真实快照：`uv run pql data snapshot --source akshare --symbols 510300,510500,518880,511010 --start 2013-01-01`，确认生成 `data/snapshots/market-<今日>-v1/` 且 `manifest.json` 含四个 sha256；随后把真实 holdout 日期按 D5 规则回填到后续策略 spec（M4/M5 创建 spec 时使用）。若网络不可用：用 `--from-fixture` 开关（snapshot.py 支持从 tests fixture 构建快照，manifest 标 `source: synthetic`）继续后续里程碑，并在 README 注明真实适配器未联网验证。

### M3 时序契约 + 基础回测 + Control 策略（提案 Week 3–4）

依赖 M2。

1. `src/pql/timing.py`：D2 的 `TimingContract` + `assert_no_lookahead(contract)`（`execution_bar<1` 抛 `TimingError`）。
2. `src/pql/backtest/costs.py`：`load_cost_model(path)`、`apply_stress(model, multiplier)`（D3）。
3. `src/pql/backtest/engine.py` + `api.py`：D10。按 `TradingIntent` 类型路由——SignalIntent→`from_signals`；TargetWeightIntent→`from_orders(targetpercent, cash_sharing=True, call_seq='auto', val_price=前收, group_by=True)`。信号 shift、价格序列选择、`direction="longonly"`、`BacktestResult` 组装。边界：信号全 False→空仓净值恒 1（不得抛错）；universe 中某标的当日无数据→该标的当日不可成交并在 orders meta 记录 `skipped_no_price`。
4. `src/pql/backtest/metrics.py`：D8 全部指标 + `metrics_vs_benchmark(result, benchmark_equity)`（超额收益、跟踪误差）。
5. Control 策略 `strategies/buy_hold_control.yaml`（kind=`buy_hold`，universe=[510300]，权重 100%，无再平衡）+ `src/pql/signals/buy_hold.py`。它是系统自检，不是 Alpha。
6. 黄金测试 `tests/test_buy_hold_golden.py`：合成 10 日价格 `[100,101,102,...]`、显式 `ZeroCostFixture(fee_rate=0)` 与 `fee_rate=0.001` 两种，手算期望净值与 metrics，断言 `np.allclose`。`ZeroCostFixture` 仅在引擎单元测试使用，不触发 D3 成本政策。该测试是回测引擎正确性的基准。
7. `tests/test_timing.py`：构造"只用 T 收盘信息"的信号，断言 `execution_bar=1` 时首笔成交发生在 T+1；`execution_bar=0` 被 `assert_no_lookahead` 拒绝。

**M3 验证**：`uv run pytest -q` 全绿（含 golden）；用真实快照跑 `uv run pql experiment run --strategy buy_hold_control`（此命令在 M4 实现，本步可先用临时脚本调 `run_backtest`），输出 CAGR/Sharpe/MaxDD 与 benchmark 对比表。

### M4 Experiment Registry + ETF Trend 策略（提案 Week 5–6）

依赖 M3。

1. `src/pql/registry/experiments.py`：`next_experiment_id()`（扫描 `experiments/`）、`write_manifest(...)`（D7 全字段，code_commit 用 `git rev-parse HEAD`，dirty 用 `git status --porcelain` 非空；**code_dirty=true 时用 `git diff` 存 `git_diff.patch` 并记录 `git_diff_sha256`**，否则拒绝写 manifest）、`load_manifest(exp_id)`。
2. `src/pql/registry/budget.py`：`check_budget(spec, ledger)`——统计该 strategy lineage 已有 **SELECT run 数（effective_trial_count）** 与每个参数键已出现的不同取值数；超过 `max_total_selection_runs` 或 `max_variants_per_param` → exit 2 + 提示"建立新的 Hypothesis Version"（提案 §11）。计数与 DSR 的 selection_key 同源（A6）。
3. `src/pql/cli.py` 的 `experiment` 组（D7 一致化）：
    - `pql experiment create --strategy <name> [--params k=v ...]`：建 `experiments/EXP-NNNN/manifest.yaml`（研究问题+config+decision，不跑回测）。
    - `pql experiment run --exp EXP-NNNN [--params k=v ...]`：预算检查→加载 spec+dataset（版本必须与 spec 一致，否则 exit 1）→生成信号→`run_backtest`→写 `runs/RUN-XXXX/`（含 run_kind/selection_key）→打印指标。`--params` 覆盖 spec 默认参数但必须落在 `param_grid` 内，否则 exit 1；**首次 `--strategy X` 自动建首个 EXP，后续必须显式 `--exp`，禁止一次 run 隐式建新 EXP**。
    - `pql experiment decide --exp EXP-NNNN --decision ACCEPTED|REJECTED --reason ...`
    - `pql registry rebuild` / `pql registry list [--strategy X]`
4. 确定性校验器 `src/pql/validation/deterministic.py` + `pql validate run --exp EXP-NNNN`，输出 `reports/validation/<exp>/deterministic.json`，逐项 PASS/FAIL（提案 §20.3）：
    - `no_same_bar_fill`：manifest.timing.execution_bar≥1；
    - `no_future_data`：抽 5 个信号日，把数据截断到该日重算信号，与全量数据信号逐位相等（point-in-time 截断测试）；
    - `dataset_pinned`：dataset_version 存在且快照 sha256 与 manifest 一致；
    - `cost_nonzero`：fee_rate>0；
    - `valid_trading_dates`：所有成交日 ∈ 交易日历；
    - `holdout_compliance`：`holdout_access.log` 中该策略访问次数符合 spec 授权；
    - `reproducible`：重跑一次，对 equity/orders 做**语义比较**（`pandas.testing.assert_frame_equal(rtol=1e-12, atol=1e-12)`，先 sort index/columns、normalize dtype），通过则记 `semantic_result_hash`（值序列规范化后的 sha256）；不用原始 parquet 字节 hash（浮点/serialization 会造成无研究意义的位差异）。
5. ETF Trend 策略：`strategies/etf_trend_v1.yaml`（D6 模板；windows 用 M2 真实快照日期）+ `src/pql/signals/trend_ma.py`：`close_adj > MA(ma_period)`→risk on 持有本标的，否则 risk off 持现金；逐标的独立信号，`max_positions=2` 时按动量强度排序截取（排序只用 ≤T 数据）。执行 `SPECIFIED→RESEARCH` 迁移（`pql gate promote` 的简化前置：M4 先用 `lifecycle.transition` 直调，M7 收口到 gate CLI）。
6. 测试：`tests/test_budget.py`（超限拦截）、`tests/test_registry.py`（manifest 字段完整性、编号递增）、`tests/test_deterministic_validator.py`（用故意 `execution_bar=0` 与 fee=0 的 fixture 断言 FAIL）。

**M4 验证**：`uv run pytest -q` 全绿；真实跑 3 个实验：`pql experiment run --strategy etf_trend_v1 --params ma_period=200` 等三个网格值，`pql registry list --strategy etf_trend_v1` 显示 3 行；`pql validate run` 对其中一个全部 PASS；`pql experiment decide` 把一个标记 REJECTED 后 manifest 落盘。

### M5 ETF Momentum 策略 + Robustness 验证（提案 Week 7–8）

依赖 M4。

1. ETF Momentum Rotation：`strategies/etf_momentum_v1.yaml` + `src/pql/signals/momentum_rotation.py`：相对动量 = `close_adj.pct_change(momentum_days)`，绝对动量过滤 = 动量>0（可加 MA 趋势过滤 `ma_filter`），月度再平衡（`rebalance: monthly` = 每月第一个交易日），Top-K 等权（K=`risk.max_positions`，默认 2）；再平衡日外信号保持不变。参数：`momentum_days`（网格 [60,120,180]）、`ma_filter`（[0(关闭),200]）、`top_k`（[1,2,3]）——全部写入 spec `param_grid` 冻结。
2. `src/pql/validation/walkforward.py`：滚动 walk-forward，train=756 交易日、test=252、step=252；每段在 train 上按 Sharpe 选参（网格来自 spec），test 段应用；拼接 test 段得 OOS 合并净值。数据不足 train+test → 报告中记 `skipped: insufficient_data`（不算失败）。
3. `src/pql/validation/robustness.py`：
    - 参数稳健：遍历 `param_grid` 全网格（IS 区间），输出指标表；`param_stability = mean(sharpe ≥ 0.5*best_sharpe)`；
    - 时间稳健：IS 按自然年切片，逐年 cagr/sharpe/maxdd/turnover/exposure。
4. `src/pql/validation/regimes.py`（规则定义，禁止事后划分）：Trend = benchmark(510300) `close_adj` 相对其 200 日均线的上/下；Volatility = 20 日年化已实现波动率 > **expanding 中位数（median(vol[≤T-1])）** → HIGH；Liquidity = 20 日均 amount > **expanding 中位数（median(amount[≤T-1])）** → HIGH（阈值只用 ≤T-1 数据，避免全样本中位数把未来数据泄入历史 regime 标签）。按出现的 regime 组合分别输出 metrics。Rate regime 不在 v0.1（见 Assumptions A5）。
5. `src/pql/validation/pipeline.py`：`pql validate candidate --strategy <name>` = **development validation**：跑 IS 基线 + walkforward + 参数/时间稳健 + regime + cost stress + exec stress + bootstrap + DSR + kill（M6 实现），**绝对禁止读取 Final Holdout**（源码层：HoldoutGuard 在未 frozen 时拒绝，且 candidate 阶段不调用任何 holdout 数据）。汇总 `reports/validation/<strategy>/candidate_report.json`，每项对照 `config/validation_gates.yaml` 的 `candidate` 节给 PASS/FAIL，末尾总判定。**Final Holdout 由 M6 的 `pql validate final` 在 Freeze 后单独消费**（D9 `final` 节）。
6. 测试：`tests/test_walkforward.py`（合成数据断言段边界无重叠、test 段参数只来自 train 选择）、`tests/test_regimes.py`（构造已知 regime 序列断言划分）、`tests/test_pipeline.py`（fixture 策略全链路跑通，门槛 PASS/FAIL 路径各一）。

**M5 验证**：`uv run pytest -q` 全绿；真实跑 `pql validate candidate --strategy etf_momentum_v1`（先用 M2 快照）与 `--strategy etf_trend_v1`，确认 candidate_report.json 生成且 `holdout_access.log` **无新增**（candidate 阶段禁读 holdout）。

### M6 压力测试 + 统计验证 + Kill Tests + AI 评审（提案 Week 9–10）

依赖 M5（pipeline 编排器）。

1. `src/pql/validation/stress.py`：
    - 成本压力：multiplier [1,2,3]（`apply_stress`，D3）；
    - 执行压力变体（固定枚举，全部跑）：`{execution_bar:2}`、`{execution_price:open}`、`{slippage:+0.002}`、`{miss_rate:0.05, seed:7}`、`{execution_bar:1, execution_price:open}`。**miss 实现是路径无关的**：用固定 seed 生成确定性 `reject_mask`（5% 订单被拒），作为执行参数**让引擎整体重跑**（走 `run_backtest`），而不是在完整回测后删订单再重建净值——事后删单会让被删 SELL 导致后续 BUY 现金不足、后续 SELL 不存在，结果失真。每次变体均写入 Trial Ledger（`run_kind=STRESS`，不计入 `effective_trial_count`）。
2. `src/pql/validation/bootstrap.py`：对策略日收益做 circular block bootstrap，`block_len = ceil(n^(1/3))`，R=1000，seed=spec.seed；输出 Sharpe/CAGR/MaxDD 的分布与 95% CI。
3. `src/pql/validation/overfitting.py`：Deflated Sharpe Ratio（Bailey–López de Prado），试验数 **N = effective_trial_count = COUNT(DISTINCT selection_key across lineage)，仅 `run_kind=SELECT` 的独立候选配置计入**（D7；bootstrap/stress/kill/fold 不直接加 N），偏度/峰度用策略日收益估计；输出 DSR 概率值。
4. `src/pql/validation/kill.py`：**Kill Test Family**（提案 §16.9），每个 Family 输出 `family_result`（KILLED/PASSED；KILLED 定义：变体 `cagr≤0 且 sharpe≤0`）与 `killed_fraction`（family 内多个子变体时计被 KILLED 占比），gate 按 `max_kill_families_killed` 判定 **Family 数**而非子变体数：
    - `K01 drop_best_year`（去掉年收益最高的自然年）
    - `K02 drop_best_trades`（去掉盈利最大的 min(10, 10%) 笔交易）：**明确两种模式分开记录**——`ATTRIBUTION_TEST`（从历史收益扣除其贡献，诊断）与 `COUNTERFACTUAL_TEST`（屏蔽这些 entry 后完整重跑），报告不得混用
    - `K03 universe_loo`（逐个剔除标的，输出 killed_fraction）
    - `K04 delay_execution`（execution_bar+1）
    - `K05 cost_x2`
    - `K06 shift_rebalance`（再平衡日后移 1 交易日）
    - `K07 perturb_params`（数值参数 ±10% 各一次，输出 killed_fraction）
    - `K08 shift_start`（起始日后移 60 交易日）
5. `pql validate final --strategy <name>` + 接入 `pipeline.py`：**Candidate Freeze 之后**（spec hash / code commit / param set / gate_version / config 哈希已锁定，D6）执行 final validation：**只跑 Final Holdout**（经 HoldoutGuard，fail-closed 一次性消费；消费后 `holdout_status.consumed=true` 不可逆，二次调用被 `HoldoutError` 拒绝），gates 按 D9 `final` 节判定。stress / bootstrap / DSR / kill 已在 candidate 阶段完成（D9 `candidate` 节），**不在此重复**。`pql validate candidate` 输出 development validation（不读 holdout）。
6. AI 评审（提案 §20）：
    - `ai/researcher_prompt.md`、`ai/reviewer_prompt.md`（检查实现错误/统计错误/泄漏/成交模型/研究设计）、`ai/challenger_prompt.md`（唯一目标=找理由拒绝；只接收 spec、manifest、代码、dataset metadata、回测与验证结果）；
    - `src/pql/review/bundle.py` + `pql review bundle --exp EXP-NNNN --role reviewer|challenger` → `reports/review_bundles/<exp>_<role>.md`，内容 = 上述允许文件拼接 + 数据 metadata + gates 结果。**Challenger 可以看到 `StrategySpec.hypothesis`（否则无法挑战经济逻辑），但禁止看到**：`researcher_prompt`、`research/` 探索过程、Researcher reasoning、先前 Reviewer 结论——bundle 生成时强制过滤。测试断言 challenger 包**不含 `research/` 内容与 `researcher_prompt`**，而非不含 hypothesis。
7. 测试：`tests/test_stress.py`（miss 用固定 seed 断言 reject_mask 确定、且走完整重跑而非删单后重建）、`tests/test_bootstrap.py`（固定 seed 断言 CI 可复现）、`tests/test_kill.py`（drop_best_year 用构造数据断言去掉的确实是最高年；drop_best_trades 两种模式结果分别记录）、`tests/test_bundle.py`（challenger 包含 hypothesis 但不含 research//researcher_prompt）、`tests/test_final_validation.py`（未 freeze 被拒、fail-closed 顺序、消费 holdout 一次、二次调用被拒、变更冻结项需新版本）、`tests/test_ledger.py`（**effective_trial_count = DISTINCT selection_key**：5 个 SELECT 配置 + 1000 bootstrap + 若干 stress/kill/fold → N=5；v2 重试同参数不重复计数）。

**M6 验证**：`uv run pytest -q` 全绿；`pql validate candidate --strategy etf_momentum_v1` candidate_report.json 含 stress/bootstrap/DSR/kill 章节且 `holdout_access.log` 无新增；Promote→CANDIDATE（Freeze）→ `pql validate final` 仅输出 holdout 章节，`holdout_access.log` 恰新增 1 行且二次运行被 `HoldoutError` 拒绝；`pql review bundle --exp <任一实验> --role challenger` 生成 md 含 hypothesis 但不含 `research/`/`researcher_prompt`。

### M7 Risk + Paper Trading + Promotion Gate（提案 Week 11–12）

依赖 M4（registry/lifecycle），建议在 M6 后执行。

1. `src/pql/risk/rules.py`：订单级检查，全部实现（提案 §17）：`max_position_weight`(0.6)、`max_portfolio_exposure`(1.0)、`max_turnover_per_rebalance`(2.0)、`max_order_value`(100000 CNY)、`cash_check`、`stale_price_check`（**行情日期 < latest_expected_completed_bar → 拒单**；`latest_expected_completed_bar` 是最近一根已完成日线的交易日，≠ 今日——交易日上午昨日才完成日线，按今日判 stale 会误拒）、`duplicate_order_check`（同日同标的同向）、`invalid_symbol_check`（∈ instruments 配置）、`tradability_check`（执行日 ≥ listed_date）。阈值放 `config/validation_gates.yaml` 新增 `risk:` 节。Kill switch：仓库根存在 `KILL_SWITCH` 文件 → 订单生成直接 exit 3。`latest_expected_completed_bar` 语义纳入 TimingContract（D2）。
2. `src/pql/portfolio/target.py`：策略信号 → 目标权重（等权、max_positions、现金剩余）→ `TargetPortfolio{date, weights: {symbol: w}}`。
3. `src/pql/execution/orders.py`：当前持仓 + 目标权重 → 订单列表（BUY/SELL/HOLD，数量按 lot_size=100 取整、含目标/现持仓/调整量/依据/风险提示，提案 §19 输出格式）→ 过 risk rules。
4. `src/pql/execution/paper.py`：`PaperAccount`（状态 parquet 于 `data/paper/<strategy>/positions.parquet`、`cash.parquet`、日志 JSONL）；`pql paper replay --strategy X --start YYYY-MM-DD --end YYYY-MM-DD`：逐交易日循环（信号只用 ≤T 数据、T+1 按 execution_price 成交、计成本、更新持仓、写日志）；异常（缺价、风控拒单）写 `failures.jsonl` 且计入 silent_failure 当且仅当未被日志捕获。
5. `src/pql/execution/reconcile.py`：每日对账 = 用订单流水独立重算持仓/现金，与 PaperAccount 状态比对；差异 → `unreconciled` 计数。`pql paper report --strategy X`：输出 trading_days、rebalance_cycles、sim_orders、unreconciled、silent_failures、净值 vs benchmark 图（matplotlib 存 reports/），并对照 D9 `paper` 门槛给准入判定。
6. Promotion Gate：`pql gate promote --strategy X --to <STATE> --approver <name> --reason "..."`：前置条件硬检查——SPECIFIED 要求 spec 六要素（执行时点/成本模型/验证方案/参数范围/预算/假设）齐全；RESEARCH→CANDIDATE 要求 **development validation（candidate_report）全 PASS 且 code_dirty==false**，并执行 Candidate Freeze（D6）；CANDIDATE→VALIDATED 要求 **final_report 全 PASS（含 holdout 已消费）+ code_dirty==false**；PAPER 要求 paper report 五项门槛达标；LIVE 要求 `--approver` 为人类（CLI 强制非空且不得为 `ai`/`agent` 字样）。全部经 `lifecycle.transition` 落 registry + audit log。AI 无实盘批准权（提案 §6.7）在 LIVE 检查中代码级强制。
7. 端到端编排 `pql gate demo`（可选但必须有）：用 etf_trend_v1 自动走 SPECIFIED→…→PAPER 全链路并打印每步证据路径。
8. 测试：`tests/test_risk_rules.py`（每条规则一个反例断言拒单）、`tests/test_paper.py`（合成数据 replay 断言对账 0 差异、T+1 成交）、`tests/test_gate.py`（每个 STATE 前置失败路径各一 + LIVE 拒绝 approver=ai）。

**M7 验证**：`uv run pytest -q` 全绿；真实数据 `pql paper replay --strategy etf_trend_v1 --start <IS末尾前60交易日> --end <IS末尾>`（IS 内回放避免消耗 holdout），`pql paper report` 输出五指标；`pql gate promote --strategy etf_trend_v1 --to CANDIDATE ...` 等逐步迁移，`strategy_registry.yaml` history 完整可追溯。

## Critical files & anchors

1. `src/pql/backtest/api.py` — `run_backtest` 契约：时序/成本/数据视图在此交汇，是全系统承重墙。
2. `src/pql/schemas.py` — StrategySpec/CostModel 的字段定义，所有 YAML、registry、gate 依赖它。
3. `src/pql/data/snapshot.py` — 快照不可变性、checksum、只读语义的实现处。
4. `src/pql/validation/pipeline.py` — 验证编排与门槛判定，VALIDATED 状态的唯一入口。
5. `config/validation_gates.yaml` — 所有研究门槛阈值，调整研究严格度只改这里。

## Verification

全局命令（工作目录 = 仓库根）：

```
uv sync --all-extras --group dev
uv run pytest -q                 # 全部离线测试必须绿
uv run ruff check src tests      # 风格门禁
```

新行为端到端证据链（按顺序执行）：

1. `uv run pql data snapshot --source akshare --symbols 510300,510500,518880,511010 --start 2013-01-01` → 生成 `data/snapshots/market-*-v1/`，`manifest.json` 含 sha256；重跑同名 → exit 1。
2. `uv run pql experiment run --strategy buy_hold_control` → 指标表；`tests/test_buy_hold_golden.py` 已用手算值锁定引擎正确性。
3. `uv run pql experiment run --strategy etf_trend_v1 --params ma_period=200` → `experiments/EXP-0001/manifest.yaml` 含 code_commit；`pql validate run --exp EXP-0001` 七项全 PASS（含重跑语义一致，`semantic_result_hash` 匹配）。
4. 预算：连续 run 至超过 `max_variants_per_param` → exit 2。
5. `uv run pql validate candidate --strategy etf_momentum_v1` → candidate_report.json（development validation，含 stress/bootstrap/DSR/kill，无 holdout 章节）；随后 `uv run pql gate promote --strategy etf_momentum_v1 --to CANDIDATE ...`（Freeze）→ `uv run pql validate final --strategy etf_momentum_v1` → final_report.json 仅 holdout 章节，`data/metadata/holdout_access.log` 恰新增 1 行；重复 `validate final` → 被 `HoldoutError` 拒绝。
6. `uv run pql review bundle --exp EXP-0002 --role challenger` → md 包生成，含 hypothesis 但不含 `research/`/`researcher_prompt`。
7. `uv run pql paper replay --strategy etf_trend_v1 ... && uv run pql paper report --strategy etf_trend_v1` → 五项 paper 门槛指标输出。
8. `uv run pql gate promote --strategy etf_trend_v1 --to CANDIDATE --approver zhangjl --reason ...` → registry history 追加；`--to LIVE --approver ai` → 被拒。

验收映射（提案 §25 的 16 条）：1→M2 快照；2→M2 quality；3→D2/M3 test_timing；4→M3 golden；5→M4 trend + M5 momentum；6→M4 registry（含 REJECTED）；7→M4 reproducible 检查；8→M5 param_stability；9→M5 time windows；10→M6 cost stress；11→M6 kill；12→M6 reviewer bundle；13→M6 challenger bundle + kill 实验设计在 prompt 内；14→M7 paper replay；15→M7 reconcile；16→registry history + audit.log + holdout_access.log。

## Assumptions & contingencies

- **A1 范围**：本计划覆盖完整 v0.1（用户已确认全量按里程碑执行）。
- **A2 Git 提交**：每里程碑结束提交一次；实验 manifest 需要 `code_commit`，这是功能需求而非流程偏好。
- **A3 数据源**：akshare 免 token 为主源；tushare 可选，token 仅以 `<YOUR_TUSHARE_TOKEN>` 占位符出现。若执行时网络不可用：M2 起用 `--from-fixture` 合成快照继续全流程，真实适配器标记未验证（README 记录），联网后补跑真实快照并重建实验。
- **A4 vectorbt**：按 1.1.0 规划（API 已核实 from_signals + from_orders(targetpercent/cash_sharing/call_seq/val_price) 语义，见 D10）。1.x 为近期大版本重写，`from_orders`/`from_signals` 签名在实现时以运行时确认为准。若安装或运行在 Windows 上失败：降级 `vectorbt==0.28.5` 并按其 PyPI metadata 放宽 numpy/pandas 下限，其余设计（shift 成交、fees/slippage 参数、intent 双路由）不变。
- **A5 Rate Regime 延期**：提案 §16.5 四类 regime 中 Rate 无冻结数据源，v0.1 只实现 Trend/Volatility/Liquidity；在 regime 报告中显式标注 `rate_regime: not_implemented_v0.1`。
- **A6 试验计数口径**：`effective_trial_count = COUNT(DISTINCT selection_key across strategy lineage)`，仅 `run_kind=SELECT` 的独立候选配置计入（bootstrap/stress/kill/fold 不直接加 N，D7）；Research Budget（`max_total_selection_runs`）、`max_variants_per_param` 与 DSR 的 N 共用同一口径。
- **A7 门槛阈值**：D9 全部数值是默认研究口径，用户可日后只改 `config/validation_gates.yaml` 调整，不需要改代码。
- **A8 最低佣金**：v0.1 成本模型不含 min_fee（方案 A，D3）；待执行引擎支持逐笔 `max(order_value*fee_rate, min_fee)` 时再引入。生产路径 `fee_rate>0` 强制，引擎单元测试用显式 `ZeroCostFixture`。
- **A9 评审修正已合并**：本计划已按外部评审（docs/review/1.md，经本会话两轮逐条核验）合并修正。第一轮：Holdout 改为一次性消费（D5/D6/M6）、回测 API 双意图（D10/M3）、成本真实进 Equity（D3）、miss 路径无关重跑（M6）、单位归一化（M2）、CalendarAdapter（M2）、regime expanding 中位数（M5）、verify-on-read（D5）、语义可复现（M4）、gate_version 冻结（D9）、Kill Test Family（M6）、stale-price（M7）、证券代码规范化（D4）。第二轮：**RunKind + selection_key + effective_trial_count=DISTINCT lineage（bootstrap/stress/kill/fold 不计入 N，D7/M6）**、**Experiment→Run 模型 + CLI 一致化（D7/M4）**、**非-Holdout 证伪全移到 candidate、final 只 holdout（D9/M5/M6）**、**预算改名 max_total_selection_runs 与 DSR 同源（D6/M4）**、**Holdout fail-closed（D5）**、**Challenger 可看 hypothesis 禁 researcher 推理（M6）**、**TargetWeight val_price=Execution Revaluation（D10）**、**Freeze 指纹加 config 哈希 + versioned config 禁改（D6）**。
