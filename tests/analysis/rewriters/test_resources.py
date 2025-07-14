import pytest

from bartiq import Routine, compile_routine
from bartiq.analysis.rewriters.resources import ResourceRewriter
from bartiq.analysis.rewriters.sympy_expression import _SYMPY_BACKEND
from bartiq.compilation import CompilationFlags


@pytest.fixture(scope="function")
def root():
    return {
        "name": "root",
        "children": [
            {
                "name": "a",
                "children": [
                    {"name": "b", "resources": [{"name": "dummy", "type": "additive", "value": "max(0, b)"}]},
                    {"name": "c", "resources": [{"name": "dummy", "type": "additive", "value": "max(0, c)"}]},
                ],
            },
            {
                "name": "x",
                "children": [
                    {"name": "y", "resources": [{"name": "dummy", "type": "additive", "value": "max(0, y)"}]},
                    {"name": "z", "resources": [{"name": "dummy", "type": "additive", "value": "max(0, z)"}]},
                ],
            },
        ],
    }


@pytest.fixture(scope="function")
def compiled(root):
    return compile_routine(
        Routine.from_qref(root, _SYMPY_BACKEND), compilation_flags=CompilationFlags.EXPAND_RESOURCES
    ).routine


def test_resource_rewriter_does_not_change_routine_expr(compiled):
    resource_rewriter = ResourceRewriter(routine=compiled, resource="dummy")
    resource_rewriter.assume("b>0").assume("y>0").assume("z>0").assume("c>0").simplify().expand().substitute(
        "y + z", "A"
    )

    # Why `str` here? Because the symbols in the actual expression have assumptions on them!
    assert str(resource_rewriter.expression) == "A + b + c"

    assert resource_rewriter.routine.resource_values["dummy"] == _SYMPY_BACKEND.as_expression(
        "Max(0, b) + Max(0, c) + Max(0, y) + Max(0, z)"
    )


def test_apply_to_whole_routine(compiled):
    resource_rewriter = ResourceRewriter(routine=compiled, resource="dummy")
    resource_rewriter.assume("b>0").assume("y>0").assume("z>0").assume("c>0").simplify().expand().substitute(
        "y + z", "A"
    )
    new_routine = resource_rewriter.apply_to_whole_routine()

    # Test that the routine attribute has not been modified in-place
    assert resource_rewriter.routine.resource_values["dummy"] == compiled.resource_values["dummy"]

    # Test that the new routine top-level resource is the same as the rewriter attribute expression
    assert str(new_routine.resource_values["dummy"]) == str(resource_rewriter.expression)

    # Test that the history has percolated through the children correctly.
    assert str(new_routine.children["a"].children["b"].resource_values["dummy"]) == "b"
    assert str(new_routine.children["x"].children["z"].resource_values["dummy"]) == "z"
