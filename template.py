import json
import re

# ==========================================
# 实验配置 (Experiment Configuration)
# ==========================================
# 修改此变量以选择消融实验策略:
# 1: Baseline: Direct Prediction (直接预测)
# 2: Strategy A: Standard CoT (标准思维链)
# 3: Strategy B: Sparse/Coordinate Representation (稀疏坐标表示)
# 4: Strategy C: The "Python Programmer" (伪代码生成)
# 5: Strategy D: Hypothesis & Verification (假设验证法)
# 6: Strategy E: C + D & run locally
STRATEGY_ID = 6

# ==========================================
# 辅助函数 (Helper Functions)
# ==========================================

def grid_to_str(grid):
    return str(grid)

def grid_to_sparse(grid):
    coords = []
    for r, row in enumerate(grid):
        for c, val in enumerate(row):
            # 假设0是背景色，稀疏表示只记录非0值
            if val != 0:
                coords.append(f"({r},{c}):{val}")
    return ", ".join(coords)

def parse_grid_from_text(text):
    """
    从文本中提取二维数组格式的网格
    """
    candidates = []
    # 查找所有以 [[ 开头的索引
    start_indices = [m.start() for m in re.finditer(r'\[\[', text)]
    
    for start in start_indices:
        balance = 0
        for i in range(start, len(text)):
            if text[i] == '[':
                balance += 1
            elif text[i] == ']':
                balance -= 1
            
            if balance == 0:
                candidate = text[start:i+1]
                candidates.append(candidate)
                break
                
    # 倒序尝试解析，优先取最后的输出
    for candidate in reversed(candidates):
        try:
            # 尝试作为JSON解析
            json_str = candidate.replace("'", '"')
            grid = json.loads(json_str)
            if isinstance(grid, list) and all(isinstance(row, list) for row in grid):
                return grid
        except:
            try:
                # 尝试作为Python列表解析
                grid = eval(candidate)
                if isinstance(grid, list) and all(isinstance(row, list) for row in grid):
                    return grid
            except:
                pass
    return []

def parse_sparse_from_text(text):
    """
    从文本中提取坐标格式的网格 (r,c):v
    """
    matches = re.findall(r'\((\d+),\s*(\d+)\)\s*:\s*(\d+)', text)
    if not matches:
        return []
    
    max_r = 0
    max_c = 0
    cells = {}
    for r_str, c_str, v_str in matches:
        r, c, v = int(r_str), int(c_str), int(v_str)
        cells[(r,c)] = v
        max_r = max(max_r, r)
        max_c = max(max_c, c)
        
    # 创建网格，默认填充0
    grid = [[0 for _ in range(max_c + 1)] for _ in range(max_r + 1)]
    for (r,c), v in cells.items():
        grid[r][c] = v
    return grid

# ==========================================
# 策略实现 (Strategy Implementations)
# ==========================================

def construct_baseline(d):
    messages = []
    user_content = ""
    
    for i, example in enumerate(d['train']):
        user_content += f"Train Example {i+1}:\n"
        user_content += f"Input: {grid_to_str(example['input'])}\n"
        user_content += f"Output: {grid_to_str(example['output'])}\n\n"
        
    test_input = d['test'][0]['input']
    user_content += "Test Input:\n"
    user_content += f"{grid_to_str(test_input)}\n"
    
    user_content += "You are solving ARC problems, give an result according to the given examples. YOU SHOULD TAKE SPECIAL CARE OF THE OUTPUT DIMENSION SIZE."
    
    messages.append({"role": "user", "content": user_content})
    return messages

def construct_cot(d):
    messages = construct_baseline(d)
    content = messages[0]['content']
    if content.endswith("Output:"):
        content = content[:-7].strip()
    content += "\n\nLet's think step by step to solve this.\n"
    content += "Step 1: Identify the dimension change rule (e.g., Input (H,W) -> Output (H,W), or (H,W) -> (3,3), etc.) from the examples.\n"
    content += "Step 2: Calculate the exact target dimension (Rows, Cols) for the Test Input.\n"
    content += "Step 3: Determine the content filling logic.\n"
    content += "Step 4: Generate the Final Output Grid.\n"
    content += "Response:"
    messages[0]['content'] = content
    return messages

def construct_sparse(d):
    messages = []
    user_content = ""
    
    for i, example in enumerate(d['train']):
        user_content += f"Train Example {i+1}:\n"
        user_content += f"Input: {grid_to_sparse(example['input'])}\n"
        user_content += f"Output: {grid_to_sparse(example['output'])}\n\n"
        
    test_input = d['test'][0]['input']
    user_content += "Test Input:\n"
    user_content += f"{grid_to_sparse(test_input)}\n"
    user_content += "1. First specify the target matrix dimensions (Rows, Cols).\n"
    user_content += "2. Then output the result strictly as a standard Python list of lists (Dense Grid), NOT sparse coordinates.\n"
    user_content += "Example format: [[0, 1], [2, 3]]\n"
    user_content += "response:"
    
    messages.append({"role": "user", "content": user_content})
    return messages

def construct_python(d):
    messages = []
    system_content = "You are a Python expert. Write a function `transform(grid)` to solve this ARC task."
    messages.append({"role": "system", "content": system_content})
    
    user_content = ""
    for i, example in enumerate(d['train']):
        user_content += f"Train Example {i+1}:\n"
        user_content += f"Input: {grid_to_str(example['input'])}\n"
        user_content += f"Output: {grid_to_str(example['output'])}\n\n"
        
    test_input = d['test'][0]['input']
    user_content += "Test Input:\n"
    user_content += f"{grid_to_str(test_input)}\n"
    
    user_content += "\nWrite a Python function `transform` that maps input to output.\n"
    user_content += "CRITICAL REQUIREMENTS:\n"
    user_content += "1. Use python to determine the dimension changes between input and output, then apply this python promgram to the final question.\n"
    user_content += "2. After figuring out the potential output size, initialize the result grid with the correct dimensions BEFORE filling it.\n"
    user_content += "3. Return the result as a standard list of lists (no numpy).\n"
    user_content += "4. Finally, apply `transform` to the Test Input and print the result strictly as a list of lists."
    
    messages.append({"role": "user", "content": user_content})
    return messages

def construct_hypothesis(d):
    messages = construct_baseline(d)
    content = messages[0]['content']
    if content.endswith("Output:"):
        content = content[:-7]
        
    content += "\nMethodology:\n"
    content += "1. Propose 3 possible transformation rules.\n"
    content += "2. For each rule, VERIFY if it correctly predicts the Output Dimension for ALL training examples.\n"
    content += "3. Select the best rule.\n"
    content += "4. Apply it to the Test Input and output the final grid.\n"
    messages[0]['content'] = content
    return messages

def construct_iterative_python(d):
    messages = []
    system_content = "You are a Python expert. Your task is to write a Python function `transform(grid)` that solves the given ARC task based on training examples."
    messages.append({"role": "system", "content": system_content})
    
    user_content = ""
    for i, example in enumerate(d['train']):
        user_content += f"Train Example {i+1}:\n"
        user_content += f"Input: {grid_to_str(example['input'])}\n"
        user_content += f"Output: {grid_to_str(example['output'])}\n\n"
        
    test_input = d['test'][0]['input']
    user_content += "Test Input:\n"
    user_content += f"{grid_to_str(test_input)}\n"
    
    user_content += "\nRequirements:\n"
    user_content += "1. Infer the logic from the Train Examples.\n"
    user_content += "2. Write a Python function `transform(grid)` that takes a grid (list of lists) as input and returns the transformed grid.\n"
    user_content += "3. The function must be robust and handle the transformation logic generally.\n"
    user_content += "4. Return ONLY the python code wrapped in ```python ... ``` block. Do not output the result of the test input manually. I will run your code.\n"
    user_content += "5. Do not use external libraries like numpy. Use standard Python lists.\n"
    
    messages.append({"role": "user", "content": user_content})
    return messages

# ==========================================
# 接口函数 (Interface Functions)
# ==========================================

def construct_prompt(d):
    """
    构造用于大语言模型的提示词
    
    参数:
    d (dict): jsonl数据文件的一行，解析成字典后的变量。
              注意：传入的 'd' 已经过处理，其 'test' 字段列表
              只包含 'input'，不包含 'output' 答案。
    
    返回:
    list: OpenAI API的message格式列表，允许设计多轮对话式的prompt
    示例: [{"role": "system", "content": "系统提示内容"}, 
           {"role": "user", "content": "用户提示内容"}]
    """
    if STRATEGY_ID == 1:
        return construct_baseline(d)
    elif STRATEGY_ID == 2:
        return construct_cot(d)
    elif STRATEGY_ID == 3:
        return construct_sparse(d)
    elif STRATEGY_ID == 4:
        return construct_python(d)
    elif STRATEGY_ID == 5:
        return construct_hypothesis(d)
    elif STRATEGY_ID == 6:
        return construct_iterative_python(d)
    else:
        return construct_baseline(d)

def parse_output(text):
    """
    解析大语言模型的输出文本，提取预测的网格
    
    参数:
    text (str): 大语言模型在设计prompt下的输出文本
    
    返回:
    list: 从输出文本解析出的二维数组 (Python列表，元素为整数)
    示例: [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
    
    """
    # 优先尝试解析标准的二维数组格式
    grid = parse_grid_from_text(text)
    if grid:
        return grid
        
    # 如果是稀疏表示策略，或者模型输出了坐标格式，尝试解析坐标
    if STRATEGY_ID == 3 or not grid:
        sparse_grid = parse_sparse_from_text(text)
        if sparse_grid:
            return sparse_grid
            
    return []