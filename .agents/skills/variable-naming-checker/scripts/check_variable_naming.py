#!/usr/bin/env python3
import sys
import os
import re
import subprocess
import ast

# Standard PEP 8 patterns for Python
SNAKE_CASE_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
PASCAL_CASE_RE = re.compile(r"^[A-Z][a-zA-Z0-9]*$")
UPPER_SNAKE_CASE_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")

# JS/TS patterns
JS_CAMEL_CASE_RE = re.compile(r"^[a-z_$][a-zA-Z0-9_$]*$")
JS_PASCAL_CASE_RE = re.compile(r"^[A-Z][a-zA-Z0-9_$]*$")
JS_UPPER_SNAKE_CASE_RE = re.compile(r"^[A-Z_$][A-Z0-9_$]*$")

# Python Built-ins to check for shadowing
PYTHON_BUILTINS = {
    "id", "type", "list", "dict", "set", "str", "int", "float", "bool",
    "sum", "max", "min", "any", "all", "open", "file", "dir", "input",
    "object", "len", "hash", "range", "abs", "round", "map", "filter",
    "zip", "next", "iter", "pow", "repr", "chr", "ord", "bin", "hex", "oct"
}

# JS/TS Built-ins to check for shadowing
JS_BUILTINS = {
    "Object", "Array", "Function", "String", "Number", "Boolean", "Symbol",
    "Map", "Set", "WeakMap", "WeakSet", "Promise", "Error", "EvalError",
    "RangeError", "ReferenceError", "SyntaxError", "TypeError", "URIError",
    "window", "document", "console", "process", "global", "require", "module", "exports"
}

# Exemptions for short names (1 character)
SHORT_EXEMPTIONS = {"i", "j", "k", "n", "_", "x", "y", "z", "e", "f", "d"}

# Directories to ignore
EXCLUDED_DIRS = {
    ".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", "artifacts"
}

# Extensions to scan
PYTHON_EXTENSIONS = {".py"}
JS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx"}


class PythonNamingVisitor(ast.NodeVisitor):
    def __init__(self, filename, content):
        self.filename = filename
        self.lines = content.splitlines()
        self.findings = []
        self.scope_stack = []

    def has_bypass(self, lineno):
        if lineno <= 0 or lineno > len(self.lines):
            return False
        line = self.lines[lineno - 1]
        return "# nosec" in line or "# ignore-naming" in line

    def add_finding(self, lineno, error_type, name, suggestion):
        if not self.has_bypass(lineno):
            self.findings.append({
                "file": self.filename,
                "line": lineno,
                "type": error_type,
                "name": name,
                "suggestion": suggestion
            })

    def visit_ClassDef(self, node):
        name = node.name
        if not PASCAL_CASE_RE.match(name):
            self.add_finding(
                node.lineno,
                "Style Mismatch (Class)",
                name,
                f"Class name '{name}' should use PascalCase (e.g., 'MyClass')."
            )
        self.scope_stack.append("class")
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node):
        self.check_function(node)

    def visit_AsyncFunctionDef(self, node):
        self.check_function(node)

    def check_function(self, node):
        name = node.name
        # Ignore special/dunder methods or AST visitor methods
        if not (name.startswith("__") and name.endswith("__")) and not name.startswith("visit_"):
            if not SNAKE_CASE_RE.match(name):
                self.add_finding(
                    node.lineno,
                    "Style Mismatch (Function)",
                    name,
                    f"Function/Method name '{name}' should use snake_case (e.g., 'my_function')."
                )

        # Check function arguments
        all_args = []
        if node.args.args: all_args.extend(node.args.args)
        if node.args.kwonlyargs: all_args.extend(node.args.kwonlyargs)
        if node.args.vararg: all_args.append(node.args.vararg)
        if node.args.kwarg: all_args.append(node.args.kwarg)

        for arg in all_args:
            arg_name = arg.arg
            if arg_name in ("self", "cls"):
                continue
            
            # Style check
            if not SNAKE_CASE_RE.match(arg_name):
                self.add_finding(
                    arg.lineno,
                    "Style Mismatch (Argument)",
                    arg_name,
                    f"Argument name '{arg_name}' should use snake_case (e.g., 'my_arg')."
                )
            # Shadowing check
            if arg_name in PYTHON_BUILTINS:
                self.add_finding(
                    arg.lineno,
                    "Shadowing Built-in (Argument)",
                    arg_name,
                    f"Argument name '{arg_name}' shadows Python built-in function/type."
                )
            # Too short check
            if len(arg_name) == 1 and arg_name not in SHORT_EXEMPTIONS:
                self.add_finding(
                    arg.lineno,
                    "Too Short (Argument)",
                    arg_name,
                    f"Argument name '{arg_name}' is too short/uninformative."
                )

        self.scope_stack.append("function")
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_Name(self, node):
        # We only check assigned names (Store context)
        if isinstance(node.ctx, ast.Store):
            name = node.id
            if name.startswith("__") and name.endswith("__"):
                return

            in_function = "function" in self.scope_stack
            
            # Style Check
            if in_function:
                # Inside function: must be snake_case
                is_valid = bool(SNAKE_CASE_RE.match(name))
                style_desc = "snake_case (e.g., 'my_variable')"
            else:
                # Global/Module level: can be snake_case or UPPER_SNAKE_CASE (constants)
                is_valid = bool(SNAKE_CASE_RE.match(name) or UPPER_SNAKE_CASE_RE.match(name))
                style_desc = "snake_case or UPPER_SNAKE_CASE"

            if not is_valid:
                self.add_finding(
                    node.lineno,
                    "Style Mismatch (Variable)",
                    name,
                    f"Variable name '{name}' should use {style_desc}."
                )

            # Shadowing check
            if name in PYTHON_BUILTINS:
                self.add_finding(
                    node.lineno,
                    "Shadowing Built-in (Variable)",
                    name,
                    f"Variable '{name}' shadows Python built-in function/type."
                )

            # Too short check
            if len(name) == 1 and name not in SHORT_EXEMPTIONS:
                self.add_finding(
                    node.lineno,
                    "Too Short (Variable)",
                    name,
                    f"Variable name '{name}' is too short/uninformative."
                )


def scan_javascript_file(file_path, content) -> list:
    findings = []
    lines = content.splitlines()
    
    var_decl_re = re.compile(r"\b(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\b")
    func_decl_re = re.compile(r"\bfunction\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(")
    class_decl_re = re.compile(r"\bclass\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\b")
    
    for line_num, line in enumerate(lines, 1):
        if any(bypass in line for bypass in ("// nosec", "// ignore-naming", "/* nosec", "/* ignore-naming")):
            continue
            
        # 1. Class declarations
        class_match = class_decl_re.search(line)
        if class_match:
            name = class_match.group(1)
            if not JS_PASCAL_CASE_RE.match(name):
                findings.append({
                    "file": file_path,
                    "line": line_num,
                    "type": "Style Mismatch (Class)",
                    "name": name,
                    "suggestion": f"Class name '{name}' should use PascalCase (e.g., 'MyClassName')."
                })
                
        # 2. Function declarations
        func_match = func_decl_re.search(line)
        if func_match:
            name = func_match.group(1)
            if not (JS_CAMEL_CASE_RE.match(name) or JS_PASCAL_CASE_RE.match(name)):
                findings.append({
                    "file": file_path,
                    "line": line_num,
                    "type": "Style Mismatch (Function)",
                    "name": name,
                    "suggestion": f"Function name '{name}' should use camelCase or PascalCase (for React components)."
                })
            if name in JS_BUILTINS:
                findings.append({
                    "file": file_path,
                    "line": line_num,
                    "type": "Shadowing Built-in (Function)",
                    "name": name,
                    "suggestion": f"Function name '{name}' shadows JS/TS built-in global."
                })
            if len(name) == 1 and name not in SHORT_EXEMPTIONS:
                findings.append({
                    "file": file_path,
                    "line": line_num,
                    "type": "Too Short (Function)",
                    "name": name,
                    "suggestion": f"Function name '{name}' is too short/uninformative."
                })
                
        # 3. Variable declarations
        var_matches = var_decl_re.findall(line)
        for name in var_matches:
            if class_match and name == class_match.group(1):
                continue
            if func_match and name == func_match.group(1):
                continue
                
            # Check style (camelCase or UPPER_SNAKE_CASE)
            if not (JS_CAMEL_CASE_RE.match(name) or JS_UPPER_SNAKE_CASE_RE.match(name)):
                findings.append({
                    "file": file_path,
                    "line": line_num,
                    "type": "Style Mismatch (Variable)",
                    "name": name,
                    "suggestion": f"Variable name '{name}' should use camelCase or UPPER_SNAKE_CASE."
                })
            # Shadowing check
            if name in JS_BUILTINS:
                findings.append({
                    "file": file_path,
                    "line": line_num,
                    "type": "Shadowing Built-in (Variable)",
                    "name": name,
                    "suggestion": f"Variable name '{name}' shadows JS/TS built-in global."
                })
            # Too short check
            if len(name) == 1 and name not in SHORT_EXEMPTIONS:
                findings.append({
                    "file": file_path,
                    "line": line_num,
                    "type": "Too Short (Variable)",
                    "name": name,
                    "suggestion": f"Variable name '{name}' is too short/uninformative."
                })
                
    return findings


def get_git_files() -> list:
    """Gets tracked and untracked files in the repository using git ls-files."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            check=True
        )
        if not result.stdout:
            return []
        files = [f.decode('utf-8', errors='ignore') for f in result.stdout.split(b'\x00') if f]
        return files
    except subprocess.CalledProcessError as e:
        print(f"Error running git ls-files: {e.stderr.decode('utf-8', errors='ignore')}", file=sys.stderr)
        return []


def main():
    print("Initializing variable naming compliance check...")
    files_to_scan = get_git_files()
    if not files_to_scan:
        print("No files found to scan.")
        sys.exit(0)

    all_findings = []
    python_count = 0
    js_count = 0
    
    for file_path in files_to_scan:
        if os.path.isdir(file_path):
            continue
            
        # Check exclusions in path
        path_parts = file_path.replace("\\", "/").split("/")
        if any(part in EXCLUDED_DIRS for part in path_parts):
            continue
            
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        if ext in PYTHON_EXTENSIONS:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                tree = ast.parse(content, filename=file_path)
                visitor = PythonNamingVisitor(file_path, content)
                visitor.visit(tree)
                all_findings.extend(visitor.findings)
                python_count += 1
            except SyntaxError as e:
                print(f"Warning: Syntax error parsing '{file_path}': {e}", file=sys.stderr)
            except Exception as e:
                print(f"Warning: Could not analyze '{file_path}': {e}", file=sys.stderr)
                
        elif ext in JS_EXTENSIONS:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                findings = scan_javascript_file(file_path, content)
                all_findings.extend(findings)
                js_count += 1
            except Exception as e:
                print(f"Warning: Could not analyze '{file_path}': {e}", file=sys.stderr)

    print(f"Analyzed {python_count} Python file(s) and {js_count} JavaScript/TypeScript file(s).")
    
    if all_findings:
        print("\n" + "="*80)
        print(" WARNING: Variable Naming Compliance Report")
        print("="*80)
        
        # Group findings by file
        by_file = {}
        for f in all_findings:
            by_file.setdefault(f["file"], []).append(f)
            
        for file_path, file_findings in sorted(by_file.items()):
            print(f"\n📂 {file_path}")
            for f in sorted(file_findings, key=lambda x: x["line"]):
                print(f"  • Line {f['line']}: [{f['type']}] Name: '{f['name']}'")
                print(f"    Suggestion: {f['suggestion']}")
                print("-"*80)
                
        print(f"\nScan complete. Found {len(all_findings)} variable naming issue(s).")
        print("Please review and fix these names to align with project best practices,")
        print("or add `# ignore-naming` (Python) or `// ignore-naming` (JS) to bypass this line.")
        sys.exit(1)
    else:
        print("\nScan complete. All variables comply with naming best practices. Outstanding job!")
        sys.exit(0)


if __name__ == "__main__":
    main()
