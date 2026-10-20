# vendor 代码审读记录（本次复现的范围边界）

审读时间：2026-10-20（本地 Windows 运行环境）。仅阅读 frozen vendor 代码，未做任何修改。

## 1. vendor/molrepbench/scripts/qualitative_eval.py（论文原 LLM 裁判）

已核实的原实现事实：

- 裁判模型：`gemini-3-flash-preview`（Gemini 3 Flash Preview），
  API：`https://generativelanguage.googleapis.com/v1beta/models/...:generateContent`，
  密钥环境变量：`GEMINI_API_KEY`。
- 生成参数：temperature 0.7、topP 0.95、maxOutputTokens 65536、
  thinkingConfig {thinkingLevel: LOW, includeThoughts: False}、
  responseMimeType=application/json + responseSchema 结构化输出。
- 批量方式：每个 (representation, molecule_id) 把 **14 个模型**的 B6 回答
  （raw_response 截断至 2000 字符 + generated_string）合并进**一次** Gemini 调用，
  交叉比较。14 个模型文件见脚本内 MODEL_CONFIGS。
- 评分维度（responseSchema）：
  - chemical_reasoning_quality：整数 1-5
  - error_pattern：枚举 none / syntax_error / wrong_scaffold /
    missing_substituents / stereochemistry_error / hallucination
  - representation_faithfulness：整数 1-5
  - overall_quality：整数 1-5
  - qualitative_insights：2-3 句具体化学观察
  - comparative_summary：跨模型比较总结
- 抽样：`--n-molecules` 默认 10，`--seed` 默认 42（config.SEED），
  从第一个存在的结果文件的 molecule_id 中随机抽样。
- 输出：`results_small/qualitative_eval_b6_v2.jsonl`（逐条追加，可断点）。

边界声明：

- 本包的 `reproduce.py judge`（repro/extensions.py）是**改编扩展**的 rubric，
  不是论文原裁判 prompt 的逐字重放；裁判模型、批量方式、评分维度
  若与原实现不一致，不得声称复现论文图 1/2 的裁判部分。
- 裁判结果不等于化学真值，需人工抽查。
- 本次交付**未运行**裁判：需要 Gemini API 密钥与 14 个模型的 B6 结果文件，
  本机不具备（预算仅 smoke，无 GEMINI_API_KEY）。

## 2. tools/token_audit.py（token 长度审计入口）

- 用 transformers `AutoTokenizer`（需 `--tokenizer` 指定 HF ID 或本地路径），
  默认取 `chebi20_test.csv` 前 1000 个分子（`--n`），对 9 种表示分别记录
  字符数与真实 token 数（无"字符数/4"近似）。
- 这是 tokenizer 长度审计，**不是**论文 §6 机制图的完整复现。
- 论文 §6 / 附录 H/I 的线性探针、注意力重放等流程在公开的 32 个文件中
  **未找到**可完整重放的实现；相关模型、1000/50 分子样本、输入模板、
  层选择、token span、池化、训练/测试划分、注意力归一化等细节需向作者澄清。
  本次**未运行** token_audit（未安装 transformers，也未指定 tokenizer）。

## 3. 对报告的要求（据此执行）

- 裁判与机制分析在最终报告中列为"未完成/待澄清"，不得伪装已跑。
- 任何重新实现必须标注 supplemental reimplementation。
