# ARC 任务评测框架

本项目实现了一套针对 ARC (Abstraction and Reasoning Corpus) 数据集的自动化评测流程，集成了策略定义、模型测试、结果可视化及错误分析功能。

## 📁 文件说明

### 核心代码
*   **`template.py`**
    核心实现文件。定义了不同的求解策略（Strategy），负责构建提示词（Prompt construction）以及解析模型输出（Output parsing）。
*   **`test_prompt.py`**
    测试主程序。负责加载数据集、批量运行测试、调用 LLM 接口，并统计最终的准确率。

### 辅助工具
*   **`visualize.py`**
    可视化模块。用于将输入输出网格转换为图像，便于直观分析模型表现。
*   **`analyze_errors.py`**
    错误分析模块。提供对预测结果的细粒度分析（如检测维度错误、数值错误等）。

## 🚀 运行指南

请在命令行中运行以下指令以启动测试：

```bash
python test_prompt.py --dataset val.jsonl --output_md experiment_results.md --runs_dir runs/easy
```

### 参数详解
*   `--dataset`: 数据集文件路径（例如 `val.jsonl`）。
*   `--output_md`: 汇总结果的 Markdown 文件输出路径，将生成在当前目录下。
*   `--runs_dir`: 详细运行日志的存储目录。详细的实验记录将保存在该目录（如 `./runs/easy`）下（需保证文件夹存在）