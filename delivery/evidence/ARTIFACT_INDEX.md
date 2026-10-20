# 证据索引（本次复现，所有产物路径与含义）

生成时间：2026-10-20。本地路径根：`C:\Users\Asus\Desktop\molrepbench\molrepbench_reproduction\`

## 1. 来源与许可

| 文件 | 内容 |
|---|---|
| `UPSTREAM_PROVENANCE.json` | 作者仓库 `arunraja-hub/molrepbench` 固定 commit `21d36941cddf0dc1ffb5f3590296592dc68e4ac8` 的 32 个文件 SHA256 |
| `vendor/molrepbench/` | 作者原始代码，**未做任何修改**；`verify-vendor` 校验 32/32 一致 |
| `repro/` | 本次新增的便携运行器（准备/推理/评分/审计/报告），复用作者 prompts 与转换函数 |

## 2. 环境

| 文件 | 内容 |
|---|---|
| `evidence/doctor_output.json` | 本次运行环境：Python 3.12.15、Windows 11、rdkit 2025.9.6 等全部 pin 版本、obabel CLI 路径 |
| `evidence/env_install_log.txt` | `.venv`（Python 3.12.14 + requirements.txt）安装日志 |
| `evidence/pip_freeze_conda_molrep.txt` / `evidence/conda_list_molrep.txt` | 实际执行管线所用 conda 环境 `molrep` 的完整依赖快照 |
| `evidence/unittest_run.txt` | 11 个单元测试全部通过的完整日志 |

## 3. 计划（离线，不调用模型）

| 文件 | 内容 |
|---|---|
| `plans/smoke/plan.json` + `manifest.jsonl` | 270 条请求；8 任务 × 9 表示全覆盖；manifest SHA256 与交付环境一致 |
| `plans/paper/plan.json` + `manifest.jsonl` | 29139 条请求；`excluded.jsonl` 记录 3 个缺 IUPAC 名称的分子对（B5:355、B10:170、B10:195） |
| `plans/paper_verified/plan.json` + `manifest.jsonl` | 仅保留 OPSIN 立体身份完全一致的 IUPAC 输入：27654 条，928 条排除 |
| `evidence/prepare_smoke_log.txt`、`evidence/prepare_paper_log.txt`、`evidence/prepare_paper_verified_log.txt` | 生成日志 |

## 4. 数据审计与标签

| 文件 | 内容 |
|---|---|
| `evidence/audit_rerun.json` + `audit_rerun_log.txt` | 离线审计重跑，与交付环境证据逐字段一致（B5/B9/B10/理解力子集） |
| `evidence/iupac_audit_final_log.txt` | 含 RDKit 互变异构体枚举警告的运行日志（max transforms/max tautomers reached、kekulize 失败） |
| `evidence/iupac_input_audit.json` | 4551 个 (SMILES, IUPAC) 成员经 OPSIN 解析结果：2697 立体身份一致、41 仅连接性一致、1567 不一致、287 无法解析 |
| `evidence/iupac_prefetch_run.txt` | 并行预取日志（3743 次网络解析，10 次抓取失败记录在 `results/opsin_failures.jsonl`） |
| `evidence/b9_label_sensitivity.json` | B9 4 个争议标签在默认与 10000 上限枚举下均不一致的敏感性记录 |
| `evidence/representation_length_stats.json` | 9 种表示在 paper 计划中的字符长度统计（CML 均值 4363、MolJSON 2888、canonical SMILES 70） |

## 5. 模型运行（真实推理）

| 文件 | 内容 |
|---|---|
| `settings.json` | 本次模型配置（base_url https://api.deepseek.com、model deepseek-flash、thinking 关闭、max_tokens 8192、prompt_only），**不含密钥** |
| `.env`（未交付） | 密钥本地文件，已在 .gitignore；由 tools/run_with_key.py 注入子进程环境变量 |
| `evidence/settings_decisions.md` | 模型身份、推理模式实测、结构化输出、采样参数与偏差（partial reproduction 依据） |
| `results/probe_A_thinking_off_2048/`、`probe_B_default_8192/`、`probe_C_thinking_off_8192/` | 三组参数各 1 条真实请求，用于证明 `thinking:{type:disabled}` 确实关闭推理（无 reasoning_tokens、无 reasoning_content） |
| `results/deepseek-flash_off_smoke/` | 早期 2 条 HTTP 401 失败记录（保留，不删除） |
| `results/deepseek-flash_off_smoke_run2/` | 空 content 失败记录（推理吃光 2048 预算，保留） |
| **`results/deepseek-flash_off_smoke_run3/`** | **正式运行**：270/270 成功；raw.jsonl、scored.jsonl、summary.csv/json、evaluation_status.json、paired_bootstrap.json（空，原因见下） |
| `evidence/score_run3_log.txt`、`evidence/bootstrap_run3_log.txt`、`evidence/smoke_run_log.txt` | 评分、bootstrap、运行日志 |
| `evidence/report_examples.json` | 8 条真实链路示例 + 10 个真实失败案例（抽取自 raw/scored） |

运行统计：270 请求全部 API 成功，269 条解析出答案，267 条 finish_reason=stop，
3 条 finish_reason=length（截断），0 条带推理痕迹，平均 1312 tokens/请求。

## 6. 报告与交付

| 文件 | 内容 |
|---|---|
| `reports/deepseek-flash_off_smoke_run3/experiment_results.docx/.pdf` | 内置机器摘要报告 |
| `reports/deepseek-flash_off_smoke_run3/复现报告_完整版.docx/.pdf` | 完整中文报告：14 章 + 8 条任务链路 + 8 个失败案例 + 100 行成绩总表 |
| `delivery/口述稿_2-3分钟.md` | 2–3 分钟中文口述稿（可直接照读） |
| `delivery/教授追问应答.md` | 15 个教授可能追问的问题与基于证据的回答 |
| `delivery/README.md` | 交付说明与作者代码/本次修改的归属划分 |
| `delivery/未完成清单.md` | 未执行项、需降级表述项、替代实现、数据缺陷、许可提示 |
| `delivery/settings.sample.json` | 脱敏配置 |
| `delivery/SHA256SUMS.txt` | 交付件校验和 |
| `molrepbench_reproduction_delivery.zip` | 最终打包（94 个文件，约 9.3 MB），已扫描确认不含密钥 |

## 7. 工具脚本（本次新增）

`tools/run_with_key.py`（密钥启动）、`tools/prefetch_iupac.py`（并行 OPSIN 预取）、
`tools/api_probe.py`（连通性诊断）、`tools/key_shape_check.py`（密钥形状诊断）、
`tools/try_thinking_variants.py`（推理参数三组探测）、`tools/extract_examples.py`（链路与失败案例抽取）、
`tools/representation_lengths.py`（表示长度统计）、`tools/b9_label_sensitivity_record.py`（B9 敏感性记录）、
`tools/poll_run.py`、`tools/results_table.py`（进度与成绩查看）、
`tools/build_final_report.py`（完整报告生成）、`tools/package_delivery.py`（打包）、
`tools/secret_scan.py`（密钥泄漏扫描）。

## 8. 状态口径（截至交付）

- **已完成**：隔离环境、vendor 32/32 校验、11/11 单元测试、smoke 270 与 paper 29139 计划
  （manifest 哈希与交付环境一致）、离线审计重跑（含 RDKit 枚举警告）、OPSIN IUPAC 审核（4551 成员）、
  paper_verified 路线（27654）、270 条真实推理全部成功、评分与失败案例分析、报告与交付包。
- **未完成**：paper profile 29139 请求、论文 15 个模型、thinking on、FCD、LLM 裁判、§6 tokenizer 与机制分析。
- **bootstrap 为 0 比较的原因**：实现要求每组至少 3 个可配对分子，smoke 每任务仅 2 个分子；
  未放宽阈值去凑数字。