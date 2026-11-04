"""Unit tests for the AST parsing engine."""

import sys
from pathlib import Path

sys.path.insert(0, "src")

from codna.ast_parser import parse_file, parse_source, Function, Class, Parameter

ROOT = Path("src/codna")


def test_parse_simple_function():
    source = b"def add(a, b):\n    return a + b\n"
    ast = parse_source(source, "add.py", language="python")
    assert ast is not None
    assert len(ast.functions) == 1
    func = ast.functions[0]
    assert func.name == "add"
    assert len(func.parameters) == 2
    assert func.parameters[0].name == "a"
    assert func.parameters[1].name == "b"
    assert func.start_line == 1


def test_parse_class_with_method():
    source = b"""
class Calculator:
    def multiply(self, x, y):
        return x * y
"""
    ast = parse_source(source, "calc.py", language="python")
    assert ast is not None
    assert len(ast.classes) == 1
    cls = ast.classes[0]
    assert cls.name == "Calculator"
    assert len(cls.methods) == 1
    assert cls.methods[0].name == "multiply"
    assert cls.methods[0].is_method is True
    assert cls.methods[0].class_name == "Calculator"


def test_parse_imports():
    source = b"import os\nfrom sys import path, argv\n"
    ast = parse_source(source, "imp.py", language="python")
    assert ast is not None
    assert len(ast.imports) == 2
    import_stmt = ast.imports[0]
    assert import_stmt.is_from is False
    from_stmt = ast.imports[1]
    assert from_stmt.is_from is True
    assert from_stmt.module == "sys"


def test_parse_file_on_disk():
    ast = parse_file(ROOT / "scanner.py", ROOT, language="python")
    assert ast is not None
    assert ast.language == "python"
    # scanner.py has a class with methods; count all functions incl. methods
    total_funcs = len(ast.functions) + sum(len(c.methods) for c in ast.classes)
    assert total_funcs > 0


def test_empty_source():
    ast = parse_source(b"", "empty.py", language="python")
    assert ast is not None
    assert ast.functions == []
    assert ast.classes == []


def test_parameter_with_type_and_default():
    source = b"def greet(name: str = 'world') -> str:\n    return name\n"
    ast = parse_source(source, "greet.py", language="python")
    assert ast is not None
    func = ast.functions[0]
    assert func.parameters[0].name == "name"
    assert func.parameters[0].type == "str"
    assert func.parameters[0].default == "'world'"
    assert func.return_type == "str"
