# 本次 settings 决策与协议偏差记录（2026-10-20）

## 模型身份（partial reproduction）

- 本次实际使用：**DeepSeek 官方 API** `https://api.deepseek.com`，`model=deepseek-flash`。
- 实测证据：请求 `deepseek-chat` 时，响应 `"model":"deepseek-flash"`，
  即该端点将 chat 别名路由到 flash。因此以服务端返回的模型名为准记录。
- 连接性探测（tools/api_probe.py，真实响应）：
  `"model":"deepseek-flash"`、`finish_reason":"stop"`、
  `usage: prompt_tokens=13, completion_tokens=2, total_tokens=15`、
  `system_fingerprint=e72d3c7f663d3e1383b00b3884cb4501`。
- 论文（vendor/molrepbench/scripts/config.py）使用的 15 个模型为：
  Qwen3-4B/30B-A3B/235B-A22B-Thinking-2507、Phi-4、Phi-4-Reasoning(+Plus)、
  OLMo-3.1-32B-Instruct/Think、ChemDFM-v2.0-14B、ChemDFM-R-14B、Ether0-24B、
  Mistral-Small-24B-Instruct-2501、Qwen2.5-14B，以及两个 Qwen3-4B MolJSON 微调变体。
- DeepSeek 不在其中，因此**任何比较均标为 partial reproduction**；
  不能声称“复现了论文某一行结果”，只能说“按同一协议测了同一批表示与任务”。
- 该模型未做本地权重核验：本次只能证明服务端返回了上述模型名与用量，
  无法核验其确切 HF ID、revision、量化方式与服务端版本。

## 推理模式

- `thinking` 字段只是记录标签，实际开关由后端决定。本次已**实测验证**：
  - 不传 thinking 参数、max_tokens=2048 时：HTTP 200 但 `content` 为空
    （runner 记录 "No final content; inspect token budget or backend reasoning
    configuration"），延迟约 10 秒 —— 推理轨迹吃光了 2048 预算。
  - 不传 thinking 参数、max_tokens=8192 时：usage 含
    `completion_tokens_details.reasoning_tokens=1724`，响应含
    `reasoning_content`（4579 字符）—— **证明该模型默认会推理**。
  - 传 `extra_body={"thinking":{"type":"disabled"}}` 时：usage 中**没有**
    reasoning_tokens，响应中**没有** reasoning_content
    （两组预算 2048 与 8192 均如此）—— **关闭推理确实生效**。
- 因此最终配置使用 `thinking:{"type":"disabled"}`，等价于论文的 thinking off 条件。
- 未使用 `deepseek-reasoner`：该模型为推理模型且无法关闭推理，强行关闭属伪造 off 条件。
- 证据文件：results/probe_A_thinking_off_2048/、results/probe_B_default_8192/、
  results/probe_C_thinking_off_8192/（各 1 条真实请求的 raw.jsonl 与 settings_used.json）。

## 输出预算

- 本次统一 `max_tokens=8192`。
- 论文按任务分别设定 thinking off 预算：B1 100、B2 50、B3 200、B4 100、
  B5 100、B9 100、B10 100、B6 1024；thinking on 为 512-2048（配合
  thinking_max_tokens 256-512）。本运行器无逐任务预算逻辑，故统一取值。
- 取 8192 的原因：B6 的 CML/MolJSON 参考答案字符长度均值 3351/2223、
  最大 20450/12393（evidence/representation_length_stats.json），
  过小预算会人为制造截断，把"表示更长"与"预算不足"混为一谈。
- 仍可能出现真实截断（finish_reason=length），统计时按实际记录，不删除。

## 结构化输出

- `schema_mode="prompt_only"`：不发送 response_format / structured_outputs。
- B6 提示词文本本身已要求输出 JSON（作者 prompts.create_generation_prompt，
  use_json_format=True），因此 JSON 约束只来自提示词而非 API schema。
- 与论文的结构化输出约束不同，属协议偏差，已记录。

## 采样参数

- temperature 0.6、top_p 0.95、max_tokens 2048（本次统一值）。
- 论文按模型分别设定（如 Qwen3 thinking 系列 0.6/0.95/20，Phi-4 0.8/0.95/50，
  生成任务 thinking-off 上限 1024）。本次统一值与任一论文模型都不完全相同。
- 未发送 seed：该 API 的 seed 兼容性未验证，不盲目套用；随机性未受控，
  报告中必须说明。
- max_tokens 2048 > 论文生成任务 off 的 1024；但 MolJSON 参考答案长度可达
  12393 字符（见 evidence/representation_length_stats.json），CML 可达 20450，
  因此 B6 的 CML/MolJSON 存在截断风险，run 后必须按 finish_reason 核对。

## 密钥处理

- 密钥仅通过 tools/run_with_key.py 在用户终端隐藏输入，注入子进程环境变量。
- 不写入 settings.json、日志、报告、results 文件或 Git。