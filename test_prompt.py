# 这个文件的作用：在 ARC 的 jsonl 验证集上，串起完整的评测流程：
# 1）读取 jsonl 数据
# 2）对每个任务调用 construct_prompt 得到 prompt
# 3）调用大模型
# 4）用 parse_output 解析模型输出
# 5）统计有多少完全匹配 ground truth 并计算 accuracy

import os, json
import requests
import concurrent.futures
import datetime
import re
import traceback
import argparse
from openai import OpenAI

try:
    # 更专业的命令行进度条
    from tqdm import tqdm
except ImportError:
    tqdm = None

import template
from template import construct_prompt, parse_output, STRATEGY_ID
from visualize import save_comparison
from analyze_errors import analyze_grid_error

def extract_python_code(text):
    """从 markdown 中提取 python 代码块"""
    pattern = r"```python(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return matches[-1].strip() # 返回最后一个代码块
    # 尝试找没有 python 标签的
    pattern = r"```(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return matches[-1].strip()
    return text.strip() # Fallback

def generate_execution_report(pred, gt):
    """
    生成详细的执行报告，用于反馈给 LLM。
    return: error_msg (if any), is_correct (bool)
    """
    # 1. Type Check
    if not isinstance(pred, list):
        return f"Type Error: Expected a list of lists, but got {type(pred)}.", False
    
    if not all(isinstance(row, list) for row in pred):
        return "Type Error: Expected a list of lists (2D grid), but some rows are not lists.", False
        
    # 2. Shape Check
    gt_rows, gt_cols = len(gt), len(gt[0]) if gt else 0
    pred_rows = len(pred)
    if pred_rows != gt_rows:
        return f"Shape Mismatch: Expected {gt_rows} rows, but got {pred_rows} rows.", False
        
    pred_cols = len(pred[0]) if pred else 0
    # Check if all rows have same length
    if any(len(row) != pred_cols for row in pred):
         return "Shape Error: Inconsistent row lengths in predicted grid.", False
         
    if pred_cols != gt_cols:
        return f"Shape Mismatch: Expected {gt_cols} columns, but got {pred_cols} columns.", False

    # 3. Content Check
    mismatches = []
    total_pixels = gt_rows * gt_cols
    error_count = 0
    
    for r in range(gt_rows):
        for c in range(gt_cols):
            if pred[r][c] != gt[r][c]:
                error_count += 1
                if len(mismatches) < 5: # Limit detailed errors
                    mismatches.append(f"({r},{c}): Expected {gt[r][c]}, Got {pred[r][c]}")
                    
    if error_count == 0:
        return "Correct", True
        
    error_msg = f"Pixel Mismatch: {error_count}/{total_pixels} pixels are incorrect.\n"
    error_msg += "First few mismatches:\n" + "\n".join(mismatches)
    return error_msg, False

def run_python_code(code, input_grid):
    """
    执行生成的 Python 代码 transform(grid)。
    返回: (success, result/error_msg)
    """
    try:
        # 定义局部命名空间
        local_scope = {}
        # 执行代码定义 transform 函数
        exec(code, {}, local_scope)
        
        if 'transform' not in local_scope:
            return False, "Function `transform` not defined in code."
            
        transform_func = local_scope['transform']
        
        # 运行函数
        # 深拷贝 input_grid 防止原数据被修改
        input_copy = json.loads(json.dumps(input_grid)) 
        result = transform_func(input_copy)
        
        return True, result
    except Exception:
        # 捕获执行过程中的报错
        error_msg = traceback.format_exc()
        # 限制报错信息长度，防止 Context 溢出
        if len(error_msg) > 20:
             error_msg = error_msg[:10] + "\n...[Error Traceback Truncated]...\n" + error_msg[-10:]
        return False, error_msg

def get_or_create_run_dir(strategy_id, runs_root=None):
    """
    获取或创建运行目录。
    如果最近一次运行是同策略且未完成，则复用该目录（断点续传）。
    否则创建新目录。
    """
    if runs_root is None:
        runs_root = os.path.join(os.path.dirname(__file__), "runs")
    os.makedirs(runs_root, exist_ok=True)
    
    # 查找最近的运行目录
    subdirs = sorted([d for d in os.listdir(runs_root) if os.path.isdir(os.path.join(runs_root, d))], reverse=True)
    
    # 优先寻找符合新命名格式且匹配当前策略的目录
    candidate_dir = None
    for d in subdirs:
        if d.startswith(f"{strategy_id}-"):
            candidate_dir = d
            break
    
    # 如果没找到新格式的，回退到检查列表第一个（兼容旧格式）
    if not candidate_dir and subdirs:
        candidate_dir = subdirs[0]

    if candidate_dir:
        latest_dir = os.path.join(runs_root, candidate_dir)
        info_path = os.path.join(latest_dir, "run_info.json")
        if os.path.exists(info_path):
            try:
                with open(info_path, "r", encoding="utf-8") as f:
                    info = json.load(f)
                # 如果是同一个策略，且状态不是 completed，则恢复
                if info.get("strategy_id") == strategy_id and info.get("status") != "completed":
                    print(f"检测到未完成的任务 (Run {candidate_dir})，将尝试断点续传...")
                    return latest_dir, True
            except Exception as e:
                print(f"读取运行信息失败: {e}")

    # 创建新目录
    timestamp = datetime.datetime.now().strftime("%d-%H-%M")
    dirname = f"strategy_{strategy_id}-{timestamp}"
    new_dir = os.path.join(runs_root, dirname)
    os.makedirs(new_dir, exist_ok=True)
    
    # 初始化运行信息
    with open(os.path.join(new_dir, "run_info.json"), "w", encoding="utf-8") as f:
        json.dump({"strategy_id": strategy_id, "status": "running", "timestamp": timestamp}, f)
        
    return new_dir, False

def mark_run_completed(run_dir):
    """标记运行为已完成"""
    info_path = os.path.join(run_dir, "run_info.json")
    if os.path.exists(info_path):
        try:
            with open(info_path, "r+", encoding="utf-8") as f:
                info = json.load(f)
                info["status"] = "completed"
                f.seek(0)
                json.dump(info, f)
                f.truncate()
        except:
            pass

def save_detailed_log(run_dir, results, accuracy, total_tasks, valid_count, duration, strategy_id):
    """
    保存详细的运行日志到 run_dir/detail.md
    """
    detail_file = os.path.join(run_dir, "detail.md")
    timestamp = os.path.basename(run_dir) # 使用文件夹名作为时间戳

    # 策略描述映射
    strategy_info = {
        1: "Baseline: Direct Prediction",
        2: "Strategy A: Standard CoT",
        3: "Strategy B: Sparse Rep",
        4: "Strategy C: Python Programmer",
        5: "Strategy D: Hypothesis & Verification"
    }
    method_name = strategy_info.get(strategy_id, f"Unknown Strategy {strategy_id}")

    # Create images directory
    images_dir = os.path.join(run_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    with open(detail_file, "w", encoding="utf-8") as f:
        f.write(f"# Run Detail - {timestamp}\n\n")
        f.write(f"- **Strategy**: {strategy_id} ({method_name})\n")
        f.write(f"- **Accuracy**: {accuracy:.4f}\n")
        f.write(f"- **Valid Responses**: {valid_count}/{total_tasks}\n")
        f.write(f"- **Duration**: {duration:.2f}s\n\n")
        f.write("---\n\n")
        
        for idx, pred, gt, error, messages, reply, attempts in results:
            f.write(f"## Task {idx}\n")
            
            if not attempts:
                 # 兼容旧版本或无 attempt 记录的情况
                 # Generate visualization
                img_filename = f"task_{idx}.png"
                img_path = os.path.join(images_dir, img_filename)
                try:
                    save_comparison(pred, gt, img_path)
                    # Use relative path for markdown
                    f.write(f"### Visualization (Final)\n")
                    f.write(f"![Task {idx} Comparison](images/{img_filename})\n\n")
                except Exception as e:
                    f.write(f"**Visualization Error**: {e}\n\n")

                if error:
                    f.write(f"**Error**: {error}\n\n")
                    continue
                
                status = "✅ Correct" if pred == gt else "❌ Incorrect"
                f.write(f"**Status**: {status}\n\n")
                
                if pred != gt:
                    code, desc = analyze_grid_error(pred, gt)
                    f.write(f"**Analysis**: {code} - {desc}\n\n")

                f.write("### Prompt\n")
                if messages:
                    for m in messages:
                        role = m.get('role', 'unknown')
                        content = m.get('content', '')
                        f.write(f"**{role}**:\n\n```text\n{content}\n```\n\n")
                else:
                    f.write("(No messages recorded)\n\n")
                
                f.write("### Response\n")
                f.write(f"```text\n{reply}\n```\n\n")
                
                f.write("### Prediction vs GT\n")
                f.write(f"- **Pred**: `{pred}`\n")
                f.write(f"- **GT**:   `{gt}`\n\n")
                f.write("---\n")
            else:
                # 使用 attempts 信息生成更详细的报告
                f.write(f"### Iteration History ({len(attempts)} attempts)\n\n")
                
                for atmpt in attempts:
                    i = atmpt.get("attempt", 0)
                    a_last_user = atmpt.get("agent_last_user", "")
                    a_reply = atmpt.get("agent_reply", "")
                    a_code = atmpt.get("code", "")
                    a_pred = atmpt.get("test_pred")
                    a_err = atmpt.get("error")
                    a_train_checks = atmpt.get("train_checks")
                    a_critic_prompt = atmpt.get("critic_prompt")
                    a_critic_reply = atmpt.get("critic_reply")
                    a_feedback = atmpt.get("feedback_to_agent")
                    
                    f.write(f"#### Attempt {i}\n\n")

                    # 0. Show what was sent to the normal model + its raw reply
                    if a_last_user:
                        f.write(
                            "<details><summary>Normal Model Input (last user message)</summary>\n\n"
                            f"```text\n{a_last_user}\n```\n\n"
                            "</details>\n\n"
                        )
                    if a_reply:
                        f.write(
                            "<details><summary>Normal Model Output (raw)</summary>\n\n"
                            f"```text\n{a_reply}\n```\n\n"
                            "</details>\n\n"
                        )
                    
                    # 1. Show Code (Collapsed)
                    f.write(f"<details><summary>Generated Code</summary>\n\n```python\n{a_code}\n```\n\n</details>\n\n")

                    # 1.5 Show Train Evaluations (the model's full answers on train inputs)
                    if a_train_checks:
                        f.write("<details><summary>Train Evaluations (per example)</summary>\n\n")
                        for tr in a_train_checks:
                            tr_idx = tr.get("index")
                            tr_inp = tr.get("input")
                            tr_exp = tr.get("expected")
                            tr_success = tr.get("success")
                            tr_actual = tr.get("actual")
                            tr_runtime_error = tr.get("runtime_error")
                            tr_report = tr.get("report")
                            tr_is_correct = tr.get("is_correct")

                            status = "✅" if tr_is_correct else "❌"
                            f.write(f"**Train {tr_idx}**: {status}\n\n")
                            f.write(f"Input:\n```text\n{tr_inp}\n```\n\n")
                            f.write(f"Expected:\n```text\n{tr_exp}\n```\n\n")

                            if tr_success and isinstance(tr_actual, list):
                                f.write(f"Actual:\n```text\n{tr_actual}\n```\n\n")

                                # Optional visualization for train example
                                img_train_filename = f"task_{idx}_attempt_{i}_train_{tr_idx}.png"
                                img_train_path = os.path.join(images_dir, img_train_filename)
                                try:
                                    save_comparison(tr_actual, tr_exp, img_train_path)
                                    f.write(f"![Attempt {i} Train {tr_idx} Visualization](images/{img_train_filename})\n\n")
                                except Exception as e:
                                    f.write(f"**Train Visualization Error**: {e}\n\n")
                            elif tr_runtime_error:
                                f.write(f"Runtime Error:\n```text\n{tr_runtime_error}\n```\n\n")

                            if tr_report:
                                f.write(f"Report:\n```text\n{tr_report}\n```\n\n")

                            f.write("---\n")

                        f.write("</details>\n\n")
                    
                    # 2. Show Visualization
                    if a_pred:
                        img_filename = f"task_{idx}_attempt_{i}.png"
                        img_path = os.path.join(images_dir, img_filename)
                        try:
                            save_comparison(a_pred, gt, img_path)
                            f.write(f"![Attempt {i} Visualization](images/{img_filename})\n\n")
                        except Exception as e:
                            f.write(f"**Visualization Error**: {e}\n\n")
                    else:
                        f.write("**No visualization available (Execution Failed or No Output)**\n\n")

                    # 3. Show Error/Status
                    if a_err:
                        f.write(f"**Execution Report**:\n```text\n{a_err}\n```\n\n")
                    else:
                        is_corr = (a_pred == gt)
                        status_icon = "✅" if is_corr else "❌"
                        f.write(f"**Status**: {status_icon} (Train Validation Passed)\n\n")

                    # 4. Show Critic Advice
                    if a_critic_prompt:
                        f.write(
                            "<details><summary>Critic Prompt</summary>\n\n"
                            f"```text\n{a_critic_prompt}\n```\n\n"
                            "</details>\n\n"
                        )
                    if a_critic_reply:
                        f.write(
                            "<details><summary>Critic Reply</summary>\n\n"
                            f"```text\n{a_critic_reply}\n```\n\n"
                            "</details>\n\n"
                        )

                    if a_feedback:
                        f.write(
                            "<details><summary>Feedback Sent Back To Normal Model</summary>\n\n"
                            f"```text\n{a_feedback}\n```\n\n"
                            "</details>\n\n"
                        )
                        
                    f.write("---\n")

                # 最终状态
                status = "✅ Correct" if pred == gt else "❌ Incorrect"
                f.write(f"### Final Status: {status}\n")
                f.write("---\n")

    return detail_file

def update_main_log(accuracy, total_tasks, valid_count, detail_path, duration, task_range, error_summary, strategy_id, md_file_path=None):
    """
    更新主日志文件 experiment_results.md，按策略分块记录
    """
    if md_file_path:
        md_file = md_file_path
    else:
        md_file = os.path.join(os.path.dirname(__file__), "experiment_results.md")

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not os.path.exists(md_file):
        with open(md_file, "w", encoding="utf-8") as f:
            f.write("# Experiment Results\n\n")

    # 策略描述映射
    strategy_info = {
        1: ("Baseline: Direct Prediction", "Direct Input->Output pairs. No system prompt."),
        2: ("Strategy A: Standard CoT", "Baseline + 'Let's think step by step' suffix."),
        3: ("Strategy B: Sparse Rep", "Coordinate format (r,c):v + CoT."),
        4: ("Strategy C: Python Programmer", "Role: Python Expert. Write transform() function."),
        5: ("Strategy D: Hypothesis & Verification", "Propose 3 rules -> Verify on train -> Apply to test.")
    }

    method_name, prompt_desc = strategy_info.get(strategy_id, (f"Unknown Strategy {strategy_id}", "Custom Strategy"))

    # 构造相对路径用于链接
    if detail_path:
        rel_path = os.path.relpath(detail_path, os.path.dirname(md_file)).replace("\\", "/")
    else:
        rel_path = "#" # Fallback if no log file

    header_section = f"## Strategy {strategy_id}: {method_name}\n**Prompt Framework**: {prompt_desc}\n\n"
    table_header = "| Timestamp | Task Range | Accuracy | Valid/Total | Duration | Detail Link | Error Summary |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    new_row = f"| {timestamp} | {task_range} | {accuracy:.4f} | {valid_count}/{total_tasks} | {duration:.2f}s | [View Log]({rel_path}) | {error_summary} |\n"

    content = ""
    if os.path.exists(md_file):
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()

    section_marker = f"## Strategy {strategy_id}:"

    if section_marker in content:
        # 策略章节已存在，找到表格末尾插入新行
        lines = content.splitlines()
        new_lines = []
        in_target_section = False
        inserted = False

        for i, line in enumerate(lines):
            if line.startswith(section_marker):
                in_target_section = True
                new_lines.append(line)
                continue

            if in_target_section:
                # 如果遇到下一个标题，说明当前章节结束
                if line.startswith("#"):
                    if not inserted:
                        # 如果还没插入，就在这里插入（可能是表格刚结束）
                        # 往回找非空行，确保紧跟表格
                        if new_lines and new_lines[-1].strip() == "":
                            new_lines.pop()
                        new_lines.append(new_row.strip())
                        new_lines.append("") # 保持空行
                        inserted = True
                    in_target_section = False
                elif line.strip() == "" and i + 1 < len(lines) and lines[i+1].startswith("|"):
                    # 表格中间的空行？不应该有，忽略
                    pass

            new_lines.append(line)

        # 如果循环结束还没插入（例如是文件最后一个章节）
        if in_target_section and not inserted:
             if new_lines and new_lines[-1].strip() == "":
                 new_lines.pop()
             new_lines.append(new_row.strip())

        final_content = "\n".join(new_lines)
        if not inserted and not in_target_section: 
             # 这种情况理论上不应该发生，除非 section_marker 匹配到了但逻辑没覆盖
             # Fallback: append
             final_content += "\n" + new_row

    else:
        # 策略章节不存在，追加到文件末尾
        if content and not content.endswith("\n"):
            content += "\n"
        final_content = content + "\n" + header_section + table_header + new_row

    with open(md_file, "w", encoding="utf-8") as f:
        f.write(final_content)
    
    print(f"实验结果已更新到 {md_file}")

def load_jsonl(path):
    """
    功能：
        从给定的 jsonl 文件中读取所有样本，并返回一个列表，每个元素是一个任务字典。
        每一行对应一个 ARC 任务（例如包含 "train" / "test" 等字段）。

    输入参数：
        path: 字符串形式的文件路径，例如 "val.jsonl"。

    返回值：
        data: 列表（list），其中每个元素是一个字典（dict），表示一个 ARC 任务。
              例如 data[i] = d_i，其中 d_i 可以直接传给 construct_prompt(d_i) 使用。
    """
    data = []
    # 逐行读取 jsonl，每一行是一个完整的任务字典
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data.append(json.loads(line))
    return data


def check_accuracy(predictions, ground_truths):
    """
    功能：
        计算模型预测结果与 ground truth 之间的“完全匹配”准确率。
        完全匹配指：预测网格与真实网格在尺寸和每个元素上都完全相同。

    输入参数：
        predictions: 列表（list）
                     每个元素是模型预测的输出网格（通常是一个二维列表，如 [[0,1],[1,0],...]）。
        ground_truths: 列表（list）
                       每个元素是对应样本的真实输出网格（二维列表）。

    返回值：
        accuracy: 浮点数（float），表示完全匹配的比例
    """
    if len(predictions) != len(ground_truths):
        raise ValueError(f"预测数量({len(predictions)})与标签数量({len(ground_truths)})不一致")

    total = len(ground_truths)
    if total == 0:
        return 0.0

    correct = 0
    for pred, gt in zip(predictions, ground_truths):
        # Python 列表的 == 比较会递归比较元素和嵌套结构
        if pred == gt:
            correct += 1

    return correct / total


def speak_and_listen(messages, model_name, temperature=1.0, max_tokens = 8192, session=None):
    """
    修改后的函数：调用 DeepSeek API
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    
    # Windows 注册表回退机制：如果环境变量未加载，尝试直接读取注册表
    if not api_key and os.name == 'nt':
        try:
            import winreg
            # 优先尝试 Machine (系统) 变量
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment") as key:
                api_key, _ = winreg.QueryValueEx(key, "DEEPSEEK_API_KEY")
        except Exception:
            pass
            
        if not api_key:
            try:
                # 尝试 User (用户) 变量
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
                    api_key, _ = winreg.QueryValueEx(key, "DEEPSEEK_API_KEY")
            except Exception:
                pass

    if not api_key:
        raise RuntimeError(
            "环境变量 DEEPSEEK_API_KEY 未设置，无法调用 DeepSeek API"
        )

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False
        )
        return response.choices[0].message.content

    except Exception as e:
        raise RuntimeError(f"调用 DeepSeek API 发生异常: {e}")

def get_critic_feedback(code, error_log, model_name, session=None):
    """
    让 LLM 充当老师，着重分析差异或解释报错。
    """
    prompt = ""
    if "Runtime Error" in error_log:
        # 如果是运行时错误，重点分析代码逻辑哪里错了
        prompt = f"""
        You are an ARC Python Debugger.
        The following Python code crashed during execution.
        
        Code:
        ```python
        {code}
        ```
        
        Error Traceback:
        {error_log}
        
        Task:
        Explain WHY the code crashed and suggest a fix in one short paragraph.
        """
    else:
        # 如果是结果错误，重点在于对比期望和实际输出
        # error_log 此时包含 "Failed Verification: ... (r,c): Expected X, Got Y ..."
        prompt = f"""
        You are a Senior Algorithms Reviewer for the ARC (Abstraction and Reasoning Corpus) challenge.
        Your goal is not just to point out pixel errors, but to diagnose **Structural Flaws** in the generated logic.

        ## Analysis Protocol
        Before reporting errors, you must perform these checks:

        1. **Dimension Analysis (Crucial)**:
        - Calculate the Input Dimension (H_in, W_in) and Output Dimension (H_out, W_out).
        - Determine the scaling factor. 
            - Example: If Input is 6x3 and Output is 9x3, the height factor is 1.5x.
            - **Rule**: A 1.5x, 2x, or 3x scale usually implies **Interleaving, Tiling, or Upscaling**. It almost NEVER means "Input + Append some rows".

        2. **Pattern Consistency**:
        - If the code simply does `result = input.copy()` and then appends lines to the end, but the task implies a global transformation (like zooming in), reject the code immediately as "Lazy Patching".

        ## Feedback Format
        If the code fails:
        1. State the Dimension Change clearly.
        2. Criticize the **Approach**, not just the pixels.
        - Bad: "Pixel (7,0) is wrong."
        - Good: "The code creates 9 rows by appending 3 rows to the end. But the transformation requires inserting a new row after every 2 input rows (Interleaving). The structure is wrong."

        ## Geometric Hints for ARC Tasks:
        1. **Scaling**: If the output size is a multiple of the input (e.g., 2x, 3x), consider representing each pixel as a 2x2 or 3x3 block.
        2. **Interpolation**: If the output height is 1.5x the input (e.g., 6 -> 9), you are likely **interleaving** rows (e.g., row A, row B -> row A, row B, row A+B combined).
        3. **Avoid Hardcoding**: Do not solve the problem by hardcoding indices (e.g., `if i==0...`) or simply appending rows to the bottom. Look for a rule that applies to the *whole* grid.
        
        Execution Report:
        {error_log}
        
        Code:
        ```python
        {code}
        ```
        
        Task:
        1. Read the mismatch report carefully.
        2. Identify the pattern of the error (e.g., "Wrong color used", "Object shifted by 1 pixel", "Dimensions flipped").
        3. Explain what logic in the code likely caused this specific pattern of error.
        Keep it concise.
        """
    
    messages = [
        {"role": "user", "content": prompt}
    ]
    
    try:
        analysis = speak_and_listen(messages, model_name=model_name, temperature=1.0, max_tokens=1000, session=session)
        return {"prompt": prompt, "reply": analysis}
    except Exception as e:
        return {"prompt": prompt, "reply": f"CRITIC_FAIL: {str(e)}\nOriginal Error: {error_log}"}

def process_single_task(task_data, idx, model_name, session):
    """
    处理单个任务的函数，用于并行执行
    """
    # 预先提取 gt_grid，以便在出错时也能返回
    gt_grid = None
    if task_data and len(task_data) > 1:
        gt_grid = task_data[1]

    # 存储每轮尝试的信息
    attempts_info = []

    try:
        # 解包预处理好的数据
        task_for_prompt, _ = task_data

        # 2）构造 prompt
        messages = construct_prompt(task_for_prompt)

        # 3）如果是 Strategy 6 (Iterative Refinement)，进入专门的循环逻辑
        if STRATEGY_ID == 6:
            max_retries = 5
            reply_text = ""
            final_pred_grid = []
            
            # 本地保存消息历史以供记录
            messages_history = list(messages)
            
            for attempt in range(max_retries + 1):
                # 记录本轮调用前，普通模型看到的最后一条 user 消息（便于复盘）
                last_user_before_call = ""
                for m in reversed(messages_history):
                    if m.get("role") == "user":
                        last_user_before_call = m.get("content", "")
                        break

                # 调用模型
                reply_text = speak_and_listen(messages_history, model_name=model_name, temperature=1.0, max_tokens=8192, session=session)
                
                # 记录助手回复
                messages_history.append({"role": "assistant", "content": reply_text})
                
                # 提取代码
                code = extract_python_code(reply_text)
                
                # 在训练集上验证
                train_examples = task_for_prompt['train']
                all_passed = True
                error_report = ""
                train_checks = []
                
                for i, example in enumerate(train_examples):
                    inp = example['input']
                    expected_out = example['output']
                    
                    success, result_or_error = run_python_code(code, inp)
                    
                    if not success:
                        all_passed = False
                        error_report += f"Train Example {i+1} Runtime Error:\n{result_or_error}\n"
                        train_checks.append({
                            "index": i + 1,
                            "input": inp,
                            "expected": expected_out,
                            "success": False,
                            "actual": None,
                            "runtime_error": result_or_error,
                            "report": "Runtime Error",
                            "is_correct": False,
                        })
                        break 
                    
                    # 使用新的详细检查函数
                    report, is_correct = generate_execution_report(result_or_error, expected_out)
                    train_checks.append({
                        "index": i + 1,
                        "input": inp,
                        "expected": expected_out,
                        "success": True,
                        "actual": result_or_error,
                        "runtime_error": None,
                        "report": report,
                        "is_correct": is_correct,
                    })
                    
                    if not is_correct:
                        all_passed = False
                        error_report += f"Train Example {i+1} Failed Verification:\n{report}\n"
                        break
                
                # 【新增逻辑】无论训练集是否通过，都尝试运行测试集以供可视化
                current_attempt_test_pred = None
                try:
                    test_inp_vis = task_for_prompt['test'][0]['input']
                    s_vis, r_vis = run_python_code(code, test_inp_vis)
                    if s_vis and isinstance(r_vis, list):
                        current_attempt_test_pred = r_vis
                except:
                    pass

                critic_prompt_log = None
                critic_reply_log = None
                feedback_to_agent_log = None

                if all_passed:
                    # 验证通过，运行测试集（正式）
                    test_inp = task_for_prompt['test'][0]['input']
                    success_test, result_test = run_python_code(code, test_inp)
                    if success_test:
                        final_pred_grid = result_test

                        # 记录这一轮（也是最后一轮）的信息
                        attempts_info.append({
                            "attempt": attempt,
                            "agent_last_user": last_user_before_call,
                            "agent_reply": reply_text,
                            "code": code,
                            "test_pred": final_pred_grid,
                            "error": None,
                            "train_checks": train_checks,
                            "critic_prompt": None,
                            "critic_reply": None,
                            "feedback_to_agent": None,
                        })
                        
                        # 成功，跳出循环
                        break
                    else:
                        # 测试集运行失败（虽然训练集过了），记录错误并重试
                        error_report += f"Test Input Runtime Error:\n{result_test}\n"
                        all_passed = False

                # 如果没通过，且还有机会，追加反馈
                if not all_passed and attempt < max_retries:
                    print(f"Task {idx} Attempt {attempt+1} Failed. Calling Critic...")
                    
                    # 调用 Critic 获取高层建议
                    critic_result = get_critic_feedback(code, error_report, model_name=model_name, session=session)
                    critic_prompt_log = critic_result.get("prompt")
                    critic_reply_log = critic_result.get("reply")
                    
                    feedback = (
                        "Previous code failed verification.\n\n"
                        "This is the Critic Analysis, please fix the code based on this analysis:\n"
                        f"{critic_reply_log}\n\n"
                    )
                    feedback_to_agent_log = feedback
                    messages_history.append({"role": "user", "content": feedback})
                
                # 记录本轮信息
                attempts_info.append({
                    "attempt": attempt,
                    "agent_last_user": last_user_before_call,
                    "agent_reply": reply_text,
                    "code": code,
                    "test_pred": current_attempt_test_pred,
                    "error": error_report,
                    "train_checks": train_checks,
                    "critic_prompt": critic_prompt_log,
                    "critic_reply": critic_reply_log,
                    "feedback_to_agent": feedback_to_agent_log,
                })
            
            # 循环结束后（无论成功还是耗尽次数），返回结果
            # 如果 final_pred_grid 还是空的，尝试用最后一次生成的代码跑一下测试集（即使训练集没全对）
            if not final_pred_grid and code:
                 test_inp = task_for_prompt['test'][0]['input']
                 s, r = run_python_code(code, test_inp)
                 if s:
                     final_pred_grid = r

            # 返回详细信息：索引，预测，真值，错误，完整对话历史，最后回复，尝试记录
            # 为了兼容性，pred_grid 必须是 list
            if not isinstance(final_pred_grid, list):
                final_pred_grid = []
                
            return idx, final_pred_grid, gt_grid, None, messages_history, reply_text, attempts_info

        else:
            # 原有的非迭代逻辑
            
            # 3）调用大模型
            reply_text = speak_and_listen(messages, model_name=model_name, temperature=1.0, max_tokens=8192, session=session)

            # 4）解析模型输出为网格
            pred_grid = parse_output(reply_text)
            
            # 伪造一个 attempt info
            last_user_before_call = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    last_user_before_call = m.get("content", "")
                    break
            attempts_info.append({
                "attempt": 0,
                "agent_last_user": last_user_before_call,
                "agent_reply": reply_text,
                "code": extract_python_code(reply_text),
                "test_pred": pred_grid,
                "error": None,
                "train_checks": None,
                "critic_prompt": None,
                "critic_reply": None,
                "feedback_to_agent": None,
            })
            
            # 返回详细信息：索引，预测，真值，错误，发送的消息，收到的回复
            return idx, pred_grid, gt_grid, None, messages, reply_text, attempts_info
            
    except Exception as e:
        # 发生错误时，消息和回复可能为空，但尽量返回 gt_grid
        return idx, None, gt_grid, str(e), [], "", []

def run_strategy(strategy_id, preprocessed_tasks, tasks, task_range_str, runs_dir_base=None, output_md_path=None):
    template.STRATEGY_ID = strategy_id
    print(f"\n{'='*40}")
    print(f"Running Strategy {strategy_id}")
    print(f"{'='*40}\n")

    start_time = datetime.datetime.now()
    model_name = "deepseek-chat"
    
    # 获取或创建运行目录
    run_dir, is_resume = get_or_create_run_dir(strategy_id, runs_root=runs_dir_base)
    checkpoint_path = os.path.join(run_dir, "checkpoint.jsonl")
    print(f"当前运行目录: {run_dir}")
    
    # 加载 checkpoint
    processed_indices = set()
    results = []
    if is_resume and os.path.exists(checkpoint_path):
        print(f"正在加载 Checkpoint...")
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    idx = record["idx"]
                    processed_indices.add(idx)
                    # 兼容旧版 checkpoint，如果没有 messages/reply 字段则设为空
                    results.append((
                        idx, 
                        record["pred"], 
                        record["gt"], 
                        record["error"],
                        record.get("messages", []),
                        record.get("reply", ""),
                        record.get("attempts", [])
                    ))
                except:
                    pass
        print(f"已加载 {len(processed_indices)} 个任务。")

    # 并行执行配置
    max_workers = 5  # 根据API限制调整并发数
    
    # 筛选未完成的任务
    tasks_to_run = []
    for idx, task_data in enumerate(preprocessed_tasks, start=1):
        if idx not in processed_indices:
            tasks_to_run.append((idx, task_data))
            
    if not tasks_to_run:
        print("所有任务已完成！")
    else:
        print(f"开始评测，剩余 {len(tasks_to_run)} 个任务，并发数: {max_workers}")
        
        # 创建 Session 对象复用 TCP 连接
        with requests.Session() as session:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务
                future_to_task = {
                    executor.submit(process_single_task, task_data, idx, model_name, session): idx 
                    for idx, task_data in tasks_to_run
                }
                
                # 使用 tqdm 显示进度
                if tqdm:
                    pbar = tqdm(total=len(tasks_to_run), desc=f"Strategy {strategy_id}", unit="task")
                
                # 打开 checkpoint 文件准备追加写入
                with open(checkpoint_path, "a", encoding="utf-8") as f_ckpt:
                    for future in concurrent.futures.as_completed(future_to_task):
                        idx, pred, gt, error, messages, reply, attempts = future.result()
                        
                        # 记录结果
                        record = {
                            "idx": idx,
                            "pred": pred,
                            "gt": gt,
                            "error": error,
                            "messages": messages,
                            "reply": reply,
                            "attempts": attempts
                        }
                        
                        # 写入 checkpoint (主线程写入，无需文件锁)
                        f_ckpt.write(json.dumps(record) + "\n")
                        f_ckpt.flush() # 确保立即写入磁盘
                        
                        if error:
                            if tqdm:
                                tqdm.write(f"Task {idx} failed: {error}")
                            else:
                                print(f"\nTask {idx} failed: {error}")
                            # 使用返回的 gt (如果存在)，否则用空列表
                            safe_gt = gt if gt is not None else []
                            results.append((idx, [], safe_gt, error, messages, reply, attempts))
                        else:
                            results.append((idx, pred, gt, None, messages, reply, attempts))
                            
                        if tqdm:
                            pbar.update(1)
                        
                if tqdm:
                    pbar.close()

    # 标记运行完成
    mark_run_completed(run_dir)

    # 按索引排序，确保顺序一致
    results.sort(key=lambda x: x[0])
    
    predictions = [r[1] for r in results if r[3] is None]
    ground_truths = [r[2] for r in results if r[3] is None]
    
    # 统计有效回复数（没有报错的任务数）
    valid_count = len(predictions)

    # 5）计算准确率
    acc = check_accuracy(predictions, ground_truths)
    print(f"Strategy {strategy_id} - 总任务数: {len(tasks)}, 成功执行: {valid_count}, 完全匹配准确率: {acc:.4f}")
    
    end_time = datetime.datetime.now()
    duration = (end_time - start_time).total_seconds()

    # 生成错误摘要
    error_summary_parts = []
    for idx, pred, gt, error, messages, reply, attempts in results:
        if error:
            error_summary_parts.append(f"T{idx}:Err")
            continue
            
        if pred == gt:
            continue # Correct
            
        # Analyze mismatch
        code, desc = analyze_grid_error(pred, gt)
        
        # Extract percentage if present in desc
        pct = ""
        pct_match = re.search(r"\((\d+%)\)", desc)
        if pct_match:
            pct = f"({pct_match.group(1)})"
            
        error_summary_parts.append(f"T{idx}:{code}{pct}")
    
    error_summary_str = "; ".join(error_summary_parts) if error_summary_parts else "All Correct"

    # 6) 保存详细日志并更新主索引
    detail_path = save_detailed_log(run_dir, results, acc, len(tasks), valid_count, duration, strategy_id)
    update_main_log(acc, len(tasks), valid_count, detail_path, duration, task_range_str, error_summary_str, strategy_id, md_file_path=output_md_path)

def main():
    """
    功能：
        串联整个评测流程，形成完整的 pipeline。
    """
    parser = argparse.ArgumentParser(description="ARC Evaluation Script")
    parser.add_argument("--dataset", type=str, default="val.jsonl", help="Path to the dataset jsonl file")
    parser.add_argument("--output_md", type=str, default=None, help="Path to the summary markdown file")
    parser.add_argument("--runs_dir", type=str, default=None, help="Path to the base directory for run logs")
    args = parser.parse_args()

    # 1. 选择要评测的 jsonl 文件
    jsonl_path = args.dataset
    if not os.path.isabs(jsonl_path):
        jsonl_path = os.path.join(os.path.dirname(__file__), jsonl_path)
    
    if not os.path.exists(jsonl_path):
        raise FileNotFoundError(f"找不到验证集文件: {jsonl_path}")

    tasks = load_jsonl(jsonl_path)
    
    # 配置测试范围 (1-based index)
    # 如果 SPECIFIC_TASK_IDS 不为空，则优先测试这些ID指定的任务（忽略 START/END 范围）
    # SPECIFIC_TASK_IDS = [2,7,10,17,20,21,22,23,24,25,26,27,28,29,30] # 例如: [3, 7, 15]
    SPECIFIC_TASK_IDS = []
    START_TASK_NUM = 1
    END_TASK_NUM = 5
    
    selected_tasks = []
    task_range_str = ""

    if SPECIFIC_TASK_IDS:
        print(f"模式: 指定任务测试 -> {SPECIFIC_TASK_IDS}")
        task_range_str = f"Specific: {SPECIFIC_TASK_IDS}"
        # 注意：jsonl加载出来的 tasks 列表是 0-indexed，但 SPECIFIC_TASK_IDS 是 1-indexed
        for idx in SPECIFIC_TASK_IDS:
            if 1 <= idx <= len(tasks):
                selected_tasks.append(tasks[idx-1])
            else:
                print(f"Warning: Task ID {idx} out of range (Total: {len(tasks)})")
        tasks = selected_tasks
    else:
        # 确保范围有效
        total_available = len(tasks)
        start_idx = max(0, START_TASK_NUM - 1)
        end_idx = min(total_available, END_TASK_NUM)
        
        if start_idx >= total_available:
            print(f"警告: 起始索引 {START_TASK_NUM} 超出总任务数 {total_available}")
            return

        # 切片任务
        tasks = tasks[start_idx:end_idx]
        task_range_str = f"{start_idx+1}-{end_idx}"
    
    print(f"Selected tasks: {task_range_str} (Total: {len(tasks)})")
    
    # 预处理数据：分离题目和答案
    preprocessed_tasks = []
    for task in tasks:
        # 构造一个不包含 test.output 的副本
        task_for_prompt = json.loads(json.dumps(task))
        if "test" in task_for_prompt:
            for sample in task_for_prompt["test"]:
                if "output" in sample:
                    del sample["output"]
        
        # 提取 ground truth
        gt_grid = task["test"][0]["output"]
        preprocessed_tasks.append((task_for_prompt, gt_grid))

    for strategy_id in range(6, 7):
        run_strategy(strategy_id, preprocessed_tasks, tasks, task_range_str, runs_dir_base=args.runs_dir, output_md_path=args.output_md)

if __name__ == "__main__":
    main()
# 上面的函数只是作为示例框架，你可以任意修改和实现其中的逻辑