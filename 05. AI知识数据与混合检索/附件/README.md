# 实验05附件导航

本课程使用一个共享运行包，避免每次复制后丢失数据血缘。请返回项目根目录使用 `coursekit/intelligence.py`；不要在本附件目录新建第二份data。

- [运行源码](../../coursekit/intelligence.py)：seed_corpus、latest_documents、chunk_documents、build_index、search。
- [课程安装与入口](../../README.md)：Windows环境、基础与模型依赖。
- [完整实验手册](../实验手册.md)：逐阶段操作及预期结果。
- [报告与评分](../实验报告提交及评分标准.md)：必交证据和评分标准。

标准入口：`.\.venv\Scripts\python.exe -m coursekit lab05 --mode lexical`；语义对照把最后一个参数改为 `--mode semantic`。

本实验同时读取 `data/raw/documents.jsonl` 中的规则文档和实验 04 生成的 `data/gold/realtime_service.json`，两者的哈希共同进入索引身份，因此附件目录不含单独的数据副本。请在 `coursekit/intelligence.py` 的 `search()` 候选过滤处完成未知可见性 fail-closed 改动，并用正常 public/internal 正例和未知标签负例验证。第二种关键词方法、RRF 和切分参数变式可用于进阶比较；独立操作分以本人代码改动、预测和正负例证据为准。

本章编号为 **05**。附件及自写脚本用于评分时，按 [学号与提交验收](../../docs/学号与提交验收.md) 使用 `capture --lab 05` 保存真实输出、错误和退出状态，以及配套 JSON/HTML。截图须原生显示学号、实验号 05、run_id 和真实结果；机器身份核对与授课老师逐张截图复核都通过后才可验收。无学号、UNREGISTERED 或不一致须退回补证。
