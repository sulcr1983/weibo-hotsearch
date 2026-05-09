#!/usr/bin/env python3
"""代码清理工具 - 执行 /neat 指令流程"""
import os
import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SYSTEM_DIR = PROJECT_ROOT / "system"

def find_py_files():
    """获取所有 Python 文件"""
    files = []
    for p in SYSTEM_DIR.rglob("*.py"):
        if p.is_file() and "__pycache__" not in str(p):
            files.append(p)
    return sorted(files)

def analyze_dead_code(filepath):
    """分析文件中的死代码"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    
    issues = []
    imports = set()
    used_names = set()
    
    # 收集导入的名称
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.add(alias.asname or alias.name)
        # 收集使用的名称
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used_names.add(node.id)
    
    # 找出未使用的导入
    unused_imports = imports - used_names
    for imp in unused_imports:
        issues.append(f"未使用的导入: {imp}")
    
    return issues

def find_todos(filepath):
    """查找 TODO 注释"""
    todos = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            if 'TODO' in line or 'FIXME' in line or 'HACK' in line:
                todos.append((i, line.strip()))
    return todos

def check_naming(filepath):
    """检查命名规范"""
    issues = []
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return issues
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            name = node.name
            if not name.islower() or '_' not in name and len(name) > 3:
                if not name.startswith('_'):
                    issues.append(f"函数名 '{name}' 不符合 snake_case 规范")
        elif isinstance(node, ast.ClassDef):
            name = node.name
            if not name[0].isupper():
                issues.append(f"类名 '{name}' 不符合 PascalCase 规范")
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Store):
                if not node.id.islower() and not node.id.isupper():
                    if not node.id.startswith('_'):
                        issues.append(f"变量名 '{node.id}' 建议使用 snake_case")
    
    return issues

# 执行清理分析
print("=" * 70)
print("1. 死代码清扫 - 分析未使用的导入")
print("=" * 70)

all_dead_code = {}
for pyfile in find_py_files():
    issues = analyze_dead_code(pyfile)
    if issues:
        all_dead_code[pyfile.name] = issues
        print(f"\n{pyfile.relative_to(PROJECT_ROOT)}")
        for issue in issues:
            print(f"  - {issue}")

print("\n" + "=" * 70)
print("2. 技术债务归档 - 收集 TODO/FIXME/HACK")
print("=" * 70)

all_todos = {}
for pyfile in find_py_files():
    todos = find_todos(pyfile)
    if todos:
        all_todos[pyfile.name] = todos
        print(f"\n{pyfile.relative_to(PROJECT_ROOT)}")
        for line_num, text in todos:
            print(f"  L{line_num}: {text}")

# 写入技术债务文件
debt_content = "# 技术债务清单\n\n"
debt_content += "## 待修复问题\n\n"
for filename, todos in all_todos.items():
    debt_content += f"### {filename}\n\n"
    for line_num, text in todos:
        debt_content += f"- L{line_num}: {text}\n"
    debt_content += "\n"

debt_file = SYSTEM_DIR / "tech_debt.md"
with open(debt_file, 'w', encoding='utf-8') as f:
    f.write(debt_content)
print(f"\n技术债务已归档到: {debt_file}")

print("\n" + "=" * 70)
print("3. 命名一致性校验")
print("=" * 70)

naming_issues = {}
for pyfile in find_py_files():
    issues = check_naming(pyfile)
    if issues:
        naming_issues[pyfile.name] = issues
        print(f"\n{pyfile.relative_to(PROJECT_ROOT)}")
        for issue in issues:
            print(f"  - {issue}")

# 生成重构建议
refactor_content = "# 重构建议清单\n\n"
refactor_content += "## 命名规范问题\n\n"
for filename, issues in naming_issues.items():
    refactor_content += f"### {filename}\n\n"
    for issue in issues:
        refactor_content += f"- {issue}\n"
    refactor_content += "\n"

refactor_file = SYSTEM_DIR / "refactor_suggestions.md"
with open(refactor_file, 'w', encoding='utf-8') as f:
    f.write(refactor_content)
print(f"\n重构建议已保存到: {refactor_file}")

print("\n" + "=" * 70)
print("4. 清理完成汇总")
print("=" * 70)
print(f"- 扫描文件数: {len(find_py_files())}")
print(f"- 未使用导入: {sum(len(v) for v in all_dead_code.values())} 处")
print(f"- 技术债务: {sum(len(v) for v in all_todos.values())} 处")
print(f"- 命名问题: {sum(len(v) for v in naming_issues.values())} 处")
print(f"- 技术债务文件: {debt_file}")
print(f"- 重构建议: {refactor_file}")
