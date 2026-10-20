# 第三方材料说明（THIRD PARTY NOTICES）

本仓库**不包含**作者 `arunraja-hub/molrepbench` 的代码与数据，原因是该 commit
（`21d36941cddf0dc1ffb5f3590296592dc68e4ac8`）**未附带 LICENSE 文件**，无法确认再分发授权。
如需完整复现，请自行从官方来源获取并遵守其许可条款。

## 需要自行获取的材料

| 材料 | 来源 | 说明 |
|---|---|---|
| 作者代码（32 个文件） | `https://github.com/arunraja-hub/molrepbench` @ `21d36941cddf0dc1ffb5f3590296592dc68e4ac8` | 放入 `vendor/molrepbench/` |
| 基准数据 | 同仓库的 `benchmark_data_small.zip`（约 31 MB） | 解压为 `data/`（见下方命令） |
| 论文原文 | arXiv:2606.03057 | 本仓库不含 PDF，仅提供链接 |

## 校验方式

`UPSTREAM_PROVENANCE.json` 记录了作者 32 个文件的 SHA256。取得 vendor 代码后可验证：

```powershell
python reproduce.py verify-vendor     # 期望 files_checked=32, changed_or_missing=[]
```

数据准备：

```powershell
python reproduce.py setup             # 解压 benchmark_data_small.zip 为 data/
```

## 本仓库包含什么

- `repro/`、`tools/`、`tests/`：本次新增的运行器、诊断工具与测试（本次工作，非作者代码）。
- `delivery/`、`evidence/`、`results/`、`reports/`：本次真实运行产生的原始回答、逐题评分、
  汇总表、DOCX/PDF 报告与全部日志。
- `plans/smoke/`：270 条 smoke 计划的 manifest（可直接复现）。
- `settings.sample.json`：脱敏配置；密钥只放在本地 `.env`（已 gitignore），从未入库。

## 数据引用

- 论文：Benchmarking LLMs on Molecular Representation ...（见 arXiv 链接）
- OPSIN：IUPAC 名称解析使用公共服务 `opsin.ch.cam.ac.uk`，属名称解析而非模型推理。
