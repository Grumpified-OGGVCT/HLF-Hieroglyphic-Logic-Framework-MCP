"""End-to-end math pipeline tests for HLF v3 — verifies bytecode emitter + VM dispatch."""

import math
import pytest
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.runtime import HlfVM


def _run(src: str):
    """Compile and execute HLF source, return scope dict."""
    compiler = HLFCompiler()
    result = compiler.compile(src)
    assert result.get("bytecode"), f"Compilation produced no bytecode: {result.get('errors')}"
    vm = HlfVM(max_gas=5000)
    out = vm.execute(result["bytecode"])
    return out.scope


class TestMathPipeline:
    """End-to-end tests for the HLF math pipeline (set_stmt + MATH_* dispatch)."""

    def test_simple_arithmetic(self):
        scope = _run("[HLF-v3]\nSET result = 2 + 3\nRESULT done\n\u03a9")
        assert scope["result"] == 5

    def test_order_of_operations(self):
        scope = _run("[HLF-v3]\nSET result = 2 + 3 * 4\nRESULT done\n\u03a9")
        assert scope["result"] == 14

    def test_parenthesized_expression(self):
        scope = _run("[HLF-v3]\nSET result = (2 + 3) * 4\nRESULT done\n\u03a9")
        assert scope["result"] == 20

    def test_variable_average(self):
        scope = _run(
            "[HLF-v3]\nSET a = 10\nSET b = 20\nSET result = (a + b) / 2\nRESULT done\n\u03a9"
        )
        assert scope["result"] == pytest.approx(15.0)

    def test_complex_variable_expression(self):
        scope = _run(
            "[HLF-v3]\nSET x = 3\nSET y = 4\nSET result = (x * x) + (y * y)\nRESULT done\n\u03a9"
        )
        assert scope["result"] == 25

    def test_math_pow(self):
        scope = _run("[HLF-v3]\nSET result = MATH_POW(2, 10)\nRESULT done\n\u03a9")
        assert scope["result"] == 1024.0

    def test_math_pi(self):
        scope = _run("[HLF-v3]\nSET result = MATH_PI()\nRESULT done\n\u03a9")
        assert abs(scope["result"] - math.pi) < 0.001

    def test_division_float(self):
        scope = _run("[HLF-v3]\nSET result = 10 / 3\nRESULT done\n\u03a9")
        assert scope["result"] == pytest.approx(10 / 3)

    def test_negation(self):
        scope = _run("[HLF-v3]\nSET result = -42\nRESULT done\n\u03a9")
        assert scope["result"] == -42

    def test_math_sqrt(self):
        scope = _run("[HLF-v3]\nSET result = MATH_SQRT(16)\nRESULT done\n\u03a9")
        assert scope["result"] == 4.0

    def test_math_abs(self):
        scope = _run("[HLF-v3]\nSET result = MATH_ABS(-99)\nRESULT done\n\u03a9")
        assert scope["result"] == 99

    def test_math_nested_sqrt_pow(self):
        scope = _run(
            "[HLF-v3]\nSET x = 3\nSET y = 4\nSET result = MATH_SQRT(MATH_POW(x, 2) + MATH_POW(y, 2))\nRESULT done\n\u03a9"
        )
        assert scope["result"] == 5.0  # Pythagorean triple: sqrt(9 + 16)

    def test_compound_expression_with_math(self):
        # 2^10 + pi ≈ 1024 + 3.14159 = 1027.14159...
        scope = _run(
            "[HLF-v3]\nSET result = MATH_POW(2, 10) + MATH_PI()\nRESULT done\n\u03a9"
        )
        assert scope["result"] == pytest.approx(1024.0 + math.pi)

    def test_math_max_min(self):
        scope = _run(
            "[HLF-v3]\nSET a = MATH_MAX(10, 20)\nSET b = MATH_MIN(10, 20)\nSET result = a + b\nRESULT done\n\u03a9"
        )
        assert scope["result"] == 30

    def test_set_with_previously_set_variable(self):
        # Verify SET can read previously SET variables in expressions
        scope = _run(
            "[HLF-v3]\nSET x = 100\nSET y = x + 1\nSET result = y * 2\nRESULT done\n\u03a9"
        )
        assert scope["result"] == 202

    def test_math_floor_ceil_round(self):
        scope = _run(
            "[HLF-v3]\nSET f = MATH_FLOOR(3.7)\nSET c = MATH_CEIL(3.2)\nSET r = MATH_ROUND(3.5)\nSET result = f + c + r\nRESULT done\n\u03a9"
        )
        assert scope["result"] == (3 + 4 + 4)
