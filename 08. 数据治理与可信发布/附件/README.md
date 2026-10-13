# 实验08附件导航

- [治理源码](../../coursekit/governance.py)：八项基线发布检查，包含核对上游运行产物身份的 `identity_evidence`；机器身份检查不代替授课老师逐张复核截图。
- [检索与版本源码](../../coursekit/intelligence.py)：manifest校验、权限过滤和实际索引。
- [服务源码](../../coursekit/service.py)：缓存身份与HTTP证据。
- [完整手册](../实验手册.md) 与 [评分标准](../实验报告提交及评分标准.md)。

在项目根目录执行 `.\.venv\Scripts\python.exe -m coursekit lab08`。先确认实验 01—07 产物齐全；本次报告引用自己运行生成的 `release_checks.json`。

个人核心改动为加入 silver_lineage 第九项检查；审核状态对照为观察项。当前发布门禁验证“模拟服务使用分析与规则查询平台”在本人笔记本上运行的 extractive 服务；选择模型路径的同学另附本人模型结果和失败记录。

本章编号为 **08**。附件及自写脚本用于评分时，按 [学号与提交验收](../../docs/学号与提交验收.md) 使用 `capture --lab 08` 保存真实输出、错误和退出状态，以及配套 JSON/HTML。截图须原生显示学号、实验号 08、run_id 和真实结果；机器身份核对与授课老师逐张截图复核都通过后才可验收。无学号、UNREGISTERED 或不一致须退回补证。
