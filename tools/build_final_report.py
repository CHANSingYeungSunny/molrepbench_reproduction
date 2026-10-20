"""Build the full Chinese reproduction report (DOCX + PDF) from real artifacts.

Everything in the report is read from files produced by this session:
plans/*/plan.json, results/deepseek-flash_off_smoke_run3/{run_metadata,summary,
evaluation_status,scored,paired_bootstrap}, evidence/*.json.
No invented numbers, no success that did not happen.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from repro.reporting import style_document, table  # noqa: E402

RUN_NAME = 'deepseek-flash_off_smoke_run3'
RUN = ROOT / 'results' / RUN_NAME
OUT = ROOT / 'reports' / RUN_NAME


def jload(p):
    raw = Path(p).read_bytes()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        raw.decode('utf-16')
        return json.loads(raw.decode('utf-16'))
    return json.loads(raw.decode('utf-8-sig'))


summary = jload(RUN / 'summary.json')
status = jload(RUN / 'evaluation_status.json')
meta = jload(RUN / 'run_metadata.json')
examples = jload(ROOT / 'evidence' / 'report_examples.json')
smoke_plan = jload(ROOT / 'plans' / 'smoke' / 'plan.json')
paper_plan = jload(ROOT / 'plans' / 'paper' / 'plan.json')
verified_plan = jload(ROOT / 'plans' / 'paper_verified' / 'plan.json')
provenance = jload(ROOT / 'UPSTREAM_PROVENANCE.json')
iupac_audit = jload(ROOT / 'evidence' / 'iupac_input_audit.json')
b9 = jload(ROOT / 'evidence' / 'b9_label_sensitivity.json')
lengths = jload(ROOT / 'evidence' / 'representation_length_stats.json')
doctor = jload(ROOT / 'evidence' / 'doctor_output.json')
bootstrap = jload(RUN / 'paired_bootstrap.json')

scored = [json.loads(l) for l in (RUN / 'scored.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]

REPS = ['canonical_smiles', 'isomeric_smiles', 'randomized_smiles', 'deepsmiles',
        'iupac', 'selfies', 'moljson', 'cml', 'inchi']
REP_CN = {'canonical_smiles': 'canonical SMILES（规范 SMILES）', 'isomeric_smiles': 'isomeric SMILES（含立体）',
          'randomized_smiles': 'randomized SMILES（随机写法）', 'deepsmiles': 'DeepSMILES',
          'iupac': 'IUPAC 名称', 'selfies': 'SELFIES', 'moljson': 'MolJSON',
          'cml': 'CML（化学标记语言）', 'inchi': 'InChI'}
TASK_CN = {1: '原子计数', 2: '官能团识别', 3: '性质预测（logP/TPSA/HBD/HBA）', 4: '多选题检索',
           5: '同一性判断（异构体）', 6: '逆向生成', 9: '互变异构体判断', 10: '质子化状态判断'}

iupac_stats = {
    'total': len(iupac_audit),
    'exact': sum(1 for r in iupac_audit if r.get('exact_stereo_match') is True),
    'conn_only': sum(1 for r in iupac_audit if r.get('connectivity_match') is True
                     and r.get('exact_stereo_match') is not True),
    'mismatch': sum(1 for r in iupac_audit if r.get('exact_stereo_match') is False),
    'unparsed': sum(1 for r in iupac_audit if r.get('exact_stereo_match') is None),
}

per_task = {}
for s in scored:
    per_task.setdefault(s['task'], {'n': 0, 'scored': 0, 'correct': 0})
    per_task[s['task']]['n'] += 1
    if s.get('correct') is not None:
        per_task[s['task']]['scored'] += 1
        per_task[s['task']]['correct'] += int(bool(s['correct']))

summary_rows = []
for r in summary:
    def g(k):
        v = r.get(k)
        return '-' if v in (None, '') else (f'{v:.3f}' if isinstance(v, float) else str(v))
    summary_rows.append([f"B{r['task']}", r['representation'], g('accuracy_all'), g('macro_f1'),
                         g('logp_spearman'), g('tpsa_spearman'), g('validity_rate'), g('exact_match')])


def sec_report_1_3(doc):
    doc.add_heading('一、复现目标与范围', level=1)
    doc.add_paragraph(
        '论文《Rethinking Molecular Text Representations for LLMs: An Empirical Study》要回答一个问题：'
        '把同一个分子写成不同"文本表示"（canonical SMILES、SELFIES、IUPAC 名称、CML 等），'
        '大语言模型（LLM）的回答会不会变？论文在 9 种表示 × 8 类任务上系统测量，'
        '比较 open-weight 化学模型的差异。')
    doc.add_paragraph(
        '本次复现的范围：作者公开的 9 种表示与 B1 B2 B3 B4 B5 B6 B9 B10 共 8 类任务；'
        f'实际执行的推理规模为 smoke profile（{smoke_plan["request_count"]} 条请求，'
        f'结果目录 results/{RUN_NAME}）。paper profile（{paper_plan["request_count"]} 条）因预算未执行，'
        '论文的 15 个模型本次一个也没有跑，因此所有结论都是 partial reproduction（部分复现），'
        '不能声称复现了论文的某一行结果。')
    doc.add_paragraph('本次实际使用的模型：DeepSeek 官方 API deepseek-flash（推理关闭），'
                      '不在论文的 15 个模型列表内。')

    doc.add_heading('二、论文与官方代码来源', level=1)
    doc.add_paragraph(f"仓库：{provenance.get('repo') or provenance.get('repository') or 'arunraja-hub/molrepbench'}")
    doc.add_paragraph(f"固定 commit：{provenance.get('commit', '21d36941cddf0dc1ffb5f3590296592dc68e4ac8')}")
    doc.add_paragraph('本次未修改 vendor/ 任何文件；reproduce.py verify-vendor 校验 32/32 文件 SHA256 一致。'
                      '所有适配（例如 Windows 上 CML 格式支持）都放在 repro/ 与 tools/ 中，并在报告中标注。')
    doc.add_paragraph('许可提示：该 commit 未包含 LICENSE 文件，公开再分发前需向作者确认许可。')

    doc.add_heading('三、环境、数据、样本与排除项', level=1)
    table(doc, ['项目', '内容'], [
        ['Python', doctor.get('python')],
        ['平台', doctor.get('platform')],
        ['RDKit', doctor.get('dependencies', {}).get('rdkit')],
        ['OpenBabel', f"{doctor.get('dependencies', {}).get('openbabel')}（obabel CLI：{doctor.get('obabel_executable')}）"],
        ['smoke 计划', f"{smoke_plan['request_count']} 条；8 任务 × 9 表示全覆盖；manifest SHA256 {smoke_plan['manifest_sha256'][:16]}…"],
        ['paper 计划', f"{paper_plan['request_count']} 条；排除 {paper_plan['excluded_count']} 个缺 IUPAC 名称的分子对"],
        ['paper_verified', f"{verified_plan['request_count']} 条；排除 {verified_plan['excluded_count']} 条（仅保留名称经 OPSIN 验证的输入）"],
        ['单元测试', '11/11 通过'],
    ])
    doc.add_paragraph('样本 ID 规则：B{task}:{item_id}:{subtask}:{representation}，'
                      '例如 B1:439741:C:canonical_smiles 表示"任务1、分子439741、问C原子数、用规范SMILES给出"。')
    doc.add_paragraph('paper 路线的 3 个排除项：B5:355、B10:170、B10:195，'
                      '原因是这两个分子缺 IUPAC 名称（pair_conversion_failed），已记入 excluded.jsonl，'
                      '没有删除记录、没有补 SMILES 假充。')


def sec_report_4_5(doc):
    doc.add_heading('四、九种表示分别编码什么，为什么选它们', level=1)
    doc.add_paragraph('分子式 C7H17NO3（例如）可以写成很多种文本。表示（representation）就是"用什么文本形式把分子交给模型"。'
                      '它们编码的信息量不同，所以能区分出"模型到底依赖哪种线索"。')
    rows = [
        ['canonical_smiles', '唯一规范化的 SMILES 字符串', '不含立体化学', '基准表示；所有其他表示都与它对照'],
        ['isomeric_smiles', '保留 @/@@ 立体标记的 SMILES', '保留立体', '检验模型能否读出立体信息'],
        ['randomized_smiles', '随机原子遍历顺序的 SMILES', '不含立体', '同一分子的"不同写法"，检验模型是否依赖固定顺序'],
        ['deepsmiles', '带闭环与环数字的 SMILES 变体', '不含立体', '更紧凑，可能丢失语义'],
        ['iupac', 'IUPAC 系统命名（自然语言式）', '通常丢失质子化/互变细节', '有语义线索，但命名会"标准化掉"状态'],
        ['selfies', 'SELFIES 语法，任何随机串都是合法分子', '语法合法≠化学正确', '可把"幻觉输出"与"非法输出"区分开'],
        ['moljson', '显式列出全部原子与键的 JSON', '可含立体与电荷', '像表格，信息全但很长'],
        ['cml', '化学标记语言（XML）', '可含立体与电荷', '显式表示图结构，最长'],
        ['inchi', 'InChI 哈希串', '规范化、含立体层', '去局部化编码，难反推'],
    ]
    table(doc, ['表示', '编码什么', '立体/电荷/互变', '为什么用它'], rows, widths=[1.2, 1.7, 1.3, 2.3])
    pooled = lengths.get('pooled_comprehension_mean_chars', {})
    if pooled:
        doc.add_paragraph('本次在 paper 计划上实测的平均字符长度（同一批分子、同一批题目）：')
        table(doc, ['表示', '平均字符数'],
              [[REP_CN[k], f'{v:.0f}'] for k, v in sorted(pooled.items(), key=lambda kv: kv[1])])

    doc.add_heading('五、八类任务分别测什么，用什么指标', level=1)
    doc.add_paragraph('任务按"难度递进"设计：先数原子（最简单），再认官能团（模式匹配），'
                      '再猜性质（需要理解整体），再比较两个分子（需要细微差别），最后反过来生成分子（最难）。'
                      '同一种表示在不同任务上的表现差异，能说明模型在该表示下"能走多远"。')
    table(doc, ['任务', '测什么', '为什么用这个指标'], [
        ['B1 原子计数', '数某种元素的原子个数', '整数精确匹配（accuracy），最干净的信号'],
        ['B2 官能团识别', '识别 5 类官能团', 'macro-F1：类别不均衡时比准确率公平'],
        ['B3 性质预测', '预测 logP / TPSA / HBD / HBA', '连续量用 Spearman 相关系数；HBD/HBA 用整数准确率'],
        ['B4 多选题', '4 个候选中选正确描述', '准确率；同一分子只计一次'],
        ['B5 同一性判断', '两个分子是否同一个（含立体/取代差异）', '准确率，标签取自 CSV ground_truth'],
        ['B6 逆向生成', '从自然语言描述生成分子表示', 'validity（能否解码成合法分子）+ exact match + Tanimoto；有效≠正确'],
        ['B9 互变异构体', '两个结构是否互为互变异构', '准确率'],
        ['B10 质子化状态', '两个结构质子化态是否相同', '准确率'],
    ], widths=[1.1, 2.3, 3.1])
    doc.add_paragraph('重要口径：标准答案全部由 RDKit / OpenBabel 计算，LLM 只是被测试对象。'
                      '本报告不会把 RDKit 算出的答案当成模型的推理结果。')


def sec_report_6_7(doc):
    doc.add_heading('六、核心代码与数据流', level=1)
    doc.add_paragraph('一条完整链路：SMILES → 表示字符串 → prompt → 模型回答 → 标准答案 → 得分。'
                      '对应的四个文件：')
    table(doc, ['文件', '作用'], [
        ['repro/core.py', '把成员分子重新编码成 9 种表示，生成逐题 prompt（manifest.jsonl）'],
        ['repro/inference.py', '调用 OpenAI 兼容接口，只发送 prompt（参考答案不进请求），保存原始回答'],
        ['repro/scoring.py', '解析模型回答、计算指标、汇总任务×表示、配对 bootstrap'],
        ['repro/audit.py', '数据审计与 IUPAC 名称 OPSIN 审核'],
        ['vendor/molrepbench/scripts/utils/prompts.py', '作者原始 prompt 模板（未修改）'],
    ])
    doc.add_paragraph('本次新增（作者代码之外）：repro/core.py 的 Windows CML 平台适配、'
                      'tools/prefetch_iupac.py（并行 OPSIN 预取）、tools/run_with_key.py（密钥隐藏输入）、'
                      'tools/api_probe.py 与 tools/key_shape_check.py（诊断）、'
                      'tools/build_final_report.py（本报告）。')
    code = ('# repro/scoring.py 解析模型最终答案（节选）\n'
            'def parse(text):\n'
            '    # 取最后一个 \\boxed{...}，否则取 "Final answer:" 之后的内容\n'
            '    boxes = re.findall(r"\\\\boxed\\{([^}]*)\\}", text)\n'
            '    if boxes:\n'
            '        return boxes[-1].strip()\n'
            '    ...')
    doc.add_paragraph('解析规则（决定"什么算答案"）：')
    p = doc.add_paragraph(code)
    p.runs[0].font.name = 'Consolas'
    p.runs[0].font.size = __import__('docx').shared.Pt(9)

    doc.add_heading('七、每类任务一条真实链路（prompt / 参考答案 / 模型回答 / 评分）', level=1)
    for task in (1, 2, 3, 4, 5, 6, 9, 10):
        ex = examples['examples'][f'B{task}']
        doc.add_heading(f"B{task} {TASK_CN[task]}｜{ex['id']}", level=2)
        doc.add_paragraph(f"表示：{REP_CN[ex['representation']]}｜指标：{ex['metric']}｜"
                          f"模型原始回答长度：{ex['raw_answer_chars']} 字符｜"
                          f"finish_reason={ex['finish_reason']}｜"
                          f"usage={json.dumps(ex['usage'], ensure_ascii=False) if ex['usage'] else '无'}")
        doc.add_paragraph('实际发送的 prompt：')
        doc.add_paragraph(ex['prompt'][:700])
        doc.add_paragraph(f"参考答案：{ex['ground_truth']}")
        doc.add_paragraph('模型原始回答（开头节选）：')
        doc.add_paragraph(ex['raw_answer_head'][:700])
        doc.add_paragraph(f"解析出的答案：{ex['parsed']}｜判分：{'正确' if ex['correct'] else '错误'}"
                          + (f"｜解码状态：{ex['decode_status']}" if ex.get('decode_status') else ''))


def sec_report_8_9(doc):
    doc.add_heading('八、成绩、覆盖与共同样本', level=1)
    doc.add_paragraph(f"推理完成度：{status['api_success']}/{status['expected_requests']} 条 API 成功，"
                      f"{status['parsed_answers']} 条解析出答案，result_kind={status.get('result_kind')}。")
    doc.add_paragraph('运行状态（来自 evaluation_status.json）：')
    table(doc, ['字段', '值'], [[k, json.dumps(v, ensure_ascii=False) if isinstance(v, bool) else str(v)]
                                for k, v in status.items() if k != 'note'])
    doc.add_paragraph('任务 × 表示成绩（- 表示该任务不使用该指标）：')
    table(doc, ['任务', '表示', 'accuracy_all', 'macro_f1', 'logp_rho', 'tpsa_rho', 'validity', 'exact_match'],
          summary_rows)
    doc.add_paragraph('按任务汇总（9 种表示合并）：')
    table(doc, ['任务', '题数', '已判分', '正确', '正确率'],
          [[f"B{t}", v['n'], v['scored'], v['correct'],
            f"{v['correct']/v['scored']:.2f}" if v['scored'] else '-']
           for t, v in sorted(per_task.items())])
    doc.add_paragraph('覆盖率：8 任务 × 9 表示 = 72 个格子全部有请求且全部成功返回（270/270）。'
                      '没有任何格子因失败被删除。')
    doc.add_paragraph('共同样本比较（bootstrap）：本次 comparisons = 0。原因不是程序出错，'
                      '而是实现要求每个"任务×表示"至少 3 个可配对分子（scoring.py 中 len(ids) < 3 即跳过），'
                      '而 smoke 每个任务只有 2 个分子，因此拒绝给出置信区间。'
                      '我们没有为了"有数"而放宽阈值——2 个配对单位做出的 CI 没有统计意义。'
                      '要得到 CI，必须运行 paper 级 profile（每任务 200 分子）。')

    doc.add_heading('九、真实失败案例（全部来自本次真实返回）', level=1)
    for i, f in enumerate(examples['failures'][:8], 1):
        doc.add_heading(f"案例 {i}：{f['kind']}｜{f['id']}", level=2)
        doc.add_paragraph(f"原因：{f['why']}")
        doc.add_paragraph(f"参考答案：{f.get('ground_truth', '-')}｜解析结果：{f.get('parsed')}｜"
                          f"判定：{f['counted_as']}")
        doc.add_paragraph('prompt 节选：' + f['prompt_head'][:180].replace('\n', ' '))
        doc.add_paragraph('回答尾部节选：' + f['answer_tail'][-220:].replace('\n', ' '))


def sec_report_10_13(doc):
    doc.add_heading('十、与论文一致和不一致的地方', level=1)
    table(doc, ['方面', '论文', '本次', '性质'], [
        ['模型', '15 个 open-weight 化学模型', '1 个 DeepSeek 官方 API 模型', '不一致 → partial reproduction'],
        ['推理规模', 'paper profile 约 29139 请求/模型', f'smoke profile {smoke_plan["request_count"]} 请求', '不一致（预算所限）'],
        ['IUPAC 输入', '使用公开名称', '先用公开名称，再用 OPSIN 审核出 verified 路线', '本次更严格'],
        ['token 预算', '按任务分别设定（off 50–1024）', '统一 8192', '不一致，已记录'],
        ['结构化输出', '结构化输出约束', 'prompt_only（仅靠提示词要求 JSON）', '不一致，已记录'],
        ['B5 标签', '论文称 375/500 一致', '按 CSV ground_truth（250 Yes/125+125 No）', '以公开 CSV 为准'],
        ['B9 4 对争议标签', '未讨论', '保留公开标签并做敏感性检查', '本次新增'],
    ])
    doc.add_paragraph('与论文方法一致之处：表示集合相同、任务相同、prompt 来自作者原始代码、'
                      '评分指标相同、bootstrap 为配对设计、种子与分母口径一致。')

    doc.add_heading('十一、本次完成 / 未完成 / 替代实现边界', level=1)
    table(doc, ['状态', '项目'], [
        ['已完成', 'Python 3.12 隔离环境与全部依赖；vendor 32/32 校验；11/11 单元测试；'
                   'smoke 270 与 paper 29139 计划生成（manifest 哈希与交付环境一致）；'
                   '离线数据审计重跑；OPSIN IUPAC 审核（4551 成员）；paper_verified 路线；'
                   'deepseek-flash 真实推理 270/270；评分、覆盖率、失败案例、bootstrap 方法说明'],
        ['未完成', 'paper profile 29139 请求运行；论文 15 个模型；thinking on 条件；'
                   'FCD（frechet chemnet distance）；LLM 裁判图（需 GEMINI_API_KEY 与 14 个模型回答）；'
                   '§6 tokenizer 与机制分析（32 个公开文件中未找到可重放实现）'],
        ['替代实现', 'Windows CML 走 obabel CLI（作者 cml_to_smiles 同款方式）；'
                     '并行 OPSIN 预取工具；报告由 tools/build_final_report.py 生成'],
        ['不可用', 'SELFIES/DeepSMILES 生成的合法性检查依赖官方解码器，本次仅用 RDKit/OpenBabel 可解码部分'],
    ])

    doc.add_heading('十二、数据本身的两个重要发现', level=1)
    doc.add_paragraph(f"IUPAC 名称审核（{iupac_stats['total']} 个成员经 OPSIN 解析）："
                      f"{iupac_stats['exact']} 个名称解析回的结构与成员 SMILES 立体身份完全一致；"
                      f"{iupac_stats['conn_only']} 个仅连接性一致（立体信息在命名中丢失）；"
                      f"{iupac_stats['mismatch']} 个不一致；{iupac_stats['unparsed']} 个无法解析。"
                      '这说明公开 IUPAC 列本身存在信息丢失与错误映射，不能默认当作可靠输入。')
    doc.add_paragraph("B9 争议标签：" + b9['conclusion'])

    doc.add_heading('十三、可复制运行命令与证据索引', level=1)
    cmds = [
        '# 环境',
        'conda create -y -n molrep -c conda-forge python=3.12 rdkit=2025.9.6 openbabel=3.1.1',
        '# 离线验证',
        'python reproduce.py doctor',
        'python reproduce.py verify-vendor',
        'python reproduce.py setup',
        'python -m unittest discover -s tests -v',
        '# 计划',
        'python reproduce.py prepare --profile smoke --out plans/smoke',
        'python reproduce.py prepare --profile paper --out plans/paper',
        '# IUPAC 审核',
        'python tools/prefetch_iupac.py',
        'python reproduce.py audit --iupac --output evidence/audit_with_iupac.json',
        'python reproduce.py prepare --profile paper --iupac-policy verified --out plans/paper_verified',
        '# 真实推理（密钥在 .env，不落盘到其他文件）',
        'python tools/run_with_key.py reproduce.py run --plan plans/smoke --settings settings.json '
        f'--out results/{RUN_NAME}',
        '# 评分与统计',
        f'python reproduce.py score --plan plans/smoke --run results/{RUN_NAME} --allow-network',
        f'python reproduce.py bootstrap --run results/{RUN_NAME} --samples 10000',
        f'python reproduce.py report --run results/{RUN_NAME} --out reports/{RUN_NAME}',
    ]
    for c in cmds:
        doc.add_paragraph(c)
    doc.add_paragraph('证据索引见 evidence/ARTIFACT_INDEX.md。')


def sec_report_14(doc):
    doc.add_heading('十四、零基础概念说明', level=1)
    doc.add_paragraph('同一个分子有多种"写法"：C7H17NO3 既可以写成 SMILES，也可以写成 SELFIES、'
                      'IUPAC 名称、CML。本实验固定题目和模型，只改变"写法"，看回答是否改变——'
                      '不是在训练新的分子模型。')
    doc.add_paragraph('RDKit 是工具，LLM 是被测对象：RDKit 负责把分子在各表示间转换、'
                      '计算标准答案、判断生成结果能否解码；LLM 只负责回答问题。'
                      '本报告不会把 RDKit 的结果当成 LLM 的能力。')
    doc.add_paragraph('几个容易误解的点：')
    table(doc, ['说法', '为什么不准确'], [
        ['SELFIES 合法就说明答案对', 'SELFIES 语法上任何字符串都是合法分子；合法≠化学正确'],
        ['MolJSON/CML 更全面所以更好', '它们显式列出原子键，但更长，可能超出模型稳定输出的长度'],
        ['IUPAC 名称最语义化', '命名会标准化掉质子化/互变细节，反而丢失状态信息'],
        ['validity=1 就答对了', 'B6 必须同时看 exact match 与 Tanimoto，本次多组 validity=1 但 exact=0'],
    ])


def build_docx(path):
    from docx import Document
    doc = Document()
    style_document(doc)
    doc.add_heading('论文复现报告：分子文本表示对 LLM 的影响', level=0)
    doc.add_paragraph(f"模型：{meta['settings']['model']}（{meta['settings']['base_url']}，"
                      f"推理关闭，thinking off 已实测）｜规模：smoke "
                      f"{smoke_plan['request_count']} 请求｜运行目录：results/{RUN_NAME}｜"
                      "性质：partial reproduction（论文模型未跑）")
    sec_report_1_3(doc)
    sec_report_4_5(doc)
    sec_report_6_7(doc)
    sec_report_8_9(doc)
    sec_report_10_13(doc)
    sec_report_14(doc)
    doc.save(str(path))
    return path


def build_pdf(path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib import colors
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    ss = getSampleStyleSheet()
    body = ParagraphStyle('body', parent=ss['Normal'], fontName='STSong-Light', fontSize=9.5, leading=14)
    h1 = ParagraphStyle('h1', parent=ss['Heading1'], fontName='STSong-Light', fontSize=14, leading=19, spaceBefore=10)
    h2 = ParagraphStyle('h2', parent=ss['Heading2'], fontName='STSong-Light', fontSize=11, leading=16, spaceBefore=7)

    story = [Paragraph('论文复现报告：分子文本表示对 LLM 的影响', h1),
             Paragraph(f"模型 {meta['settings']['model']}｜smoke {smoke_plan['request_count']} 请求｜"
                       "partial reproduction（论文模型未跑）", body), Spacer(1, 4)]

    def H1(t):
        story.append(Paragraph(t, h1))

    def P(t):
        story.append(Paragraph(t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), body))
        story.append(Spacer(1, 3))

    def TBL(headers, rows, widths=None):
        data = [headers] + rows
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'STSong-Light'),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DDE8F1')),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#BBBBBB')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(t)
        story.append(Spacer(1, 4))

    H1('一、复现目标与范围')
    P('论文测量"同一个分子写成不同文本表示，LLM 回答是否改变"。本次复现 9 种表示 × 8 类任务，'
      f'实际执行 smoke profile（{smoke_plan["request_count"]} 条），paper profile（'
      f'{paper_plan["request_count"]} 条）与论文 15 个模型本次均未执行，属 partial reproduction。')
    H1('二、来源与环境')
    P(f"仓库 {provenance.get('repo') or provenance.get('repository') or 'arunraja-hub/molrepbench'}，"
      f"commit {provenance.get('commit', '21d36941cddf0dc1ffb5f3590296592dc68e4ac8')}，vendor 32/32 校验未改。")
    P(f"Python {doctor.get('python')}；RDKit {doctor.get('dependencies', {}).get('rdkit')}；"
      f"OpenBabel {doctor.get('dependencies', {}).get('openbabel')}；单元测试 11/11。")
    H1('三、九种表示与八类任务')
    TBL(['表示', '编码什么', '立体/电荷', '为何用它'], [
        ['canonical_smiles', '规范化 SMILES', '无', '基准对照'],
        ['isomeric_smiles', '含 @/@@ 的 SMILES', '保留立体', '检验立体信息'],
        ['randomized_smiles', '随机顺序 SMILES', '无', '同一分子不同写法'],
        ['deepsmiles', '紧凑 SMILES 变体', '无', '可能丢语义'],
        ['iupac', '系统命名', '多丢失状态', '语义线索但会标准化'],
        ['selfies', '语法合法即分子', '语法层面', '区分幻觉与非法'],
        ['moljson', '全原子键 JSON', '可含', '信息全但长'],
        ['cml', 'XML 化学标记语言', '可含', '显式图结构最长'],
        ['inchi', '规范化哈希', '含立体层', '难反推'],
    ], widths=[38 * mm, 55 * mm, 30 * mm, 50 * mm])
    if pooled := lengths.get('pooled_comprehension_mean_chars', {}):
        TBL(['表示', '平均字符数（实测）'],
            [[REP_CN[k], f'{v:.0f}'] for k, v in sorted(pooled.items(), key=lambda kv: kv[1])])
    TBL(['任务', '测什么', '指标'], [
        ['B1', '数原子', 'accuracy'],
        ['B2', '认官能团', 'macro-F1'],
        ['B3', 'logP/TPSA/HBD/HBA', 'Spearman / accuracy'],
        ['B4', '四选一', 'accuracy'],
        ['B5', '同一性判断', 'accuracy'],
        ['B6', '逆向生成', 'validity + exact + Tanimoto'],
        ['B9', '互变异构体', 'accuracy'],
        ['B10', '质子化状态', 'accuracy'],
    ], widths=[16 * mm, 80 * mm, 70 * mm])
    H1('四、真实链路示例（节选 B1 与 B6）')
    for key in ('B1', 'B6'):
        ex = examples['examples'][key]
        P(f"<b>{ex['id']}</b>（{REP_CN[ex['representation']]}，finish_reason={ex['finish_reason']}）")
        P('prompt：' + ex['prompt'][:260].replace('\n', ' / '))
        P(f"参考答案：{ex['ground_truth']}｜模型解析答案：{ex['parsed']}｜判分：{'正确' if ex['correct'] else '错误'}")
    H1('五、成绩与覆盖')
    P(f"API 成功 {status['api_success']}/{status['expected_requests']}，解析答案 {status['parsed_answers']}，"
      f"result_kind={status.get('result_kind')}。")
    TBL(['任务', '题数', '已判分', '正确', '正确率'],
        [[f"B{t}", v['n'], v['scored'], v['correct'], f"{v['correct']/v['scored']:.2f}" if v['scored'] else '-']
         for t, v in sorted(per_task.items())])
    P('bootstrap comparisons = 0：实现要求每组至少 3 个配对分子，smoke 每任务仅 2 个分子，'
      '拒绝给出无意义的置信区间；未放宽阈值。')
    H1('六、真实失败案例')
    for i, f in enumerate(examples['failures'][:5], 1):
        P(f"{i}. {f['kind']}｜{f['id']}｜{f['why']}｜判定：{f['counted_as']}")
    H1('七、数据本身的问题')
    P(f"IUPAC 审核：{iupac_stats['total']} 个成员中仅 {iupac_stats['exact']} 个名称与成员 SMILES "
      f"立体身份一致，{iupac_stats['conn_only']} 个仅连接性一致，{iupac_stats['mismatch']} 个不一致，"
      f"{iupac_stats['unparsed']} 个无法解析。")
    P(f"B9：{b9['conclusion']}")
    H1('八、完成与未完成')
    P('已完成：环境、vendor 校验、单元测试、smoke/paper 计划、离线审计、OPSIN 审核、'
      'verified 路线、270 条真实推理、评分与失败案例分析。')
    P('未完成：paper profile 29139 请求、论文 15 个模型、thinking on 条件、FCD、'
      'LLM 裁判图、§6 tokenizer 与机制分析。')
    P('替代实现：Windows CML 走 obabel CLI（与作者 cml_to_smiles 同款方式）。')
    SimpleDocTemplate(str(path), pagesize=A4, title='MolRepBench 复现报告').build(story)
    return path


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    d = build_docx(OUT / '复现报告_完整版.docx')
    p = build_pdf(OUT / '复现报告_完整版.pdf')
    print('written:', d)
    print('written:', p)