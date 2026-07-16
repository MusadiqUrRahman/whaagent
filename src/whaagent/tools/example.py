import ast
import operator
from typing import Any

from whaagent.interfaces.base import Tool

# Allowed operators for safe math evaluation
_ALLOWED_OPERATORS: dict[type, Any] = {  # type: ignore[misc]
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
_ALLOWED_FUNCTIONS: dict[str, Any] = {  # type: ignore[misc]
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
}


class CalculatorTool(Tool):
    """
    A calculator tool that provides safe mathematical expression evaluation.

    This tool uses Abstract Syntax Tree (AST) parsing to evaluate mathematical
    expressions safely, preventing code injection by only allowing specific
    operators and functions.

    Features:
        - Supports basic arithmetic operations: +, -, *, /, //, %, **
        - Supports unary operators: +, - (negation)
        - Built-in functions: abs, round, min, max, sum
        - Supports lists and tuples for multi-argument functions
        - Safe evaluation using AST parsing

    Usage Examples:
        "2 + 2 * 3"          # Returns "8"
        "(5 + 3) * 2"        # Returns "16"
        "abs(-5)"           # Returns "5"
        "min([1, 2, 3])"     # Returns "1"
        "max(4, 7, 2)"       # Returns "7"
        "sum([1, 2, 3, 4])"  # Returns "10"

    Error Handling:
        - Invalid syntax raises ValueError with descriptive message
        - Unsupported operators/functions raise ValueError
        - Malformed expressions raise ValueError

    Security:
        - All expressions are parsed through AST before evaluation
        - Only pre-approved operators and functions are allowed
        - No arbitrary code execution possible
    """

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return (
            "Evaluate a mathematical expression. Supports basic operators "
            "(+, -, *, /, //, %, **) and functions (abs, round, min, max, sum)."
        )

    def invoke(self, input_str: str) -> str:
        """Evaluate a mathematical expression safely."""
        try:
            result = self._eval_safe(input_str)
            return str(result)
        except Exception as e:
            return f"Error: {e}"

    def _eval_safe(self, expr: str) -> Any:
        """Safely evaluate a mathematical expression using AST parsing."""
        node = ast.parse(expr, mode="eval")
        return self._eval_node(node.body)

    def _eval_node(self, node: ast.AST) -> Any:
        """Recursively evaluate AST nodes with safe operations only."""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op_type = type(node.op)
            if op_type not in _ALLOWED_OPERATORS:
                raise ValueError(f"Operator {op_type.__name__} is not allowed")
            op_func = _ALLOWED_OPERATORS[op_type]  # type: ignore[index]
            return op_func(left, right)  # type: ignore[operator]
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            op_type = type(node.op)  # type: ignore[assignment]
            if op_type not in _ALLOWED_OPERATORS:
                raise ValueError(f"Operator {op_type.__name__} is not allowed")
            op_func = _ALLOWED_OPERATORS[op_type]  # type: ignore[index]
            return op_func(operand)  # type: ignore[operator]
        elif isinstance(node, ast.Call):
            func_name = getattr(node.func, "id", "")
            if func_name not in _ALLOWED_FUNCTIONS:
                raise ValueError(f"Function {func_name} is not allowed")
            args = [self._eval_node(arg) for arg in node.args]
            func = _ALLOWED_FUNCTIONS[func_name]  # type: ignore[index]
            return func(*args)  # type: ignore[operator]
        elif isinstance(node, ast.List):
            return [self._eval_node(item) for item in node.elts]
        elif isinstance(node, ast.Tuple):
            return tuple(self._eval_node(item) for item in node.elts)
        elif isinstance(node, ast.Num):  # Python < 3.8
            return node.n
        else:
            raise ValueError(f"Unsupported expression: {ast.dump(node)}")


class WeatherTool(Tool):
    """A mock weather tool for testing."""

    @property
    def name(self) -> str:
        return "weather"

    @property
    def description(self) -> str:
        return "Get current weather for a location."

    def invoke(self, input_str: str) -> str:
        return f"The weather in {input_str} is currently sunny."
