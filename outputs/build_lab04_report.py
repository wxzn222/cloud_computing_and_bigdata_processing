from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path.cwd()
TEMPLATE = Path(r'C:\Users\15971\Downloads\云计算与大数据处理_实验报告模版.docx')
OUTPUT = ROOT / 'submissions/lab04/01_实验报告/实验报告_何嘉欣_2410311411.docx'

doc = Document(str(TEMPLATE))
doc.core_properties.title = '云计算与大数据处理实验报告：实验四 增量事件处理与故障恢复'
doc.core_properties.author = '何嘉欣'
doc.core_properties.subject = '实验四 增量事件处理与故障恢复'

cover_values = {
    '实验名称': '实验四　增量事件处理与故障恢复',
    '实验日期': '2026年11月19日',
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


def bullet(text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.42)
    p.paragraph_format.first_line_indent = Inches(-0.2)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run('• ' + text)
    set_run_font(run, '宋体', 10.5)
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
    for index, line in enumerate(lines):
        run = p.add_run(line)
        set_run_font(run, 'Consolas', 8.3)
        if index < len(lines) - 1:
            run.add_break()


def image_with_caption(filename, caption, width=5.2):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(ROOT / 'submissions/lab04/evidence/截图' / filename), width=Inches(width))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(8)
    run = cap.add_run(caption)
    set_run_font(run, '宋体', 9)


def force_black(paragraphs):
    for paragraph in paragraphs:
        for run in paragraph.runs:
            run.font.color.rgb = RGBColor(0, 0, 0)


heading('实验四　增量事件处理与故障恢复', 1)
para('本报告记录本人学号 2410311411、实验/项目号 04 的完整实验过程。实验从实验二生成的 20,000 条合法独特 Silver 事件出发，每 500 条作为一个微批写入本机 SQLite；重点核对事件写入与检查点推进是否处于同一事务、重复投递是否产生额外效果、提交前异常能否同时回滚，以及关闭连接后能否从磁盘状态恢复。')

heading('一、实验目的', 1)
para('1. 理解微批、offset、checkpoint、事务、幂等写入与重放之间的关系，区分逻辑处理位置和可见事件数量。', first_line=False)
para('2. 在 SQLite 中完成 40 个 500 条微批写入，并验证 100 条重复投递不会新增记录。', first_line=False)
para('3. 注入提交前受控异常，观察事件写入和检查点更新同时回滚；关闭连接后重新打开磁盘数据库并恢复。', first_line=False)
para('4. 接受新 ID 的晚到事件，重新计算历史 Gold 汇总，并区分事件时间与处理时间。', first_line=False)
para('5. 独立实现个人事务函数，覆盖正常写入、旧批次重放、提交前失败、磁盘重连和恢复后再次重放。', first_line=False)
para('6. 明确实验边界：本章只验证单个 SQLite 数据库内的事务性效果与主键去重，不等同于跨机容错、进程强杀恢复或全局 exactly-once。', first_line=False)

heading('二、实验环境与输入', 1)
add_table(['项目', '实测值'], [
    ['操作系统', 'Windows 11 家庭版 中文版，64 位，版本 10.0.26200'],
    ['处理器', 'AMD Ryzen 7 8845H，8 核 16 逻辑处理器'],
    ['Python', '3.12.13，64 位'],
    ['SQLite', '3.50.4'],
    ['PyArrow', '25.0.1'],
    ['项目解释器', r'D:\云计算与大数据处理\reference-BDP\.venv\Scripts\python.exe'],
    ['Silver 输入', 'data/silver/events.parquet，20,000 行、8 列'],
    ['Silver SHA-256', '516b3d78aab91c1487d9a24979eaef514c5acb7309d0d82a6688a762836634dc'],
    ['本次主运行 run_id', '91b7e89eedff45ee981613572867b55f'],
    ['数据库目录 run_id', 'df5e2ceefb8d'],
], widths=[1.7, 4.1], font_size=8.6)
para('前置 Silver 与实验三使用的输入一致，主运行从 20,000 条记录开始。微批大小为 500，因此首次处理分成 40 批。实验三的固定批处理基线是 20,000 条；本章随后新增一个恢复事件和一个晚到事件，所以最终 Gold 请求总数为 20,002。原始 JSONL 的 20,102 行包含 100 条重复和 2 条非法记录，这两个数量已在实验二清洗，不应与本章最终行数混为一谈。')
para('开始身份运行 run_id 为 058ed7a3d4054d00960b2ea661ceaf2a，最终身份运行 run_id 为 75038dfbc68f4ad1b6e497e422d49f45。主运行、数据库只读核验和个人事务核验的 run_id 在正文和证据索引中分别列出。')
image_with_caption('01-start-identity.png', '图 1  实验四开始身份（学号、实验号 04 与 run_id 同屏）', width=5.1)

heading('三、独立预测', 1)
para('设数据库初始已有 3 个独特事件，检查点为 3；准备处理新事件 X，成功后检查点应变为 4。先按不同提交边界进行预测，再用真实运行核对。')
add_table(['场景', '最终可见事件数', '检查点', '应重放哪部分'], [
    ['两项都在同一事务中成功提交', '4', '4', '无需重放'],
    ['写入 X 后、提交前抛异常并回滚', '3', '3', '重启后重放 X 及检查点更新'],
    ['X 已单独提交，检查点尚未更新就失败', '4', '3', '重放 X 和检查点；事件 ID 去重避免重复行'],
    ['检查点先提交到 4，X 尚未写入就失败', '3', '4', '不能直接跳过，需要回查或重建该位置'],
], widths=[2.3, 1.1, 0.8, 1.8], font_size=8.3)
para('前两行说明同一事务能够把数据和进度绑定在一起；第三行说明进度落后会带来重放，主键去重可以抑制重复业务效果；第四行说明进度超前更危险，消费者可能认为 X 已处理而永远跳过它。主键去重只能阻止同一 ID 再次插入，不能证明某个检查点位置的数据真的已经写入。')

heading('四、增量处理机制', 1)
para('本章把 20,000 条事件按每批 500 条切片。offset 表示已经处理到的逻辑输入位置，checkpoint 是把该位置持久化的状态；本章恰好按顺序记录位置，所以最终 offset 与最终行数都为 20,002，但一般系统里两者不一定相等。批处理函数先检查同一 event_id 的既有内容，完全重复允许忽略，同 ID 不同内容则拒绝，随后写入事件并推进检查点。')
code_block("""con.execute('BEGIN IMMEDIATE')
for row in rows:
    values = tuple(row[field] for field in EVENT_FIELDS)
    old = con.execute('SELECT * FROM events WHERE event_id=?',
                      (row['event_id'],)).fetchone()
    if old and old != values:
        raise ValueError('Conflicting duplicate event_id')
    con.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,?)', values)

con.execute('''INSERT INTO checkpoint VALUES (1, ?)
               ON CONFLICT(id) DO UPDATE
               SET offset = MAX(offset, excluded.offset)''', (next_offset,))
if fail_before_commit:
    raise RuntimeError('INJECTED_FAILURE_BEFORE_COMMIT')
con.commit()""")
para('事件表以 event_id 为主键，重复 ID 不能形成两条记录；checkpoint 表只有一行，MAX(offset, excluded.offset) 防止旧批次重放让进度倒退。异常分支执行 rollback()，所以数据行和检查点一起失效。这个 MAX 规则依赖单条顺序输入、没有未完成空洞的假设；若多个分区乱序完成，直接取全局最大位置可能跨过尚未处理的前置数据。')

heading('五、分阶段运行结果', 1)
add_table(['阶段', '新增事件数', '可见总行数', '检查点', '判定依据'], [
    ['初始微批完成', '20,000', '20,000', '20,000', '40 个 500 条批次；initial_inserted=20000'],
    ['重放前 100 条', '0', '20,000', '20,000', 'duplicate_inserted=0，主键去重生效'],
    ['提交前失败并回滚', '0', '20,000', '20,000', 'failure_injected=true；失败前后均为 20000/20000'],
    ['关闭连接后恢复', '1', '20,001', '20,001', 'recovered_inserted=1，从磁盘重连后重放'],
    ['接受晚到事件', '1', '20,002', '20,002', 'late_inserted=1；final_rows=final_offset=20002'],
], widths=[1.45, 0.9, 0.9, 0.85, 2.05], font_size=8.0)
para('主运行先完整提交 20,000 条 Silver 事件，再把前 100 条作为重复投递重新交给 apply_batch，新增数为 0，说明主键和 INSERT OR IGNORE 抑制了重复效果。随后写入新的 increment-new 时，在 checkpoint 推进之后、事务提交之前抛出 RuntimeError；异常分支回滚，数据库仍为 20,000 行、检查点仍为 20,000。关闭连接后重新打开同一个 events.sqlite，再重放该事件，新增 1 条；最后接受新 ID 的 increment-late，再新增 1 条。')

heading('六、主运行业务汇总', 1)
para('主运行证据 run_id 为 91b7e89eedff45ee981613572867b55f，内部数据库目录 run_id 为 df5e2ceefb8d。这不是两个业务版本号：前者标识课程证据运行，后者标识本次创建的数据库目录。最终数据库 SHA-256 为 4d0741a0704a8df6428f2bfb07b03f0691fd476c56b46da9a30f9e9ff52125b6。')
add_table(['服务', '请求数', '输入 Token', '输出 Token'], [
    ['assistant', '14,009', '12,633,388', '4,310,320'],
    ['batch', '2,023', '1,816,567', '616,515'],
    ['search', '3,970', '3,568,992', '1,219,714'],
    ['合计', '20,002', '18,018,947', '6,146,549'],
], widths=[1.05, 1.0, 1.35, 1.35], font_size=8.8)
para('与实验三的 20,000 条基线相比，assistant 增加 1 条请求、1,538 个输入 Token 和 291 个输出 Token；search 增加 1 条请求、1,769 个输入 Token 和 396 个输出 Token；batch 不变。增加的两条记录分别来自复用 Silver 中一条记录内容的新 ID 恢复事件，以及事件时间被改为 2026-02-28T23:59:00+00:00 的晚到事件。因此最终请求数为 20,002，而不是把实验三的 20,000 强行保持不变。')
para('Gold 汇总文件 realtime_service.json 的 SHA-256 为 d9d4eb24264819b20d5e64a86138b075df3efb0664a677c7a507e9b6d9f5466c。它是后续实验 07 的固定只读统计来源，只暴露按服务的 requests、input_tokens 和 output_tokens，不提供任意 SQL 接口。')
image_with_caption('02-main-replay.png', '图 2  主运行完整状态：微批、重放、失败回滚、恢复、晚到与最终 Gold 汇总', width=4.8)

heading('七、真实数据库只读核验', 1)
para('inspect_state.py 从 data/state/latest.json 找到本次数据库，以 SQLite URI 的 mode=ro 打开只读连接，直接查询事件数、检查点、两个 increment- 事件和按服务汇总，再与 Gold 列表比较。该步骤不是重新打印 replay.json，而是从数据库实际读取状态。')
add_table(['检查项', '实际结果', '结论'], [
    ['数据库路径', 'data/state/runs/df5e2ceefb8d/events.sqlite', '与 latest.json 指向一致'],
    ['事件总数', '20,002', '20,000 Silver + 恢复 1 + 晚到 1'],
    ['检查点', '20,002', '最后一批和两个新增事件均已提交'],
    ['恢复事件', 'increment-new，2026-03-02T03:46:35+00:00', '新 ID，来自顺序输入后的恢复'],
    ['晚到事件', 'increment-late，2026-02-28T23:59:00+00:00', '新 ID，事件时间早于原始首条记录'],
    ['Gold 一致性', 'matches_gold=true', '数据库聚合与 Gold 服务汇总完全一致'],
], widths=[1.15, 2.75, 1.9], font_size=8.3)
para('只读核验运行 run_id 为 5287cd662cb14aa99c7e4c0bd8aa72d9。输出中的 aggregate 与 realtime_service.json 完全相同，说明已提交数据库状态、检查点和对外统计三者一致。')
image_with_caption('03-database-inspection.png', '图 3  只读连接查询真实 SQLite：20,002 行、检查点 20,002、两个新 ID 且 matches_gold=true', width=5.25)

heading('八、个人关键改动：短事务函数', 1)
para('本次选择练习 B，依据附件骨架独立实现 apply_student(con, rows, next_offset, fail_before_commit=False)。函数显式开始事务，在同一个事务内写入事件并推进检查点，提交前注入异常时统一回滚，正常结束时统一提交；返回值用提交后的事件总数减去事务开始时的事件总数，表示本批真正新增的记录数。完整个人源码位于 submissions/lab04/student_apply_batch.py，差异位于 02_代码与提交/代码差异/student_apply_batch.diff。')
code_block("""con.execute("BEGIN IMMEDIATE")
try:
    before = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    for event_id, tokens in rows:
        con.execute("INSERT OR IGNORE INTO events(id, tokens) VALUES (?, ?)",
                    (event_id, tokens))
    con.execute("INSERT INTO checkpoint(id, offset) VALUES (1, ?) "
                "ON CONFLICT(id) DO UPDATE "
                "SET offset = MAX(offset, excluded.offset)", (next_offset,))
    if fail_before_commit:
        raise RuntimeError("INJECTED_FAILURE_BEFORE_COMMIT")
    con.commit()
except Exception:
    con.rollback()
    raise
after = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
return after - before""")
para('实现前预测：初始批次写入 a、b 后应为 2 行、offset=2；重放旧批次不得倒退；写入 c 时在提交前抛异常，关闭并重开数据库后仍应保持 2/2；再次重放 c 成功后才变为 3/3；继续重放 c 仍保持 3/3。独立核验器的实际结果为 STUDENT_TRANSACTION_PASS，四个观测状态依次为 initial=(2,2)、replay_old=(2,2)、failed_and_rolled_back=(2,2)、recovered_and_replayed=(3,3)。核验器还确认事件 Token 总量为 60，说明没有丢失已提交数据或产生重复行。')
add_table(['检查阶段', '事件数', 'offset', '验证目的'], [
    ['initial', '2', '2', '正常提交两个事件并推进检查点'],
    ['replay_old', '2', '2', '旧批次重放不新增，offset 不倒退'],
    ['failed_and_rolled_back', '2', '2', '提交前异常使事件 c 与 offset=3 同时回滚'],
    ['recovered_and_replayed', '3', '3', '磁盘重开后可恢复，重复重放仍幂等'],
], widths=[1.85, 0.8, 0.8, 2.4], font_size=8.7)
para('个人函数遵循练习契约，只处理已校验且重复 ID 内容相同的行。SQLite 的 INSERT OR IGNORE 会忽略主键冲突，但不会主动指出“同一 ID 对应不同内容”；若扩展到可更正事件，必须在写入前读取旧内容并比较，或在数据库层增加内容哈希，否则会静默保留旧值。主共享管线的 apply_batch 已包含该内容冲突检查。')
para('事务时间线可以写成：BEGIN IMMEDIATE → 写入本批事件 → 更新 checkpoint → 若无异常 COMMIT；若在提交前发生异常，则进入 ROLLBACK，事件和检查点都不生效。只有主键去重而没有检查点原子性时，事件可能已经提交而进度仍落后，重启后可以重放；反过来，如果检查点先提交而事件未写入，去重无法补回被跳过的数据，必须通过回查、重建或一致性修复解决。')
image_with_caption('04-student-transaction-pass.png', '图 4  个人事务函数独立核验：STUDENT_TRANSACTION_PASS 与四个阶段状态', width=5.25)

heading('九、晚到事件与历史汇总', 1)
para('本章新增的 increment-late 事件时间为 2026-02-28T23:59:00+00:00，早于原始数据首条事件 2026-03-01T00:00:00+00:00，但它具有新的 event_id，因此是晚到事件而不是重复事件。当前政策是接受合法晚到事件，并从数据库重新计算全部历史按服务汇总；没有实现 watermark、窗口关闭或只更新固定时间窗的增量机制。')
para('该晚到事件复用了原始首条 assistant 记录的 Token 与延迟内容，但使用新 ID。因此 Gold 中 assistant 的请求数从 14,008 变为 14,009，输入 Token 增加 1,538，输出 Token 增加 291。如果后续改为按日汇总，应更新 2026-02-28 的 assistant 日桶；若该日期已缓存，还需要使按“日期 + 服务”的缓存键失效，并发布新的汇总版本，不能只覆盖一个与日期无关的全局缓存。')

heading('十、故障类型与能力边界', 1)
para('本次注入的是受控 Python RuntimeError，发生在 checkpoint 更新之后、commit 之前。异常被捕获后显式执行 rollback，并在随后关闭 SQLite 连接、从磁盘重新打开数据库后重放。该证据支持“单数据库事务在应用异常下同时回滚数据和进度，并可从已提交磁盘状态恢复”，不支持“进程被强制终止、机器断电、磁盘损坏或网络分区下也已验证恢复”。')
para('本章的 exactly-once effect 只限定在单个 SQLite 数据库和本应用的 event_id 去重逻辑内。没有 Kafka 生产者幂等、消费者组重平衡、跨数据库两阶段提交或分布式事务，因此不能写成“Kafka exactly-once 已实现”。本章也没有消息代理、分区 offset 或 watermark；这些能力需要额外组件和故障注入。')

heading('十一、必答分析题', 1)
para('1. 为什么事件写入和检查点更新必须处于同一个提交边界？如果事件单独提交、检查点失败，数据已生效但进度落后；如果检查点单独提交、事件失败，系统会跳过未处理数据。只有同一事务一起提交或回滚，单数据库内的数据和逻辑位置才保持一致。', first_line=False)
para('2. MAX(offset,new_offset) 在什么顺序假设下成立？存在未完成空洞时会怎样？它适合单条顺序输入且不存在未完成前置批次的场景，可以防止旧批次重放让进度倒退。若多个分区乱序完成，后一个批次先成功会导致全局 offset 取到较大值，系统可能跳过仍未完成的小 offset 批次，因此需要按分区保存 offset 或使用连续水位。', first_line=False)
para('3. 主键去重为什么不能修复“检查点已经超前但数据未写入”的问题？主键只能阻止同一 ID 重复插入，无法知道某个被检查点跳过的 ID 从未写入。消费者按超前 checkpoint 从更后位置继续，根本不会再读到那条记录，只能靠回查、重建或一致性修复补回。', first_line=False)
para('4. 本次注入的是受控异常、进程被杀、机器断电，还是网络分区？本次是提交前的受控 Python RuntimeError，并由代码显式 rollback；随后关闭连接再从磁盘重开。证据可支持应用异常与连接重开恢复，不支持强杀进程、断电或网络分区恢复。', first_line=False)
para('5. 晚到事件为什么不等于重复事件？本章有没有 watermark？晚到事件的事件时间较早，但 event_id 从未出现，是新事实；重复事件是同一事实再次到达。当前政策接受合法晚到事件并重算全历史汇总，没有 watermark，也没有窗口关闭机制。', first_line=False)
para('6. 本章的事务性效果限制在哪个系统范围内？为什么不能写“Kafka exactly-once 已实现”？效果限制在单个 SQLite 数据库、本应用连接和 event_id 去重范围内。没有 Kafka、消息代理 offset、跨分区协调或跨系统事务，因此不能外推为 Kafka 或全局 exactly-once。', first_line=False)

heading('十二、结论与局限', 1)
para('本实验完成了从 20,000 条 Silver 事件开始的微批增量处理。40 个 500 条批次全部成功提交；重放前 100 条新增 0；提交前注入异常后，事件数和检查点同时保持 20,000；关闭连接后从磁盘恢复新增 1 条；接受晚到事件后新增 1 条，最终数据库和 Gold 均为 20,002 条。只读连接核验 matches_gold=true，说明数据库聚合与对外汇总一致。')
para('个人短事务函数通过独立核验，验证了正常提交、旧批次重放不倒退、提交前失败回滚、磁盘重连恢复和恢复后再次重放五个契约。事务时间线表明，事件写入、checkpoint 推进和提交必须形成同一个原子边界；主键去重只能抑制重复效果，不能弥补检查点超前导致的漏读。')
para('实验边界包括：输入来自固定 Parquet 列表而非实时消息队列；故障是受控应用异常，不是物理断电或强杀进程；数据库为单个本机 SQLite 文件；去重只在 event_id 主键范围内；没有 watermark、窗口状态、跨机复制或分布式事务。更大规模与生产环境还需要并发冲突控制、分区 offset、可重放日志、崩溃一致性和跨节点恢复策略。')

heading('十三、运行证据索引', 1)
para('运行 JSON 与同名 HTML 位于 evidence/运行记录/，原始截图位于 evidence/截图/。每张评分截图均保留学号 2410311411、实验/项目号 04、run_id 和真实结果。', first_line=False)
add_table(['用途', 'run_id', '截图文件'], [
    ['开始身份', '058ed7a3d4054d00960b2ea661ceaf2a', '01-start-identity.png'],
    ['主运行与最终状态', '91b7e89eedff45ee981613572867b55f', '02-main-replay.png'],
    ['数据库只读核验', '5287cd662cb14aa99c7e4c0bd8aa72d9', '03-database-inspection.png'],
    ['个人事务函数核验', 'dadd21b276d8450d800edef1d45d0783', '04-student-transaction-pass.png'],
    ['最终身份', '75038dfbc68f4ad1b6e497e422d49f45', '05-final-identity.png'],
], widths=[1.45, 2.65, 1.9], font_size=7.8)
para('主运行业务结果位于 03_业务结果/，其中包括 replay.json 与 realtime_service.json；真实数据库 events.sqlite、latest.json 位于 04_状态与数据库/。个人源码位于 submissions/lab04/student_apply_batch.py，未实现骨架与完整 diff 位于 02_代码与提交/。')
image_with_caption('05-final-identity.png', '图 5  实验四最终身份（学号、实验号 04 与 run_id 同屏）', width=5.1)

heading('十四、代码仓库', 1)
para('实验一至实验四的报告、代码、业务结果、数据库状态、运行 JSON/HTML 与截图已汇总到以下仓库：', first_line=False)
para('https://github.com/wxzn222/cloud_computing_and_bigdata_processing', bold=True, first_line=False)
para('报告正文学号：2410311411　　实验/项目号：04', bold=True, first_line=False)

section = doc.sections[0]
footer_p = section.footer.paragraphs[0]
footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = footer_p.add_run('学号 2410311411　|　实验四　增量事件处理与故障恢复')
set_run_font(run, '宋体', 8.5)

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
doc.save(str(OUTPUT))
print(OUTPUT.resolve())
print('paragraphs', len(doc.paragraphs), 'tables', len(doc.tables))
