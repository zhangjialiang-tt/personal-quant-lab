# Review Bundle — EXP-0016 (reviewer)

strategy: `etf_momentum_v1`
experiment: `EXP-0016`

## StrategySpec

hypothesis: 在多资产 ETF universe 中，中期相对动量较强且绝对动量为正的资产，未来一段时间可能具有更好的风险调整收益；通过月度 Top-K 等权轮动控制换手。

```yaml
# D6 strategy spec: ETF Momentum Rotation v1 (M5.1)
# PLAN_CLARIFICATION M5-001: top_k is the research parameter (actual requested K);
# risk.max_positions is the hard risk ceiling. effective_k = min(top_k, max_positions),
# so the frozen grid [1,2,3] is behaviorally meaningful.
name: etf_momentum_v1
hypothesis: "在多资产 ETF universe 中，中期相对动量较强且绝对动量为正的资产，未来一段时间可能具有更好的风险调整收益；通过月度 Top-K 等权轮动控制换手。"
universe: ["510300.SH", "510500.SH", "518880.SH", "511010.SH"]
benchmark: "510300.SH"
signal:
    kind: momentum_rotation
    momentum_days: 120 # 默认值；研究参数须落在 param_grid
    ma_filter: 0 # 0=disable, 200=close_adj>MA200
    top_k: 2
rebalance: monthly
risk: { max_positions: 3 } # hard ceiling; effective_k = min(top_k, max_positions)
dataset_version: market-20260808-v1
market_rule_version: cn-etf-2026-v1
cost_model_version: cn-etf-cost-2026-v1
timing: { execution_bar: 1, execution_price: close }
windows:
    in_sample: ["2020-01-02", "2024-12-31"]
    holdout: ["2025-01-01", "2026-08-07"]
param_grid:
    momentum_days: [60, 120, 180]
    ma_filter: [0, 200]
    top_k: [1, 2, 3]
research_budget:
    max_total_selection_runs: 50 # >= 18-组合笛卡尔积
    max_variants_per_param: { momentum_days: 3, ma_filter: 2, top_k: 3 }
    holdout_access: { allowed: false }
seed: 42
```

## Experiment Manifest

```yaml
{
  "experiment_id": "EXP-0016",
  "strategy": "etf_momentum_v1",
  "research_question": "candidate development validation: etf_momentum_v1",
  "decision": "PENDING",
  "reason": ""
}
```

## Runs

```yaml
{
  "run_id": "RUN-00001",
  "run_kind": "SELECT",
  "selection_key": "ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2
  },
  "metrics": {
    "cagr": 0.34840715773102127,
    "annual_vol": 0.15163407274078453,
    "sharpe": 2.048133177238671,
    "max_drawdown": -0.12103675806719838,
    "calmar": 2.8785235435469048,
    "n_trades": 40,
    "turnover": 0.015804077231609905,
    "exposure": 0.8997500416270083,
    "win_rate": 0.725
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00002",
  "run_kind": "SELECT",
  "selection_key": "ma_filter=0;momentum_days=60;top_k=1",
  "parameters": {
    "momentum_days": 60,
    "ma_filter": 0,
    "top_k": 1
  },
  "metrics": {
    "cagr": 0.5273103802796621,
    "annual_vol": 0.1824897528947834,
    "sharpe": 2.4135816692792966,
    "max_drawdown": -0.19206654931225153,
    "calmar": 2.7454566251533428,
    "n_trades": 12,
    "turnover": 0.019440580269862902,
    "exposure": 0.9305766313299008,
    "win_rate": 0.6666666666666666
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00003",
  "run_kind": "SELECT",
  "selection_key": "ma_filter=0;momentum_days=60;top_k=2",
  "parameters": {
    "momentum_days": 60,
    "ma_filter": 0,
    "top_k": 2
  },
  "metrics": {
    "cagr": 0.2986184546268482,
    "annual_vol": 0.14895330994497202,
    "sharpe": 1.82942334958977,
    "max_drawdown": -0.19206654931225153,
    "calmar": 1.5547655523366033,
    "n_trades": 59,
    "turnover": 0.02890886254289757,
    "exposure": 0.930376236517701,
    "win_rate": 0.7966101694915254
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00004",
  "run_kind": "SELECT",
  "selection_key": "ma_filter=0;momentum_days=60;top_k=3",
  "parameters": {
    "momentum_days": 60,
    "ma_filter": 0,
    "top_k": 3
  },
  "metrics": {
    "cagr": 0.27448759601838923,
    "annual_vol": 0.14543816183502775,
    "sharpe": 1.7409905892642221,
    "max_drawdown": -0.19206654931225164,
    "calmar": 1.4291275445998761,
    "n_trades": 57,
    "turnover": 0.026341083816712203,
    "exposure": 0.930258746163136,
    "win_rate": 0.7543859649122807
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00005",
  "run_kind": "SELECT",
  "selection_key": "ma_filter=200;momentum_days=60;top_k=1",
  "parameters": {
    "momentum_days": 60,
    "ma_filter": 200,
    "top_k": 1
  },
  "metrics": {
    "cagr": 0.5184739120173245,
    "annual_vol": 0.16869729121055346,
    "sharpe": 2.562089532892931,
    "max_drawdown": -0.11972792947880406,
    "calmar": 4.3304341290652,
    "n_trades": 9,
    "turnover": 0.014780157294456938,
    "exposure": 0.796806259941958,
    "win_rate": 0.7777777777777778
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00006",
  "run_kind": "SELECT",
  "selection_key": "ma_filter=200;momentum_days=60;top_k=2",
  "parameters": {
    "momentum_days": 60,
    "ma_filter": 200,
    "top_k": 2
  },
  "metrics": {
    "cagr": 0.40184877567374455,
    "annual_vol": 0.1494526939552488,
    "sharpe": 2.336174753594668,
    "max_drawdown": -0.11972792947880384,
    "calmar": 3.3563494952519517,
    "n_trades": 30,
    "turnover": 0.017116473346833992,
    "exposure": 0.7967699423843613,
    "win_rate": 0.8666666666666667
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00007",
  "run_kind": "SELECT",
  "selection_key": "ma_filter=200;momentum_days=60;top_k=3",
  "parameters": {
    "momentum_days": 60,
    "ma_filter": 200,
    "top_k": 3
  },
  "metrics": {
    "cagr": 0.3816621371412732,
    "annual_vol": 0.1480319603152972,
    "sharpe": 2.259064107797813,
    "max_drawdown": -0.11972792947880395,
    "calmar": 3.1877452387484975,
    "n_trades": 31,
    "turnover": 0.017647440603906918,
    "exposure": 0.7966912056795539,
    "win_rate": 0.7741935483870968
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00008",
  "run_kind": "SELECT",
  "selection_key": "ma_filter=0;momentum_days=120;top_k=1",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 1
  },
  "metrics": {
    "cagr": 0.6907444991745453,
    "annual_vol": 0.17759046295500974,
    "sharpe": 3.0486996007489777,
    "max_drawdown": -0.11972792947880395,
    "calmar": 5.769284595344408,
    "n_trades": 4,
    "turnover": 0.00698051015223555,
    "exposure": 0.8998981921626286,
    "win_rate": 0.5
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00009",
  "run_kind": "SELECT",
  "selection_key": "ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2
  },
  "metrics": {
    "cagr": 0.34840715773102127,
    "annual_vol": 0.15163407274078453,
    "sharpe": 2.048133177238671,
    "max_drawdown": -0.12103675806719838,
    "calmar": 2.8785235435469048,
    "n_trades": 40,
    "turnover": 0.015804077231609905,
    "exposure": 0.8997500416270083,
    "win_rate": 0.725
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00010",
  "run_kind": "SELECT",
  "selection_key": "ma_filter=0;momentum_days=120;top_k=3",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 3
  },
  "metrics": {
    "cagr": 0.31796464365564536,
    "annual_vol": 0.1488251854941637,
    "sharpe": 1.9303539547678377,
    "max_drawdown": -0.12103675806719838,
    "calmar": 2.6270089246699304,
    "n_trades": 42,
    "turnover": 0.017092802675380946,
    "exposure": 0.8995411769785819,
    "win_rate": 0.7142857142857143
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00011",
  "run_kind": "SELECT",
  "selection_key": "ma_filter=200;momentum_days=120;top_k=1",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 200,
    "top_k": 1
  },
  "metrics": {
    "cagr": 0.6661402908982705,
    "annual_vol": 0.17259156487780034,
    "sharpe": 3.0468093009421477,
    "max_drawdown": -0.11972792947880395,
    "calmar": 5.56378360335882,
    "n_trades": 4,
    "turnover": 0.006980455671017464,
    "exposure": 0.8321106826845539,
    "win_rate": 0.5
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00012",
  "run_kind": "SELECT",
  "selection_key": "ma_filter=200;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 200,
    "top_k": 2
  },
  "metrics": {
    "cagr": 0.38302813301173044,
    "annual_vol": 0.1493877315253713,
    "sharpe": 2.246550129200732,
    "max_drawdown": -0.11972792947880384,
    "calmar": 3.199154405151057,
    "n_trades": 34,
    "turnover": 0.013361229580012917,
    "exposure": 0.8318557181010676,
    "win_rate": 0.7352941176470589
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00013",
  "run_kind": "SELECT",
  "selection_key": "ma_filter=200;momentum_days=120;top_k=3",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 200,
    "top_k": 3
  },
  "metrics": {
    "cagr": 0.35638146119707903,
    "annual_vol": 0.14818202962062121,
    "sharpe": 2.132173625064178,
    "max_drawdown": -0.11972792947880384,
    "calmar": 2.9765942061177246,
    "n_trades": 35,
    "turnover": 0.01445786096483025,
    "exposure": 0.8317516216304551,
    "win_rate": 0.7142857142857143
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00014",
  "run_kind": "SELECT",
  "selection_key": "ma_filter=0;momentum_days=180;top_k=1",
  "parameters": {
    "momentum_days": 180,
    "ma_filter": 0,
    "top_k": 1
  },
  "metrics": {
    "cagr": 0.6973178258715238,
    "annual_vol": 0.1738585439760228,
    "sharpe": 3.132718259161838,
    "max_drawdown": -0.11972792947880395,
    "calmar": 5.8241867950700135,
    "n_trades": 0,
    "turnover": 0.0007799697806568753,
    "exposure": 0.8496106281439493,
    "win_rate": NaN
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00015",
  "run_kind": "SELECT",
  "selection_key": "ma_filter=0;momentum_days=180;top_k=2",
  "parameters": {
    "momentum_days": 180,
    "ma_filter": 0,
    "top_k": 2
  },
  "metrics": {
    "cagr": 0.3846968207300707,
    "annual_vol": 0.14805117300931717,
    "sharpe": 2.2736494779671808,
    "max_drawdown": -0.11990156642611327,
    "calmar": 3.2084386567804497,
    "n_trades": 37,
    "turnover": 0.013599026735936014,
    "exposure": 0.849043253671129,
    "win_rate": 0.8378378378378378
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00016",
  "run_kind": "SELECT",
  "selection_key": "ma_filter=0;momentum_days=180;top_k=3",
  "parameters": {
    "momentum_days": 180,
    "ma_filter": 0,
    "top_k": 3
  },
  "metrics": {
    "cagr": 0.3676275833494125,
    "annual_vol": 0.14594944802883775,
    "sharpe": 2.2191915582153965,
    "max_drawdown": -0.11990156642611327,
    "calmar": 3.0660782365671175,
    "n_trades": 42,
    "turnover": 0.015538028321735384,
    "exposure": 0.8489857065500187,
    "win_rate": 0.7142857142857143
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00017",
  "run_kind": "SELECT",
  "selection_key": "ma_filter=200;momentum_days=180;top_k=1",
  "parameters": {
    "momentum_days": 180,
    "ma_filter": 200,
    "top_k": 1
  },
  "metrics": {
    "cagr": 0.7329542216544895,
    "annual_vol": 0.17159891319723825,
    "sharpe": 3.293029293102272,
    "max_drawdown": -0.11972792947880395,
    "calmar": 6.12183159639663,
    "n_trades": 0,
    "turnover": 0.000779540534358239,
    "exposure": 0.8325240170016759,
    "win_rate": NaN
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00018",
  "run_kind": "SELECT",
  "selection_key": "ma_filter=200;momentum_days=180;top_k=2",
  "parameters": {
    "momentum_days": 180,
    "ma_filter": 200,
    "top_k": 2
  },
  "metrics": {
    "cagr": 0.43547280353891304,
    "annual_vol": 0.15250648291869273,
    "sharpe": 2.448013362065142,
    "max_drawdown": -0.11972792947880384,
    "calmar": 3.6371864562813427,
    "n_trades": 32,
    "turnover": 0.014060169475586057,
    "exposure": 0.8317633293586401,
    "win_rate": 0.78125
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00019",
  "run_kind": "SELECT",
  "selection_key": "ma_filter=200;momentum_days=180;top_k=3",
  "parameters": {
    "momentum_days": 180,
    "ma_filter": 200,
    "top_k": 3
  },
  "metrics": {
    "cagr": 0.43108316913300393,
    "annual_vol": 0.15200255617332972,
    "sharpe": 2.4354535277997003,
    "max_drawdown": -0.11972792947880384,
    "calmar": 3.600523044285345,
    "n_trades": 33,
    "turnover": 0.015003304869451414,
    "exposure": 0.8317190212559561,
    "win_rate": 0.7272727272727273
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00020",
  "run_kind": "EVALUATE",
  "selection_key": "ma_filter=200;momentum_days=180;top_k=1",
  "parameters": {
    "momentum_days": 180,
    "ma_filter": 200,
    "top_k": 1
  },
  "metrics": {
    "cagr": 1.1730362269423362,
    "annual_vol": 0.19494209294648757,
    "sharpe": 4.084009822420137,
    "max_drawdown": -0.08387861739840863,
    "calmar": 13.984925638087491,
    "n_trades": 0,
    "turnover": 0.003972222222222222,
    "exposure": 0.9246031746031746,
    "win_rate": NaN
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00021",
  "run_kind": "EVALUATE",
  "selection_key": "ma_filter=0;momentum_days=180;top_k=1",
  "parameters": {
    "momentum_days": 180,
    "ma_filter": 0,
    "top_k": 1
  },
  "metrics": {
    "cagr": 0.7601150726095462,
    "annual_vol": 0.17521191052689056,
    "sharpe": 3.317619233524827,
    "max_drawdown": -0.0664476126347402,
    "calmar": 11.439313505330396,
    "n_trades": 0,
    "turnover": 0.003972222222222222,
    "exposure": 0.9920634920634921,
    "win_rate": NaN
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00022",
  "run_kind": "EVALUATE",
  "selection_key": "ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2
  },
  "metrics": {
    "cagr": 0.10068827989298201,
    "annual_vol": 0.10999942729181375,
    "sharpe": 0.9270416639564795,
    "max_drawdown": -0.12103675806719838,
    "calmar": 0.8318818307830164,
    "n_trades": 4,
    "turnover": 0.01522889034610029,
    "exposure": 0.5038759689922481,
    "win_rate": 0.5
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00023",
  "run_kind": "EVALUATE",
  "selection_key": "ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2
  },
  "metrics": {
    "cagr": 0.42814251170613526,
    "annual_vol": 0.1644265133103109,
    "sharpe": 2.2506588742496207,
    "max_drawdown": -0.08588050764164956,
    "calmar": 4.985328143292187,
    "n_trades": 8,
    "turnover": 0.019946310984635514,
    "exposure": 0.9950867509324293,
    "win_rate": 0.75
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00024",
  "run_kind": "EVALUATE",
  "selection_key": "ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2
  },
  "metrics": {
    "cagr": 0.5519035424398158,
    "annual_vol": 0.17466311109699462,
    "sharpe": 2.6050345652940954,
    "max_drawdown": -0.11972792947880395,
    "calmar": 4.609647430155569,
    "n_trades": 3,
    "turnover": 0.0077877514220142776,
    "exposure": 0.9960585143710122,
    "win_rate": 1.0
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00025",
  "run_kind": "EVALUATE",
  "selection_key": "ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2
  },
  "metrics": {
    "cagr": 0.38337378994725957,
    "annual_vol": 0.14510705053159179,
    "sharpe": 2.3100178010471453,
    "max_drawdown": -0.0737297642124376,
    "calmar": 5.199715393672554,
    "n_trades": 13,
    "turnover": 0.020697545122824786,
    "exposure": 0.9956509477590487,
    "win_rate": 0.7692307692307693
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00026",
  "run_kind": "EVALUATE",
  "selection_key": "ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2
  },
  "metrics": {
    "cagr": 0.2737045084030998,
    "annual_vol": 0.15590195420189001,
    "sharpe": 1.6302244702490487,
    "max_drawdown": -0.08299611192430811,
    "calmar": 3.2977991626007306,
    "n_trades": 10,
    "turnover": 0.027275940016398856,
    "exposure": 0.9946575114641826,
    "win_rate": 0.7
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00027",
  "run_kind": "DIAGNOSTIC",
  "selection_key": "_regime=DOWN|HIGH_VOL|HIGH_LIQ;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_regime": "DOWN|HIGH_VOL|HIGH_LIQ"
  },
  "metrics": {
    "regime_combo": "DOWN|HIGH_VOL|HIGH_LIQ",
    "n_days": 37,
    "sharpe": NaN,
    "annual_vol": 0.0,
    "mean_daily_return": 0.0,
    "status": "ok"
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00028",
  "run_kind": "DIAGNOSTIC",
  "selection_key": "_regime=DOWN|HIGH_VOL|LOW_LIQ;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_regime": "DOWN|HIGH_VOL|LOW_LIQ"
  },
  "metrics": {
    "regime_combo": "DOWN|HIGH_VOL|LOW_LIQ",
    "n_days": 5,
    "sharpe": NaN,
    "annual_vol": 0.0,
    "mean_daily_return": 0.0,
    "status": "ok"
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00029",
  "run_kind": "DIAGNOSTIC",
  "selection_key": "_regime=DOWN|LOW_VOL|HIGH_LIQ;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_regime": "DOWN|LOW_VOL|HIGH_LIQ"
  },
  "metrics": {
    "regime_combo": "DOWN|LOW_VOL|HIGH_LIQ",
    "n_days": 94,
    "sharpe": 2.393084808494333,
    "annual_vol": 0.10810730915055038,
    "mean_daily_return": 0.0010266268222832637,
    "status": "ok"
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00030",
  "run_kind": "DIAGNOSTIC",
  "selection_key": "_regime=DOWN|LOW_VOL|LOW_LIQ;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_regime": "DOWN|LOW_VOL|LOW_LIQ"
  },
  "metrics": {
    "regime_combo": "DOWN|LOW_VOL|LOW_LIQ",
    "n_days": 62,
    "sharpe": NaN,
    "annual_vol": 0.0,
    "mean_daily_return": 0.0,
    "status": "ok"
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00031",
  "run_kind": "DIAGNOSTIC",
  "selection_key": "_regime=UP|HIGH_VOL|HIGH_LIQ;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_regime": "UP|HIGH_VOL|HIGH_LIQ"
  },
  "metrics": {
    "regime_combo": "UP|HIGH_VOL|HIGH_LIQ",
    "n_days": 626,
    "sharpe": 1.686738691788627,
    "annual_vol": 0.17095297738684503,
    "mean_daily_return": 0.0011442579422018162,
    "status": "ok"
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00032",
  "run_kind": "DIAGNOSTIC",
  "selection_key": "_regime=UP|LOW_VOL|HIGH_LIQ;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_regime": "UP|LOW_VOL|HIGH_LIQ"
  },
  "metrics": {
    "regime_combo": "UP|LOW_VOL|HIGH_LIQ",
    "n_days": 457,
    "sharpe": 2.8142663991796666,
    "annual_vol": 0.14835974765073826,
    "mean_daily_return": 0.0016568406857311395,
    "status": "ok"
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00033",
  "run_kind": "DIAGNOSTIC",
  "selection_key": "_regime=UP|LOW_VOL|LOW_LIQ;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_regime": "UP|LOW_VOL|LOW_LIQ"
  },
  "metrics": {
    "regime_combo": "UP|LOW_VOL|LOW_LIQ",
    "n_days": 2,
    "sharpe": 11.44828793430686,
    "annual_vol": 0.12320867436274521,
    "mean_daily_return": 0.005597334841702217,
    "status": "ok"
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00034",
  "run_kind": "STRESS",
  "selection_key": "ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2
  },
  "metrics": {
    "cagr": 0.34840715773102127,
    "annual_vol": 0.15163407274078453,
    "sharpe": 2.048133177238671,
    "max_drawdown": -0.12103675806719838,
    "calmar": 2.8785235435469048,
    "n_trades": 40,
    "turnover": 0.015804077231609905,
    "exposure": 0.8997500416270083,
    "win_rate": 0.725
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00035",
  "run_kind": "STRESS",
  "selection_key": "ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2
  },
  "metrics": {
    "cagr": 0.34166751208181,
    "annual_vol": 0.15162378783210745,
    "sharpe": 2.0151767352709866,
    "max_drawdown": -0.12293920117361656,
    "calmar": 2.779158387399167,
    "n_trades": 40,
    "turnover": 0.01580951668207684,
    "exposure": 0.8998642147919068,
    "win_rate": 0.725
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00036",
  "run_kind": "STRESS",
  "selection_key": "ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2
  },
  "metrics": {
    "cagr": 0.33494725369049827,
    "annual_vol": 0.15165297394297336,
    "sharpe": 1.9816692381724421,
    "max_drawdown": -0.12509131254285155,
    "calmar": 2.6776220257162784,
    "n_trades": 40,
    "turnover": 0.01581491963167133,
    "exposure": 0.8999632553678136,
    "win_rate": 0.725
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00037",
  "run_kind": "STRESS",
  "selection_key": "_exec=E01;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_exec": "E01"
  },
  "metrics": {
    "cagr": 0.32295449433943135,
    "annual_vol": 0.15185472093851096,
    "sharpe": 1.9197621944787309,
    "max_drawdown": -0.12202926513064272,
    "calmar": 2.646533140994343,
    "n_trades": 39,
    "turnover": 0.015869332983376692,
    "exposure": 0.8989393811767765,
    "win_rate": 0.717948717948718
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00038",
  "run_kind": "STRESS",
  "selection_key": "_exec=E02;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_exec": "E02"
  },
  "metrics": {
    "cagr": 0.3606933840496034,
    "annual_vol": 0.15190346998439463,
    "sharpe": 2.1045527202876873,
    "max_drawdown": -0.11972792947880395,
    "calmar": 3.0126085502335425,
    "n_trades": 40,
    "turnover": 0.015787546942846963,
    "exposure": 0.9003115264797508,
    "win_rate": 0.725
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00039",
  "run_kind": "STRESS",
  "selection_key": "_exec=E03;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_exec": "E03"
  },
  "metrics": {
    "cagr": 0.33804441721414213,
    "annual_vol": 0.15163443457275294,
    "sharpe": 1.997192760360342,
    "max_drawdown": -0.12409942546237507,
    "calmar": 2.723980517674771,
    "n_trades": 40,
    "turnover": 0.015812766087151733,
    "exposure": 0.8999175073016414,
    "win_rate": 0.725
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00040",
  "run_kind": "STRESS",
  "selection_key": "_exec=E04;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_exec": "E04"
  },
  "metrics": {
    "cagr": 0.3596454323923868,
    "annual_vol": 0.15337815117978748,
    "sharpe": 2.0807401799059853,
    "max_drawdown": -0.12103675806719838,
    "calmar": 2.971373640003769,
    "n_trades": 35,
    "turnover": 0.015659122205610707,
    "exposure": 0.8997752906435388,
    "win_rate": 0.6857142857142857
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00041",
  "run_kind": "STRESS",
  "selection_key": "_exec=E05;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_exec": "E05"
  },
  "metrics": {
    "cagr": 0.3606933840496034,
    "annual_vol": 0.15190346998439463,
    "sharpe": 2.1045527202876873,
    "max_drawdown": -0.11972792947880395,
    "calmar": 3.0126085502335425,
    "n_trades": 40,
    "turnover": 0.015787546942846963,
    "exposure": 0.9003115264797508,
    "win_rate": 0.725
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00042",
  "run_kind": "DIAGNOSTIC",
  "selection_key": "_kill=K02;_variant=K02_COUNTERFACTUAL;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_kill": "K02",
    "_variant": "K02_COUNTERFACTUAL"
  },
  "metrics": {
    "cagr": 0.3452390620521828,
    "annual_vol": 0.15157636080145173,
    "sharpe": 2.033318269397988,
    "max_drawdown": -0.12103675806719827,
    "calmar": 2.8523488861169755,
    "n_trades": 39,
    "turnover": 0.015784172233411567,
    "exposure": 0.8911790258864698,
    "win_rate": 0.717948717948718
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00043",
  "run_kind": "DIAGNOSTIC",
  "selection_key": "_kill=K03;_variant=K03_510300.SH;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_kill": "K03",
    "_variant": "K03_510300.SH"
  },
  "metrics": {
    "cagr": -0.11077120833623588,
    "annual_vol": 0.12164456932313084,
    "sharpe": -0.9040341297306406,
    "max_drawdown": -0.45856915637049067,
    "calmar": -0.24155834904591963,
    "n_trades": 19,
    "turnover": 0.018729142208030382,
    "exposure": 0.4967400783931937,
    "win_rate": 0.21052631578947367
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00044",
  "run_kind": "DIAGNOSTIC",
  "selection_key": "_kill=K03;_variant=K03_510500.SH;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_kill": "K03",
    "_variant": "K03_510500.SH"
  },
  "metrics": {
    "cagr": 0.4618309841318249,
    "annual_vol": 0.1587517629646513,
    "sharpe": 2.472660184200539,
    "max_drawdown": -0.12103675806719849,
    "calmar": 3.815625860330963,
    "n_trades": 26,
    "turnover": 0.009669857300799537,
    "exposure": 0.8999835255108024,
    "win_rate": 0.7692307692307693
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00045",
  "run_kind": "DIAGNOSTIC",
  "selection_key": "_kill=K03;_variant=K03_518880.SH;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_kill": "K03",
    "_variant": "K03_518880.SH"
  },
  "metrics": {
    "cagr": 0.3954886085373275,
    "annual_vol": 0.15567141742736373,
    "sharpe": 2.2197193982113848,
    "max_drawdown": -0.12103675806719838,
    "calmar": 3.2675082747817505,
    "n_trades": 34,
    "turnover": 0.014212163445363427,
    "exposure": 0.8996173792256863,
    "win_rate": 0.7352941176470589
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00046",
  "run_kind": "DIAGNOSTIC",
  "selection_key": "_kill=K03;_variant=K03_511010.SH;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_kill": "K03",
    "_variant": "K03_511010.SH"
  },
  "metrics": {
    "cagr": 0.44428699987363807,
    "annual_vol": 0.15880816884564172,
    "sharpe": 2.395666189799375,
    "max_drawdown": -0.11972792947880395,
    "calmar": 3.710805004376965,
    "n_trades": 29,
    "turnover": 0.011653082744058107,
    "exposure": 0.8998682397816562,
    "win_rate": 0.7241379310344828
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00047",
  "run_kind": "DIAGNOSTIC",
  "selection_key": "_kill=K04;_variant=K04;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_kill": "K04",
    "_variant": "K04"
  },
  "metrics": {
    "cagr": 0.32295449433943135,
    "annual_vol": 0.15185472093851096,
    "sharpe": 1.9197621944787309,
    "max_drawdown": -0.12202926513064272,
    "calmar": 2.646533140994343,
    "n_trades": 39,
    "turnover": 0.015869332983376692,
    "exposure": 0.8989393811767765,
    "win_rate": 0.717948717948718
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00048",
  "run_kind": "DIAGNOSTIC",
  "selection_key": "_kill=K05;_variant=K05;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_kill": "K05",
    "_variant": "K05"
  },
  "metrics": {
    "cagr": 0.34166751208181,
    "annual_vol": 0.15162378783210745,
    "sharpe": 2.0151767352709866,
    "max_drawdown": -0.12293920117361656,
    "calmar": 2.779158387399167,
    "n_trades": 40,
    "turnover": 0.01580951668207684,
    "exposure": 0.8998642147919068,
    "win_rate": 0.725
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00049",
  "run_kind": "DIAGNOSTIC",
  "selection_key": "_kill=K06;_variant=K06;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_kill": "K06",
    "_variant": "K06"
  },
  "metrics": {
    "cagr": 0.3276539606211637,
    "annual_vol": 0.146783797918587,
    "sharpe": 2.0051228103814487,
    "max_drawdown": -0.11972792947880395,
    "calmar": 2.736654363334413,
    "n_trades": 44,
    "turnover": 0.01590004186608118,
    "exposure": 0.8982844862089319,
    "win_rate": 0.75
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00050",
  "run_kind": "DIAGNOSTIC",
  "selection_key": "_kill=K07;_variant=K07_momentum_days-10%;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_kill": "K07",
    "_variant": "K07_momentum_days-10%"
  },
  "metrics": {
    "cagr": 0.35963158049239285,
    "annual_vol": 0.14687150393558696,
    "sharpe": 2.1662296952223703,
    "max_drawdown": -0.11972792947880395,
    "calmar": 3.0037400801795395,
    "n_trades": 45,
    "turnover": 0.015253035375081814,
    "exposure": 0.8997644453848549,
    "win_rate": 0.7777777777777778
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00051",
  "run_kind": "DIAGNOSTIC",
  "selection_key": "_kill=K07;_variant=K07_momentum_days+10%;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_kill": "K07",
    "_variant": "K07_momentum_days+10%"
  },
  "metrics": {
    "cagr": 0.36987333684185786,
    "annual_vol": 0.15007242934742618,
    "sharpe": 2.173234272941531,
    "max_drawdown": -0.12103675806719849,
    "calmar": 3.05587610531098,
    "n_trades": 41,
    "turnover": 0.01498195286862308,
    "exposure": 0.8821549919175333,
    "win_rate": 0.7317073170731707
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

```yaml
{
  "run_id": "RUN-00052",
  "run_kind": "DIAGNOSTIC",
  "selection_key": "_kill=K08;_variant=K08;ma_filter=0;momentum_days=120;top_k=2",
  "parameters": {
    "momentum_days": 120,
    "ma_filter": 0,
    "top_k": 2,
    "_kill": "K08",
    "_variant": "K08"
  },
  "metrics": {
    "cagr": 0.3683274188957848,
    "annual_vol": 0.15524858959999208,
    "sharpe": 2.0985896587749373,
    "max_drawdown": -0.12103675806719838,
    "calmar": 3.0431038039807143,
    "n_trades": 40,
    "turnover": 0.016578786899826076,
    "exposure": 0.9438554358244107,
    "win_rate": 0.725
  },
  "code_commit": "74c0d06e7ccc9bdec08d6587c9e6d944012b9ba3",
  "config_sha256": "2adad2a563accee006fd0ec24fbd963a886113660e8e4fc0496566e40cee0d13"
}
```

## Dataset Metadata

```json
{
  "dataset_version": "market-20260808-v1",
  "manifest": {
    "dataset_version": "market-20260808-v1",
    "source": "synthetic",
    "provider": "fixture",
    "download_time": "2026-08-08T09:53:04+08:00",
    "schema_version": 1,
    "adjustment": "qfq",
    "units": {
      "price": "CNY/share",
      "volume": "shares",
      "amount": "CNY"
    },
    "source_units": {
      "volume": {
        "source": "shares",
        "factor": 1.0
      },
      "amount": {
        "source": "CNY",
        "factor": 1.0
      }
    },
    "normalized_units": {
      "volume": "shares",
      "amount": "CNY"
    },
    "conversion": {
      "volume": "x1.0 (shares -> shares)",
      "amount": "x1.0 (CNY -> CNY)"
    },
    "symbols": [
      "510300.SH",
      "510500.SH",
      "518880.SH",
      "511010.SH"
    ],
    "start": "2020-01-01",
    "end": "2024-12-31",
    "calendar_source": "fixture",
    "calendar_end": "2024-12-31",
    "allow_calendar_gap": false,
    "coverage_gap": false,
    "warnings": [],
    "anomalies": [],
    "missing_ratio_by_symbol": {
      "510300.SH": 0.0,
      "510500.SH": 0.0,
      "511010.SH": 0.0,
      "518880.SH": 0.0
    },
    "files": {
      "prices.parquet": "e7836d00a95e60266410f9e55c030a3f91b2a030278e39d2ca8c728382917fe7",
      "calendar.parquet": "2dfae992293fb5d1e484dce7a3a69a154e92d7d040867cb9ae4da07f074a98be"
    }
  }
}
```

## Cost / Timing Metadata

```json
{
  "cost_model_version": "cn-etf-cost-2026-v1",
  "timing": {
    "execution_bar": 1,
    "execution_price": "close"
  },
  "windows": {
    "in_sample": [
      "2020-01-02",
      "2024-12-31"
    ],
    "holdout": [
      "2025-01-01",
      "2026-08-07"
    ]
  }
}
```

## Candidate Validation

### overall

```json
"PASS"
```

### ready_for_candidate_freeze

```json
true
```

### gate_results

```json
{
  "min_is_sharpe": true,
  "max_drawdown_floor": true,
  "walkforward": true,
  "param_stability": true,
  "time_windows_min_pos_cagr_frac": true,
  "cost_2x_min_sharpe": true,
  "exec_stress_max_drawdown_floor": true,
  "bootstrap_sharpe_p05_min": true,
  "deflated_sharpe_min": true,
  "max_kill_families_killed": true,
  "require_code_clean": true
}
```

### code_clean

```json
{
  "code_dirty": false,
  "pass": true
}
```

### effective_trial_count

```json
18
```

### dataset_source

```json
"synthetic"
```

### market_evidence

```json
false
```

### deflated_sharpe

```json
{
  "dsr_probability": 0.9972708492847416,
  "observed_sharpe": 2.048133177238671,
  "daily_sharpe": 0.12902026283128806,
  "n_observations": 1283,
  "skew": 0.13213230352410382,
  "kurtosis": 3.7535785649550224,
  "n_trials": 18,
  "annualization": 252,
  "effective_trial_count": 18,
  "trial_selection_keys": [
    "ma_filter=0;momentum_days=120;top_k=1",
    "ma_filter=0;momentum_days=120;top_k=2",
    "ma_filter=0;momentum_days=120;top_k=3",
    "ma_filter=0;momentum_days=180;top_k=1",
    "ma_filter=0;momentum_days=180;top_k=2",
    "ma_filter=0;momentum_days=180;top_k=3",
    "ma_filter=0;momentum_days=60;top_k=1",
    "ma_filter=0;momentum_days=60;top_k=2",
    "ma_filter=0;momentum_days=60;top_k=3",
    "ma_filter=200;momentum_days=120;top_k=1",
    "ma_filter=200;momentum_days=120;top_k=2",
    "ma_filter=200;momentum_days=120;top_k=3",
    "ma_filter=200;momentum_days=180;top_k=1",
    "ma_filter=200;momentum_days=180;top_k=2",
    "ma_filter=200;momentum_days=180;top_k=3",
    "ma_filter=200;momentum_days=60;top_k=1",
    "ma_filter=200;momentum_days=60;top_k=2",
    "ma_filter=200;momentum_days=60;top_k=3"
  ],
  "candidate_selection_key": "ma_filter=0;momentum_days=120;top_k=2"
}
```

### bootstrap

```json
{
  "n": 1283,
  "block_len": 11,
  "R": 1000,
  "seed": 42,
  "sharpe": {
    "p05": 1.3566976644335706,
    "p50": 2.047824530534476,
    "p95": 2.7865315127893315,
    "ci95": [
      1.2252,
      2.876237
    ]
  },
  "cagr": {
    "p05": 0.21335998391361474,
    "p50": 0.345833368406424,
    "p95": 0.5072377396522048,
    "ci95": [
      0.191236,
      0.527992
    ]
  },
  "max_drawdown": {
    "p05": -0.20764578890342367,
    "p50": -0.13014944711838616,
    "p95": -0.08851772714745498,
    "ci95": [
      -0.224715,
      -0.084344
    ]
  }
}
```

### cost_stress

```json
{
  "variants": [
    {
      "multiplier": 1,
      "sharpe": 2.048133177238671,
      "max_drawdown": -0.12103675806719838,
      "cagr": 0.34840715773102127,
      "fee_rate": 0.0003,
      "slippage": 0.001
    },
    {
      "multiplier": 2,
      "sharpe": 2.0151767352709866,
      "max_drawdown": -0.12293920117361656,
      "cagr": 0.34166751208181,
      "fee_rate": 0.0006,
      "slippage": 0.002
    },
    {
      "multiplier": 3,
      "sharpe": 1.9816692381724421,
      "max_drawdown": -0.12509131254285155,
      "cagr": 0.33494725369049827,
      "fee_rate": 0.0009,
      "slippage": 0.003
    }
  ],
  "cost_2x_sharpe": 2.0151767352709866
}
```

### execution_stress

```json
{
  "variants": [
    {
      "variant_id": "E01",
      "variant_name": "T+2 execution",
      "parameters": {
        "execution_bar": 2
      },
      "sharpe": 1.9197621944787309,
      "max_drawdown": -0.12202926513064272,
      "cagr": 0.32295449433943135,
      "valuation_mode": "execution_revaluation"
    },
    {
      "variant_id": "E02",
      "variant_name": "open execution price",
      "parameters": {
        "execution_price": "open"
      },
      "sharpe": 2.1045527202876873,
      "max_drawdown": -0.11972792947880395,
      "cagr": 0.3606933840496034,
      "valuation_mode": "execution_revaluation"
    },
    {
      "variant_id": "E03",
      "variant_name": "slippage +0.002",
      "parameters": {
        "slippage_delta": 0.002
      },
      "sharpe": 1.997192760360342,
      "max_drawdown": -0.12409942546237507,
      "cagr": 0.33804441721414213,
      "valuation_mode": "execution_revaluation"
    },
    {
      "variant_id": "E04",
      "variant_name": "miss 5% seed 7",
      "parameters": {
        "miss_rate": 0.05,
        "seed": 7
      },
      "sharpe": 2.0807401799059853,
      "max_drawdown": -0.12103675806719838,
      "cagr": 0.3596454323923868,
      "valuation_mode": "execution_revaluation"
    },
    {
      "variant_id": "E05",
      "variant_name": "T+1 / open execution price",
      "parameters": {
        "execution_bar": 1,
        "execution_price": "open"
      },
      "sharpe": 2.1045527202876873,
      "max_drawdown": -0.11972792947880395,
      "cagr": 0.3606933840496034,
      "valuation_mode": "execution_revaluation"
    }
  ],
  "worst_exec_max_drawdown": -0.12409942546237507,
  "gate_input_variant": "worst across required E01-E05 variants (M6-002)"
}
```

### kill_tests

```json
{
  "families": [
    {
      "family_id": "K01",
      "family_name": "drop_best_year",
      "family_result": "PASSED",
      "killed_fraction": 0.0,
      "gate_relevant_variant_count": 1,
      "killed_variant_count": 0,
      "variants": [
        {
          "variant_id": "K01",
          "variant_name": "drop_best_year=2022",
          "parameters": {
            "best_year": 2022
          },
          "result": "PASSED",
          "gate_relevant": true,
          "metrics": {
            "cagr": 0.2963944200199562,
            "sharpe": 1.8598325132483053,
            "max_drawdown": -0.12103675806719782
          }
        }
      ]
    },
    {
      "family_id": "K02",
      "family_name": "drop_best_trades",
      "family_result": "PASSED",
      "killed_fraction": 0.0,
      "gate_relevant_variant_count": 1,
      "killed_variant_count": 0,
      "variants": [
        {
          "variant_id": "K02_ATTRIBUTION",
          "variant_name": "drop_best_trades (attribution)",
          "parameters": {
            "mode": "ATTRIBUTION_TEST",
            "k": 4
          },
          "result": "PASSED",
          "gate_relevant": false,
          "metrics": {
            "cagr": 0.16752006220465843,
            "sharpe": 0.7013937349062569,
            "max_drawdown": -0.30393146837173124
          }
        },
        {
          "variant_id": "K02_COUNTERFACTUAL",
          "variant_name": "drop_best_trades (counterfactual)",
          "parameters": {
            "mode": "COUNTERFACTUAL_TEST",
            "k": 4
          },
          "result": "PASSED",
          "gate_relevant": true,
          "metrics": {
            "cagr": 0.3452390620521828,
            "annual_vol": 0.15157636080145173,
            "sharpe": 2.033318269397988,
            "max_drawdown": -0.12103675806719827,
            "calmar": 2.8523488861169755,
            "n_trades": 39,
            "turnover": 0.015784172233411567,
            "exposure": 0.8911790258864698,
            "win_rate": 0.717948717948718
          }
        }
      ]
    },
    {
      "family_id": "K03",
      "family_name": "universe_loo",
      "family_result": "KILLED",
      "killed_fraction": 0.25,
      "gate_relevant_variant_count": 4,
      "killed_variant_count": 1,
      "variants": [
        {
          "variant_id": "K03_510300.SH",
          "variant_name": "universe_loo drop 510300.SH",
          "parameters": {
            "drop_symbol": "510300.SH"
          },
          "result": "KILLED",
          "gate_relevant": true,
          "metrics": {
            "cagr": -0.11077120833623588,
            "annual_vol": 0.12164456932313084,
            "sharpe": -0.9040341297306406,
            "max_drawdown": -0.45856915637049067,
            "calmar": -0.24155834904591963,
            "n_trades": 19,
            "turnover": 0.018729142208030382,
            "exposure": 0.4967400783931937,
            "win_rate": 0.21052631578947367
          }
        },
        {
          "variant_id": "K03_510500.SH",
          "variant_name": "universe_loo drop 510500.SH",
          "parameters": {
            "drop_symbol": "510500.SH"
          },
          "result": "PASSED",
          "gate_relevant": true,
          "metrics": {
            "cagr": 0.4618309841318249,
            "annual_vol": 0.1587517629646513,
            "sharpe": 2.472660184200539,
            "max_drawdown": -0.12103675806719849,
            "calmar": 3.815625860330963,
            "n_trades": 26,
            "turnover": 0.009669857300799537,
            "exposure": 0.8999835255108024,
            "win_rate": 0.7692307692307693
          }
        },
        {
          "variant_id": "K03_518880.SH",
          "variant_name": "universe_loo drop 518880.SH",
          "parameters": {
            "drop_symbol": "518880.SH"
          },
          "result": "PASSED",
          "gate_relevant": true,
          "metrics": {
            "cagr": 0.3954886085373275,
            "annual_vol": 0.15567141742736373,
            "sharpe": 2.2197193982113848,
            "max_drawdown": -0.12103675806719838,
            "calmar": 3.2675082747817505,
            "n_trades": 34,
            "turnover": 0.014212163445363427,
            "exposure": 0.8996173792256863,
            "win_rate": 0.7352941176470589
          }
        },
        {
          "variant_id": "K03_511010.SH",
          "variant_name": "universe_loo drop 511010.SH",
          "parameters": {
            "drop_symbol": "511010.SH"
          },
          "result": "PASSED",
          "gate_relevant": true,
          "metrics": {
            "cagr": 0.44428699987363807,
            "annual_vol": 0.15880816884564172,
            "sharpe": 2.395666189799375,
            "max_drawdown": -0.11972792947880395,
            "calmar": 3.710805004376965,
            "n_trades": 29,
            "turnover": 0.011653082744058107,
            "exposure": 0.8998682397816562,
            "win_rate": 0.7241379310344828
          }
        }
      ]
    },
    {
      "family_id": "K04",
      "family_name": "delay_execution",
      "family_result": "PASSED",
      "killed_fraction": 0.0,
      "gate_relevant_variant_count": 1,
      "killed_variant_count": 0,
      "variants": [
        {
          "variant_id": "K04",
          "variant_name": "execution_bar=1+1",
          "parameters": {
            "execution_bar": 2
          },
          "result": "PASSED",
          "gate_relevant": true,
          "metrics": {
            "cagr": 0.32295449433943135,
            "annual_vol": 0.15185472093851096,
            "sharpe": 1.9197621944787309,
            "max_drawdown": -0.12202926513064272,
            "calmar": 2.646533140994343,
            "n_trades": 39,
            "turnover": 0.015869332983376692,
            "exposure": 0.8989393811767765,
            "win_rate": 0.717948717948718
          }
        }
      ]
    },
    {
      "family_id": "K05",
      "family_name": "cost_x2",
      "family_result": "PASSED",
      "killed_fraction": 0.0,
      "gate_relevant_variant_count": 1,
      "killed_variant_count": 0,
      "variants": [
        {
          "variant_id": "K05",
          "variant_name": "cost_x2",
          "parameters": {
            "multiplier": 2
          },
          "result": "PASSED",
          "gate_relevant": true,
          "metrics": {
            "cagr": 0.34166751208181,
            "annual_vol": 0.15162378783210745,
            "sharpe": 2.0151767352709866,
            "max_drawdown": -0.12293920117361656,
            "calmar": 2.779158387399167,
            "n_trades": 40,
            "turnover": 0.01580951668207684,
            "exposure": 0.8998642147919068,
            "win_rate": 0.725
          }
        }
      ]
    },
    {
      "family_id": "K06",
      "family_name": "shift_rebalance",
      "family_result": "PASSED",
      "killed_fraction": 0.0,
      "gate_relevant_variant_count": 1,
      "killed_variant_count": 0,
      "variants": [
        {
          "variant_id": "K06",
          "variant_name": "rebalance_shifted_1_trading_day",
          "parameters": {
            "rebalance_shift_days": 1
          },
          "result": "PASSED",
          "gate_relevant": true,
          "metrics": {
            "cagr": 0.3276539606211637,
            "annual_vol": 0.146783797918587,
            "sharpe": 2.0051228103814487,
            "max_drawdown": -0.11972792947880395,
            "calmar": 2.736654363334413,
            "n_trades": 44,
            "turnover": 0.01590004186608118,
            "exposure": 0.8982844862089319,
            "win_rate": 0.75
          }
        }
      ]
    },
    {
      "family_id": "K07",
      "family_name": "perturb_params",
      "family_result": "PASSED",
      "killed_fraction": 0.0,
      "gate_relevant_variant_count": 2,
      "killed_variant_count": 0,
      "variants": [
        {
          "variant_id": "K07_momentum_days-10%",
          "variant_name": "perturb momentum_days -10%",
          "parameters": {
            "momentum_days": 108.0
          },
          "result": "PASSED",
          "gate_relevant": true,
          "metrics": {
            "cagr": 0.35963158049239285,
            "annual_vol": 0.14687150393558696,
            "sharpe": 2.1662296952223703,
            "max_drawdown": -0.11972792947880395,
            "calmar": 3.0037400801795395,
            "n_trades": 45,
            "turnover": 0.015253035375081814,
            "exposure": 0.8997644453848549,
            "win_rate": 0.7777777777777778
          }
        },
        {
          "variant_id": "K07_momentum_days+10%",
          "variant_name": "perturb momentum_days +10%",
          "parameters": {
            "momentum_days": 132.0
          },
          "result": "PASSED",
          "gate_relevant": true,
          "metrics": {
            "cagr": 0.36987333684185786,
            "annual_vol": 0.15007242934742618,
            "sharpe": 2.173234272941531,
            "max_drawdown": -0.12103675806719849,
            "calmar": 3.05587610531098,
            "n_trades": 41,
            "turnover": 0.01498195286862308,
            "exposure": 0.8821549919175333,
            "win_rate": 0.7317073170731707
          }
        }
      ]
    },
    {
      "family_id": "K08",
      "family_name": "shift_start",
      "family_result": "PASSED",
      "killed_fraction": 0.0,
      "gate_relevant_variant_count": 1,
      "killed_variant_count": 0,
      "variants": [
        {
          "variant_id": "K08",
          "variant_name": "start_shifted_60_trading_days",
          "parameters": {
            "shift_trading_days": 60,
            "start": "2020-03-26"
          },
          "result": "PASSED",
          "gate_relevant": true,
          "metrics": {
            "cagr": 0.3683274188957848,
            "annual_vol": 0.15524858959999208,
            "sharpe": 2.0985896587749373,
            "max_drawdown": -0.12103675806719838,
            "calmar": 3.0431038039807143,
            "n_trades": 40,
            "turnover": 0.016578786899826076,
            "exposure": 0.9438554358244107,
            "win_rate": 0.725
          }
        }
      ]
    }
  ],
  "killed_family_count": 1
}
```

## Source Code

### `strategies\etf_momentum_v1.yaml`

```python
# D6 strategy spec: ETF Momentum Rotation v1 (M5.1)
# PLAN_CLARIFICATION M5-001: top_k is the research parameter (actual requested K);
# risk.max_positions is the hard risk ceiling. effective_k = min(top_k, max_positions),
# so the frozen grid [1,2,3] is behaviorally meaningful.
name: etf_momentum_v1
hypothesis: "在多资产 ETF universe 中，中期相对动量较强且绝对动量为正的资产，未来一段时间可能具有更好的风险调整收益；通过月度 Top-K 等权轮动控制换手。"
universe: ["510300.SH", "510500.SH", "518880.SH", "511010.SH"]
benchmark: "510300.SH"
signal:
    kind: momentum_rotation
    momentum_days: 120 # 默认值；研究参数须落在 param_grid
    ma_filter: 0 # 0=disable, 200=close_adj>MA200
    top_k: 2
rebalance: monthly
risk: { max_positions: 3 } # hard ceiling; effective_k = min(top_k, max_positions)
dataset_version: market-20260808-v1
market_rule_version: cn-etf-2026-v1
cost_model_version: cn-etf-cost-2026-v1
timing: { execution_bar: 1, execution_price: close }
windows:
    in_sample: ["2020-01-02", "2024-12-31"]
    holdout: ["2025-01-01", "2026-08-07"]
param_grid:
    momentum_days: [60, 120, 180]
    ma_filter: [0, 200]
    top_k: [1, 2, 3]
research_budget:
    max_total_selection_runs: 50 # >= 18-组合笛卡尔积
    max_variants_per_param: { momentum_days: 3, ma_filter: 2, top_k: 3 }
    holdout_access: { allowed: false }
seed: 42
```

### `src\pql\signals\__init__.py`

```python

```

### `src\pql\signals\buy_hold.py`

```python
"""M3 Buy & Hold Control signal (system self-check, NOT an alpha strategy): a
single symbol, 100% exposure, no active rebalancing, long-only. Entry fires on
the first available bar; the engine fills at T+1 per the TimingContract."""
from __future__ import annotations

import pandas as pd

from ..backtest.api import SignalIntent


def buy_hold_signal(dates, symbol: str) -> SignalIntent:
    """Entry at the first bar, never exit. `dates` is an index of trading days."""
    dates = pd.DatetimeIndex(pd.to_datetime(pd.Series(dates)).dt.normalize())
    entries = pd.DataFrame(False, index=dates, columns=[symbol])
    exits = pd.DataFrame(False, index=dates, columns=[symbol])
    entries.iloc[0] = True
    return SignalIntent(entries=entries, exits=exits)

```

### `src\pql\signals\momentum_rotation.py`

```python
"""M5.1 ETF Momentum Rotation signal (long-only, monthly rebalance).

Relative momentum = close_adj.pct_change(momentum_days) (<= T data only).
Absolute-momentum filter: momentum > 0. Optional MA filter: close_adj > MA(ma_filter)
when ma_filter > 0 (0 = disabled). Rolling windows use <= T data (never centered).

Rebalance contract (D6): the FIRST actual trading day of each calendar month,
derived from the research and trading dates — never a fixed 21-day cycle or
month-end.

On a rebalance day the full target vector is written: rank eligible assets by
momentum DESCENDING (tie-break: canonical symbol ASCENDING), keep the top
effective_k = min(top_k, risk.max_positions), equal weight 1/K, others 0. If no
asset is eligible the target is 100% cash (all weights 0). Non-rebalance rows
are NaN (hold current allocation, no forced rebalance).

Outputs a TargetWeightIntent so the engine routes it through from_orders
(targetpercent, cash_sharing, group_by, Execution Revaluation) per D10.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..backtest.engine import TargetWeightIntent


class MomentumError(ValueError):
    """Raised for invalid momentum signal inputs."""


def first_trading_day_of_month(dates) -> list[pd.Timestamp]:
    """First actual trading day of each calendar month, in ascending order.
    Accepts any iterable (including a set); the input is sorted first."""
    s = pd.Series(pd.to_datetime(pd.Series(sorted(dates))).dt.normalize())
    s = s.drop_duplicates().sort_values()
    ym = s.dt.strftime("%Y-%m")
    first = s.groupby(ym).first()
    return [pd.Timestamp(d) for d in first.tolist()]


def momentum_rotation_signal(
    research: pd.DataFrame,
    *,
    calendar_dates,
    momentum_days: int,
    ma_filter: int = 0,
    top_k: int = 2,
    max_positions: int | None = None,
    rebalance_days: list | None = None,
) -> TargetWeightIntent:
    """Build a monthly Top-K equal-weight TargetWeightIntent from a research
    frame ([date, symbol, close_adj]). Point-in-time: every decision at T uses
    only data <= T.

    Rebalance SCHEDULE is derived from the authoritative Snapshot trading
    calendar (calendar_dates), not from the price data: the first actual trading
    day of each calendar month is the scheduled rebalance day, exactly as frozen.
    A scheduled day with no price data simply cannot execute (the weight row for
    that date is dropped by the engine) — it is never silently redefined as the
    next available price day.

    `rebalance_days` (optional) overrides the schedule (K06 shift_rebalance
    passes a schedule shifted by one actual trading day; the decision at each
    shifted day regenerates targets using only data <= that day)."""
    if momentum_days < 1:
        raise MomentumError(f"momentum_days must be >= 1, got {momentum_days}")
    if ma_filter < 0:
        raise MomentumError(f"ma_filter must be >= 0, got {ma_filter}")
    if top_k < 1:
        raise MomentumError(f"top_k must be >= 1, got {top_k}")

    df = research[["date", "symbol", "close_adj"]]
    pivot = df.pivot(index="date", columns="symbol", values="close_adj").sort_index()
    # deterministic column order (canonical symbol ascending) for tie-breaks
    pivot = pivot[np.sort(pivot.columns)]

    momentum = pivot.pct_change(momentum_days)
    eligible = momentum > 0
    if ma_filter > 0:
        ma = pivot.rolling(ma_filter, min_periods=ma_filter).mean()
        eligible = eligible & (pivot > ma)

    effective_k = min(top_k, max_positions) if max_positions else top_k
    # schedule from the CALENDAR; only dates with prices can actually rebalance
    if rebalance_days is None:
        rebal = [d for d in first_trading_day_of_month(calendar_dates) if d in pivot.index]
    else:
        rebal = [pd.Timestamp(d) for d in rebalance_days if pd.Timestamp(d) in pivot.index]

    weights = pd.DataFrame(np.nan, index=pivot.index, columns=pivot.columns)
    for d in rebal:
        m = momentum.loc[d]
        elig = eligible.loc[d]
        sel = m[elig]
        row = pd.Series(0.0, index=pivot.columns)
        if sel.empty:
            weights.loc[d, row.index] = row  # 100% cash
            continue
        # momentum DESCENDING; ties broken by canonical symbol ASCENDING (the
        # pivot columns are pre-sorted by symbol and the sort is stable).
        ranked = sel.sort_values(ascending=False, kind="stable")
        picks = ranked.head(effective_k).index
        row[picks] = 1.0 / len(picks)
        weights.loc[d, row.index] = row

    return TargetWeightIntent(weights=weights)


__all__ = ["MomentumError", "first_trading_day_of_month", "momentum_rotation_signal"]
```

### `src\pql\signals\registry.py`

```python
"""Signal dispatch (M4). Maps a StrategySpec.signal kind + effective params to
a concrete TradingIntent. Kept here so the experiment runner and the
deterministic validator reproduce the SAME signal from the SAME inputs.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from pql.schemas import StrategySpec

from ..backtest.api import TradingIntent
from .buy_hold import buy_hold_signal
from .momentum_rotation import momentum_rotation_signal
from .trend_ma import trend_ma_signal


class SignalBuildError(ValueError):
    """Raised for an unknown signal kind or invalid signal inputs."""


def effective_params(spec: StrategySpec, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Signal params = spec defaults merged with CLI overrides (validated against
    param_grid by the runner). Excludes the `kind` discriminator."""
    base = {k: v for k, v in (spec.signal or {}).items() if k != "kind"}
    base.update(overrides or {})
    return base


def build_signal(spec: StrategySpec, research: pd.DataFrame,
                 params: dict[str, Any], calendar_dates=None) -> TradingIntent:
    """Build the TradingIntent for a spec using the given effective params and a
    point-in-time research frame. SignalIntent kinds route to from_signals /
    equal-weight orders; momentum_rotation is a TargetWeightIntent (monthly
    Top-K rotation) routed to from_orders targetpercent. `calendar_dates` is the
    authoritative Snapshot trading calendar used for the momentum rebalance
    schedule."""
    kind = spec.signal.get("kind")
    if kind == "buy_hold":
        symbol = spec.signal.get("symbol", spec.universe[0])
        return buy_hold_signal(research["date"].unique(), symbol)
    if kind == "trend_ma":
        ma_period = int(params.get("ma_period"))
        max_positions = spec.risk.get("max_positions")
        return trend_ma_signal(
            research, ma_period=ma_period, max_positions=max_positions
        )
    if kind == "momentum_rotation":
        if calendar_dates is None:
            calendar_dates = research["date"]
        return momentum_rotation_signal(
            research,
            calendar_dates=calendar_dates,
            momentum_days=int(params.get("momentum_days")),
            ma_filter=int(params.get("ma_filter", 0)),
            top_k=int(params.get("top_k")),
            max_positions=spec.risk.get("max_positions"),
        )
    raise SignalBuildError(f"unknown signal kind: {kind!r}")


__all__ = ["SignalBuildError", "build_signal", "effective_params"]
```

### `src\pql\signals\trend_ma.py`

```python
"""M4.5 Trend-following signal (long-only, point-in-time).

Hypothesis-driven (D6): when the intermediate/long-term price lies above its
long moving average, the risk/reward of trend continuation / risk exposure may
be superior to unconditional holding; otherwise hold cash.

Signal (uses ONLY data <= T, never future/execution prices):
    risk_on[symbol, T] = close_adj[T] > MA(ma_period)[T]
With max_positions = K, when more than K symbols are simultaneously risk-on,
keep the K strongest by momentum strength (close_adj/MA - 1, computed at T),
truncating deterministically: ties break by canonical symbol order (the columns
are sorted before ranking, so pandas row-order cannot decide the winner).

Returns a SignalIntent whose entries/exits are the RISING EDGES of the held
set (enter when a symbol becomes held, exit when it stops being held); the
engine fills at T+execution_bar per the TimingContract.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..backtest.api import SignalIntent


def trend_momentum_strength(pivot: pd.DataFrame, ma: pd.DataFrame) -> pd.DataFrame:
    """close_adj/MA - 1 at each bar (<= T data only). warmup -> -inf."""
    strength = (pivot / ma - 1.0).where(ma.notna(), -np.inf)
    return strength


def trend_ma_signal(
    research: pd.DataFrame,
    *,
    ma_period: int,
    max_positions: int | None = None,
) -> SignalIntent:
    """Build a long-only trend SignalIntent from a research frame
    ([date, symbol, close_adj]). `ma_period > 0`; `max_positions` truncates the
    concurrent held set to the strongest K by momentum strength."""
    if ma_period < 1:
        raise ValueError(f"ma_period must be >= 1, got {ma_period}")
    df = research[["date", "symbol", "close_adj"]]
    pivot = df.pivot(index="date", columns="symbol", values="close_adj")
    pivot = pivot.sort_index()
    # Deterministic tie-break: sort columns by canonical symbol before any
    # row-order-sensitive ranking.
    cols_sorted = sorted(pivot.columns)
    pivot = pivot[cols_sorted]

    ma = pivot.rolling(ma_period, min_periods=ma_period).mean()
    risk_on = (pivot > ma).fillna(False)

    if max_positions and max_positions < len(pivot.columns):
        strength = trend_momentum_strength(pivot, ma)
        ranked = strength.rank(axis=1, method="first", ascending=False)
        held = risk_on & (ranked <= max_positions)
    else:
        held = risk_on

    entries = held & ~held.shift(1, fill_value=False)
    exits = ~held & held.shift(1, fill_value=False)
    return SignalIntent(entries=entries, exits=exits)


__all__ = ["trend_ma_signal", "trend_momentum_strength"]
```

### `src\pql\validation\__init__.py`

```python

```

### `src\pql\validation\base.py`

```python
"""M5 shared validation helpers.

A validation run builds the strategy's PIT signal ONCE over the full in-sample
research frame (momentum/MA warmup is preserved), then executes the backtest on
an arbitrary [start, end] window via the frozen run_backtest() public API. The
signal is point-in-time (every decision at T uses only data <= T), so slicing
the execution window never leaks future data.
"""
from __future__ import annotations

from itertools import product
from pathlib import Path
from typing import Any

from pql.backtest.api import run_backtest
from pql.data.dataset import DatasetView
from pql.registry.runner import resolve_paths
from pql.schemas import PortfolioConfig, load_cost_model, load_spec
from pql.signals.registry import build_signal, effective_params
from pql.timing import TimingContract


def grid_configs(spec) -> list[dict[str, Any]]:
    """Full Cartesian product of the frozen param_grid, as a list of param
    dicts (deterministic key order)."""
    keys = list(spec.param_grid.keys())
    if not keys:
        return [{}]
    return [dict(zip(keys, combo)) for combo in product(*[spec.param_grid[k] for k in keys])]


def load_context(repo_root: str | Path, strategy: str, data_root: str | Path = "data"):
    """Load the strategy spec, its referenced cost model, and the in-sample
    DatasetView."""
    repo = Path(repo_root)
    spec = load_spec(repo / "strategies" / f"{strategy}.yaml")
    paths = resolve_paths(repo, spec)
    cost = load_cost_model(paths["cost"])
    in_sample = spec.windows["in_sample"]
    ds = DatasetView.load(
        spec.dataset_version, data_root, universe=spec.universe,
        start=in_sample[0], end=in_sample[1],
    )
    return spec, cost, ds


def build_intent(spec, params: dict[str, Any], ds: DatasetView):
    """Build the PIT signal over the full in-sample research frame, using the
    snapshot's authoritative trading calendar for the rebalance schedule."""
    return build_signal(spec, ds.research_frame(), params, calendar_dates=ds.calendar_dates())


def run_window(
    spec, params: dict[str, Any], ds: DatasetView, cost, data_root: str | Path,
    start: str, end: str,
):
    """Run the strategy on [start, end] fresh-portfolio backtest, returning the
    BacktestResult (metrics computed on that window's equity)."""
    intent = build_intent(spec, effective_params(spec, params), ds)
    win = DatasetView.load(
        spec.dataset_version, data_root, universe=spec.universe, start=start, end=end,
    )
    timing = TimingContract(
        execution_bar=int(spec.timing.get("execution_bar", 1)),
        execution_price=spec.timing.get("execution_price", "close"),
    )
    portfolio = PortfolioConfig(
        init_cash=1_000_000,
        max_positions=spec.risk.get("max_positions"),
        weighting="equal",
    )
    return run_backtest(
        intent=intent, universe=spec.universe, execution_model=timing,
        cost_model=cost, portfolio_config=portfolio, dataset=win,
    )


__all__ = ["build_intent", "load_context", "run_window"]
```

### `src\pql\validation\bootstrap.py`

```python
"""M6.3 Circular Block Bootstrap (D9).

Bootstraps the CANDIDATE parameter set's in-sample DAILY RETURNS (never the
Holdout) with a circular block resampler:

    R = 1000
    seed = spec.seed
    block_len = ceil(n ** (1/3))

Each sample: pick a random block start, take block_len consecutive returns,
circularly wrap at the end, repeat and truncate to exactly n. This is NOT an
iid resample — within-block autocorrelation is preserved. Outputs the full
Sharpe / CAGR / MaxDD distributions plus p05 / p50 / p95 and a 95% CI. The
gate (bootstrap_sharpe_p05_min) uses the p05 of the Sharpe distribution.

Determinism contract: same returns + same seed -> identical distribution;
same returns + different seed -> different distribution. The full 1000 draws
are persisted as a structured artifact (bootstrap.parquet) rather than stuffed
into a Run manifest.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pql.backtest import metrics

R = 1000


def _num(v):
    return v if isinstance(v, (int, float)) and not math.isnan(v) else None


def block_len(n: int) -> int:
    return int(np.ceil(n ** (1 / 3)))


def circular_block_sample(
    returns: np.ndarray, block_len: int, rng: np.random.Generator
) -> np.ndarray:
    """One circular block bootstrap sample of the SAME length as the input.

    Repeatedly: choose a random block start, take block_len consecutive
    returns with circular wrap (index % n), concatenate, truncate to n."""
    n = len(returns)
    if n == 0:
        return np.empty(0)
    out = np.empty(n)
    i = 0
    while i < n:
        start = int(rng.integers(0, n))
        for j in range(block_len):
            if i >= n:
                break
            out[i] = returns[(start + j) % n]
            i += 1
    return out


def _sample_metrics(rets: pd.Series, b_len: int, rng) -> dict[str, float]:
    sample = circular_block_sample(rets.to_numpy(), b_len, rng)
    eq = pd.Series(np.cumprod(1.0 + sample))
    return {
        "sharpe": metrics.sharpe(eq),
        "cagr": metrics.cagr(eq),
        "max_drawdown": metrics.max_drawdown(eq),
    }


def bootstrap(spec, equity: pd.Series, out_dir: str | Path | None = None) -> dict[str, Any]:
    """Circular block bootstrap of the candidate's in-sample daily returns.

    `equity` is the candidate IS backtest equity curve. Returns a report dict
    with the distribution (persisted to bootstrap.parquet when out_dir is
    given) and the summary percentiles + 95% CI."""
    eq = pd.Series(equity).sort_index()
    rets = eq.pct_change().dropna()
    n = len(rets)
    b_len = block_len(n)
    rng = np.random.default_rng(spec.seed)

    rows: list[dict[str, float]] = []
    for _ in range(R):
        rows.append(_sample_metrics(rets, b_len, rng))
    dist = pd.DataFrame(rows)

    def _pct(series: pd.Series, q: float) -> float:
        return float(series.quantile(q))

    def _ci(series: pd.Series) -> list[float]:
        return [round(_pct(series, 0.025), 6), round(_pct(series, 0.975), 6)]

    dist_path = None
    if out_dir is not None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        dist_path = out / "bootstrap.parquet"
        dist.to_parquet(dist_path, index=False)

    summary = {
        "n": int(n),
        "block_len": int(b_len),
        "R": int(R),
        "seed": int(spec.seed),
        "sharpe": {
            "p05": _pct(dist["sharpe"], 0.05),
            "p50": _pct(dist["sharpe"], 0.5),
            "p95": _pct(dist["sharpe"], 0.95),
            "ci95": _ci(dist["sharpe"]),
        },
        "cagr": {
            "p05": _pct(dist["cagr"], 0.05),
            "p50": _pct(dist["cagr"], 0.5),
            "p95": _pct(dist["cagr"], 0.95),
            "ci95": _ci(dist["cagr"]),
        },
        "max_drawdown": {
            "p05": _pct(dist["max_drawdown"], 0.05),
            "p50": _pct(dist["max_drawdown"], 0.5),
            "p95": _pct(dist["max_drawdown"], 0.95),
            "ci95": _ci(dist["max_drawdown"]),
        },
    }
    return {
        "summary": summary,
        "distribution": dist,
        "distribution_path": str(dist_path) if dist_path else None,
    }


def bootstrap_sharpe_p05(report: dict[str, Any]) -> float:
    return float(report["summary"]["sharpe"]["p05"])


__all__ = ["R", "block_len", "bootstrap", "bootstrap_sharpe_p05", "circular_block_sample"]
```

### `src\pql\validation\deterministic.py`

```python
"""M4.4 deterministic validator (D7 / M4.25-35, proposal §20.3).

Seven checks, each PASS/FAIL, never letting a FAIL roll up to overall PASS:

    no_same_bar_fill      execution_bar >= 1 AND no order fills at a signal bar
    no_future_data        point-in-time: truncating data to T and re-running the
                          signal must match the full-data signal at T
    dataset_pinned        snapshot exists and its checksums match the run
    cost_nonzero          production fee_rate > 0
    valid_trading_dates   every filled date is in the snapshot trading calendar
    holdout_compliance    RESEARCH runs never (illegally) touch the Final Holdout
    reproducible          re-executing the same config reproduces equity/orders
                          semantically; on PASS, records semantic_result_hash

Output is written to reports/validation/<EXP>/<RUN>/deterministic.json.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from pql.data.dataset import DatasetVersionNotFound, DatasetView, SnapshotIntegrityError
from pql.registry.experiments import load_run
from pql.registry.runner import execute_run
from pql.schemas import load_spec
from pql.signals.registry import build_signal, effective_params


class ValidationError(RuntimeError):
    """Raised when a validation cannot be performed (malformed run, etc.)."""


def _read_run_artifacts(exp_root: Path, experiment_id: str, run_id: str) -> tuple[dict, Path]:
    run = load_run(exp_root, experiment_id, run_id)
    run_dir = exp_root / experiment_id / "runs" / run_id
    return run, run_dir


def _load_equity(run_dir: Path) -> pd.Series:
    df = pd.read_parquet(run_dir / "equity.parquet")
    df = df.set_index("date").sort_index()
    return df.iloc[:, 0].astype(float)


def _load_orders(run_dir: Path) -> pd.DataFrame:
    df = pd.read_parquet(run_dir / "orders.parquet")
    if df.empty:
        return df
    return df.sort_values("id").reset_index(drop=True)


def _execution_dates(ds: DatasetView) -> pd.DatetimeIndex:
    dates = pd.to_datetime(ds.execution_frame()["date"].dt.normalize()).drop_duplicates()
    return pd.DatetimeIndex(sorted(dates))


def _semantic_compare(a: pd.DataFrame, b: pd.DataFrame) -> None:
    """normalize (sort index, sort columns, uniform dtype) then
    assert_frame_equal with the frozen rtol/atol."""
    a = a.sort_index(axis=0).sort_index(axis=1)
    b = b.sort_index(axis=0).sort_index(axis=1)
    pd.testing.assert_frame_equal(a, b, rtol=1e-12, atol=1e-12)


def _semantic_result_hash(run_dir: Path) -> str:
    """sha256 over CANONICALIZED VALUES (not parquet bytes), so identical
    semantic results hash identically regardless of serialization metadata."""
    equity = _load_equity(run_dir)
    orders = _load_orders(run_dir)
    h = hashlib.sha256()
    h.update(b"equity\n")
    for date, val in equity.items():
        h.update(f"{date.isoformat()}:{val:.17g}\n".encode())
    h.update(b"orders\n")
    for row in orders.itertuples(index=False):
        h.update(
            f"{int(row.id)}:{int(row.col)}:{int(row.idx)}:{float(row.size):.17g}:"
            f"{float(row.price):.17g}:{float(row.fees):.17g}:{int(row.side)}\n".encode()
        )
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# Individual checks
# --------------------------------------------------------------------------- #


def check_no_same_bar_fill(run: dict, run_dir: Path, col: dict | None = None) -> dict:
    """Same-bar fill prevention = the frozen TimingContract (D2): execution_bar
    >= 1 guarantees the engine shifts every signal to fill no earlier than
    T+1. This check verifies the run's recorded timing contract actually holds
    (execution_bar >= 1) and that no order fills in the pre-shift bars
    (idx < execution_bar), which are the only bars a same-bar fill could occupy.

    It does NOT independently re-derive every fill's originating signal: that
    per-fill guarantee is provided by the engine's shift and independently
    verified by the `reproducible` check (which re-executes the engine with the
    same timing contract). `col` is accepted for API symmetry but not used.
    """
    eb = int(run["timing"].get("execution_bar", -1))
    if eb < 1:
        return {"status": "FAIL", "detail": f"execution_bar={eb} < 1 admits same-bar fill"}
    orders = _load_orders(run_dir)
    if not orders.empty:
        fill_early = orders["idx"] < eb
        if fill_early.any():
            return {
                "status": "FAIL",
                "detail": f"{int(fill_early.sum())} order(s) filled before the earliest "
                f"legal bar (idx<{eb}) — same-bar fill",
            }
    return {
        "status": "PASS",
        "detail": f"timing contract valid: execution_bar={eb} >= 1; no fill before bar {eb}",
    }


def _sample_dates(dates: pd.DatetimeIndex, warmup: int, k: int = 5) -> list[pd.Timestamp]:
    """Deterministic, fixed-position sample of k dates after the warmup window."""
    usable = dates[dates >= dates[min(warmup, len(dates) - 1)]]
    n = len(usable)
    if n < k:
        k = max(1, n)
    idxs = sorted({min(int(n * (i + 1) / (k + 1)), n - 1) for i in range(k)})
    return [usable[i] for i in idxs]


def check_no_future_data(
    repo_root: Path, run: dict, exp_root: Path, data_root: Path
) -> dict:
    """Truncate the research data to each sampled date T, rebuild the signal,
    and require it to equal the full-data signal at T. This actually re-invokes
    the signal function, so internal future references are exposed."""
    spec = load_spec(repo_root / "strategies" / f"{run['strategy']}.yaml")
    effective = effective_params(spec, run.get("parameters"))
    in_sample = spec.windows["in_sample"]
    ds = DatasetView.load(
        run["dataset_version"], data_root, universe=spec.universe,
        start=in_sample[0], end=in_sample[1],
    )
    research = ds.research_frame()
    full = build_signal(spec, research, effective)
    dates = sorted(pd.to_datetime(research["date"].dt.normalize()).unique())
    warmup = int(effective.get("ma_period", 1))
    sample = _sample_dates(pd.DatetimeIndex(dates), warmup)
    for t in sample:
        truncated = research[research["date"] <= t]
        sig = build_signal(spec, truncated, effective)
        for df_name, full_df, cur_df in (
            ("entries", full.entries, sig.entries),
            ("exits", full.exits, sig.exits),
        ):
            for sym in sorted(full_df.columns):
                fv = bool(full_df.loc[t, sym]) if t in full_df.index else False
                cv = bool(cur_df.loc[t, sym]) if t in cur_df.index else False
                if fv != cv:
                    return {
                        "status": "FAIL",
                        "detail": f"future-data leak at {t.date()} symbol {sym}: "
                        f"full={fv} truncated={cv}",
                    }
    return {
        "status": "PASS",
        "detail": f"signal point-in-time identical at {len(sample)} sampled dates",
    }


def check_dataset_pinned(run: dict, data_root: Path) -> dict:
    try:
        ds = DatasetView.load(run["dataset_version"], data_root)
    except (DatasetVersionNotFound, SnapshotIntegrityError) as exc:
        return {"status": "FAIL", "detail": f"dataset unpinned: {exc}"}
    manifest_files = ds.manifest().get("files", {})
    run_checksums = run.get("dataset_checksums") or {}
    if manifest_files != run_checksums:
        return {
            "status": "FAIL",
            "detail": "snapshot checksums no longer match the run's recorded provenance",
        }
    return {
        "status": "PASS",
        "detail": f"dataset_pinned={run['dataset_version']} checksums match",
    }


def check_cost_nonzero(run: dict) -> dict:
    fee = float((run.get("cost_config") or {}).get("fee_rate", 0.0))
    if fee <= 0:
        return {"status": "FAIL", "detail": f"fee_rate={fee} <= 0 (production costs must be > 0)"}
    return {"status": "PASS", "detail": f"fee_rate={fee} > 0"}


def check_valid_trading_dates(run: dict, run_dir: Path, data_root: Path) -> dict:
    ds = DatasetView.load(run["dataset_version"], data_root)
    calendar = ds.calendar_dates()
    dates = _execution_dates(ds)
    orders = _load_orders(run_dir)
    if orders.empty:
        return {"status": "PASS", "detail": "no orders to validate"}
    bad: list[str] = []
    for row in orders.itertuples():
        idx = int(row.idx)
        if idx >= len(dates):
            bad.append(f"idx={idx} out of range")
            continue
        d = dates[idx]
        if d not in calendar:
            bad.append(f"{d.date()} (idx {idx}) not in trading calendar")
    if bad:
        return {"status": "FAIL", "detail": "; ".join(bad[:10])}
    return {"status": "PASS", "detail": f"all {len(orders)} fills on trading calendar days"}


def check_holdout_compliance(run: dict, data_root: Path, repo_root: Path) -> dict:
    spec = load_spec(repo_root / "strategies" / f"{run['strategy']}.yaml")
    allowed = bool((spec.research_budget.get("holdout_access") or {}).get("allowed", False))
    log = Path(data_root) / "metadata" / "holdout_access.log"
    accesses = 0
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("strategy") == run["strategy"]:
                accesses += 1
    if not allowed and accesses > 0:
        return {
            "status": "FAIL",
            "detail": f"holdout_access.allowed=false but {accesses} access(es) recorded for "
            f"{run['strategy']}",
        }
    return {
        "status": "PASS",
        "detail": f"holdout_access.allowed={allowed}, accesses recorded={accesses}",
    }


def check_reproducible(col: dict | None, run: dict, run_dir: Path) -> dict:
    if col is None:
        return {"status": "FAIL", "detail": "re-execution failed"}

    result = col["result"]
    # equity: stored [date,group] vs rerun Series
    stored_eq = _load_equity(run_dir)
    rerun_eq_series = pd.Series(result.equity).sort_index().astype(float)
    try:
        _semantic_compare(stored_eq.to_frame("nav"), rerun_eq_series.to_frame("nav"))
    except AssertionError as exc:
        return {"status": "FAIL", "detail": f"equity divergence: {exc}"}

    stored_orders = _load_orders(run_dir)
    rerun_orders = result.orders.reset_index(drop=True) if result.orders is not None and len(
        result.orders
    ) else pd.DataFrame()
    if not stored_orders.empty and not rerun_orders.empty:
        sel = ["col", "idx", "size", "price", "fees", "side"]
        try:
            _semantic_compare(
                stored_orders[sel].astype(float), rerun_orders[sel].astype(float)
            )
        except AssertionError as exc:
            return {"status": "FAIL", "detail": f"orders divergence: {exc}"}
    elif stored_orders.empty != rerun_orders.empty:
        return {"status": "FAIL", "detail": "order count divergence"}

    ref_hash = run.get("semantic_result_hash", "")
    now_hash = _semantic_result_hash(run_dir)
    return {
        "status": "PASS",
        "detail": f"reproducible; semantic_result_hash={now_hash}",
        "semantic_result_hash": now_hash,
        "hash_matches_recorded": bool(ref_hash) and ref_hash == now_hash,
    }


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

_ALL = [
    "no_same_bar_fill",
    "no_future_data",
    "dataset_pinned",
    "cost_nonzero",
    "valid_trading_dates",
    "holdout_compliance",
    "reproducible",
]


def validate_run(
    repo_root: str | Path,
    experiments_root: str | Path,
    experiment_id: str,
    run_id: str,
    data_root: str | Path = "data",
    report_root: str | Path = "reports",
    persist: bool = True,
) -> dict:
    """Run all seven checks for one Run. Returns the report dict; when persist,
    writes reports/validation/<EXP>/<RUN>/deterministic.json."""
    exp_root = Path(experiments_root)
    run, run_dir = _read_run_artifacts(exp_root, experiment_id, run_id)
    repo = Path(repo_root)
    data = Path(data_root)

    # Re-execute the run ONCE, sharing it between the signal-aware same-bar
    # check and the reproducibility check (single engine call).
    try:
        col = execute_run(
            repo_root_path=repo, strategy=run["strategy"],
            params=run.get("parameters"), data_root=data,
        )
    except Exception:  # noqa: BLE001 - surfaces as reproducible FAIL
        col = None

    checks = {
        "no_same_bar_fill": check_no_same_bar_fill(run, run_dir, col),
        "no_future_data": check_no_future_data(repo, run, exp_root, data),
        "dataset_pinned": check_dataset_pinned(run, data),
        "cost_nonzero": check_cost_nonzero(run),
        "valid_trading_dates": check_valid_trading_dates(run, run_dir, data),
        "holdout_compliance": check_holdout_compliance(run, data, repo),
    }
    checks["reproducible"] = check_reproducible(col, run, run_dir)

    overall = "PASS" if all(c["status"] == "PASS" for c in checks.values()) else "FAIL"

    report = {
        "experiment_id": experiment_id,
        "run_id": run_id,
        "strategy": run.get("strategy"),
        "overall": overall,
        "checks": checks,
    }
    if persist:
        from pql.registry.experiments import _yaml_write

        # Persist the semantic_result_hash into the run.yaml source of truth once
        # reproducibility passes (M4.34).
        repro = checks["reproducible"]
        if (
            repro.get("status") == "PASS"
            and repro.get("semantic_result_hash")
            and not run.get("semantic_result_hash")
        ):
            run["semantic_result_hash"] = repro["semantic_result_hash"]
            _yaml_write(run_dir / "run.yaml", run)
        out = Path(report_root) / "validation" / experiment_id / run_id / "deterministic.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["report_path"] = str(out)
    return report


__all__ = ["_ALL", "ValidationError", "validate_run"]
```

### `src\pql\validation\final.py`

```python
"""M6.8 Final Holdout validation (`pql validate final`).

The ONLY post-freeze validation. It verifies the Candidate Freeze fingerprint
against the current files, then consumes the Final Holdout exactly once (via
HoldoutGuard, fail-closed), runs the FROZEN candidate, computes holdout-only
metrics, and applies the D9 `final` gate (holdout_min_sharpe).

Absent by design: stress, bootstrap, DSR, kill, parameter search, re-training.
Final reports holdout-only sections; the IS / walk-forward / stress / bootstrap
/ DSR / kill content from the candidate report is NOT copied here.

Boundary state: the frozen strategy is run over the full [IS_start, holdout_end]
range (signal built PIT over IS+released-holdout research so MA/momentum warmup
uses legal pre-holdout history), then ONLY the holdout window's equity is
scored. This preserves the real portfolio state at the holdout boundary instead
of cold-starting at cash (PLAN_CLARIFICATION M6-005: no cold start).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from pql.backtest.api import run_backtest
from pql.data.dataset import DatasetView
from pql.registry.experiments import (
    next_experiment_id,
    selection_key,
    write_manifest,
    write_run,
)
from pql.registry.holdout import HoldoutError, HoldoutGuard
from pql.registry.provenance import dependency_versions, git_state
from pql.registry.runner import resolve_paths
from pql.schemas import PortfolioConfig, load_cost_model, load_spec
from pql.signals.registry import build_signal, effective_params
from pql.timing import TimingContract

from .freeze import compute_freeze_payload, verify_freeze


class FinalValidationError(RuntimeError):
    """Raised for final-validation failures (not frozen, freeze mismatch, ...)."""


def _num(v):
    return v if isinstance(v, (int, float)) and not math.isnan(v) else None


def _holdout_scoring_window(res, holdout_start: str, holdout_end: str):
    """Derive a CONSISTENT holdout scoring window from the full backtest result
    (which spans [IS_start, holdout_end]).

    - hol_equity: boundary-anchored equity — [last pre-holdout NAV] + holdout
      NAVs. Prepending the anchor means the FIRST holdout return (boundary ->
      day 1) is scored (a naive slice loses it: pct_change turns day 1 into
      NaN). CAGR is measured from the boundary anchor, so IS performance never
      enters the holdout metrics (review P0-2).
    - hol_orders: orders whose fill date is inside the holdout window, RE-INDEXED
      to the local holdout index so D8 turnover computes correctly.
    - hol_trades: closed trades whose exit date is inside the holdout window.
    - hol_asset: asset-value aligned to the holdout dates (for exposure).
    - hol_dates: the holdout trading dates.
    """
    full_equity = pd.Series(res.equity).sort_index()
    full_dates = full_equity.index
    hol_start = pd.Timestamp(holdout_start).normalize()
    hol_end = pd.Timestamp(holdout_end).normalize()

    pre = full_dates[full_dates < hol_start]
    anchor_date = pre[-1] if len(pre) else full_dates[0]
    anchor_nav = full_equity.loc[anchor_date]
    hol_dates = full_dates[(full_dates >= hol_start) & (full_dates <= hol_end)]
    hol_equity = pd.concat(
        [pd.Series([anchor_nav], index=[anchor_date]), full_equity.loc[hol_dates]]
    )

    # orders -> holdout, re-indexed to the local holdout index
    orders = res.orders
    hol_orders = orders
    if orders is not None and len(orders):
        full_idx_to_date = {int(i): d for i, d in enumerate(full_dates)}
        local_idx = {d: j for j, d in enumerate(hol_dates)}
        keep = []
        new_idx = []
        for o in orders.itertuples():
            d = full_idx_to_date.get(int(o.idx))
            if d is not None and hol_start <= d <= hol_end:
                keep.append(True)
                new_idx.append(local_idx[d])
            else:
                keep.append(False)
        hol_orders = orders[keep].copy()
        hol_orders["idx"] = new_idx

    # trades exiting in the holdout window
    trades = res.run_meta.get("trades")
    hol_trades = trades
    if trades is not None and len(trades):
        exit_keep = []
        for t in trades.itertuples():
            exit_idx = int(t.exit_idx)
            d = full_dates[exit_idx] if exit_idx < len(full_dates) else hol_end
            exit_keep.append(hol_start <= d <= hol_end)
        hol_trades = trades[exit_keep]

    # asset value aligned to holdout dates (exposure)
    asset_value = res.run_meta.get("asset_value")
    hol_asset = None
    if asset_value is not None:
        hol_asset = pd.Series(asset_value).sort_index().reindex(hol_dates)

    return hol_equity, hol_orders, hol_trades, hol_asset, hol_dates


class _CombinedView:
    """Read-only DatasetView-like wrapper spanning IS (freely accessible) plus
    the guard-RELEASED holdout window. The engine reads execution_frame() only;
    the signal reads research_frame(). Holdout data was released by HoldoutGuard
    (consumed once) before this view is built — the final validator never loads
    holdout data directly."""

    def __init__(self, is_view: DatasetView, holdout_view: DatasetView) -> None:
        self.is_view = is_view
        self.holdout_view = holdout_view
        self.version = is_view.version
        self.data_root = is_view.data_root

    def manifest(self) -> dict:
        return self.is_view.manifest()

    def calendar_dates(self):
        return self.is_view.calendar_dates() | self.holdout_view.calendar_dates()

    def research_frame(self) -> pd.DataFrame:
        return pd.concat([self.is_view.research_frame(), self.holdout_view.research_frame()],
                         ignore_index=True).reset_index(drop=True)

    def execution_frame(self) -> pd.DataFrame:
        return pd.concat([self.is_view.execution_frame(), self.holdout_view.execution_frame()],
                         ignore_index=True).reset_index(drop=True)

    def amount_frame(self) -> pd.DataFrame:
        return pd.concat([self.is_view.amount_frame(), self.holdout_view.amount_frame()],
                         ignore_index=True).reset_index(drop=True)


def _final_gate(repo_root, holdout_sharpe):
    import yaml

    gates = yaml.safe_load(
        (Path(repo_root) / "config" / "validation_gates.yaml").read_text(encoding="utf-8")
    ) or {}
    final = gates.get("final") or {}
    thr = _num(final.get("holdout_min_sharpe"))
    return {
        "threshold": thr,
        "holdout_sharpe": holdout_sharpe,
        "pass": holdout_sharpe is not None and (thr is None or holdout_sharpe >= thr),
    }


def validate_final(
    repo_root: str | Path,
    strategy: str,
    *,
    data_root: str | Path = "data",
    report_root: str | Path = "reports",
    experiments_root: str | Path = "experiments",
    registry_path: str | Path = "strategy_registry.yaml",
    caller: str = "validate_final",
) -> dict[str, Any]:
    """Run the Final Holdout validation. Returns the final report (persisted to
    reports/validation/<strategy>/final_report.json)."""
    repo = Path(repo_root)
    spec = load_spec(repo / "strategies" / f"{strategy}.yaml")
    paths = resolve_paths(repo, spec)
    cost = load_cost_model(paths["cost"])
    params = effective_params(spec, None)
    holdout_start, holdout_end = spec.windows["holdout"]
    is_start = spec.windows["in_sample"][0]

    guard = HoldoutGuard(registry_path, data_root)

    # 1) verify the candidate is frozen and the fingerprint still matches the
    #    current files BEFORE consuming the holdout (a mismatch must NOT consume
    #    the holdout, per D5/M6).
    try:
        frozen = guard.frozen_freeze(strategy)
    except HoldoutError as exc:
        raise FinalValidationError(str(exc)) from exc
    actual = compute_freeze_payload(repo, experiments_root, spec)
    try:
        verify_freeze(frozen, actual)
    except Exception as exc:
        raise FinalValidationError(f"freeze mismatch: {exc}") from exc
    candidate_hash = str(frozen.get("candidate_hash") or "")

    # 2) fail-closed consumption: consumed=true is persisted BEFORE data release.
    try:
        holdout_view = guard.holdout_slice(
            strategy, spec.dataset_version, holdout_start, holdout_end,
            caller=caller, purpose="final_holdout", as_view=True,
        )
    except HoldoutError as exc:
        raise FinalValidationError(str(exc)) from exc

    # 3) run the FROZEN candidate over [IS_start, holdout_end]; boundary state
    #    preserved, holdout scored only from holdout_start.
    is_view = DatasetView.load(
        spec.dataset_version, data_root, universe=spec.universe,
        start=is_start, end=spec.windows["in_sample"][1],
    )
    combined = _CombinedView(is_view, holdout_view)
    intent = build_signal(spec, combined.research_frame(), params,
                          calendar_dates=combined.calendar_dates())
    timing = TimingContract(
        execution_bar=int(spec.timing.get("execution_bar", 1)),
        execution_price=spec.timing.get("execution_price", "close"),
    )
    portfolio = PortfolioConfig(
        init_cash=1_000_000, max_positions=spec.risk.get("max_positions"), weighting="equal",
    )
    res = run_backtest(
        intent=intent, universe=spec.universe, execution_model=timing,
        cost_model=cost, portfolio_config=portfolio, dataset=combined,
    )
    from pql.backtest.metrics import compute_metrics

    hol_equity, hol_orders, hol_trades, hol_asset, hol_dates = _holdout_scoring_window(
        res, holdout_start, holdout_end
    )
    hol_metrics = compute_metrics(
        hol_equity, orders=hol_orders, trades=hol_trades,
        asset_value=hol_asset, dates=hol_dates,
    )

    gate = _final_gate(repo, _num(hol_metrics.get("sharpe")))
    overall = "PASS" if gate["pass"] else "FAIL"

    # 4) write a FINAL_HOLDOUT run to the ledger (never adds to N).
    exp_id = next_experiment_id(experiments_root)
    write_manifest(
        experiments_root, experiment_id=exp_id, strategy=strategy,
        research_question=f"final holdout validation: {strategy}",
        experiment_config={"purpose": "final_holdout", "candidate_hash": candidate_hash},
    )
    gate_state = git_state(experiments_root)
    import yaml as _yaml

    _gates = _yaml.safe_load((repo / "config" / "validation_gates.yaml").read_text(encoding="utf-8")) or {}
    gate_version = str(_gates.get("version", ""))
    run_dir = write_run(
        experiments_root=experiments_root,
        experiment_id=exp_id,
        strategy=strategy,
        parameters=dict(params),
        selection_key=selection_key(params),
        run_kind="FINAL_HOLDOUT",
        visible_to_researcher=True,
        dataset_version=spec.dataset_version,
        dataset_checksums=is_view.manifest().get("files", {}),
        market_rule_version=spec.market_rule_version,
        cost_model_version=spec.cost_model_version,
        cost_config={"version": cost.version, "fee_rate": cost.fee_rate,
                     "slippage": cost.slippage},
        gate_version=gate_version,
        gate=gate_state,
        config_sha256="",
        dependencies=dependency_versions(),
        seed=spec.seed,
        timing={"execution_bar": timing.execution_bar, "execution_price": timing.execution_price},
        metrics=dict(hol_metrics),
        equity=hol_equity,
        orders=hol_orders,
    )

    from datetime import datetime

    report = {
        "strategy": strategy,
        "candidate_hash": candidate_hash,
        "freeze_fingerprint": {k: frozen.get(k) for k in (
            "candidate_hash", "spec_sha256", "code_commit", "parameters",
            "gate_version", "gate_config_sha256", "cost_config_sha256",
            "market_rule_sha256", "instrument_sha256", "uv_lock_sha256",
            "dataset_version", "created",
        )},
        "dataset_version": spec.dataset_version,
        "dataset_source": is_view.manifest().get("source", ""),
        "market_evidence": is_view.manifest().get("source", "") != "synthetic",
        "holdout_start": holdout_start,
        "holdout_end": holdout_end,
        "holdout_metrics": {k: v for k, v in hol_metrics.items()},
        "holdout_gate": gate,
        "overall": overall,
        "final_run_ref": f"{exp_id}/{run_dir.name}",
        "holdout_access": {
            "consumed": True,
            "candidate_hash": candidate_hash,
        },
        "created": datetime.now().astimezone().isoformat(timespec="seconds"),
    }

    out = Path(report_root) / "validation" / strategy / "final_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    report["report_path"] = str(out)
    return report


__all__ = ["FinalValidationError", "validate_final"]
```

### `src\pql\validation\freeze.py`

```python
"""M6.7 Candidate Freeze (D6). The narrow RESEARCH -> CANDIDATE promotion path.

Candidate Freeze locks spec hash, code commit, parameter set, gate version +
versioned-config hashes, uv.lock and dataset version into the registry's
`candidate_freeze` block. `candidate_hash` binds ALL of them (a canonical,
key-sorted, UTF-8 serialization hashed with SHA256) — it is NOT just spec_sha256.

Freeze is EXPLICIT only (`pql gate promote --to CANDIDATE`), never automatic
after `pql validate candidate`. A candidate that fails any gate, has dirty code,
or a stale report is refused (FreezeError). Once frozen, any change to the
frozen payload requires a NEW strategy version; the freeze is never auto-updated.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pql.lifecycle import find_strategy
from pql.registry.provenance import config_hashes, git_state
from pql.registry.runner import resolve_paths
from pql.schemas import load_spec
from pql.signals.registry import effective_params


class FreezeError(RuntimeError):
    """Raised when candidate freeze preconditions are not met."""


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _canonical_json(data: Any) -> str:
    """Stable canonical serialization: sort keys, compact separators, UTF-8."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _gate_version(repo_root: Path) -> str:
    import yaml

    data = yaml.safe_load((repo_root / "config" / "validation_gates.yaml").read_text(encoding="utf-8")) or {}
    return str(data.get("version", ""))


# Reproducible strategy implementation scope: the `src/` package that produces
# the strategy's signals/backtests. Config/spec files (config/, strategies/)
# are individually bound by their own hashes (spec_sha256, gate/cost/market/
# instrument hashes), so they are NOT re-hashed here. Evidence outputs
# (reports/, experiments/) are not part of the code tree, so an evidence-only
# commit never changes code_tree_sha256 (a whole-HEAD code_commit would — that
# is the self-invalidation the reviewer flagged).
_CODE_SCOPE = ("src",)


def code_tree_sha256(repo_root: str | Path) -> str:
    """SHA256 over the strategy implementation code tree (`src/`, .py files),
    stable across evidence-only commits. Any change to the strategy code
    (engine/signals/validation/…) changes it."""
    repo = Path(repo_root)
    files: dict[str, str] = {}
    for scope in _CODE_SCOPE:
        base = repo / scope
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix == ".py" and "__pycache__" not in p.parts:
                files[p.relative_to(repo).as_posix()] = _file_sha256(p)
    return _sha256_bytes(_canonical_json(files).encode("utf-8"))


def _binding_payload(repo_root: str | Path, spec) -> dict[str, Any]:
    """The STABLE freeze binding payload (everything that must not change between
    candidate validation and freeze, and must not change after freeze). Evidence
    outputs are excluded. The SAME payload is recorded in the candidate report
    as `validation_fingerprint`, so a freeze can never silently bind an
    environment the candidate was never validated against (review P1-3)."""
    repo = Path(repo_root)
    paths = resolve_paths(repo, spec)
    cfg = config_hashes(
        paths["spec"], paths["gates"], paths["cost"], paths["market"],
        paths["instruments"],
    )
    per_file = cfg["per_file"]
    spec_sha = per_file.get(str(paths["spec"]), "")
    gate_sha = per_file.get(str(paths["gates"]), "")
    cost_sha = per_file.get(str(paths["cost"]), "")
    market_sha = per_file.get(str(paths["market"]), "")

    inst_map = {
        p.split("instruments")[-1].lstrip("/\\"): sha
        for p, sha in per_file.items()
        if "instruments" in p
    }
    inst_sha = _sha256_bytes(_canonical_json(inst_map).encode("utf-8"))
    uv_lock = repo / "uv.lock"
    uv_lock_sha = _file_sha256(uv_lock) if uv_lock.exists() else ""

    return {
        "spec_sha256": spec_sha,
        "code_tree_sha256": code_tree_sha256(repo),
        "parameters": dict(effective_params(spec, None)),
        "gate_version": _gate_version(repo),
        "gate_config_sha256": gate_sha,
        "cost_config_sha256": cost_sha,
        "market_rule_sha256": market_sha,
        "instrument_sha256": inst_sha,
        "uv_lock_sha256": uv_lock_sha,
        "dataset_version": spec.dataset_version,
    }


def validation_fingerprint(repo_root: str | Path, spec) -> dict[str, Any]:
    """The stable binding payload the candidate report records at validation
    time and the freeze re-verifies at promotion. Because both sides use the
    identical payload, the freeze can never bind an environment the candidate
    was never validated against."""
    return _binding_payload(Path(repo_root), spec)


def compute_freeze_payload(
    repo_root: str | Path, experiments_root: str | Path, spec
) -> dict[str, Any]:
    """Compute the full freeze fingerprint + candidate_hash for a spec."""
    repo = Path(repo_root)
    binding = _binding_payload(repo, spec)
    code = git_state(experiments_root)
    payload = dict(binding)
    # code_commit is informational provenance (the HEAD at freeze time); it is
    # NOT part of the stability binding, because evidence-only commits bump HEAD
    # without changing the code tree.
    payload["code_commit"] = code.commit
    # candidate_hash binds the STABLE binding payload (which includes the code
    # tree), not the whole-HEAD code_commit, so committing evidence afterwards
    # does not invalidate the freeze.
    candidate_hash = _sha256_bytes(_canonical_json(binding).encode("utf-8"))
    payload["candidate_hash"] = candidate_hash
    payload["created"] = _now()
    return payload


_BIND_KEYS = (
    "spec_sha256", "code_tree_sha256", "parameters", "gate_version",
    "gate_config_sha256", "cost_config_sha256", "market_rule_sha256",
    "instrument_sha256", "uv_lock_sha256", "dataset_version",
)


def verify_report_provenance(report: dict, payload: dict) -> None:
    """The candidate report's `validation_fingerprint` (recorded at validation
    time from the SAME binding payload the freeze uses) must match the current
    environment. Because both sides use the identical binding payload, every
    field (spec, code tree, params, gate, cost, market, instrument, uv.lock,
    dataset) is covered — no per-field checklist to forget (review P1-3)."""
    vf = report.get("validation_fingerprint")
    if not isinstance(vf, dict):
        raise FreezeError(
            "candidate report missing validation_fingerprint; "
            "regenerate the report before freezing"
        )
    for k in _BIND_KEYS:
        if vf.get(k) != payload.get(k):
            raise FreezeError(
                f"candidate report validation_fingerprint.{k} does not match the "
                "current environment; regenerate the report before freezing"
            )


def promote_to_candidate(
    repo_root: str | Path,
    strategy: str,
    *,
    approver: str,
    reason: str,
    registry_path: str | Path,
    report_root: str | Path = "reports",
    experiments_root: str | Path = "experiments",
    data_root: str | Path = "data",
) -> dict[str, Any]:
    """Explicit RESEARCH -> CANDIDATE promotion with Candidate Freeze.

    Preconditions (all must hold, else FreezeError):
        - strategy registered and in state RESEARCH
        - latest candidate_report overall == PASS
        - ready_for_candidate_freeze == true
        - code_dirty == false
        - report provenance still matches the current frozen files
    """
    repo = Path(repo_root)
    entry = find_strategy(registry_path, strategy)
    if entry is None:
        raise FreezeError(f"strategy not registered: {strategy}")
    if entry.get("state") != "RESEARCH":
        raise FreezeError(
            f"candidate freeze requires state RESEARCH, got {entry.get('state')}"
        )
    if not approver or approver in ("ai", "agent"):
        raise FreezeError("candidate freeze requires a human approver")

    report_path = Path(report_root) / "validation" / strategy / "candidate_report.json"
    if not report_path.exists():
        raise FreezeError(f"candidate report not found: {report_path}")
    import json as _json

    report = _json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("overall") != "PASS":
        raise FreezeError(f"candidate overall is {report.get('overall')!r}; not PASS")
    if not report.get("ready_for_candidate_freeze"):
        raise FreezeError("ready_for_candidate_freeze is false; freeze refused")

    spec = load_spec(repo / "strategies" / f"{strategy}.yaml")
    payload = compute_freeze_payload(repo, experiments_root, spec)
    verify_report_provenance(report, payload)

    # Re-check the CURRENT clean state (not the stale report flag): a worktree
    # that became dirty after validation must refuse the freeze (D9
    # require_code_clean). Evidence-only reports//experiments/ are outside the
    # dirty scope, so this does not reintroduce evidence self-invalidation.
    current_code = git_state(experiments_root)
    if current_code.code_dirty:
        raise FreezeError("current code is dirty; candidate freeze refused")

    # Single atomic registry mutation: RESEARCH -> CANDIDATE + history +
    # candidate_freeze in ONE write (review P2-5), so a crash cannot leave
    # state=CANDIDATE without a candidate_freeze block.
    from pql import lifecycle as _lc

    reg_path = Path(registry_path)
    registry = _lc._load_registry(reg_path)
    entry = next((e for e in registry["strategies"] if e.get("id") == strategy), None)
    if entry is None:
        raise FreezeError(f"strategy not registered: {strategy}")
    if entry.get("state") != "RESEARCH":
        raise FreezeError(
            f"candidate freeze requires state RESEARCH, got {entry.get('state')}"
        )
    if not _lc.is_legal_transition(_lc.State("RESEARCH"), _lc.State("CANDIDATE")):
        raise FreezeError("illegal transition RESEARCH -> CANDIDATE")
    hist_entry = {
        "from": "RESEARCH",
        "to": "CANDIDATE",
        "time": _lc._now(),
        "reason": reason,
        "evidence": str(report_path),
        "approver": approver,
    }
    entry["history"] = list(entry["history"]) + [hist_entry]
    entry["state"] = "CANDIDATE"
    entry["candidate_freeze"] = {k: v for k, v in payload.items()}
    _lc._write_registry(reg_path, registry)
    _lc._append_audit(reg_path, {"strategy_id": strategy, **hist_entry})
    return {"strategy": strategy, "candidate_freeze": payload}


def verify_freeze(freeze: dict, actual: dict) -> None:
    """Verify a stored freeze against the current fingerprint. ANY mismatch on
    a frozen item raises FreezeError ('Frozen candidate changed'). Component
    keys are checked first for a precise message, then the aggregate
    candidate_hash last. `code_commit` (whole HEAD) is intentionally NOT a
    binding key: evidence-only commits bump HEAD without changing the code."""
    for key in (
        "spec_sha256", "code_tree_sha256", "parameters", "gate_config_sha256",
        "cost_config_sha256", "market_rule_sha256", "instrument_sha256",
        "uv_lock_sha256", "dataset_version",
    ):
        if freeze.get(key) != actual.get(key):
            raise FreezeError(
                f"Frozen candidate changed ({key}). Create a new strategy version."
            )
    if freeze.get("candidate_hash") != actual.get("candidate_hash"):
        raise FreezeError(
            "Frozen candidate changed (candidate_hash). Create a new strategy version."
        )


__all__ = [
    "FreezeError",
    "code_tree_sha256",
    "compute_freeze_payload",
    "promote_to_candidate",
    "validation_fingerprint",
    "verify_freeze",
]
```

### `src\pql\validation\kill.py`

```python
"""M6.5 Kill Test Families (D9 applied; proposal §16.9).

Eight frozen families, each narrowed to a small set of gate-relevant variants:

    K01 drop_best_year        remove the highest-annual-return natural year
    K02 drop_best_trades      top winning trades (ATTRIBUTION + COUNTERFACTUAL)
    K03 universe_loo          drop each universe symbol, full rerun
    K04 delay_execution       execution_bar + 1 (decision unchanged)
    K05 cost_x2               apply_stress(cost, 2)
    K06 shift_rebalance       decision/rebalance schedule shifted 1 trading day
    K07 perturb_params        numeric research params -10% / +10% (deterministic)
    K08 shift_start           start shifted +60 trading days (Snapshot Calendar)

Variant KILLED definition (frozen): cagr <= 0 AND sharpe <= 0 (AND, not OR).
Family aggregation (PLAN_CLARIFICATION M6-003): family_result = KILLED if ANY
gate-relevant child variant is KILLED; killed_fraction = killed gate-relevant
variants / gate-relevant variants. K02 ATTRIBUTION mode is diagnostic only and
NOT gate-relevant (M6-003). The candidate gate counts KILLED FAMILIES
(max_kill_families_killed), never killed child variants.

K07 perturbed params may fall OUTSIDE the frozen param_grid by design (they are
Kill/Stress, not SELECT): they consume no research budget, add no trial N, and
never modify the StrategySpec.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from pql.backtest.api import run_backtest
from pql.backtest.costs import apply_stress
from pql.backtest.engine import ExecutionPerturbation
from pql.data.dataset import DatasetView
from pql.schemas import PortfolioConfig
from pql.signals.momentum_rotation import (
    first_trading_day_of_month,
    momentum_rotation_signal,
)
from pql.signals.registry import build_signal, effective_params
from pql.timing import TimingContract

KILL_FAMILIES = [
    "K01", "K02", "K03", "K04", "K05", "K06", "K07", "K08",
]
K02_ATTRIBUTION_RELEVANT = False  # attribution is diagnostic, not gate-relevant
K02_COUNTERFACTUAL_RELEVANT = True
K02_MAX_TRADES = 10  # min(10, 10%) cap


def _num(v):
    return v if isinstance(v, (int, float)) and not math.isnan(v) else None


def _is_killed(metrics: dict) -> bool:
    """Frozen KILLED definition: cagr <= 0 AND sharpe <= 0 (NaN -> not killed,
    deterministic)."""
    c = _num(metrics.get("cagr"))
    s = _num(metrics.get("sharpe"))
    return c is not None and s is not None and c <= 0 and s <= 0


def _metrics_from_returns(rets: pd.Series) -> dict[str, float]:
    from pql.backtest.metrics import cagr, max_drawdown, sharpe

    eq = np.cumprod(1.0 + rets.to_numpy())
    eq = pd.Series(eq, index=rets.index)
    return {
        "cagr": cagr(eq),
        "sharpe": sharpe(eq),
        "max_drawdown": max_drawdown(eq),
    }


def _make_view(spec, data_root, universe, start, end) -> DatasetView:
    return DatasetView.load(
        spec.dataset_version, data_root, universe=universe, start=start, end=end,
    )


def _default_timing(spec) -> TimingContract:
    return TimingContract(
        execution_bar=int(spec.timing.get("execution_bar", 1)),
        execution_price=spec.timing.get("execution_price", "close"),
    )


def _portfolio(spec) -> PortfolioConfig:
    return PortfolioConfig(
        init_cash=1_000_000,
        max_positions=spec.risk.get("max_positions"),
        weighting="equal",
    )


def _run(
    spec, cost, data_root,
    *,
    universe: list[str],
    is_view: DatasetView,
    params: dict[str, Any],
    timing: TimingContract | None = None,
    perturbation: ExecutionPerturbation | None = None,
    start: str | None = None,
    end: str | None = None,
    intent=None,
):
    """Full run_backtest over [start, end]. The intent is built from `is_view`
    (the full-in-sample view over `universe`, so warmup is preserved), then
    executed on a fresh window view. `intent` may be supplied directly (K06)."""
    start = start or spec.windows["in_sample"][0]
    end = end or spec.windows["in_sample"][1]
    if intent is None:
        intent = build_signal(
            spec, is_view.research_frame(), effective_params(spec, params),
            calendar_dates=is_view.calendar_dates(),
        )
    timing = timing or _default_timing(spec)
    win = _make_view(spec, data_root, universe, start, end)
    return run_backtest(
        intent=intent, universe=universe, execution_model=timing,
        cost_model=cost, portfolio_config=_portfolio(spec), dataset=win,
        perturbation=perturbation,
    )


def _variant(variant_id: str, name: str, params: dict, res, *, gate_relevant: bool = True) -> dict:
    return {
        "variant_id": variant_id,
        "variant_name": name,
        "parameters": params,
        "metrics": dict(res.metrics),
        "result": "KILLED" if _is_killed(res.metrics) else "PASSED",
        "gate_relevant": gate_relevant,
        "equity": res.equity,
        "orders": res.orders,
        "run_ref": None,
        "valuation_mode": res.run_meta.get("valuation_mode"),
    }


def _family(family_id: str, name: str, variants: list[dict], family_params: dict | None = None) -> dict:
    relevant = [v for v in variants if v["gate_relevant"]]
    killed = [v for v in relevant if v["result"] == "KILLED"]
    killed_fraction = (len(killed) / len(relevant)) if relevant else 0.0
    return {
        "family_id": family_id,
        "family_name": name,
        "variants": variants,
        "family_result": "KILLED" if killed else "PASSED",
        "killed_fraction": killed_fraction,
        "gate_relevant_variant_count": len(relevant),
        "killed_variant_count": len(killed),
        "family_params": family_params or {},
    }


def drop_best_year(rets: pd.Series) -> tuple[int, pd.Series]:
    """Identify the natural year with the highest annual return and return
    (best_year, returns_excluding_that_year). Frozen K01 semantics: highest
    annual (compounded) return per natural year (not Sharpe, not a miscounted
    CAGR field)."""
    year_ret = rets.groupby(rets.index.year).apply(
        lambda r: float(np.prod(1.0 + r.to_numpy()) - 1.0)
    )
    best_year = int(year_ret.idxmax())
    return best_year, rets[rets.index.year != best_year]


# --------------------------------------------------------------------------- #
# K01 drop_best_year
# --------------------------------------------------------------------------- #
def _k01(spec, cost, ds, data_root) -> dict:
    is_start, is_end = spec.windows["in_sample"]
    res = _run(spec, cost, data_root, universe=spec.universe, is_view=ds,
               params=effective_params(spec, None), start=is_start, end=is_end)
    equity = pd.Series(res.equity).sort_index()
    rets = equity.pct_change().dropna()
    best_year, remaining = drop_best_year(rets)
    m = _metrics_from_returns(remaining)
    variant = _variant(
        "K01", f"drop_best_year={best_year}", {"best_year": best_year},
        SimpleRes(m), gate_relevant=True,
    )
    year_ret = rets.groupby(rets.index.year).apply(
        lambda r: float(np.prod(1.0 + r.to_numpy()) - 1.0)
    )
    return _family("K01", "drop_best_year", [variant], {"best_year": best_year,
                                                         "annual_returns": year_ret.to_dict()})


# --------------------------------------------------------------------------- #
# K02 drop_best_trades (ATTRIBUTION + COUNTERFACTUAL)
# --------------------------------------------------------------------------- #
def top_winning_trades(closed_trades: list[dict], n_closed: int) -> list[dict]:
    """k = min(10, max(1, ceil(0.10 * n_closed))) most profitable closed trades
    (PLAN_CLARIFICATION M6-004). Frozen rounding; empty list when no closed
    trades (no fabricated trades)."""
    if n_closed <= 0:
        return []
    k = min(10, max(1, math.ceil(0.10 * n_closed)))
    ranked = sorted(closed_trades, key=lambda t: t["net_pnl"], reverse=True)
    return ranked[:k]


def _k02(spec, cost, ds, data_root) -> dict:
    is_start, is_end = spec.windows["in_sample"]
    base = _run(spec, cost, data_root, universe=spec.universe, is_view=ds,
                params=effective_params(spec, None), start=is_start, end=is_end)
    closed = [t for t in base.run_meta.get("closed_trades", []) if t.get("status") == 1]
    variants: list[dict] = []
    if not closed:
        variants.append({
            "variant_id": "K02_ATTRIBUTION",
            "variant_name": "drop_best_trades (attribution)",
            "parameters": {"mode": "ATTRIBUTION_TEST"},
            "metrics": {},
            "result": "NOT_APPLICABLE",
            "gate_relevant": False,
            "note": "no_closed_trades",
            "equity": None, "orders": None, "run_ref": None,
        })
        variants.append({
            "variant_id": "K02_COUNTERFACTUAL",
            "variant_name": "drop_best_trades (counterfactual)",
            "parameters": {"mode": "COUNTERFACTUAL_TEST"},
            "metrics": {},
            "result": "NOT_APPLICABLE",
            "gate_relevant": True,
            "note": "no_closed_trades",
            "equity": None, "orders": None, "run_ref": None,
        })
        return _family("K02", "drop_best_trades", variants)

    top = top_winning_trades(closed, len(closed))
    from pql.backtest.metrics import cagr, max_drawdown, sharpe

    # ATTRIBUTION (diagnostic): remove the top winning trades' realized PnL
    # from the equity curve from their EXIT date onward, then recompute metrics.
    # Diagnostic only — NOT gate-relevant (M6-003).
    equity = pd.Series(base.equity).sort_index()
    equity_adj = equity.copy()
    for t in top:
        d = pd.Timestamp(t["exit_date"]).normalize()
        if d in equity_adj.index:
            idx = equity_adj.index.get_loc(d)
            equity_adj.iloc[idx:] -= t["net_pnl"]
    att_metrics = {
        "cagr": cagr(equity_adj), "sharpe": sharpe(equity_adj),
        "max_drawdown": max_drawdown(equity_adj),
    }
    variants.append({
        "variant_id": "K02_ATTRIBUTION",
        "variant_name": "drop_best_trades (attribution)",
        "parameters": {"mode": "ATTRIBUTION_TEST", "k": len(top)},
        "metrics": dict(att_metrics),
        "result": "KILLED" if _is_killed(att_metrics) else "PASSED",
        "gate_relevant": K02_ATTRIBUTION_RELEVANT,
        "note": "diagnostic attribution",
        "equity": None, "orders": None, "run_ref": None,
    })

    # COUNTERFACTUAL (full rerun): reject the top trades' ENTRY orders so the
    # portfolio path evolves naturally (a missed SELL changes cash, breaking a
    # later BUY). Full engine rerun via ExecutionPerturbation.reject_mask.
    mask = pd.DataFrame(
        False, index=pd.to_datetime(equity.index), columns=pd.Index(spec.universe)
    )
    for t in top:
        d = pd.Timestamp(t["entry_date"]).normalize()
        sym = t["symbol"]
        if d in mask.index and sym in mask.columns:
            mask.loc[d, sym] = True
    cf = _run(spec, cost, data_root, universe=spec.universe, is_view=ds,
              params=effective_params(spec, None), start=is_start, end=is_end,
              perturbation=ExecutionPerturbation(reject_mask=mask))
    variants.append(_variant(
        "K02_COUNTERFACTUAL", "drop_best_trades (counterfactual)",
        {"mode": "COUNTERFACTUAL_TEST", "k": len(top)}, cf,
        gate_relevant=K02_COUNTERFACTUAL_RELEVANT,
    ))
    return _family("K02", "drop_best_trades", variants, {"k": len(top),
                                                          "n_closed_trades": len(closed)})


# --------------------------------------------------------------------------- #
# K03 universe_loo
# --------------------------------------------------------------------------- #
def _k03(spec, cost, ds, data_root) -> dict:
    is_start, is_end = spec.windows["in_sample"]
    variants = []
    for sym in list(spec.universe):
        univ = [s for s in spec.universe if s != sym]
        loo_view = _make_view(spec, data_root, univ, is_start, is_end)
        res = _run(spec, cost, data_root, universe=univ, is_view=loo_view,
                   params=effective_params(spec, None), start=is_start, end=is_end)
        variants.append(_variant(f"K03_{sym}", f"universe_loo drop {sym}",
                                 {"drop_symbol": sym}, res, gate_relevant=True))
    return _family("K03", "universe_loo", variants)


# --------------------------------------------------------------------------- #
# K04 delay_execution (execution_bar + 1, decision unchanged, Execution Revaluation)
# --------------------------------------------------------------------------- #
def _k04(spec, cost, ds, data_root) -> dict:
    base_bar = int(spec.timing.get("execution_bar", 1))
    timing = TimingContract(execution_bar=base_bar + 1,
                            execution_price=spec.timing.get("execution_price", "close"))
    is_start, is_end = spec.windows["in_sample"]
    res = _run(spec, cost, data_root, universe=spec.universe, is_view=ds,
               params=effective_params(spec, None), start=is_start, end=is_end,
               timing=timing)
    return _family("K04", "delay_execution",
                   [_variant("K04", f"execution_bar={base_bar}+1",
                             {"execution_bar": base_bar + 1}, res, gate_relevant=True)])


# --------------------------------------------------------------------------- #
# K05 cost_x2 (reuse apply_stress(cost, 2))
# --------------------------------------------------------------------------- #
def _k05(spec, cost, ds, data_root) -> dict:
    is_start, is_end = spec.windows["in_sample"]
    stressed = apply_stress(cost, 2)
    res = _run(spec, stressed, data_root, universe=spec.universe, is_view=ds,
               params=effective_params(spec, None), start=is_start, end=is_end)
    return _family("K05", "cost_x2",
                   [_variant("K05", "cost_x2", {"multiplier": 2}, res, gate_relevant=True)])


# --------------------------------------------------------------------------- #
# K06 shift_rebalance (decision schedule shifted 1 actual trading day)
# --------------------------------------------------------------------------- #
def _shift_rebalance_days(calendar_dates, rebal_days) -> list:
    sched = np.array(
        sorted({pd.Timestamp(d).normalize() for d in calendar_dates})
    )
    out = []
    for d in rebal_days:
        pos = np.searchsorted(sched, pd.Timestamp(d).normalize(), side="right")
        if pos < len(sched):
            out.append(sched[pos])
    return [pd.Timestamp(x) for x in out]


def _k06(spec, cost, ds, data_root) -> dict:
    is_start, is_end = spec.windows["in_sample"]
    kind = spec.signal.get("kind")
    if kind != "momentum_rotation":
        # No rebalance schedule to shift for this signal kind (trend/buy_hold
        # rebalance continuously via the signal). K06 is not gate-relevant here.
        return _family("K06", "shift_rebalance", [{
            "variant_id": "K06",
            "variant_name": "shift_rebalance",
            "parameters": {"rebalance_shift_days": 1},
            "metrics": {},
            "result": "NOT_APPLICABLE",
            "gate_relevant": False,
            "note": f"no rebalance schedule for signal kind {kind!r}",
            "equity": None, "orders": None, "run_ref": None,
        }])
    cal = ds.calendar_dates()
    base_rebal = first_trading_day_of_month(cal)
    shifted = _shift_rebalance_days(cal, base_rebal)
    params = effective_params(spec, None)
    research = ds.research_frame()
    intent = momentum_rotation_signal(
        research, calendar_dates=cal,
        momentum_days=int(params.get("momentum_days")),
        ma_filter=int(params.get("ma_filter", 0)),
        top_k=int(params.get("top_k")),
        max_positions=spec.risk.get("max_positions"),
        rebalance_days=shifted,
    )
    res = _run(spec, cost, data_root, universe=spec.universe, is_view=ds,
               params=params, start=is_start, end=is_end, intent=intent)
    return _family("K06", "shift_rebalance",
                   [_variant("K06", "rebalance_shifted_1_trading_day",
                             {"rebalance_shift_days": 1}, res, gate_relevant=True)])


# --------------------------------------------------------------------------- #
# K07 perturb_params (±10% numeric research params, deterministic rounding)
# --------------------------------------------------------------------------- #
def _perturb_value(value) -> tuple[float | None, float | None]:
    """(-10%, +10%) with deterministic rounding to int when the value is
    integral. Returns (lo, hi) or (None, None) for non-numeric / disabled."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return (None, None)
    lo = value * 0.9
    hi = value * 1.1
    if float(value).is_integer():
        lo = float(round(lo))
        hi = float(round(hi))
    return (lo, hi)


def _k07(spec, cost, ds, data_root) -> dict:
    is_start, is_end = spec.windows["in_sample"]
    base_params = effective_params(spec, None)
    variants: list[dict] = []
    for key, value in sorted(base_params.items()):
        lo, hi = _perturb_value(value)
        if lo is None:
            continue
        for direction, pv in (("-10%", lo), ("+10%", hi)):
            if pv == value:
                continue  # degenerate (unchanged after rounding) -> no perturbation
            perturbed = dict(base_params)
            perturbed[key] = pv
            res = _run(spec, cost, data_root, universe=spec.universe, is_view=ds,
                       params=perturbed, start=is_start, end=is_end)
            variants.append(_variant(
                f"K07_{key}{direction}", f"perturb {key} {direction}",
                {key: pv}, res, gate_relevant=True,
            ))
    return _family("K07", "perturb_params", variants)


# --------------------------------------------------------------------------- #
# K08 shift_start (start +60 actual trading days, warmup from IS history)
# --------------------------------------------------------------------------- #
def _shift_start_date(ds, start: str, n: int) -> str:
    dates = sorted({pd.Timestamp(d) for d in ds.calendar_dates()})
    idx = next((i for i, d in enumerate(dates) if d >= pd.Timestamp(start).normalize()), 0)
    target = min(idx + n, len(dates) - 1)
    return str(dates[target].date())


def _k08(spec, cost, ds, data_root) -> dict:
    is_start, is_end = spec.windows["in_sample"]
    shifted = _shift_start_date(ds, is_start, 60)
    res = _run(spec, cost, data_root, universe=spec.universe, is_view=ds,
               params=effective_params(spec, None), start=shifted, end=is_end)
    return _family("K08", "shift_start",
                   [_variant("K08", f"start_shifted_{60}_trading_days",
                             {"shift_trading_days": 60, "start": shifted},
                             res, gate_relevant=True)])


# --------------------------------------------------------------------------- #
# Aggregate
# --------------------------------------------------------------------------- #
def kill_tests(spec, cost, ds, data_root) -> dict[str, Any]:
    """Run all 8 kill families on the candidate parameter set (IS only, never
    holdout). Returns a dict keyed by family_id."""
    families = {
        "K01": _k01(spec, cost, ds, data_root),
        "K02": _k02(spec, cost, ds, data_root),
        "K03": _k03(spec, cost, ds, data_root),
        "K04": _k04(spec, cost, ds, data_root),
        "K05": _k05(spec, cost, ds, data_root),
        "K06": _k06(spec, cost, ds, data_root),
        "K07": _k07(spec, cost, ds, data_root),
        "K08": _k08(spec, cost, ds, data_root),
    }
    for fid in KILL_FAMILIES:
        families[fid]["result"] = families[fid]["family_result"]
    return families


def killed_family_count(families: dict[str, Any]) -> int:
    return sum(1 for f in families.values() if f.get("family_result") == "KILLED")


class SimpleRes:
    """Minimal BacktestResult-like shim for metrics-only variants (K01)."""

    def __init__(self, metrics: dict, equity=None, orders=None):
        self.metrics = metrics
        self.equity = equity
        self.orders = orders
        self.run_meta = {"valuation_mode": "returns-based"}


__all__ = [
    "KILL_FAMILIES",
    "drop_best_year",
    "kill_tests",
    "killed_family_count",
    "top_winning_trades",
]
```

### `src\pql\validation\overfitting.py`

```python
"""M6.4 Deflated Sharpe Ratio (Bailey–López de Prado, 2014).

Reference: Bailey, D. H., and López de Prado, M. (2014). "The Deflated Sharpe
Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality."
Journal of Portfolio Management 40(5), 94–107.

Formulas (per-observation, non-annualized Sharpe):

    V(SR) = (1 - gamma3*SR + (gamma4 - 1)/4 * SR^2) / (T - 1)

    E[max_SR | N] = sqrt(V) * [ (1 - gamma) * Z^-1(1 - 1/N)
                                + gamma * Z^-1(1 - 1/(N*e)) ]     (N >= 2)

    DSR = Z( (SR - E[max_SR]) / sqrt(V) )

with gamma = Euler–Mascheroni constant 0.57721..., Z the standard normal CDF,
gamma3 the sample skewness, gamma4 the sample PEARSON kurtosis (normal = 3,
NOT excess kurtosis), T the number of daily observations, and N the number of
independent trials. V(SR) is the sampling variance of the selected strategy's
Sharpe estimator (Lo, 2002); the SAME V is used for both the PSR denominator
and the expected-maximum deflation term — the standard Bailey–López de Prado
DSR does NOT use a cross-sectional variance of trial Sharpes. For N <= 1 there
is no multiple-testing bias, so E[max_SR] = 0 and DSR degenerates to PSR(0).

Trial count is a HARD contract: N = effective_trial_count =
COUNT(DISTINCT selection_key across the strategy lineage) where run_kind ==
SELECT. Bootstrap samples / stress variants / kill variants / walk-forward
folds / final holdout NEVER add to N. This module never re-implements trial
counting: it calls pql.registry.experiments.effective_trial_count /
select_run_keys (the SAME fact source as the Research Budget).
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd
from scipy import stats

from pql.registry.experiments import (
    effective_trial_count,
    select_run_keys,
)

GAMMA_EULER = 0.57721566490153286060651209008240243104215933593992


def _num(v):
    return v if isinstance(v, (int, float)) and not math.isnan(v) else None


def daily_sharpe(rets: pd.Series) -> float:
    r = rets.dropna()
    if len(r) < 2:
        return float("nan")
    sd = r.std(ddof=1)
    if sd == 0:
        return float("nan")
    return float(r.mean() / sd)


def deflated_sharpe_ratio(
    rets: pd.Series,
    n_trials: int,
    annualization: int = 252,
) -> dict[str, Any]:
    """Deflated Sharpe Ratio for a daily returns series and N trials.

    Returns a component dict (observed_sharpe is the ANNUALIZED Sharpe for
    reporting; the formula itself uses the per-observation daily Sharpe).
    Deterministic for fixed (returns, N): locked by a numerical reference test.
    """
    r = rets.dropna()
    T = len(r)
    sr_daily = daily_sharpe(r)
    if sr_daily is None or math.isnan(sr_daily):
        return {
            "dsr_probability": float("nan"),
            "observed_sharpe": float("nan"),
            "n_observations": T,
            "skew": float("nan"),
            "kurtosis": float("nan"),
            "n_trials": n_trials,
            "note": "insufficient data for DSR",
        }
    skew = float(stats.skew(r, bias=True))
    # gamma4 is the Pearson kurtosis (normal = 3), NOT excess kurtosis (normal
    # = 0). The DSR formula's (gamma4 - 1)/4 term derives from the Lo (2002)
    # variance (1 + gamma4/... ) with gamma4 = fourth standardized moment, so
    # fisher=False. Using excess kurtosis here would be off by 3 (review P0-1B).
    kurt = float(stats.kurtosis(r, fisher=False, bias=True))  # Pearson kurtosis
    V = (1.0 - skew * sr_daily + (kurt - 1.0) / 4.0 * sr_daily**2) / (T - 1)
    if V <= 0:
        V = 0.0
    sqrt_V = math.sqrt(V) if V > 0 else 0.0

    if n_trials <= 1:
        emax = 0.0
    else:
        emax = sqrt_V * (
            (1.0 - GAMMA_EULER) * stats.norm.ppf(1.0 - 1.0 / n_trials)
            + GAMMA_EULER * stats.norm.ppf(1.0 - 1.0 / (n_trials * math.e))
        )
    dsr = (
        float(stats.norm.cdf((sr_daily - emax) / sqrt_V))
        if V > 0
        else float("nan")
    )
    return {
        "dsr_probability": dsr,
        "observed_sharpe": float(sr_daily * math.sqrt(annualization)),
        "daily_sharpe": float(sr_daily),
        "n_observations": T,
        "skew": skew,
        "kurtosis": kurt,
        "n_trials": int(n_trials),
        "annualization": int(annualization),
    }


def deflated_sharpe_report(
    spec,
    equity: pd.Series,
    experiments_root: str | Path,
    strategy: str,
) -> dict[str, Any]:
    """DSR report with full provenance for the candidate validation:

    - N = effective_trial_count (DISTINCT SELECT selection_key across lineage)
    - trial_selection_keys = the actual SELECT keys (ledger fact source)
    - candidate_selection_key = the candidate's default params key
    stderr: bootstrap/stress/kill/fold/final never enter N.
    """
    keys = select_run_keys(experiments_root, strategy)
    n = effective_trial_count(experiments_root, strategy)
    eq = pd.Series(equity).sort_index()
    rets = eq.pct_change().dropna()
    comp = deflated_sharpe_ratio(rets, n)
    comp["effective_trial_count"] = n
    comp["trial_selection_keys"] = sorted(keys)
    comp["candidate_selection_key"] = _candidate_key(spec)
    return comp


def _candidate_key(spec) -> str:
    from pql.registry.experiments import selection_key
    from pql.signals.registry import effective_params

    return selection_key(effective_params(spec, None))


__all__ = [
    "GAMMA_EULER",
    "daily_sharpe",
    "deflated_sharpe_ratio",
    "deflated_sharpe_report",
]
```

### `src\pql\validation\pipeline.py`

```python
"""M5.6 candidate development validation pipeline (D9).

Orchestrates the M5 portion of `pql validate candidate`: IS baseline, walk-
forward, parameter robustness, time robustness, regime diagnostics. M6 gates
(cost/exec stress, bootstrap, DSR, kill) are recorded as PENDING_M6 — never
PASS. Overall is INCOMPLETE_PENDING_M6 when every M5 gate passes, FAIL
otherwise; it can never be PASS until M6 completes all candidate gates.

Holdout is a hard exclusion: the pipeline never calls HoldoutGuard.holdout_slice
and records the holdout_access.log before/after (must be identical). No
Candidate Freeze / promotion is performed (strategy stays RESEARCH).

Research runs are written to the Experiment->Run ledger: grid params as SELECT
runs (deduped by selection_key), walk-forward OOS / year / regime slices as
EVALUATE / DIAGNOSTIC runs (never adding to effective_trial_count).
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from pql.backtest.costs import apply_stress
from pql.data.dataset import DatasetView
from pql.registry.experiments import (
    next_experiment_id,
    selection_key,
    write_manifest,
    write_run,
)
from pql.registry.provenance import (
    config_hashes,
    dependency_versions,
    git_state,
)
from pql.registry.runner import resolve_paths
from pql.schemas import load_cost_model, load_spec
from pql.signals.registry import effective_params
from pql.validation.freeze import code_tree_sha256, validation_fingerprint

from .base import grid_configs, run_window
from .regimes import regime_analysis
from .robustness import parameter_robustness, time_robustness
from .walkforward import walkforward

M6_KEYS = ["cost_stress", "exec_stress", "bootstrap", "deflated_sharpe", "kill_tests"]


class PipelineError(RuntimeError):
    """Raised for pipeline orchestration failures."""


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_gates(repo_root: str | Path) -> tuple[dict, str]:
    """Return (candidate-gate thresholds, gate_version) from validation_gates.yaml."""
    path = Path(repo_root) / "config" / "validation_gates.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict(data.get("candidate", {})), str(data.get("version", ""))


def _holdout_snapshot(data_root: str | Path) -> dict:
    path = Path(data_root) / "metadata" / "holdout_access.log"
    if not path.exists():
        return {"exists": False, "lines": 0, "sha256": None}
    content = path.read_bytes()
    return {
        "exists": True,
        "lines": content.count(b"\n"),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _write_eval(
    exp_id: str, strategy: str, params: dict, run_kind: str,
    spec, cost, ds: DatasetView, gate, config_sha256: str, gate_version: str,
    metrics: dict, equity, orders, exp_root: str | Path,
    cost_model=None,
):
    """Write a window backtest result as a Run in the ledger."""
    cost_model = cost_model or cost
    return write_run(
        experiments_root=exp_root,
        experiment_id=exp_id,
        strategy=strategy,
        parameters=dict(params),
        selection_key=selection_key(params),
        run_kind=run_kind,
        visible_to_researcher=True,
        dataset_version=spec.dataset_version,
        dataset_checksums=ds.manifest().get("files", {}),
        market_rule_version=spec.market_rule_version,
        cost_model_version=spec.cost_model_version,
        cost_config={"version": cost_model.version, "fee_rate": cost_model.fee_rate,
                     "slippage": cost_model.slippage},
        gate_version=gate_version,
        gate=gate,
        config_sha256=config_sha256,
        dependencies=dependency_versions(),
        seed=spec.seed,
        timing={"execution_bar": int(spec.timing.get("execution_bar", 1)),
                "execution_price": spec.timing.get("execution_price", "close")},
        metrics=dict(metrics),
        equity=equity,
        orders=orders,
    )


def validate_candidate(
    repo_root: str | Path,
    strategy: str,
    data_root: str | Path = "data",
    report_root: str | Path = "reports",
    experiments_root: str | Path = "experiments",
    persist: bool = True,
) -> dict[str, Any]:
    """Run the M5 candidate development validation for a strategy. Returns the
    candidate report (persisted to reports/validation/<strategy>/candidate_report.json
    when persist). Never consumes holdout and never promotes the strategy."""
    repo = Path(repo_root)
    exp_root = Path(experiments_root)
    spec = load_spec(repo / "strategies" / f"{strategy}.yaml")
    paths = resolve_paths(repo, spec)
    cost = load_cost_model(paths["cost"])
    ds = DatasetView.load(
        spec.dataset_version, data_root, universe=spec.universe,
        start=spec.windows["in_sample"][0], end=spec.windows["in_sample"][1],
    )
    gates, gate_version = load_gates(repo)
    default_params = effective_params(spec, None)
    grid = grid_configs(spec)

    # M5 review P0: preflight the ENTIRE proposed SELECT grid against the
    # research budget BEFORE any backtest runs. A budget-exceed grid aborts here
    # with zero backtests executed and no SELECT runs written.
    from pql.registry.budget import check_grid_budget

    check_grid_budget(spec, exp_root, grid)

    gate = git_state(exp_root)
    cfg = config_hashes(paths["spec"], paths["gates"], paths["cost"],
                        paths["market"], paths["instruments"])
    holdout_before = _holdout_snapshot(data_root)

    # -- Experiment -> Run ledger container for this candidate validation -----
    exp_id = next_experiment_id(exp_root)
    write_manifest(
        exp_root, experiment_id=exp_id, strategy=strategy,
        research_question=f"candidate development validation: {strategy}",
        experiment_config={"gate_version": gate_version},
    )

    # -- IS baseline ----------------------------------------------------------
    is_res = run_window(spec, default_params, ds, cost, data_root,
                        spec.windows["in_sample"][0], spec.windows["in_sample"][1])
    is_metrics = dict(is_res.metrics)
    _write_eval(exp_id, strategy, default_params, "SELECT", spec, cost, ds,
                gate, cfg["config_sha256"], gate_version, is_metrics,
                is_res.equity, is_res.orders, exp_root)

    # -- parameter robustness (full grid as SELECT runs, with real artifacts) --
    pr = parameter_robustness(spec, ds, cost, data_root)
    for row in pr["rows"]:
        _write_eval(exp_id, strategy, row["params"], "SELECT", spec, cost, ds,
                    gate, cfg["config_sha256"], gate_version, row["metrics"],
                    row.get("result").equity if row.get("result") else None,
                    row.get("result").orders if row.get("result") else None,
                    exp_root)

    # -- walk-forward (OOS test folds as EVALUATE runs) -----------------------
    wf = walkforward(spec, grid, ds, cost, data_root)
    if wf.get("status") == "ok":
        for fold in wf["folds"]:
            # re-run the selected config's test fold to persist its equity/orders
            f_res = run_window(spec, fold["selected_params"], ds, cost, data_root,
                               fold["test_start"], fold["test_end"])
            _write_eval(exp_id, strategy, fold["selected_params"], "EVALUATE",
                        spec, cost, ds, gate, cfg["config_sha256"], gate_version,
                        f_res.metrics, f_res.equity, f_res.orders, exp_root)

    # -- time robustness (year slices as EVALUATE runs) -----------------------
    tr = time_robustness(spec, ds, cost, data_root)
    for yr in tr["years"]:
        if yr["status"] == "ok":
            _write_eval(exp_id, strategy, default_params, "EVALUATE", spec, cost, ds,
                        gate, cfg["config_sha256"], gate_version, yr["metrics"],
                        None, None, exp_root)

    # -- regime diagnostics (DIAGNOSTIC runs) ---------------------------------
    rg = regime_analysis(spec, ds, cost, data_root)
    for combo in rg["combos"]:
        _write_eval(exp_id, strategy, {**default_params, "_regime": combo["regime_combo"]},
                    "DIAGNOSTIC", spec, cost, ds, gate, cfg["config_sha256"],
                    gate_version, combo, None, None, exp_root)

    # -- M6: cost stress (STRESS runs, full rerun, real costs) ---------------
    from .stress import cost_stress, execution_stress, worst_exec_max_drawdown

    cost_variants = cost_stress(spec, cost, ds, data_root)
    for v in cost_variants:
        _write_eval(exp_id, strategy, default_params, "STRESS", spec, cost, ds,
                    gate, cfg["config_sha256"], gate_version, v["metrics"],
                    v["equity"], v["orders"], exp_root)
    _cost_2x = next(v for v in cost_variants if v["parameters"].get("multiplier") == 2)
    cost_2x_sharpe = _num(_cost_2x["sharpe"])

    # -- M6: execution stress (STRESS runs, frozen E01-E05) ------------------
    exec_variants = execution_stress(spec, cost, ds, data_root)
    for v in exec_variants:
        _write_eval(exp_id, strategy, {**default_params, "_exec": v["variant_id"]},
                    "STRESS", spec, cost, ds, gate, cfg["config_sha256"],
                    gate_version, v["metrics"], v["equity"], v["orders"], exp_root)
    worst_mdd = worst_exec_max_drawdown(exec_variants)

    # -- M6: circular block bootstrap (IS returns, never holdout) ------------
    from .bootstrap import bootstrap, bootstrap_sharpe_p05

    boot_out = Path(report_root) / "validation" / strategy / "bootstrap"
    bs = bootstrap(spec, is_res.equity, out_dir=boot_out if persist else None)
    bs_p05 = bootstrap_sharpe_p05(bs)

    # -- M6: Deflated Sharpe Ratio (N = effective_trial_count) ---------------
    from .overfitting import deflated_sharpe_report

    dsr = deflated_sharpe_report(spec, is_res.equity, exp_root, strategy)

    # -- M6: kill test families (DIAGNOSTIC runs) ----------------------------
    from .kill import kill_tests, killed_family_count

    families = kill_tests(spec, cost, ds, data_root)
    for fid, fam in families.items():
        for v in fam["variants"]:
            if v.get("equity") is None:
                continue
            cost_model = apply_stress(cost, 2) if fid == "K05" else cost
            _write_eval(exp_id, strategy,
                        {**default_params, "_kill": fid, "_variant": v["variant_id"]},
                        "DIAGNOSTIC", spec, cost, ds, gate, cfg["config_sha256"],
                        gate_version, v["metrics"], v["equity"], v["orders"],
                        exp_root, cost_model=cost_model)
    n_killed_families = killed_family_count(families)

    # -- gate evaluation (M5 + M6, all from validation_gates.yaml) -----------
    is_sharpe = _num(is_metrics.get("sharpe"))
    is_maxdd = _num(is_metrics.get("max_drawdown"))
    gate_results = {
        "min_is_sharpe": is_sharpe is not None and is_sharpe >= _num(gates.get("min_is_sharpe")),
        "max_drawdown_floor": is_maxdd is not None and is_maxdd >= _num(gates.get("max_drawdown_floor")),
        "walkforward": _wf_gate(wf, gates),
        "param_stability": pr["param_stability"] >= _num(gates.get("param_stability_min_frac")),
        "time_windows_min_pos_cagr_frac": (
            tr["positive_cagr_fraction"] >= _num(gates.get("time_windows_min_pos_cagr_frac"))
        ),
        "cost_2x_min_sharpe": cost_2x_sharpe is not None and cost_2x_sharpe >= _num(gates.get("cost_2x_min_sharpe")),
        "exec_stress_max_drawdown_floor": worst_mdd is not None and worst_mdd >= _num(gates.get("exec_stress_max_drawdown_floor")),
        "bootstrap_sharpe_p05_min": bs_p05 >= _num(gates.get("bootstrap_sharpe_p05_min")),
        "deflated_sharpe_min": dsr["dsr_probability"] is not None and not (
            isinstance(dsr["dsr_probability"], float) and math.isnan(dsr["dsr_probability"])
        ) and float(dsr["dsr_probability"]) >= _num(gates.get("deflated_sharpe_min")),
        "max_kill_families_killed": n_killed_families <= _num(gates.get("max_kill_families_killed")),
        "require_code_clean": not bool(gate.code_dirty),
    }
    code_clean = not bool(gate.code_dirty)
    overall = "FAIL" if any(v is False for v in gate_results.values()) else "PASS"
    ready_for_candidate_freeze = overall == "PASS"

    holdout_after = _holdout_snapshot(data_root)
    report = {
        "strategy": strategy,
        "strategy_state": "RESEARCH",  # never promoted
        "dataset_version": spec.dataset_version,
        "dataset_source": ds.manifest().get("source", ""),
        "market_evidence": ds.manifest().get("source", "") != "synthetic",
        "candidate_params": default_params,
        "gate_version": gate_version,
        "gate_content_sha256": cfg["per_file"].get(str(paths["gates"]), ""),
        "code_commit": gate.commit,
        "code_dirty": gate.code_dirty,
        "code_tree_sha256": code_tree_sha256(repo),
        "config_hashes": cfg["per_file"],
        "validation_fingerprint": validation_fingerprint(repo, spec),
        "selected_params": default_params,
        "effective_trial_count": _effective_trial_count(exp_root, strategy),
        "provenance": {
            "dataset_version": spec.dataset_version,
            "dataset_source": ds.manifest().get("source", ""),
            "code_commit": gate.commit,
            "code_dirty": gate.code_dirty,
            "gate_version": gate_version,
            "config_sha256": cfg["config_sha256"],
        },
        "holdout_access_before": holdout_before,
        "holdout_access_after": holdout_after,
        "holdout_untouched": holdout_before == holdout_after,
        "experiment_id": exp_id,
        "is_baseline": is_metrics,
        "walkforward": {k: v for k, v in wf.items() if k != "combined_oos_equity"},
        "parameter_robustness": {k: v for k, v in pr.items() if k != "rows"},
        "time_robustness": tr,
        "regime": rg,
        "cost_stress": {
            "variants": [
                {"multiplier": v["parameters"].get("multiplier"), "sharpe": v["sharpe"],
                 "max_drawdown": v["max_drawdown"], "cagr": v["cagr"],
                 "fee_rate": v.get("fee_rate"), "slippage": v.get("slippage")}
                for v in cost_variants
            ],
            "cost_2x_sharpe": cost_2x_sharpe,
        },
        "execution_stress": {
            "variants": [
                {"variant_id": v["variant_id"], "variant_name": v["variant_name"],
                 "parameters": v["parameters"], "sharpe": v["sharpe"],
                 "max_drawdown": v["max_drawdown"], "cagr": v["cagr"],
                 "valuation_mode": v.get("valuation_mode")}
                for v in exec_variants
            ],
            "worst_exec_max_drawdown": worst_mdd,
            "gate_input_variant": "worst across required E01-E05 variants (M6-002)",
        },
        "bootstrap": bs["summary"],
        "deflated_sharpe": dsr,
        "kill_tests": {
            "families": [
                {
                    "family_id": f["family_id"],
                    "family_name": f["family_name"],
                    "family_result": f["family_result"],
                    "killed_fraction": f["killed_fraction"],
                    "gate_relevant_variant_count": f["gate_relevant_variant_count"],
                    "killed_variant_count": f["killed_variant_count"],
                    "variants": [
                        {"variant_id": v["variant_id"], "variant_name": v["variant_name"],
                         "parameters": v["parameters"], "result": v["result"],
                         "gate_relevant": v["gate_relevant"], "metrics": v["metrics"]}
                        for v in f["variants"]
                    ],
                }
                for f in families.values()
            ],
            "killed_family_count": n_killed_families,
        },
        "code_clean": {"code_dirty": bool(gate.code_dirty), "pass": code_clean},
        "gate_results": gate_results,
        "overall": overall,
        "ready_for_candidate_freeze": ready_for_candidate_freeze,
        "created": _now(),
    }
    if persist:
        out = Path(report_root) / "validation" / strategy / "candidate_report.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str),
                       encoding="utf-8")
        report["report_path"] = str(out)
    return report


def _wf_gate(wf: dict, gates: dict) -> bool:
    """Positive test-segment Sharpe fraction >= threshold. Walk-forward skipped
    (insufficient data) is treated as not-failing (task M5.26: skipped, not
    FAIL) but recorded as 'skipped'."""
    if wf.get("status") == "skipped":
        return True
    frac = wf.get("positive_sharpe_segment_fraction", 0.0)
    thr = _num(gates.get("walkforward_min_segment_sharpe_frac"))
    return frac >= thr if thr is not None else True


def _num(v):
    return v if isinstance(v, (int, float)) and not math.isnan(v) else None


def _effective_trial_count(exp_root: Path, strategy: str) -> int:
    from pql.registry.experiments import effective_trial_count as _etc

    return _etc(exp_root, strategy)


__all__ = ["M6_KEYS", "PipelineError", "load_gates", "validate_candidate"]
```

### `src\pql\validation\regimes.py`

```python
"""M5.5 market regime analysis (v0.1: Trend / Volatility / Liquidity; Rate
deferred as not_implemented_v0.1).

All labels are point-in-time (use only data <= T):
- Trend: benchmark close_adj > MA200 -> UP else DOWN.
- Volatility: 20-day realized vol; HIGH when vol > expanding median(vol <= T-1).
- Liquidity: 20-day mean amount; HIGH when amount > expanding median(<= T-1).

Thresholds use the EXPANDING median shifted by one day (<= T-1), never the
full-sample median, so future data cannot leak into historical regime labels.
Per-combo metrics are computed from the strategy's daily returns grouped by the
day's regime combo (only observed combos are emitted).
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .base import run_window

ANNUALIZATION = 252
VOL_WINDOW = 20
LIQ_WINDOW = 20
TREND_MA = 200


class RegimeError(RuntimeError):
    """Raised for regime computation problems."""


def _expanding_median_shift1(series: pd.Series) -> pd.Series:
    """expanding median of values <= T-1 (shifted by one), so the label at T
    never uses its own or future values."""
    return series.expanding(min_periods=1).median().shift(1)


def trend_label(close: pd.Series) -> pd.Series:
    ma = close.rolling(TREND_MA, min_periods=TREND_MA).mean()
    return (close > ma).map({True: "UP", False: "DOWN"}).fillna("DOWN")


def volatility_label(close: pd.Series) -> pd.Series:
    daily = close.pct_change()
    vol = daily.rolling(VOL_WINDOW, min_periods=VOL_WINDOW).std() * np.sqrt(ANNUALIZATION)
    thr = _expanding_median_shift1(vol)
    label = (vol > thr).map({True: "HIGH_VOL", False: "LOW_VOL"}).fillna("LOW_VOL")
    return label


def liquidity_label(amount: pd.Series) -> pd.Series:
    ma = amount.rolling(LIQ_WINDOW, min_periods=LIQ_WINDOW).mean()
    thr = _expanding_median_shift1(ma)
    label = (ma > thr).map({True: "HIGH_LIQ", False: "LOW_LIQ"}).fillna("LOW_LIQ")
    return label


def regime_labels(benchmark_close: pd.Series, benchmark_amount: pd.Series) -> pd.DataFrame:
    """Full regime label frame (index=date, columns trend/volatility/liquidity)."""
    idx = benchmark_close.index
    return pd.DataFrame(
        {
            "trend": trend_label(benchmark_close),
            "volatility": volatility_label(benchmark_close),
            "liquidity": liquidity_label(benchmark_amount.reindex(idx)),
        }
    )


def _metrics_for_returns(rets: pd.Series) -> dict[str, float]:
    if len(rets) < 2:
        return {"n_days": len(rets), "status": "insufficient_data"}
    sd = rets.std(ddof=1)
    return {
        "n_days": len(rets),
        "sharpe": float(rets.mean() / sd * np.sqrt(ANNUALIZATION)) if sd != 0 else float("nan"),
        "annual_vol": float(sd * np.sqrt(ANNUALIZATION)),
        "mean_daily_return": float(rets.mean()),
        "status": "ok",
    }


def regime_analysis(spec, ds, cost, data_root) -> dict[str, Any]:
    """Run the strategy once on the full in-sample range, label each day's
    regime combo, and compute per-combo metrics from the grouped daily returns.
    Only observed combos are emitted; Rate is explicitly not implemented."""
    res = run_window(
        spec, _default_params(spec), ds, cost, data_root,
        spec.windows["in_sample"][0], spec.windows["in_sample"][1],
    )
    equity = pd.Series(res.equity).sort_index()
    rets = equity.pct_change().dropna()

    research = ds.research_frame()
    bench = spec.benchmark
    b_close = (
        research[research["symbol"] == bench]
        .set_index("date")["close_adj"].sort_index()
    )
    amount = ds.amount_frame()
    b_amount = (
        amount[amount["symbol"] == bench]
        .set_index("date")["amount"].sort_index()
    )
    labels = regime_labels(b_close, b_amount)

    # align returns with labels on common dates
    frames = pd.concat([rets.rename("ret"), labels], axis=1, join="inner").dropna(subset=["ret"])
    combos: dict[str, list] = {}
    for _dt, row in frames.iterrows():
        key = f"{row['trend']}|{row['volatility']}|{row['liquidity']}"
        combos.setdefault(key, []).append(row["ret"])

    combo_rows = [
        {"regime_combo": key, **_metrics_for_returns(pd.Series(vals))}
        for key, vals in sorted(combos.items())
    ]
    return {
        "combos": combo_rows,
        "observed_combo_count": len(combos),
        "trend_ma": TREND_MA,
        "vol_window": VOL_WINDOW,
        "liq_window": LIQ_WINDOW,
        "rate_regime": "not_implemented_v0.1",
    }


def _default_params(spec) -> dict[str, Any]:
    from pql.signals.registry import effective_params

    return effective_params(spec, None)


__all__ = [
    "liquidity_label",
    "regime_analysis",
    "regime_labels",
    "trend_label",
    "volatility_label",
]
```

### `src\pql\validation\robustness.py`

```python
"""M5.3 / M5.4 parameter + time robustness (D8/D9).

Parameter robustness: evaluate the FULL frozen param_grid Cartesian product on
the in-sample range; param_stability = mean(sharpe >= 0.5 * best_sharpe),
using the frozen formula verbatim (even when best_sharpe < 0).

Time robustness: slice the in-sample range by CALENDAR YEAR (never fixed 252-day
blocks); each year reports the D8 metric set; positive_cagr_fraction = fraction
of valid years with CAGR > 0. Years with insufficient data are reported as
`insufficient_data` and excluded from the denominator (never silently PASSed).
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from pql.registry.experiments import selection_key

from .base import grid_configs, run_window

# Minimum trading days for a calendar-year slice to count as a valid year in
# the positive-CAGR denominator (partial/insufficient years are excluded).
MIN_YEAR_DAYS = 60


def parameter_robustness(spec, ds, cost, data_root) -> dict[str, Any]:
    """Full-grid in-sample evaluation. Returns grid rows, best params, best
    sharpe, and the frozen param_stability fraction. Sharpe=NaN is treated as
    -inf for best-selection (a config that doesn't trade never wins)."""
    grid = grid_configs(spec)
    rows: list[dict] = []
    best_sharpe = float("-inf")
    best_cfg = None
    for cfg in grid:
        res = run_window(
            spec, cfg, ds, cost, data_root, spec.windows["in_sample"][0],
            spec.windows["in_sample"][1],
        )
        sharpe = res.metrics.get("sharpe")
        s = float(sharpe) if sharpe is not None and not math.isnan(float(sharpe)) else float("-inf")
        rows.append(
            {"params": cfg, "selection_key": selection_key(cfg), "metrics": dict(res.metrics),
             "result": res}
        )
        if s > best_sharpe:
            best_sharpe = s
            best_cfg = cfg

    def _stable(row):
        s = row["metrics"].get("sharpe")
        if s is None or math.isnan(float(s)):  # nan -> not stable
            return 0.0
        return 1.0 if float(s) >= 0.5 * best_sharpe else 0.0

    stable = [_stable(r) for r in rows]
    param_stability = sum(stable) / len(rows) if rows else 0.0
    return {
        "grid_size": len(grid),
        "rows": rows,
        "best_params": best_cfg,
        "best_selection_key": selection_key(best_cfg) if best_cfg else None,
        "best_sharpe": best_sharpe,
        "param_stability": param_stability,
    }


def _year_slices(ds) -> list[tuple[str, str, str]]:
    """Calendar-year slices of the in-sample range: [(year, start, end)]."""
    dates = pd.to_datetime(pd.Series(ds.research_frame()["date"].dt.normalize()).unique())
    years = sorted({d.year for d in dates})
    out = []
    for yr in years:
        y_dates = [d for d in dates if d.year == yr]
        out.append((str(yr), y_dates[0].strftime("%Y-%m-%d"), y_dates[-1].strftime("%Y-%m-%d")))
    return out


def time_robustness(spec, ds, cost, data_root) -> dict[str, Any]:
    """Per-calendar-year IS metrics + positive CAGR fraction over valid years.
    A year is valid only if it has >= MIN_YEAR_DAYS trading days and a
    computable CAGR; partial/insufficient years are recorded as
    `insufficient_data` and excluded from the denominator."""
    slices = _year_slices(ds)
    year_rows: list[dict] = []
    valid_cagr_years = 0
    positive_cagr_years = 0
    for year, start, end in slices:
        days = _days(ds, int(year))
        res = run_window(spec, _default_params(spec), ds, cost, data_root, start, end)
        m = dict(res.metrics)
        cagr = m.get("cagr")
        if days < MIN_YEAR_DAYS or cagr is None or math.isnan(float(cagr)):
            year_rows.append({"year": year, "trading_days": days,
                              "status": "insufficient_data", "metrics": m})
            continue
        valid_cagr_years += 1
        if cagr > 0:
            positive_cagr_years += 1
        year_rows.append({"year": year, "trading_days": days,
                          "status": "ok", "metrics": m})
    pos_cagr_frac = (
        positive_cagr_years / valid_cagr_years if valid_cagr_years else 0.0
    )
    return {
        "years": year_rows,
        "valid_year_count": valid_cagr_years,
        "positive_cagr_year_count": positive_cagr_years,
        "positive_cagr_fraction": pos_cagr_frac,
        "min_year_days": MIN_YEAR_DAYS,
    }


def _days(ds, year: int) -> int:
    """Number of UNIQUE trading dates in the calendar year (M5 review P1: the
    long research frame has one row per symbol per date, so counting rows would
    inflate by the universe size)."""
    dates = pd.to_datetime(ds.research_frame()["date"]).dt.normalize()
    return int(dates[dates.dt.year == year].nunique())


def _default_params(spec) -> dict[str, Any]:
    from pql.signals.registry import effective_params

    return effective_params(spec, None)


__all__ = ["grid_configs", "parameter_robustness", "time_robustness"]
```

### `src\pql\validation\stress.py`

```python
"""M6.1 / M6.2 Cost + Execution stress (D9/D3/D2).

Cost stress: multiplier [1x, 2x, 3x] via the frozen `apply_stress` (scales
fee_rate AND slippage; D3). Every variant is a FULL `run_backtest()` — cost is
fed through the engine so it lands in equity/orders/fees/metrics, never a
post-hoc subtraction from final returns.

Execution stress: the frozen E01-E05 enumeration (M6.2), all executed:
    E01 {execution_bar: 2}
    E02 {execution_price: open}
    E03 {slippage: base + 0.002}        (ADDITIVE, not multiplicative)
    E04 {miss_rate: 0.05, seed: 7}      (deterministic reject-mask, full rerun)
    E05 {execution_bar: 1, execution_price: open}

Execution Revaluation is preserved for every variant: TargetWeightIntent
keeps val_price = close of the bar before the execution bar (execution_bar=1 ->
T close; execution_bar=2 -> T+1 close), and for `execution_price=open` the
portfolio VALUATION stays on raw close while the fill uses raw open (never
close==open). The 5 variants are a FROZEN stress space: no adding / deleting
variants based on results.
"""
from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from typing import Any

from pql.backtest.api import run_backtest
from pql.backtest.costs import apply_stress
from pql.backtest.engine import ExecutionPerturbation
from pql.data.dataset import DatasetView
from pql.schemas import PortfolioConfig
from pql.signals.registry import effective_params
from pql.timing import TimingContract

from .base import build_intent

# Frozen required execution-stress variants (M6.2). Do not add/remove based on
# observed results.
EXEC_VARIANTS = [
    ("E01", "T+2 execution", {"execution_bar": 2}),
    ("E02", "open execution price", {"execution_price": "open"}),
    ("E03", "slippage +0.002", {"slippage_delta": 0.002}),
    ("E04", "miss 5% seed 7", {"miss_rate": 0.05, "seed": 7}),
    ("E05", "T+1 / open execution price", {"execution_bar": 1, "execution_price": "open"}),
]
COST_MULTIPLIERS = (1, 2, 3)


def _num(v):
    return v if isinstance(v, (int, float)) and not math.isnan(v) else None


def _run_variant(
    spec,
    params: dict[str, Any],
    ds: DatasetView,
    cost,
    data_root: str | Path,
    *,
    timing: TimingContract | None = None,
    perturbation: ExecutionPerturbation | None = None,
    start: str | None = None,
    end: str | None = None,
):
    """Full run_backtest on [start, end] with optional timing / cost / execution
    perturbation overrides. Signal is built PIT once over the full in-sample
    research frame (momentum warmup preserved); the window/delay/price/cost
    knobs only affect EXECUTION, never the decision."""
    intent = build_intent(spec, effective_params(spec, params), ds)
    start = start or spec.windows["in_sample"][0]
    end = end or spec.windows["in_sample"][1]
    win = DatasetView.load(
        spec.dataset_version, data_root, universe=spec.universe, start=start, end=end,
    )
    if timing is None:
        timing = TimingContract(
            execution_bar=int(spec.timing.get("execution_bar", 1)),
            execution_price=spec.timing.get("execution_price", "close"),
        )
    portfolio = PortfolioConfig(
        init_cash=1_000_000,
        max_positions=spec.risk.get("max_positions"),
        weighting="equal",
    )
    return run_backtest(
        intent=intent, universe=spec.universe, execution_model=timing,
        cost_model=cost, portfolio_config=portfolio, dataset=win,
        perturbation=perturbation,
    )


def _variant(variant_id: str, name: str, params: dict, res) -> dict[str, Any]:
    return {
        "variant_id": variant_id,
        "variant_name": name,
        "parameters": params,
        "metrics": dict(res.metrics),
        "sharpe": _num(res.metrics.get("sharpe")),
        "max_drawdown": _num(res.metrics.get("max_drawdown")),
        "cagr": _num(res.metrics.get("cagr")),
        "equity": res.equity,
        "orders": res.orders,
        "run_ref": None,
        "valuation_mode": res.run_meta.get("valuation_mode"),
    }


def cost_stress(
    spec, cost, ds: DatasetView, data_root: str | Path,
    multipliers: tuple[int, ...] = COST_MULTIPLIERS,
) -> list[dict[str, Any]]:
    """Cost stress variants 1x/2x/3x. Each is a full backtest with the stressed
    cost model (apply_stress). The 2x Sharpe is the gate input; 1x is the
    baseline/consistency check; 3x is diagnostic stress evidence."""
    variants: list[dict[str, Any]] = []
    params = effective_params(spec, None)
    for m in multipliers:
        stressed = apply_stress(cost, m)
        res = _run_variant(spec, params, ds, stressed, data_root)
        v = _variant(f"C{m}x", f"cost x{m}", {"multiplier": m}, res)
        v["fee_rate"] = stressed.fee_rate
        v["slippage"] = stressed.slippage
        v["cost_model_version"] = cost.version
        variants.append(v)
    return variants


def execution_stress(spec, cost, ds: DatasetView, data_root: str | Path) -> list[dict[str, Any]]:
    """Run ALL frozen execution variants (E01-E05) on the in-sample window."""
    base_timing = TimingContract(
        execution_bar=int(spec.timing.get("execution_bar", 1)),
        execution_price=spec.timing.get("execution_price", "close"),
    )
    params = effective_params(spec, None)
    variants: list[dict[str, Any]] = []

    def run(timing, cost_model, perturbation=None):
        return _run_variant(spec, params, ds, cost_model, data_root,
                            timing=timing, perturbation=perturbation)

    # E01 execution_bar=2 (Execution Revaluation -> val_price = T+1 close)
    res = run(TimingContract(execution_bar=2, execution_price=base_timing.execution_price), cost)
    variants.append(_variant("E01", "T+2 execution", {"execution_bar": 2}, res))

    # E02 execution_price=open (valuation stays close, fill at open)
    res = run(TimingContract(execution_bar=base_timing.execution_bar, execution_price="open"), cost)
    variants.append(_variant("E02", "open execution price", {"execution_price": "open"}, res))

    # E03 slippage +0.002 (ADDITIVE to base slippage, frozen M6 contract)
    slippy = replace(cost, slippage=cost.slippage + 0.002)
    res = run(base_timing, slippy)
    variants.append(_variant("E03", "slippage +0.002", {"slippage_delta": 0.002}, res))
    variants[-1]["slippage"] = slippy.slippage

    # E04 miss 5% seed 7 (deterministic reject-mask, full engine rerun)
    res = run(base_timing, cost, perturbation=ExecutionPerturbation(miss_rate=0.05, seed=7))
    variants.append(_variant("E04", "miss 5% seed 7", {"miss_rate": 0.05, "seed": 7}, res))

    # E05 execution_bar=1 + execution_price=open
    res = run(TimingContract(execution_bar=1, execution_price="open"), cost)
    variants.append(_variant("E05", "T+1 / open execution price",
                             {"execution_bar": 1, "execution_price": "open"}, res))

    return variants


def worst_exec_max_drawdown(exec_variants: list[dict[str, Any]]) -> float:
    """Conservative gate input: min(max_drawdown) across ALL required execution
    variants (PLAN_CLARIFICATION M6-002: the plan/D9 give no per-variant
    aggregation, so we use the worst required variant, never the prettiest)."""
    mds = [_num(v.get("max_drawdown")) for v in exec_variants if v.get("variant_id") in _REQUIRED_EXEC]
    vals = [m for m in mds if m is not None]
    return min(vals) if vals else 0.0


_REQUIRED_EXEC = {v[0] for v in EXEC_VARIANTS}


__all__ = [
    "COST_MULTIPLIERS",
    "EXEC_VARIANTS",
    "cost_stress",
    "execution_stress",
    "worst_exec_max_drawdown",
]
```

### `src\pql\validation\walkforward.py`

```python
"""M5.2 walk-forward validation (D8/D9).

Fixed rolling scheme: train=756 trading days, test=252, step=252. Each fold
selects the best grid config on the TRAIN window only (by Sharpe, tie-break
selection_key ascending), then scores it OOS on the TEST window. The signal is
built point-in-time over the full in-sample research, so the test window has
pre-test momentum/MA warmup without leaking test data into selection.

Fold repetition never multiplies the trial count: selection uses the same
DISTINCT selection_keys across folds (dedup by key, D7/A6).
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

from pql.backtest.metrics import compute_metrics
from pql.registry.experiments import selection_key

from .base import run_window

TRAIN = 756
TEST = 252
STEP = 252
_MIN_DAYS = TRAIN + TEST


class WalkforwardSkipped(Exception):
    """Raised when the data is too short for even one walk-forward fold."""


def segment_folds(n_days: int) -> list[tuple[int, int, int, int]]:
    """[(train_start, train_end, test_start, test_end)] indices, non-overlapping
    test segments, rolling train window of TRAIN days."""
    out: list[tuple[int, int, int, int]] = []
    i = 0
    while i * STEP + TRAIN + TEST <= n_days:
        train_start = i * STEP
        train_end = train_start + TRAIN
        test_start = train_end
        test_end = test_start + TEST
        out.append((train_start, train_end, test_start, test_end))
        i += 1
    return out


def _select_on_train(grid, spec, ds, cost, data_root, start, end) -> tuple[float, str, dict]:
    """Pick the best config by IS Sharpe on the train window only (tie-break:
    selection_key ascending). Returns (best_sharpe, best_key, best_params)."""
    best: tuple[float, str, dict] | None = None
    for cfg in grid:
        res = run_window(spec, cfg, ds, cost, data_root, start, end)
        sharpe = res.metrics.get("sharpe")
        if sharpe is None or math.isnan(float(sharpe)):  # nan -> worst
            sharpe = float("-inf")
        sk = selection_key(cfg)
        if best is None or sharpe > best[0] or (sharpe == best[0] and sk < best[1]):
            best = (float(sharpe), sk, dict(cfg))
    assert best is not None
    return best


def walkforward(
    spec,
    grid: list[dict[str, Any]],
    ds,
    cost,
    data_root: str | Path,
) -> dict[str, Any]:
    """Run walk-forward over the full in-sample range. Returns a report dict
    with per-fold selections/OOS metrics, combined OOS metrics, and the positive
    test-segment Sharpe fraction. If data is too short, returns skipped."""
    dates = pd.to_datetime(pd.Series(ds.research_frame()["date"].dt.normalize()).unique())
    dates = pd.DatetimeIndex(sorted(dates))
    n = len(dates)
    if n < _MIN_DAYS:
        return {
            "status": "skipped",
            "reason": f"insufficient_data: {n} trading days < {_MIN_DAYS} (train+test)",
            "n_days": n,
            "train": TRAIN,
            "test": TEST,
            "step": STEP,
        }

    folds = segment_folds(n)
    fold_reports: list[dict] = []
    combined_equity_parts: list[pd.Series] = []
    prev_value = 1_000_000.0
    for (ts, te, us, ue) in folds:
        train_start = dates[ts].strftime("%Y-%m-%d")
        train_end = dates[te - 1].strftime("%Y-%m-%d")
        test_start = dates[us].strftime("%Y-%m-%d")
        test_end = dates[ue - 1].strftime("%Y-%m-%d")

        best_sharpe, best_key, best_params = _select_on_train(
            grid, spec, ds, cost, data_root, train_start, train_end
        )
        test_res = run_window(spec, best_params, ds, cost, data_root, test_start, test_end)
        test_metrics = test_res.metrics
        # chain the OOS equity so the combined curve is continuous
        test_equity = pd.Series(test_res.equity).sort_index()
        scale = prev_value / test_equity.iloc[0]
        chained = test_equity * scale
        combined_equity_parts.append(chained)
        prev_value = chained.iloc[-1]

        fold_reports.append(
            {
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                "selected_params": best_params,
                "selection_key": best_key,
                "train_sharpe": best_sharpe,
                "test_metrics": {k: v for k, v in test_metrics.items()},
            }
        )

    combined_equity = pd.concat(combined_equity_parts)
    combined_metrics = compute_metrics(combined_equity)
    pos_frac = sum(
        1 for f in fold_reports
        if (f["test_metrics"].get("sharpe") or float("-inf")) > 0
    ) / len(fold_reports)

    return {
        "status": "ok",
        "train": TRAIN,
        "test": TEST,
        "step": STEP,
        "fold_count": len(fold_reports),
        "folds": fold_reports,
        "combined_oos_metrics": {k: v for k, v in combined_metrics.items()},
        "positive_sharpe_segment_fraction": pos_frac,
        "combined_oos_equity": combined_equity,
    }


__all__ = ["STEP", "TEST", "TRAIN", "WalkforwardSkipped", "segment_folds", "walkforward"]
```

### `src\pql\backtest\__init__.py`

```python

```

### `src\pql\backtest\api.py`

```python
"""M3 backtest public API (D10). `run_backtest` is the single domain entry point;
strategies never import vectorbt directly. Production cost policy (fee_rate > 0)
is enforced here; the raw engine (engine.run_backtest_impl) is what the ZeroCost
golden unit tests exercise.
"""
from __future__ import annotations

from pql.schemas import BacktestResult, CostModel, PortfolioConfig
from pql.timing import TimingContract

from ..data.dataset import DatasetView
from .costs import assert_production_costs
from .engine import (
    ExecutionPerturbation,
    SignalIntent,
    TargetWeightIntent,
    TradingIntent,
    generate_reject_mask,
    run_backtest_impl,
)

__all__ = [
    "BacktestResult",
    "ExecutionPerturbation",
    "SignalIntent",
    "TargetWeightIntent",
    "TradingIntent",
    "generate_reject_mask",
    "run_backtest",
]


def run_backtest(
    intent: TradingIntent,
    universe: list[str],
    execution_model: TimingContract,
    cost_model: CostModel,
    portfolio_config: PortfolioConfig,
    dataset: DatasetView,
    perturbation: ExecutionPerturbation | None = None,
) -> BacktestResult:
    """Run a backtest through the vectorbt engine; production cost must be > 0."""
    assert_production_costs(cost_model)
    return run_backtest_impl(
        intent=intent,
        universe=universe,
        execution_model=execution_model,
        cost_model=cost_model,
        portfolio_config=portfolio_config,
        dataset=dataset,
        perturbation=perturbation,
    )


```

### `src\pql\backtest\costs.py`

```python
"""M3 cost model helpers (D3). `apply_stress` scales fee_rate and slippage by a
multiplier (1x/2x/3x). Production cost must be positive; the engine unit tests
use an explicit ZeroCostFixture instead of weakening the production policy.
"""
from __future__ import annotations

from dataclasses import replace

from pql.schemas import CostModel, load_cost_model


class CostModelError(ValueError):
    """Raised when a cost model violates the production non-zero cost policy."""


def apply_stress(model: CostModel, multiplier: float) -> CostModel:
    """Scale fee_rate and slippage by `multiplier` (plan M6: 1x/2x/3x)."""
    if multiplier <= 0:
        raise CostModelError(f"stress multiplier must be > 0, got {multiplier}")
    return replace(
        model,
        fee_rate=model.fee_rate * multiplier,
        slippage=model.slippage * multiplier,
    )


def assert_production_costs(model: CostModel) -> None:
    """Production backtests must have positive fee_rate (D3)."""
    if model.fee_rate <= 0:
        raise CostModelError(
            f"production cost model must have fee_rate > 0, got {model.fee_rate}; "
            "use ZeroCostFixture only in engine unit tests"
        )


__all__ = [
    "CostModel",
    "CostModelError",
    "apply_stress",
    "assert_production_costs",
    "load_cost_model",
]

```

### `src\pql\backtest\engine.py`

```python
"""M3 vectorbt engine (D10). Routes TradingIntent to vectorbt:
- SignalIntent -> Portfolio.from_signals (shift signals by execution_bar)
- TargetWeightIntent -> Portfolio.from_orders (targetpercent, cash_sharing,
  call_seq='auto', group_by, val_price = Execution Revaluation)

Crucial separation (frozen contract): portfolio VALUATION uses the raw close
series, order EXECUTION uses the raw open/close series (execution_price), and
TargetWeight sizing (val_price) uses the raw close. Adjusted research prices are
never used for execution. Builds the BacktestResult with vectorbt provenance.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import vectorbt as vbt

from pql.schemas import BacktestResult, CostModel, PortfolioConfig
from pql.timing import TimingContract, assert_no_lookahead

from ..data.dataset import DatasetView
from .metrics import compute_metrics


@dataclass(frozen=True)
class SignalIntent:
    """Long-only entries/exits boolean signals (Trend / Buy & Hold)."""

    entries: pd.DataFrame  # bool, index=date, columns=symbol
    exits: pd.DataFrame  # bool, index=date, columns=symbol


@dataclass(frozen=True)
class TargetWeightIntent:
    """Target portfolio weights (Rotation / Allocation). NaN = no adjustment."""

    weights: pd.DataFrame  # float [0,1], index=date, columns=symbol


TradingIntent = SignalIntent | TargetWeightIntent


@dataclass(frozen=True)
class ExecutionPerturbation:
    """M6 miss-stress perturbation (path-dependent, full engine rerun — NOT
    post-hoc order surgery).

    The caller passes EITHER an explicit `reject_mask` (bool grid on
    date x symbol: True = the order is rejected) OR `miss_rate` + `seed` (the
    engine builds the deterministic mask aligned to the actual order-event
    grid). Rejected cells are dropped from the execution input BEFORE vectorbt
    runs, so the whole portfolio path (cash, subsequent buys/sells) evolves
    naturally — a missed SELL changes cash and can break a later BUY, which a
    post-hoc deletion could never reproduce.
    """

    reject_mask: pd.DataFrame | None = None
    miss_rate: float = 0.0
    seed: int = 0

    def validate(self) -> None:
        if self.reject_mask is not None and (self.miss_rate or self.seed):
            raise ValueError("provide either reject_mask or miss_rate/seed, not both")
        if self.reject_mask is None and (self.miss_rate < 0 or self.miss_rate > 1):
            raise ValueError(f"miss_rate must be in [0, 1], got {self.miss_rate}")


def generate_reject_mask(
    event_cells: pd.DataFrame, miss_rate: float, seed: int
) -> pd.DataFrame:
    """Deterministic reject mask over the order-event grid.

    Selects ceil(miss_rate * n_events) event cells via a seeded RNG. Same seed
    -> same mask; different seed -> different mask (frozen M6 contract). Cells
    that are not order events are never rejected. Returns True where the order
    is REJECTED.
    """
    rng = np.random.default_rng(seed)
    mask = pd.DataFrame(False, index=event_cells.index, columns=event_cells.columns)
    locs = np.argwhere(event_cells.to_numpy())
    n = len(locs)
    if n == 0:
        return mask
    k = int(np.ceil(miss_rate * n))
    if k > 0:
        chosen = rng.choice(n, size=min(k, n), replace=False)
        for i in chosen:
            r, c = locs[i]
            mask.iat[r, c] = True
    return mask


def _price_frame(dataset: DatasetView, column: str) -> pd.DataFrame:
    frame = dataset.execution_frame()  # [date, symbol, open, close]
    if column not in ("open", "close"):
        raise ValueError(f"column must be 'open' or 'close', got {column!r}")
    pivot = frame.pivot(index="date", columns="symbol", values=column)
    return pivot.sort_index()


def _to_equity_series(value) -> pd.Series:
    """Total portfolio value; a multi-column value frame is summed to one nav."""
    if isinstance(value, pd.DataFrame):
        return value.sum(axis=1)
    return value


def _closed_trades(trades, cols: list[str], dates: pd.Index) -> list[dict]:
    """Normalize vectorbt closed-trade records into PQL `ClosedTrade` facts
    (K02 drop_best_trades needs entry/exit dates, symbol, size, net PnL, fees).
    vectorbt `pnl` is net of entry/exit fees; `fees` is the total trade fee."""
    out: list[dict] = []
    if trades is None or len(trades) == 0:
        return out
    for t in trades.itertuples():
        entry_idx = int(t.entry_idx)
        exit_idx = int(t.exit_idx)
        col = int(t.col)
        symbol = cols[col] if col < len(cols) else str(col)
        entry_date = str(dates[entry_idx].date()) if entry_idx < len(dates) else None
        exit_date = str(dates[exit_idx].date()) if exit_idx < len(dates) else None
        fees = float(getattr(t, "entry_fees", 0.0)) + float(getattr(t, "exit_fees", 0.0))
        out.append(
            {
                "symbol": symbol,
                "entry_date": entry_date,
                "exit_date": exit_date,
                "size": float(t.size),
                "net_pnl": float(t.pnl),
                "fees": fees,
                "status": int(t.status),
            }
        )
    return out


def run_backtest_impl(
    intent,
    universe: list[str],
    execution_model: TimingContract,
    cost_model: CostModel,
    portfolio_config: PortfolioConfig,
    dataset: DatasetView,
    perturbation: ExecutionPerturbation | None = None,
) -> BacktestResult:
    assert_no_lookahead(execution_model)
    if perturbation is not None:
        perturbation.validate()

    # VALUATION price is always the raw close; EXECUTION price is open or close.
    raw_close = _price_frame(dataset, "close")
    order_price = (
        _price_frame(dataset, "open")
        if execution_model.execution_price == "open"
        else raw_close
    )
    cols = [s for s in universe if s in raw_close.columns]
    raw_close = raw_close.reindex(columns=cols)
    order_price = order_price.reindex(columns=cols)
    n = execution_model.execution_bar
    has_price = order_price.notna()

    skipped: list[tuple] = []
    if isinstance(intent, SignalIntent):
        entries = intent.entries.reindex(
            index=order_price.index, columns=order_price.columns, fill_value=False
        )
        exits = intent.exits.reindex(
            index=order_price.index, columns=order_price.columns, fill_value=False
        )
        # skipped is judged at the EXECUTION day (signal shifted), where the fill
        # would have happened: signal active pre-shift AND no execution price.
        active_exec = (entries | exits).shift(n, fill_value=False)
        skipped = [
            (d.date(), s)
            for d in order_price.index
            for s in order_price.columns
            if not bool(has_price.loc[d, s]) and bool(active_exec.loc[d, s])
        ]
        entries = entries & has_price
        exits = exits & has_price

        # Multi-asset SignalIntent = ONE shared portfolio account (single
        # init_cash pool), not N independent per-symbol portfolios.
        #
        # Allocation: with PortfolioConfig.weighting == "equal", the held set is
        # allocated EQUAL portfolio weight (1/n_held). from_signals cannot
        # express this for multiple simultaneous entries: its `size` is in
        # shares (size_type='amount'), so two simultaneous entries degenerate to
        # 100%/0% (the first symbol consumes the whole pool). We therefore route
        # the multi-asset equal-weight case through the same from_orders
        # targetpercent machinery as TargetWeightIntent.
        # PLAN_DEVIATION (M4 review): multi-asset equal-weight SignalIntent no
        # longer maps strictly to from_signals; documented in the M4 report.
        val_price = raw_close.shift(1).fillna(raw_close)
        if portfolio_config.weighting == "equal" and len(cols) > 1:
            held = (entries.cumsum() - exits.cumsum()).clip(0, 1).astype(bool)
            n_held = held.sum(axis=1).replace(0, 1.0)
            weights = held.div(n_held, axis=0).where(held, 0.0)
            # ROW-level rebalance (M4 rev2): whenever the held set CHANGES at a
            # bar (any entry/exit), submit the FULL target vector so every held
            # symbol (existing AND newly added) is re-weighted to 1/N. A
            # cell-level mask would leave untouched symbols at their stale
            # weight (e.g. A stays 50% when B exits, instead of rebalancing to
            # 100%). On bars with no held-set change the whole row is NaN ->
            # no rebalancing (pure SignalIntent enter/exit semantics).
            held_changed = (entries | exits).any(axis=1)
            weights = weights.where(held_changed, other=float("nan"), axis=0)
            weights = weights.where(has_price)
            weights_exec = weights.shift(n)
            if perturbation is not None:
                reject = (
                    perturbation.reject_mask
                    if perturbation.reject_mask is not None
                    else generate_reject_mask(
                        weights_exec.notna(), perturbation.miss_rate, perturbation.seed
                    )
                )
                reject = reject.reindex(
                    index=weights_exec.index, columns=weights_exec.columns, fill_value=False
                )
                weights_exec = weights_exec.where(~reject)
            pf = vbt.Portfolio.from_orders(
                close=raw_close,
                price=order_price,
                size=weights_exec,
                size_type="targetpercent",
                cash_sharing=True,
                call_seq="auto",
                group_by=True,
                val_price=val_price,
                init_cash=portfolio_config.init_cash,
                fees=cost_model.fee_rate,
                slippage=cost_model.slippage,
                freq="D",
                direction="longonly",
            )
            intent_kind = "signal"
            valuation_mode = "equal_weight_signal"
        else:
            entries_exec = entries.shift(n, fill_value=False)
            exits_exec = exits.shift(n, fill_value=False)
            if perturbation is not None:
                reject = (
                    perturbation.reject_mask
                    if perturbation.reject_mask is not None
                    else generate_reject_mask(
                        (entries_exec | exits_exec), perturbation.miss_rate, perturbation.seed
                    )
                )
                reject = reject.reindex(
                    index=entries_exec.index, columns=entries_exec.columns, fill_value=False
                )
                entries_exec = entries_exec & ~reject
                exits_exec = exits_exec & ~reject
            pf = vbt.Portfolio.from_signals(
                close=raw_close,
                price=order_price,
                entries=entries_exec,
                exits=exits_exec,
                init_cash=portfolio_config.init_cash,
                fees=cost_model.fee_rate,
                slippage=cost_model.slippage,
                freq="D",
                direction="longonly",
                group_by=True,
                cash_sharing=True,
            )
            intent_kind = "signal"
            valuation_mode = "signal_fill"
    else:
        weights = intent.weights.reindex(
            index=order_price.index, columns=order_price.columns
        )
        weights_exec = weights.shift(n)
        skipped = [
            (d.date(), s)
            for d in order_price.index
            for s in order_price.columns
            if not bool(has_price.loc[d, s]) and pd.notna(weights_exec.loc[d, s])
        ]
        weights = weights.where(has_price)
        # Execution Revaluation (frozen): target quantity sized at the close of
        # the bar BEFORE the execution bar; first bar falls back to its own close.
        val_price = raw_close.shift(1).fillna(raw_close)
        weights_exec = weights.shift(n)
        if perturbation is not None:
            reject = (
                perturbation.reject_mask
                if perturbation.reject_mask is not None
                else generate_reject_mask(
                    weights_exec.notna(), perturbation.miss_rate, perturbation.seed
                )
            )
            reject = reject.reindex(
                index=weights_exec.index, columns=weights_exec.columns, fill_value=False
            )
            weights_exec = weights_exec.where(~reject)
        pf = vbt.Portfolio.from_orders(
            close=raw_close,
            price=order_price,
            size=weights_exec,
            size_type="targetpercent",
            cash_sharing=True,
            call_seq="auto",
            group_by=True,
            val_price=val_price,
            init_cash=portfolio_config.init_cash,
            fees=cost_model.fee_rate,
            slippage=cost_model.slippage,
            freq="D",
            direction="longonly",
        )
        intent_kind = "target_weight"
        valuation_mode = "execution_revaluation"

    equity = _to_equity_series(pf.value())
    asset_value = _to_equity_series(pf.asset_value())
    orders = pf.orders.records
    trades = pf.trades.records
    metrics = compute_metrics(
        equity,
        orders=orders,
        trades=trades,
        asset_value=asset_value,
        dates=order_price.index,
    )
    run_meta = {
        "engine": "vectorbt",
        "vectorbt_version": vbt.__version__,
        "intent": intent_kind,
        "execution_bar": n,
        "execution_price": execution_model.execution_price,
        "valuation_mode": valuation_mode,
        "cost_model_version": cost_model.version,
        "fee_rate": cost_model.fee_rate,
        "slippage": cost_model.slippage,
        "init_cash": portfolio_config.init_cash,
        "skipped_no_price": skipped,
        "closed_trades": _closed_trades(trades, cols, order_price.index),
        "asset_value": asset_value,
        "trades": trades,
        "perturbation": (
            {
                "miss_rate": perturbation.miss_rate,
                "seed": perturbation.seed,
                "reject_mask": perturbation.reject_mask is not None,
            }
            if perturbation is not None
            else None
        ),
    }
    return BacktestResult(equity=equity, orders=orders, metrics=metrics, run_meta=run_meta)
```

### `src\pql\backtest\metrics.py`

```python
"""M3 domain metrics (D8). Formulas are frozen by the plan, NOT borrowed from
vectorbt's default statistics: annualization factor 252, Sharpe rf=0, std
ddof=1. Equity-based metrics are independently unit-tested against hand-built
return series. Trade/position FACTS (n_trades, win_rate, exposure, turnover)
are extracted from the executed vectorbt portfolio (trades/orders/asset_value)
and reduced with PQL-defined formulas — the engine supplies facts, PQL defines
the metrics.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ANNUALIZATION = 252


def _returns(equity: pd.Series) -> pd.Series:
    return equity.pct_change().dropna()


def cagr(equity: pd.Series) -> float:
    n = len(equity)
    if n < 2 or equity.iloc[0] <= 0 or equity.iloc[-1] <= 0:
        return float("nan")
    return float((equity.iloc[-1] / equity.iloc[0]) ** (ANNUALIZATION / (n - 1)) - 1)


def annual_vol(equity: pd.Series) -> float:
    r = _returns(equity)
    if len(r) < 2:
        return float("nan")
    return float(r.std(ddof=1) * np.sqrt(ANNUALIZATION))


def sharpe(equity: pd.Series) -> float:
    r = _returns(equity)
    if len(r) < 2:
        return float("nan")
    sd = r.std(ddof=1)
    if sd == 0:
        return float("nan")
    return float(r.mean() / sd * np.sqrt(ANNUALIZATION))


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return float((equity / equity.cummax() - 1).min())


def calmar(cagr_value: float, max_dd: float) -> float:
    if max_dd == 0:
        return float("nan")
    return float(cagr_value / abs(max_dd))


def _turnover(orders: pd.DataFrame, dates: pd.Index, equity: pd.Series) -> float:
    """D8 turnover = daily average of one-sided traded notional / portfolio nav.
    One-sided: each order's gross notional |size*price| counts once per day."""
    if orders is None or orders.empty or dates is None or len(dates) == 0:
        return 0.0
    by_idx: dict[int, list] = {}
    for o in orders.itertuples():
        by_idx.setdefault(int(o.idx), []).append(o)
    daily_traded = []
    for i, _dt in enumerate(dates):
        notional = sum(
            abs(float(o.size) * float(o.price)) for o in by_idx.get(i, [])
        )
        daily_traded.append(notional)
    nav = equity.reindex(dates)
    daily_tov = [
        (t / e if e > 0 else 0.0) for t, e in zip(daily_traded, nav)
    ]
    return float(np.mean(daily_tov)) if daily_tov else 0.0


def _exposure(asset_value: pd.Series, equity: pd.Series) -> float:
    """D8 exposure = daily mean of asset value / total value (0..1)."""
    if asset_value is None or asset_value.empty:
        return float("nan")
    aligned = pd.concat([asset_value, equity], axis=1, join="inner")
    if aligned.empty:
        return float("nan")
    ratio = aligned.iloc[:, 0] / aligned.iloc[:, 1].replace(0, np.nan)
    return float(ratio.mean())


def _trade_stats(trades: pd.DataFrame, orders: pd.DataFrame | None) -> tuple[int, float]:
    """n_trades counts CLOSED round trips; win_rate = fraction with pnl > 0
    (vectorbt pnl is net of entry/exit fees)."""
    if trades is not None and not trades.empty:
        if "status" in trades.columns:
            closed = trades[trades["status"] == 1]
        else:
            closed = trades
        if "pnl" in closed.columns and len(closed):
            return len(closed), float((closed["pnl"] > 0).mean())
        return len(closed), float("nan")
    return (len(orders) if orders is not None else 0), float("nan")


def compute_metrics(
    equity: pd.Series,
    *,
    orders: pd.DataFrame | None = None,
    trades: pd.DataFrame | None = None,
    asset_value: pd.Series | None = None,
    dates: pd.Index | None = None,
) -> dict[str, float]:
    """Full D8 metric set. Equity metrics always; order-derived metrics from the
    executed vectorbt portfolio facts when provided."""
    cagr_v = cagr(equity)
    maxd = max_drawdown(equity)
    metrics: dict[str, float] = {
        "cagr": cagr_v,
        "annual_vol": annual_vol(equity),
        "sharpe": sharpe(equity),
        "max_drawdown": maxd,
        "calmar": calmar(cagr_v, maxd),
    }
    n_trades, win_rate = _trade_stats(trades, orders)
    metrics.update(
        {
            "n_trades": n_trades,
            "turnover": _turnover(orders, dates, equity),
            "exposure": _exposure(asset_value, equity),
            "win_rate": win_rate,
        }
    )
    return metrics


def metrics_vs_benchmark(equity: pd.Series, benchmark_equity: pd.Series) -> dict[str, float]:
    """Excess return and tracking error vs a benchmark equity curve."""
    r = _returns(equity)
    rb = _returns(benchmark_equity)
    excess = (equity.iloc[-1] / equity.iloc[0]) - (benchmark_equity.iloc[-1] / benchmark_equity.iloc[0])
    aligned = pd.concat([r, rb], axis=1, join="inner").dropna()
    te = (
        float(aligned.iloc[:, 0].sub(aligned.iloc[:, 1]).std(ddof=1) * np.sqrt(ANNUALIZATION))
        if len(aligned) > 1
        else float("nan")
    )
    return {"excess_return": float(excess), "tracking_error": te}

```
