# 实验 02 附件

主流水线位于 `coursekit/pipeline.py` 的 `validate_event()` 和 `lab02()`。从课程根目录运行 `.\.venv\Scripts\python.exe -m coursekit lab02`。

- `inspect_gold.py`：使用参数化 DuckDB 查询，核对 Silver 与 Gold 的请求数和 Token 总量。
- `student_quality_policy.py`：个人附加契约实验。复制到 `submissions/lab02`，将上限从 2000 改成 1200，并比较接受、重复与拒绝计数。它调用共用校验函数，但不改变供后续实验使用的 Silver 数据。

两份脚本依靠文件所在位置向上两层定位课程根目录。请保留手册规定的复制位置，避免随意移到桌面后路径失效。

个人提交包括规则源码、diff、两种阈值结果、三类坏样本预测及实测。实验 03、04 继续读取默认 `data/silver/events.parquet` 与 `data/manifests/silver.json`，不要用个人阈值产物覆盖它们。

## 身份与运行记录

先登记本人学号。课程入口和本章可执行附件会在真实运行时生成带学号、实验号 **02** 与 `run_id` 的 JSON/HTML；独立命令或预期故障可用 `capture --lab 02` 保存真实输出、错误和退出状态。截图须原生显示本人学号、实验号、`run_id` 与真实结果。缺学号、身份与结果不一致，或没有真实结果的提交不予验收。身份登记只用于标识本人，不能代替实验结果。完整提交方式参照[公共提交与验收规范](../../docs/学号与提交验收.md)。
