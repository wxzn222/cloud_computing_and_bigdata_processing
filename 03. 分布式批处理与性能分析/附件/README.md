# 实验 03 附件

共享运行入口位于 `coursekit/pipeline.py` 的 `lab03()`。从课程根目录运行 `.\.venv\Scripts\python.exe -m coursekit lab03 --workers 2 --partitions 8`。

`student_latency_aggregate.py` 是必做个人改动：复制到 `submissions/lab03`，先将慢请求阈值从 1000 改成 2000，再新增每服务 `errors/error_rate` 的 Dask 与 SQL 实现。保存完整源码 diff、预测与实际输出。它会在本人笔记本上启动两个 Worker 进程，在主入口保护内执行，并使用独立 SQL 检查结果。

`check_error_extension.py --threshold 2000` 逐行读取 Silver，独立验证同学们新增的错误统计。初始练习文件尚未实现新字段，专项核验会提示缺少字段；完成独立编码后应通过。不得修改核验器冒充完成。

输入是供后续实验共用的 Silver Parquet，输出为 `outputs/lab03/student-latency-<阈值>.json`，不会改写输入数据。运行时使用课程 `.venv` 解释器，并保留文件所在的两层目录关系。

性能判断须分清集群启动、主计算与诊断时间；PID、耗时和任务图大小不能照抄示例。更多 Worker 未必更快，结果正确与证据真实是评分依据。

## 身份与运行记录

先登记本人学号。课程入口和本章可执行附件会在真实运行时生成带学号、实验号 **03** 与 `run_id` 的 JSON/HTML；独立命令或预期故障可用 `capture --lab 03` 保存真实输出、错误和退出状态。截图须原生显示本人学号、实验号、`run_id` 与真实结果。缺学号、身份与结果不一致，或没有真实结果的提交不予验收。身份登记只用于标识本人，不能代替实验结果。完整提交方式参照[公共提交与验收规范](../../docs/学号与提交验收.md)。
