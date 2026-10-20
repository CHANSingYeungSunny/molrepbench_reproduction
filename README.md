# MolRepBench 论文复现项目

本包依据你提供的论文 **Rethinking Molecular Text Representations for LLMs: An Empirical Study**（arXiv:2606.03057v1）及作者公开仓库制作。它包含作者原始代码、原始预处理数据 ZIP、便携 Python 运行器、逐条实验提示词生成器、评分器、测试、中文解释和 CodeBuddy 提示词。

**当前完成的是代码与数据流程验证，没有运行真实 LLM 实验，也没有得到论文复现成绩。** 运行模型需要你已有的本地服务或 API。完整复现还涉及原论文模型、推理模式、生成裁判和机制分析，不能仅凭脚本成功退出宣称全部完成。

先把 `CODEBUDDY_PROMPT.txt` 全文交给 CodeBuddy，让它在解压后的本项目根目录工作。

## 1 零基础启动

建议使用 **64 位 Python 3.12**（也可尝试 3.11）。只解压到一个普通文件夹，不要在 ZIP 内运行。

想先一条命令准备环境，可运行 `py -3.12 start_here.py`（Windows）或 `python3.12 start_here.py`（Mac/Linux）；Windows 也可双击 `START_HERE_WINDOWS.bat`。它会安装依赖并执行下列离线检查，不调用 LLM。具体错误请交给 CodeBuddy，不能仅看窗口是否关闭判断成功。

Windows PowerShell：

```powershell
cd 你的解压目录\molrepbench_reproduction
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe reproduce.py doctor
.\.venv\Scripts\python.exe reproduce.py verify-vendor
.\.venv\Scripts\python.exe reproduce.py setup
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe reproduce.py prepare --profile smoke --out plans/smoke
```

macOS / Linux：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python reproduce.py doctor
.venv/bin/python reproduce.py verify-vendor
.venv/bin/python reproduce.py setup
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python reproduce.py prepare --profile smoke --out plans/smoke
```

后面的 `python` 均指此虚拟环境中的 Python。上面只安装依赖、解压数据、测试和生成提示词，**没有调用付费 LLM**。`plans/smoke/manifest.jsonl` 中有 270 条实际提示词。smoke 每类仅取前 2 个分子或分子对，用于验证流程，样本既小又不保证类别平衡，不能作为科学结论。

OpenBabel 安装失败时，使用 conda-forge 的 Python 3.12 环境安装 `rdkit openbabel`，再安装其余依赖；不要用假的 XML 输出替代 CML。核心命令本身跨平台；本次实际验证环境是 Linux Python 3.12，Windows 需由 CodeBuddy 当地验证。STOUT 的缺失警告来自作者模块的可选导入，本运行器使用公开数据中的 IUPAC 名称，不依赖 STOUT。

## 2 接入真实模型

复制 `settings.example.json` 为 `settings.json`，填入实际服务的 `base_url` 与 `model`。

默认示例面向支持相应参数的 vLLM 服务。**模型必须已加载；本包不含模型权重，也不会自动启动 GPU 服务。** 在 Linux GPU 主机安装适配的 vLLM 后，可按服务支持的方式启动：

```bash
vllm serve /absolute/path/to/downloaded/model --served-model-name my-model --port 8000
```

然后设 `model` 为 `my-model`。这里的名字不是论文模型版本的证明，另需记录下载来源、revision、量化方式和服务启动命令。作者模型与参数位于 `vendor/molrepbench/scripts/config.py`；其中 `/node2/...` 是作者机器路径，不能直接复制使用。

API 路线须为支持 `/chat/completions` 的服务。按服务文档设置 `schema_mode`、`token_parameter` 和推理参数。通用 API 通常应删除 vLLM 专有 `top_k`、`chat_template_kwargs`，不要把一个模型的参数套在所有模型上。`thinking` 字段只是记录标签；**实际推理开关由后端参数/模型本身决定**。设置为 on 并不自动启用推理。某些模型不支持关闭推理，应标记不支持，不能伪造 off 条件。

需要密钥时只设置环境变量，例如 PowerShell `$env:LLM_API_KEY="你的密钥"` 或 bash `export LLM_API_KEY='你的密钥'`。不要写入源码、提示词、报告或 Git。

```bash
python reproduce.py run --plan plans/smoke --settings settings.json --out results/smoke --max-requests 1
python reproduce.py run --plan plans/smoke --settings settings.json --out results/smoke
python reproduce.py score --plan plans/smoke --run results/smoke --allow-network
```

第一次只验证一个请求；随后同一命令续跑。成功的 ID 会跳过，失败项会重试。更换模型、参数或提示词后必须使用新的 `--out`。HTTP 400/401/403/404 会中止，避免持续错误请求。服务不支持 JSON schema 时应修正配置；若使用 `prompt_only`，必须记录与论文的结构化输出约束不同。

## 3 公开数据与论文的差异

冻结仓库：<https://github.com/arunraja-hub/molrepbench>

固定 commit：`21d36941cddf0dc1ffb5f3590296592dc68e4ac8`。`UPSTREAM_PROVENANCE.json` 保存 32 个 Git 跟踪文件的 SHA256。`vendor/` 原始文件保持不变；`repro/` 是本次新增实现，复用了作者的提示词、SMARTS、属性计算和转换函数。

| 已核实问题 | 本包处理 | 对结论的影响 |
|---|---|---|
| 作者配置含绝对服务器路径 | 在内存中替换数据/输出路径 | 只解决可运行性 |
| B5 提示词问“同一分子”，代码用 `natural/stereoisomer` 定标签 | 读取 CSV 的 `ground_truth` | 375/500 标签与原代码不同，不能当作原表格严格重放 |
| B5 CSV 与当前 RDKit 立体身份判断 500/500 一致 | 保留 CSV 标签 | 立体异构体应回答 No；字符串不同也可能是同一分子 |
| B9/B10 CSV 的 source 全部标 ChEBI-20，论文写 ZINC250K | 明确记录未能证实源数据一致 | 不能声称重建了论文的 ZINC 数据 |
| B9/B10 预存 SELFIES 与具体成员 SMILES 不一致的成员数为 183 和 118 | 所有非 IUPAC 表示从成员 SMILES 重新生成 | 修正输入，但不等于复现作者原始输入字节 |
| B9 有 4/250 对的 CSV 标签与当前 RDKit 默认规范互变异构体判断不一致 | 保留公开标签，导出争议索引 | 需检查版本/枚举限制；不擅自宣布作者标错 |
| B9 有 125 对、B10 有 105 对不同结构共享同一 IUPAC 名称 | 默认公开名称路线标未验证；另提供 OPSIN 审核过滤路线 | 名称可能丢失所需区分信息；不能把信息丢失都归因于 LLM |
| 论文 B6 为 200，仓库配置为 250 | paper profile 使用 200 | 记录偏差，不能混用样本规模 |
| 原 B4 按表示改变选项顺序 | 本包对同一问题使用相同顺序 | 更便于配对比较，属于协议改动 |
| 原代码有 `\n\n` 停止序列 | 本包不设置空行停止 | 避免答案被空行提前截断，属于解码差异 |

运行 `python reproduce.py audit` 可重新生成离线审计。它可能耗时约几分钟，RDKit 对复杂分子的互变异构体枚举可能达到默认限制；日志必须保留。

## 4 IUPAC 输入必须单独审核

IUPAC 不等于把 SMILES 换个字符串。公开名称可能对应标准化后的互变异构体或电荷态；同一名称未必忠实表示每个分子对成员。默认 `--iupac-policy released` 是“复用公开名称”路线，所有此类输入标为未验证，不能直接据此下科学结论。

```bash
python reproduce.py audit --iupac
python reproduce.py prepare --profile paper --iupac-policy verified --out plans/paper_verified
```

`audit --iupac` 通过 OPSIN 检查不同名称与成员 SMILES 的映射，可能有数千次网络解析请求，不调用 LLM。它记录不一致、解析失败和网络失败。verified 路线仅保留 OPSIN 解析后与成员结构**立体身份完全一致**的 IUPAC 输入。它不自动发明新名称、不用 SMILES 假充 IUPAC，也不改变其他表示。过滤后样本数可能显著变小，比较须使用共同样本；解析失败不能直接认定化学名称无效。

离线运行时 8 种非 IUPAC 输入表示可本地生成；IUPAC 输入可复用公开名称，IUPAC 生成结果的有效性评分则需要 OPSIN 或已缓存的解析结果。没有解析时显示未评估，不记作失败。

## 5 完整的 9 种表示与 8 类任务

| 任务 | 单一表示的计划规模 | 主指标 |
|---|---:|---|
| B1 元素原子计数 | 200 个分子，每个选 1 元素 | exact accuracy |
| B2 官能团识别 | 200 × 5 问题 | 5 个标签的 Macro-F1 |
| B3 性质估计 | 200 × 4 问题 | LogP/TPSA Spearman；HBD/HBA exact accuracy |
| B4 描述检索 | 78 个四选一问题 | top-1 accuracy |
| B5 同分子判断 | 500 对 | accuracy |
| B6 描述生成分子 | 200 个描述 | validity、exact match、三类指纹 Tanimoto、可选 FCD |
| B9 互变异构体识别 | 250 对 | accuracy |
| B10 质子化态识别 | 210 对 | accuracy |

B7/B8 不在论文这 8 类主任务中，保留作者编号 B9/B10，不凑成 10 个任务。

```bash
python reproduce.py prepare --profile paper --out plans/paper
```

此环境公开名称路线实际得到 **29,139 次请求/模型/条件**；原定 29,142，3 个 IUPAC 输入对因缺名被明确排除。详见 `excluded.jsonl`。完整比较 16 个模型配置，粗略约 46.6 万请求，尚未计多次重复、重试或额外推理条件；不能直接运行 `all models`。CodeBuddy 应先展示实际计划和 token 用量，根据你明确指定的模型/预算执行。

```bash
python reproduce.py run --plan plans/paper --settings settings.json --out results/modelA_off_run1
python reproduce.py score --plan plans/paper --run results/modelA_off_run1 --allow-network
python reproduce.py bootstrap --run results/modelA_off_run1 --samples 10000
python reproduce.py report --run results/modelA_off_run1 --out reports/modelA_off_run1
```

更严谨的输入路线请把 `plans/paper` 换成 `plans/paper_verified`，并在新结果目录运行；两种路线的成绩不能直接混合。

## 6 如何检查结果

- `plan.json` 记录样本、seed、RDKit 版本、请求数、协议差异。
- `manifest.jsonl` 记录每一条实际 prompt、答案、问题 ID、表示、输入状态和 prompt SHA256。
- `excluded.jsonl` 记录无法生成的输入；不会静默消失。
- `run_metadata.json` 记录模型设置与配置指纹；`raw.jsonl` 保存模型实际输出、usage、finish_reason 和状态。
- `scored.jsonl` 保存逐题解析、正确性和生成分子的解码状态。
- `summary.csv/json` 保存按任务/表示汇总的成绩与分母。
- `evaluation_status.json` 区分预定、调用成功、解析成功和解码完成；不会自动声称 full paper reproduced。

连续性质的 Spearman/MAE 仅在成功解析的数字上计算，同时报告覆盖率。离散准确率以计划请求为分母，失败/无答案计错。B2 有未解析项时 headline Macro-F1 留空，仅提供 valid-only 参考值和全体准确率。生成有效性未解码时保留空值；同时区分有效分子条件下的 Tanimoto 与把无效输出计零的全体均值。生成 exact match 主列按作者实现忽略立体，另列报告含立体版本。

配对 bootstrap 默认比较预先指定的 canonical SMILES，与论文“挑最优后比较其余”的选择规则不同。B2 按分子成组抽样，保留 5 个标签；B3 每个连续性质重新计算 Spearman。采用共同分子样本；未做多重比较校正。小样本不能仅看排名。缺失或不恒定数据无法计算时会留空。

## 7 可选部分与完整复现边界

FCD：安装 `fcd` 后用 `score --fcd`；ChemNet 权重与 ML 依赖可能还需下载。FCD 是分布指标，样本过少不可靠。缺依赖、解码未完成或计算失败会明确记录，绝不写假数值。

LLM 裁判：`python reproduce.py judge --plan plans/paper --run results/modelA_off_run1 --settings judge_settings.json --n 10`。本包裁判 rubric 是解释性的**改编扩展**，不是论文裁判原始 prompt 的逐字重放。作者原实现见 `vendor/molrepbench/scripts/qualitative_eval.py`；论文使用 Gemini 3 Flash，每个模型/表示 10 个描述。复现论文图 1/2 时需对齐模型、样本、rubric 和汇总办法。

机制研究：`tools/token_audit.py` 提供真实 tokenizer 的长度审计入口；它用公开 test 的前 N 个分子，未证明与论文 1,000 个分子完全一致。作者公开 32 文件中未找到可直接重放 §6 全部线性探针/注意力图的完整流程。本包没有伪装成已经补齐。若教授要求全文所有图，需进一步确认作者样本、层、池化、划分与训练设置，再独立实现并清楚标为补充复现。

## 8 本次交付的验证范围

本地已生成 smoke 和 paper 请求清单，完成离线数据审计与软件测试。测试中用明确的 fixture 响应检查解析、评分、缺失分母、请求构建与续跑，**这些 fixture 不是模型实验结果**。测试临时文件不进入正式结果目录。

`evidence/` 保存验证日志、环境版本、数据审计和计划摘要。没有真实模型回答文件，也没有真实 LLM 成绩。你当地完成后运行 `report` 可生成基于真实保存结果的 DOCX/PDF；再人工检查，并用 CodeBuddy 把样本、核心代码、实际 prompt、成绩、错误案例和论文差异补进最终汇报。

## 9 核心代码阅读顺序

1. `repro/core.py` 的 `prepare`：原始 SMILES → 9 种输入 → 调作者 prompt → 冻结逐题清单。
2. `vendor/molrepbench/scripts/utils/prompts.py`：实际使用的 8 类原始任务 prompt。
3. `vendor/molrepbench/scripts/utils/representations.py`、`moljson/conversion.py`：格式转换。
4. `vendor/molrepbench/scripts/config.py`：5 个官能团的 SMARTS、模型参数与预算。
5. `repro/inference.py` 的 `request_payload/run`：只将 prompt 发给模型，参考答案留给评分器。
6. `repro/scoring.py`：最后答案解析、指标、覆盖率与配对比较。

## 10 来源与文件权利

论文：<https://arxiv.org/abs/2606.03057>。数据与原始代码来自上列固定仓库及其 bundled archive。该 commit 未包含 LICENSE 文件；本包保留来源且不重新授权作者材料。要公开发布时，应核实作者代码与 ChEBI 数据的许可。新增 `repro/` 代码与作者原代码的归属须区分；不要把作者全部代码称为自己原创。
