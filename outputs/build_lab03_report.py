from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path.cwd()
TEMPLATE = Path(r'C:\Users\15971\Downloads\云计算与大数据处理_实验报告模版.docx')
OUTPUT = ROOT / 'submissions/lab03/01_实验报告/实验报告_何嘉欣_2410311411.docx'
DOCX_OUTPUTS = ROOT / 'outputs/lab03/docx'

doc = Document(str(TEMPLATE))
doc.core_properties.title = '云计算与大数据处理实验报告：实验三 分布式批处理与性能分析'
doc.core_properties.author = '何嘉欣'
doc.core_properties.subject = '实验三 分布式批处理与性能分析'

cover_values = {
    '实验名称': '实验三　分布式批处理与性能分析',
    '实验日期': '2026年11月13日',
    '专业': '计算机科学与技术',
    '班级': '24计科4',
    '学号': '2410311411',
    '姓名': '何嘉欣',
    '指导教师': '刘锦行',
}
for row in doc.tables[0].rows:
    key = row.cells[0].text.strip()
    if key in cover_values:
        cell = row.cells[1]
        cell.text = ''
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(cover_values[key])
        run.font.name = '宋体'
        run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), '宋体')
        run.font.size = Pt(12)
        run.font.bold = False
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

# The template has an extra blank paragraph and an explicit page break after
# the cover table. Removing only the tail after the table keeps the cover
# intact and lets the body start on the next page without a blank page.
cover_table = doc.tables[0]._tbl
seen_cover = False
for child in list(doc.element.body.iterchildren()):
    if child is cover_table:
        seen_cover = True
        continue
    if seen_cover and child.tag != qn('w:sectPr'):
        doc.element.body.remove(child)

normal = doc.styles['Normal']
normal.font.name = '宋体'
normal._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
normal.font.size = Pt(10.5)
normal.paragraph_format.line_spacing = 1.5
normal.paragraph_format.space_after = Pt(4)


def set_run_font(run, name='宋体', size=10.5, bold=False):
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), name)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor(0, 0, 0)


def para(text='', bold=False, size=10.5, align=None, name='宋体', space_after=4, first_line=True):
    p = doc.add_paragraph()
    p.alignment = align if align is not None else WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_after = Pt(space_after)
    if first_line:
        p.paragraph_format.first_line_indent = Pt(size * 2)
    if text:
        run = p.add_run(text)
        set_run_font(run, name, size, bold)
    return p


def heading(text, level=1):
    p = doc.add_paragraph()
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(10 if level == 1 else 8)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text)
    set_run_font(run, '黑体', {1: 16, 2: 13, 3: 11.5}[level], True)
    return p


def shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), fill)
    tc_pr.insert_element_before(shd, 'w:noWrap', 'w:tcMar', 'w:textDirection',
                                'w:tcFitText', 'w:vAlign', 'w:hideMark')


def set_table_borders(table):
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement('w:tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), '4')
        el.set(qn('w:space'), '0')
        el.set(qn('w:color'), '808080')
        borders.append(el)
    tbl_pr.insert_element_before(borders, 'w:shd', 'w:tblLayout', 'w:tblCellMar',
                                 'w:tblLook', 'w:tblCaption', 'w:tblDescription')


def add_table(headers, rows, widths=None, font_size=9):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = 'Normal Table'
    set_table_borders(table)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.allow_autofit = False
    for i, text in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ''
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.0
        run = p.add_run(str(text))
        set_run_font(run, '黑体', font_size, True)
        shade(cell, 'D9E2F3')
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    for values in rows:
        cells = table.add_row().cells
        for i, value in enumerate(values):
            cells[i].text = ''
            p = cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            run = p.add_run(str(value))
            set_run_font(run, '宋体', font_size)
            cells[i].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    if widths:
        for i, width in enumerate(widths):
            table.columns[i].width = Inches(width)
        for row in table.rows:
            row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
            for i, width in enumerate(widths):
                row.cells[i].width = Inches(width)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return table


def code_block(text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.25)
    p.paragraph_format.right_indent = Inches(0.15)
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.line_spacing = 1.0
    lines = text.splitlines()
    for i, line in enumerate(lines):
        run = p.add_run(line)
        set_run_font(run, 'Consolas', 8.3)
        if i < len(lines) - 1:
            run.add_break()


def image_with_caption(filename, caption, width=5.45):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(str(ROOT / 'submissions/lab03/evidence/截图' / filename), width=Inches(width))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(8)
    run = cap.add_run(caption)
    set_run_font(run, '宋体', 9)


def bullet(text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.42)
    p.paragraph_format.first_line_indent = Inches(-0.2)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run('• ' + text)
    set_run_font(run, '宋体', 10.5)
    return p


heading('实验三　分布式批处理与性能分析', 1)
para('本报告记录本人学号 2410311411、实验/项目号 03 的完整实验过程。实验以实验二输出的 20,000 行 Silver Parquet 为固定输入，使用 Dask 在本机启动独立 Worker 进程完成分组聚合，再用 DuckDB 独立 SQL 核对结果。实验重点不是证明“进程越多越快”，而是分清数据分区、Worker 进程、任务图和 Shuffle，判断结果是否正确、工作量是否倾斜，并解释真实计时中各项成本。')

heading('一、实验目的', 1)
para('1. 理解批处理、分区、Worker、Scheduler、任务图和 Shuffle 之间的关系，能用真实进程编号说明任务确实在多个进程执行。', first_line=False)
para('2. 用 DuckDB 作为独立参照，验证 Dask 聚合结果，区分“结果正确”“执行更快”和“数据分布均匀”三个不同问题。', first_line=False)
para('3. 比较一 Worker 八分区、两 Worker 八分区、两 Worker 四分区三组配置，按照启动、主计算和总时间三个口径分析成本。', first_line=False)
para('4. 观察三个服务键在 Shuffle 后形成的实际分区行数，解释热键倾斜为什么不能靠继续增加分区自动消除。', first_line=False)
para('5. 在附件现有管线中完成慢请求阈值调整、每服务错误数与错误率聚合，通过 Dask/SQL 双路和独立核验器证明统计口径正确。', first_line=False)
para('6. 通过非法 Worker 配置和合法配置恢复，理解参数边界；说明本机多进程证据不能外推为生产跨机容错能力。', first_line=False)

heading('二、实验环境与输入', 1)
add_table(['项目', '实测值'], [
    ['操作系统', 'Windows 11 家庭版 中文版，64 位，版本 10.0.26200'],
    ['处理器', 'AMD Ryzen 7 8845H，8 核 16 逻辑处理器'],
    ['内存', '约 32 GB（29,099,000 KiB 可见内存）'],
    ['Python', '3.12.13，MSC v.1944 64 位'],
    ['项目解释器', r'D:\云计算与大数据处理\reference-BDP\.venv\Scripts\python.exe'],
    ['工作目录', r'D:\云计算与大数据处理\reference-BDP'],
    ['Dask / distributed', '2026.8.0 / 2026.8.0'],
    ['DuckDB / PyArrow / pandas', '1.5.5 / 25.0.1 / 3.0.5'],
    ['Silver 输入', 'data/silver/events.parquet，20,000 行、8 列'],
    ['Silver SHA-256', '516b3d78aab91c1487d9a24979eaef514c5acb7309d0d82a6688a762836634dc'],
], widths=[1.8, 4.0], font_size=8.6)
para('Silver 清单记录的原始文件 SHA-256 为 0d93bcd25e28047f804238c220bdb5b1d2dadf328647c07de85ba0104e8e2854，Silver 契约版本为 2，行数为 20,000。每行包含 event_id、event_time、service、model、input_tokens、output_tokens、latency_ms 和 status 八个字段。本实验只读取 Silver，不修改输入文件；三组性能对照和个人脚本都使用同一份数据。')
para('前置核验的实际输出为 rows=20000 和 silver hash verified。证据运行 run_id 为 fa687482e47d4e109e68273a71e7a59c，stage 为 probe-01。')
image_with_caption('01-silver-hash.png', '图 1  Silver 行数与 SHA-256 清单核验（学号、实验号 03、run_id 与结果同屏）', width=5.2)

heading('三、独立预测', 1)
heading('3.1 哈希分区手算', 2)
para('设 12 条事件中 A 有 8 条、B 有 3 条、C 有 1 条，仅用于手算的哈希为 A→0、B→1、C→2，再按 hash % 4 分区。各服务键只会落到一个计算分区，因此 4 个分区的行数如下。', first_line=False)
add_table(['服务键', '记录数', 'hash 值', 'hash % 4', '目标分区', '该分区行数'], [
    ['A', '8', '0', '0', '分区 0', '8'],
    ['B', '3', '1', '1', '分区 1', '3'],
    ['C', '1', '2', '2', '分区 2', '1'],
    ['—', '0', '—', '—', '分区 3', '0'],
], widths=[0.8, 0.8, 0.8, 0.9, 1.1, 1.2], font_size=8.8)
para('预测结果：分区 0、1、2、3 的行数分别为 8、3、1、0。若把分区数增加为 8，三个键的 hash % 8 仍分别是 0、1、2，只会形成三个非空分区，行数仍是 8、3、1，不会自然得到 8 个都有数据且均匀的分区。分区的数量只表示可拆出的工作块上限，不表示每个块都会分到记录。该手算哈希只用于解释取模行为，Dask 的真实哈希函数和具体分区编号可能不同，实际行数必须读取运行结果。')

heading('3.2 不同样本量的平均值手算', 2)
para('分区 1 有 2 条记录、平均延迟 10 ms，说明该分区延迟总和为 2×10=20 ms；分区 2 有 8 条记录、平均延迟 100 ms，说明延迟总和为 8×100=800 ms。全局延迟总和为 20+800=820 ms，全局记录数为 2+8=10，所以全局平均延迟为 820÷10=82 ms。', first_line=False)
para('直接计算 (10+100)÷2=55 ms 是错误的，因为它把只有 2 条记录的分区和有 8 条记录的分区赋予了相同权重，丢失了样本量这个分母。正确做法是让每个分区输出“总和 + 计数”，合并后再用总总和除以总计数。平均值本身不是可以直接相加的局部量，必须依赖可合并的充分统计量。')

heading('四、执行结构与真实多进程', 1)
para('本实验使用 distributed.LocalCluster 启动本地集群，参数为 n_workers=workers、threads_per_worker=1、processes=True、memory_limit=\'1GiB\'、host=\'127.0.0.1\'、dashboard_address=None。其中 processes=True 要求 Worker 是独立 Python 进程，而不是把任务放入同一进程的线程池；memory_limit 是单个 Worker 的教学限制，不是整机内存上限；host=127.0.0.1 把通信限制在本机。')
code_block("""with LocalCluster(n_workers=workers, threads_per_worker=1, processes=True,
                  memory_limit='1GiB', host='127.0.0.1',
                  dashboard_address=None) as cluster:
    with Client(cluster) as client:
        df = dd.read_parquet(str(silver)).repartition(npartitions=partitions)
        shuffled = df.shuffle(on='service', shuffle_method='tasks')
        group = shuffled.groupby('service').agg({...})
        actual = group.compute()""")
para('Scheduler 负责维护任务依赖、分派任务和收集状态；Worker 是执行具体任务的独立进程；Driver 是运行主脚本、构造任务图并调用 compute 的进程。分区是数据块及其对应计算，不是机器；任务图是“有哪些计算、谁依赖谁”的图；.compute() 才触发实际执行。Shuffle 按 service 重新分配记录，使相同服务键进入同一个哈希分区，过程中需要序列化、进程间传输、临时内存和调度。')
para('三组运行的 Worker 身份均来自 client.run(os.getpid)，不是手工填写。w1p8 只有一个 Worker PID 19836；w2p8 有两个不同 PID 5712 和 33736；w2p4 有两个不同 PID 10540 和 15996。这三个结果证明了本次运行的进程边界，但所有进程都位于同一台笔记本。')
add_table(['配置', 'Scheduler 可见 Worker 数', '真实 Worker PID', '不同 PID 数'], [
    ['w1 / p8', '1', '19836', '1'],
    ['w2 / p8', '2', '5712、33736', '2'],
    ['w2 / p4', '2', '10540、15996', '2'],
], widths=[1.1, 1.6, 2.2, 1.1], font_size=8.8)

heading('五、聚合正确性与任务规模', 1)
para('Dask 结果按 service 排序后与 DuckDB SQL 结果逐行比较，三组配置均得到 matches_duckdb=true。按服务聚合的实际结果如下；三组配置的数值完全相同。', first_line=False)
add_table(['服务', '请求数', '输入 Token', '输出 Token', '延迟总和（ms）'], [
    ['assistant', '14,008', '12,631,850', '4,310,029', '28,448,309'],
    ['batch', '2,023', '1,816,567', '616,515', '4,079,006'],
    ['search', '3,969', '3,567,223', '1,219,318', '8,137,035'],
    ['合计', '20,000', '18,015,640', '6,145,862', '40,664,350'],
], widths=[1.0, 1.0, 1.25, 1.2, 1.55], font_size=8.5)
para('这里的“正确”有两层含义：Dask 的多进程结果与 DuckDB 参照完全一致；三组配置的 Silver SHA-256 都是 516b3d78aab91c1487d9a24979eaef514c5acb7309d0d82a6688a762836634dc。DuckDB 是单进程参照路径，用于独立计算，不是性能竞赛的基线。')
para('任务数描述任务图规模，不等于输出行数。w1p8 和 w2p8 的主聚合任务图都有 115 个任务，w2p4 有 43 个任务；虽然最终输出只有 3 行服务汇总，任务图仍包含读取、重分区、Shuffle、局部聚合、合并以及依赖关系。输入行数是 20,000，输出行数是 3，任务数则是执行计划中的计算节点数量，三者不能混用。')

heading('六、三组性能配置与计时口径', 1)
add_table(['配置', '数据哈希（前 12 位）', '不同 PID 数', '任务数', '启动秒', '主计算秒', '总秒', 'SQL 一致'], [
    ['w1p8', '516b3d78aab9', '1', '115', '2.6939202', '3.3333064', '7.1099734', 'true'],
    ['w2p8', '516b3d78aab9', '2', '115', '2.9119467', '4.7153337', '8.4843690', 'true'],
    ['w2p4', '516b3d78aab9', '2', '43', '2.8535218', '4.4924883', '8.0016020', 'true'],
], widths=[0.65, 1.25, 0.65, 0.65, 0.8, 0.9, 0.8, 0.7], font_size=7.7)
para('四个计时字段的口径不同：duckdb_seconds 是 DuckDB 独立参照查询的时间；startup_seconds 是从创建集群到客户端可用的启动时间；compute_seconds 是主 Dask 聚合 .compute() 的时间；total_seconds 是从启动集群开始，到主聚合、额外分区诊断、客户端退出和集群清理全部结束的总时间。主聚合后又执行了一次 map_partitions(len).compute() 获取分区行数，因此 total_seconds 明显大于 startup_seconds + compute_seconds，不能把差额误认为主查询耗时。')
add_table(['配置', 'DuckDB 参照秒', '启动秒', '主计算秒', '总秒'], [
    ['w1p8', '0.0921820', '2.6939202', '3.3333064', '7.1099734'],
    ['w2p8', '0.0367485', '2.9119467', '4.7153337', '8.4843690'],
    ['w2p4', '0.0367614', '2.8535218', '4.4924883', '8.0016020'],
], widths=[1.0, 1.25, 1.05, 1.05, 1.05], font_size=8.8)
para('实测没有出现两 Worker 更快：w2p8 的主计算比 w1p8 多 1.3820273 秒，总时间多 1.3743956 秒；w2p4 的主计算比 w1p8 多 1.1591819 秒，总时间多 0.8916286 秒。该结果不是失败，也不需要虚构加速。20,000 行对本机进程集群较小，启动和清理约 2.7—2.9 秒，Shuffle 需要序列化和进程间交换，调度器还要管理 115 或 43 个任务；同时 assistant 热键占 14,008 行，绝大部分工作量集中在一个键上，增加第二个 Worker 很难把这一整块均匀切开。单次测量还会受到缓存、后台程序、CPU 频率和操作系统调度影响。')
image_with_caption('02-w1-p8.png', '图 2  一 Worker、八分区：单 PID、任务数、分区行数、计时与 SQL 一致性', width=4.0)
image_with_caption('03-w2-p8.png', '图 3  两 Worker、八分区：两个不同 PID、任务数、分区行数、计时与 SQL 一致性', width=3.98)
image_with_caption('04-w2-p4.png', '图 4  两 Worker、四分区：两 PID、43 个任务及真实分区行数', width=4.15)

heading('七、分区倾斜分析', 1)
para('w2p8 的分区行数为 [2023, 0, 14008, 3969, 0, 0, 0, 0]，总和为 20,000；非空分区只有 3 个，最大分区 14,008 行，占全部数据的 70.04%。w2p4 的行数为 [2023, 0, 14008, 3969]，同样只有 3 个非空分区。assistant 占 14,008/20,000=70.04%，batch 占 2,023/20,000=10.115%，search 占 3,969/20,000=19.845%。', first_line=False)
add_table(['指标', 'w2p8 实测', '解释'], [
    ['分区行数', '[2023, 0, 14008, 3969, 0, 0, 0, 0]', '8 个数据块中只有 3 个非空'],
    ['总行数', '20,000', '与 Silver 输入及聚合请求总数一致'],
    ['非空分区数', '3', '等于参与 Shuffle 的服务键数量'],
    ['最大分区', '14,008 行', 'assistant 热键，占 70.04%'],
    ['最小非空分区', '2,023 行', 'batch，占 10.115%'],
], widths=[1.35, 2.45, 2.0], font_size=8.5)
para('8 个分区不会自动变成 8 份均匀工作，因为哈希 Shuffle 按服务键决定去向：只有 3 个不同的 service 键，最多形成 3 个非空分区，若发生哈希碰撞还可能更少。增加分区数只能增加空的或很小的任务块，不能把单个热键自动拆成更多块。若要改善该聚合的热键，需要考虑预聚合、加盐后的两阶段聚合或改变分区策略，但这会引入额外任务和正确性约束，不能只凭“分区更多”宣称更快。')
image_with_caption('05-partition-skew.png', '图 5  八分区真实行数、非空分区数量与最大分区诊断', width=5.2)

heading('八、个人改动与独立核验', 1)
heading('8.1 慢请求阈值由 1000 ms 改为 2000 ms', 2)
para('运行前预测：阈值提高后，请求总数不变，延迟总和与平均延迟不变；慢请求定义为 latency_ms ≥ 阈值，因此原先落在 1000—1999 ms 的记录不再计入慢请求，慢请求数和慢请求率都会下降。实际结果与预测一致。')
add_table(['服务', '请求数', '1000 ms 慢请求', '1000 ms 慢请求率', '2000 ms 慢请求', '2000 ms 慢请求率'], [
    ['assistant', '14,008', '10,589', '75.59%', '7,120', '50.83%'],
    ['batch', '2,023', '1,519', '75.09%', '1,011', '49.98%'],
    ['search', '3,969', '3,043', '76.67%', '2,041', '51.42%'],
], widths=[0.95, 0.8, 1.0, 1.0, 1.0, 1.0], font_size=8.2)
para('两次运行的 matches_sql 均为 true，说明 Dask 与 DuckDB 在各自阈值下完全一致。1000 ms 结果对应 run_id 7fc9b0e9426c4b599ee82a5730325a26；2000 ms 最终结果对应 run_id 06bbcb7572864418acad6e01d14474d0。阈值是业务规则，不改变 Silver 输入；慢请求率的分母始终是该服务的全部合法请求。')
image_with_caption('06-latency-1000.png', '图 6  初始阈值 1000 ms 的每服务请求数、延迟总和与慢请求率', width=4.0)

heading('8.2 新增 errors 与 error_rate 的四处代码改动', 2)
para('在 Dask 路径中，先按 status == \'error\' 构造每行错误标志，再与慢请求标志一起聚合；随后把聚合列 is_error 重命名为 errors。DuckDB 参照路径使用 CASE WHEN status = \'error\' THEN 1 ELSE 0 END 独立计数，继续沿用原有逐行比较。最后用 errors / requests 计算 error_rate。四处改动都在附件现有 main() 内完成，没有改写 Silver，也没有把结果写死。')
code_block("""# 1) Dask：逐行构造错误标志
df = df.assign(
    is_slow=(df["latency_ms"] >= SLOW_MS).astype("int64"),
    is_error=(df["status"] == "error").astype("int64"),
)

# 2) Dask：聚合错误数并重命名为 errors
actual = df.groupby("service").agg({
    "event_id": "count", "latency_ms": "sum",
    "is_slow": "sum", "is_error": "sum",
}).compute()
actual = actual.reset_index().rename(columns={
    "event_id": "requests", "latency_ms": "latency_ms_sum",
    "is_slow": "slow_requests", "is_error": "errors",
})

# 3) DuckDB：独立 SQL 同口径统计
SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END)::BIGINT AS errors

# 4) 最终比例：分母为该服务全部合法请求
actual["error_rate"] = actual["errors"] / actual["requests"]""")
para('最终 2000 ms 运行新增的错误统计为：assistant errors=543、error_rate=0.03876356367789834；batch errors=78、error_rate=0.03855659911023233；search errors=179、error_rate=0.04509952128999748。三个服务合计 800 个错误，占总请求 20,000 的 4.00%。独立核验器逐行读取 Silver 的 service 与 status，重新计数并核对分母、错误数和比例，实际输出 ERROR_EXTENSION_PASS {\'total_errors\': 800}。')
image_with_caption('07-latency-2000-errors.png', '图 7  最终阈值 2000 ms：新增 errors/error_rate 且 Dask 与 SQL 一致', width=5.05)
image_with_caption('08-error-extension.png', '图 8  独立核验器输出 ERROR_EXTENSION_PASS，总错误数为 800', width=5.2)

heading('8.3 手算核对与边界示例', 2)
para('以 assistant 为例，latency_ms_sum=28,448,309，requests=14,008，所以平均延迟为 28,448,309÷14,008=2030.8615790976585 ms。slow_requests=7,120，慢请求率为 7,120÷14,008=0.508280982295831，即 50.83%。errors=543，错误率为 543÷14,008=0.03876356367789834，即 3.88%。这三项手算结果与 JSON 完全一致。')
para('边界口径为：A 服务 4 条请求（ok、ok、error、ok）时 errors=1、error_rate=1÷4=0.25；B 服务 3 条请求（error、error、ok）时 errors=2、error_rate=2÷3≈0.6667；全为 ok 的服务错误率为 0。空服务没有请求，也不产生输出行，所以不会构造 0÷0。不能先计算每个分区的错误率再直接取平均，必须合并错误总数与请求总数后再相除。')
image_with_caption('09-manual-check.png', '图 9  assistant 均值、慢请求率与错误率的手算核对', width=5.2)

heading('九、配置失败与恢复', 1)
para('按手册尝试 workers=0、partitions=8。程序在启动集群前执行范围检查并明确拒绝：ValueError: Teaching limits: 1-4 workers, 1-64 partitions. 外层预期失败运行 run_id 为 f2ca7d1094b54c8cbad6d8c00c78ec33，退出码为 1。这个失败说明参数边界被正确执行，不代表 Worker 宕机，也不涉及任务重试或状态恢复。')
image_with_caption('10-expected-failure.png', '图 10  workers=0 被参数范围检查拒绝的真实错误与退出信息', width=5.2)
para('随后以 workers=2、partitions=8 重新运行，得到两个不同 PID、matches_duckdb=true 和完整聚合结果，run_id 为 b72960e1868040288f4e3ab839cf4b2e。图 3 同时作为恢复成功的证据。恢复路径没有把 processes 改为 False，也没有删除异常或篡改退出码。')

heading('十、必答分析题', 1)
para('1. 8 个分区为什么不等于 8 台机器或 8 个 Worker？分区是数据块和计算组织单位，Worker 才是执行进程，机器则是物理或虚拟资源。本次 8 个分区由 repartition(npartitions=8) 产生，两个 Worker 仍运行在同一台电脑上；分区可以多于、少于或等于 Worker 数，三者概念不同。', first_line=False)
para('2. 为什么 3 个服务键经 Shuffle 后很难均匀填满 8 个分区？因为哈希分区把同一个键的全部记录送到同一个目标分区，只有 3 个键时最多只有 3 个非空分区；不同键还可能碰撞。实测只有 [2023, 14008, 3969] 三个非空块，assistant 占 70.04%，增加空分区不会自动把热键拆开。', first_line=False)
para('3. 为什么不能对不同大小分区的平均值直接取平均？平均值丢失了各分区的样本量。2 条记录的平均 10 ms 与 8 条记录的平均 100 ms 合并后，总和为 2×10+8×100=820 ms、计数为 10，全局平均为 82 ms；直接得到 55 ms 是把两个分区错当成同等权重。', first_line=False)
para('4. 本章 total_seconds 为什么包含超过主计算的工作？它从创建集群前开始，包括集群启动、客户端连接、主聚合、另行执行的分区行数诊断、客户端关闭和 Worker 清理；compute_seconds 只覆盖主聚合 .compute()。因此 total_seconds 不能直接当作主查询耗时，也不能与只测 SQL 的 duckdb_seconds 直接比较。', first_line=False)
para('5. 两 Worker 比一 Worker 慢时，应检查哪些可测因素？应检查集群启动与清理、任务调度、Shuffle 的序列化和进程间传输、热键倾斜、数据规模、每 Worker 线程数、内存限制、缓存冷热、后台程序、CPU 频率与单次测量波动。本次主要可见因素是启动/清理约 2.8—2.9 秒、Shuffle 与调度开销，以及 assistant 14,008 行的热键集中；单次结果只能支持初步观察。', first_line=False)
para('6. 本机多个进程的证据为什么不足以证明生产跨机容错？这些进程共享同一操作系统、CPU、内存和本地文件系统，没有真实的跨机网络、节点断电、磁盘故障或共享存储异常。两个 PID 只能证明任务在本机不同进程中执行且结果一致，不能证明节点替换、副本切换、网络分区恢复或云弹性伸缩。', first_line=False)

heading('十一、结论与局限', 1)
para('本实验在同一份 20,000 行 Silver 输入上完成了 Dask 多进程聚合和 DuckDB 独立核对，三组配置结果均为 matches_duckdb=true。两 Worker 没有带来加速，w2p8 总时间为 8.484 秒、主计算为 4.715 秒，均高于 w1p8 的 7.110 秒和 3.333 秒；这一结果与启动、Shuffle、调度和热键倾斜相符，不能用 Worker 数直接推断性能。')
para('分区诊断显示 8 个分区只有 3 个非空，最大分区 14,008 行，说明输出只有 3 个服务不代表中间工作量只有 3 份。个人改动把慢请求阈值从 1000 ms 调到 2000 ms，新增 errors/error_rate 的 Dask 与 SQL 双路实现，专项核验输出总错误数 800；assistant 的手算均值、慢请求率和错误率均与程序结果一致。')
para('本实验的边界是：数据约 2 万行，三组配置各测量一次，所有 Worker 都在同一台 Windows 笔记本上，通过本机回环通信；没有跨机网络、节点故障、共享存储或生产集群，也没有对缓存和硬件负载做严格控制。因此结论只适用于本次受控教学环境，不能据此宣称线性加速或生产级容错。若要得到稳定性能结论，需要在独立环境重复测量、报告均值和波动区间，并分别记录冷缓存、热缓存和系统负载。')

heading('十二、运行证据索引', 1)
para('运行 JSON 与同名 HTML 位于 evidence/运行记录/，原始截图位于 evidence/截图/。每张评分截图均保留学号 2410311411、实验/项目号 03、run_id 和真实结果。', first_line=False)
add_table(['序号', '用途', 'run_id', '截图文件'], [
    ['1', 'Silver 行数与哈希', 'fa687482e47d4e109e68273a71e7a59c', '01-silver-hash.png'],
    ['2', 'w1p8 基准', '1856d8e5555f45ddba473928894571bd', '02-w1-p8.png'],
    ['3', 'w2p8 与恢复', 'b72960e1868040288f4e3ab839cf4b2e', '03-w2-p8.png'],
    ['4', 'w2p4 基准', 'd601cd13c0d54ca5ab4c2e9e0637d5c9', '04-w2-p4.png'],
    ['5', '分区倾斜诊断', '17394ae66a054bffa1404c850fd9643b', '05-partition-skew.png'],
    ['6', '阈值 1000 ms', '7fc9b0e9426c4b599ee82a5730325a26', '06-latency-1000.png'],
    ['7', '阈值 2000 ms 与错误率', '06bbcb7572864418acad6e01d14474d0', '07-latency-2000-errors.png'],
    ['8', '错误扩展专项核验', 'fc57c9f154c147fb9ff9a1a1d40eca88', '08-error-extension.png'],
    ['9', '手算核对', 'd05efed99ba74f7b9790ed11e7f2a6de', '09-manual-check.png'],
    ['10', '非法 Worker 预期失败', 'f2ca7d1094b54c8cbad6d8c00c78ec33', '10-expected-failure.png'],
], widths=[0.45, 1.5, 2.55, 1.8], font_size=7.8)
para('完整代码差异位于 02_代码与改动/代码差异/student_latency_1000_to_2000_errors.diff；修改前与当前脚本分别位于 02_代码与改动/修改前/ 和 02_代码与改动/当前代码/。三份性能 JSON、1000/2000 业务结果及身份旁证位于 03_业务结果/。')

heading('十三、代码仓库', 1)
para('实验一、实验二和实验三的报告、代码、业务结果、运行 JSON/HTML 与截图已汇总到以下仓库：', first_line=False)
para('https://github.com/wxzn222/cloud_computing_and_bigdata_processing', bold=True, first_line=False)
para('报告正文学号：2410311411　　实验/项目号：03', bold=True, first_line=False)

section = doc.sections[0]
footer_p = section.footer.paragraphs[0]
footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = footer_p.add_run('学号 2410311411　|　实验三　分布式批处理与性能分析')
set_run_font(run, '宋体', 8.5)


def force_black(paragraphs):
    for paragraph in paragraphs:
        for run in paragraph.runs:
            run.font.color.rgb = RGBColor(0, 0, 0)


force_black(doc.paragraphs)
for table_obj in doc.tables:
    for row_obj in table_obj.rows:
        for cell_obj in row_obj.cells:
            force_black(cell_obj.paragraphs)
for section_obj in doc.sections:
    for story in (section_obj.header, section_obj.footer, section_obj.first_page_header, section_obj.first_page_footer,
                  section_obj.even_page_header, section_obj.even_page_footer):
        force_black(story.paragraphs)
        for table_obj in story.tables:
            for row_obj in table_obj.rows:
                for cell_obj in row_obj.cells:
                    force_black(cell_obj.paragraphs)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
DOCX_OUTPUTS.mkdir(parents=True, exist_ok=True)
doc.save(str(OUTPUT))
print(OUTPUT.resolve())
print('paragraphs', len(doc.paragraphs), 'tables', len(doc.tables))
