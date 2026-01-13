import os
import re
import ast

def analyze_grid_error(pred, gt):
    if not isinstance(pred, list) or not pred:
        return "Fmt", "Invalid Format"
    if not isinstance(gt, list) or not gt:
        return "Data", "Invalid GT"
    if not all(isinstance(row, list) for row in pred):
        return "Fmt", "Not 2D Grid"

    h_pred, h_gt = len(pred), len(gt)
    w_pred = len(pred[0]) if h_pred > 0 else 0
    w_gt = len(gt[0]) if h_gt > 0 else 0

    if h_pred != h_gt or w_pred != w_gt:
        return "Dim", f"Shape mismatch ({h_pred}x{w_pred} vs {h_gt}x{w_gt})"

    total = h_pred * w_pred
    if total == 0: return "Empty", "Empty Grid"

    errors = 0
    pred_vals = set()
    gt_vals = set()

    try:
        for r in range(h_pred):
            if len(pred[r]) != w_pred: return "Fmt", "Ragged Array"
            for c in range(w_pred):
                p, g = pred[r][c], gt[r][c]
                pred_vals.add(p)
                gt_vals.add(g)
                if p != g:
                    errors += 1
    except Exception:
        return "Err", "Comparison Error"

    if errors == 0: return "OK", "Correct"
    
    err_rate = errors / total
    if err_rate == 1.0: return "Fail", "100% Wrong"
    if errors <= 2: return "Near", f"{errors} pixels wrong"
    if pred_vals != gt_vals: return "Col", f"Colors differ {pred_vals} vs {gt_vals}"
    
    return "Pat", f"{errors} pixels wrong ({err_rate:.0%})"

def process_detail_file(file_path):
    if not os.path.exists(file_path):
        return "File Not Found"
        
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Clean old report
    if "## Error Analysis Report" in content:
        content = content.split("## Error Analysis Report")[0].strip() + "\n"

    task_pattern = re.compile(r"## Task (\d+)(.*?)((?=## Task)|$)", re.DOTALL)
    summary_parts = []
    report_lines = ["\n\n---\n\n## Error Analysis Report\n"]
    
    has_errors = False
    
    for match in task_pattern.finditer(content):
        tid = match.group(1)
        tcontent = match.group(2)
        
        code = "Unk"
        desc = ""
        
        if "**Status**: ✅ Correct" in tcontent:
            continue 
        
        has_errors = True
        
        if "**Status**: ❌ Incorrect" in tcontent:
            pm = re.search(r"- \*\*Pred\*\*: `(.*?)`", tcontent)
            gm = re.search(r"- \*\*GT\*\*:   `(.*?)`", tcontent)
            if pm and gm:
                try:
                    pred = ast.literal_eval(pm.group(1))
                    gt = ast.literal_eval(gm.group(1))
                    code, desc = analyze_grid_error(pred, gt)
                except:
                    code, desc = "Parse", "Parse Error"
            else:
                code, desc = "Log", "Log Missing Data"
        elif "**Error**" in tcontent:
            code, desc = "Err", "Runtime Error"
            
        # Add to summary
        pct = ""
        pct_match = re.search(r"\((\d+%)\)", desc)
        if pct_match:
            pct = f"({pct_match.group(1)})"
            
        summary_parts.append(f"T{tid}:{code}{pct}")
        
        report_lines.append(f"### Task {tid}")
        report_lines.append(f"- **Type**: {code}")
        report_lines.append(f"- **Details**: {desc}\n")

    if not has_errors:
        report_lines.append("All tasks correct.")
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content + "\n".join(report_lines))
        
    return "; ".join(summary_parts) if summary_parts else "All Correct"

def main():
    root = os.path.dirname(__file__)
    md_path = os.path.join(root, "experiment_results.md")
    
    if not os.path.exists(md_path):
        print("experiment_results.md not found")
        return

    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    new_lines = []
    table_needs_col = False
    
    for line in lines:
        stripped = line.strip()
        
        # Header detection
        if stripped.startswith("| Timestamp"):
            if "Error Summary" not in stripped:
                new_lines.append(stripped + " Error Summary |\n")
                table_needs_col = True
            else:
                new_lines.append(line)
                table_needs_col = False
            continue
            
        # Separator detection
        if stripped.startswith("| :---"):
            if table_needs_col:
                new_lines.append(stripped + " :--- |\n")
            else:
                new_lines.append(line)
            continue
            
        # Row detection
        if stripped.startswith("|") and "runs/" in stripped:
            # Extract link
            match = re.search(r"\[View Log\]\((.*?)\)", line)
            summary = "N/A"
            if match:
                rel = match.group(1)
                abs_p = os.path.join(root, rel)
                print(f"Analyzing {rel}...")
                summary = process_detail_file(abs_p)
            
            parts = [p.strip() for p in stripped.split('|') if p]
            
            if table_needs_col:
                # Append new column
                new_row = "| " + " | ".join(parts) + f" | {summary} |\n"
                new_lines.append(new_row)
            else:
                # Update last column if it exists, or append if missing
                if len(parts) == 5:
                    new_row = "| " + " | ".join(parts) + f" | {summary} |\n"
                elif len(parts) >= 6:
                    parts[5] = summary # Update 6th column
                    new_row = "| " + " | ".join(parts[:6]) + " |\n"
                else:
                    new_row = line
                
                new_lines.append(new_row)
        else:
            new_lines.append(line)
            
    with open(md_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("Done.")

if __name__ == "__main__":
    main()
