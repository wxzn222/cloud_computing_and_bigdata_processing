# 实验06附件导航

在本人笔记本的同一个 BDP 工作区中，继续使用实验 05 的虚构规则索引。

- [共享源码](../../coursekit/intelligence.py)：answer、evaluate与真实Ollama调用。
- [完整手册](../实验手册.md)：四类问题、指标、阈值、模型对照和冻结测试。
- [报告要求](../实验报告提交及评分标准.md)：逐题证据、独立改动与人工评审。
- [安装入口](../../README.md)：模型依赖与本地缓存。

标准命令为 `.\.venv\Scripts\python.exe -m coursekit lab06 --split dev --generator extractive`；模型路径把最后一个参数改为 `--generator ollama`，测试阶段把 `--split dev` 改为 `--split test`。

独立作业位于 `answer()` 的证据选择逻辑。测试标签保持冻结，评价结果由实际逐题输出计算。默认摘录路径不调用 LLM；选择模型路径时保留实际调用或失败证据，并记录 model_id 与 digest。

本章编号为 **06**。附件及自写脚本用于评分时，按 [学号与提交验收](../../docs/学号与提交验收.md) 使用 `capture --lab 06` 保存真实输出、错误和退出状态，以及配套 JSON/HTML。截图须原生显示学号、实验号 06、run_id 和真实结果；机器身份核对与授课老师逐张截图复核都通过后才可验收。无学号、UNREGISTERED 或不一致须退回补证。
