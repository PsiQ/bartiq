import pytest

from bartiq import Routine, compile_routine
from bartiq.analysis.rewriters.routine_rewriter import rewrite_routine_resources
from bartiq.analysis.rewriters.sympy_expression import sympy_rewriter
from bartiq.compilation import CompilationFlags


def from_str_to_str(backend, expr: str):
    """Remove assumptions from symbols and ensure string matching works"""
    return str(backend.as_expression(expr))


@pytest.fixture(scope="function")
def root():
    return {
        "name": "root",
        "children": [
            {
                "name": "a",
                "children": [
                    {
                        "name": "b",
                        "resources": [
                            {"name": "dummy_a", "type": "additive", "value": "max(0, b)"},
                            {"name": "dummy_b", "type": "additive", "value": "log(1 + b)"},
                        ],
                    },
                    {
                        "name": "c",
                        "resources": [
                            {"name": "dummy_a", "type": "additive", "value": "max(0, c)"},
                            {"name": "dummy_b", "type": "additive", "value": "min(2, c)"},
                        ],
                    },
                ],
            },
            {
                "name": "x",
                "children": [
                    {
                        "name": "y",
                        "resources": [
                            {"name": "dummy_a", "type": "additive", "value": "max(0, y)"},
                            {"name": "dummy_b", "type": "additive", "value": "ceiling(y)"},
                        ],
                    },
                    {
                        "name": "z",
                        "resources": [
                            {"name": "dummy_a", "type": "additive", "value": "max(0, z)"},
                            {"name": "dummy_b", "type": "additive", "value": "Heaviside(z, 0.5)"},
                        ],
                    },
                ],
            },
        ],
    }


@pytest.fixture(scope="function")
def compiled(root, backend):
    return compile_routine(
        Routine.from_qref(root, backend), compilation_flags=CompilationFlags.EXPAND_RESOURCES
    ).routine


def test_rewrite_routine_resources(compiled, backend):
    resources = ["dummy_a", "dummy_b"]
    rewriter = sympy_rewriter(compiled.resource_values["dummy_a"])
    rewriter = (
        rewriter.assume("b>0")
        .assume("y>0")
        .assume("z>10")
        .assume("c>5")
        .simplify()
        .expand()
        .substitute("y + z", "A")
        .substitute("ceiling($x)", "x")
    )
    new_routine = rewrite_routine_resources(compiled, resources, rewriter.history(), sympy_rewriter)

    # Test that the new routine top-level resource is the same as the rewriter attribute expression
    print(rewriter.expression)
    print(compiled.resource_values)
    print(new_routine.resource_values)
    assert new_routine.resource_values["dummy_a"] == rewriter.expression

    # Test that the history has percolated through the children correctly.
    # Dummy A resource
    assert str(new_routine.children["a"].children["b"].resource_values["dummy_a"]) == from_str_to_str(backend, "b")
    assert str(new_routine.children["x"].children["z"].resource_values["dummy_a"]) == from_str_to_str(backend, "z")

    assert str(new_routine.children["a"].resource_values["dummy_a"]) == from_str_to_str(backend, "b+c")
    assert str(new_routine.children["x"].resource_values["dummy_a"]) == from_str_to_str(backend, "A")

    # Dummy B resource
    assert str(new_routine.children["a"].children["c"].resource_values["dummy_b"]) == from_str_to_str(backend, "2")
    assert str(new_routine.children["x"].children["z"].resource_values["dummy_b"]) == from_str_to_str(backend, "1")

    assert str(new_routine.children["a"].resource_values["dummy_b"]) == from_str_to_str(backend, "log(b+1)+2")
    assert str(new_routine.children["x"].resource_values["dummy_b"]) == from_str_to_str(backend, "y+1")
