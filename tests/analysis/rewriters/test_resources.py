from bartiq import Routine, compile_routine
from bartiq.analysis.rewriters.resources import ResourceRewriter
from bartiq.analysis.rewriters.sympy_expression import _SYMPY_BACKEND
from bartiq.compilation import CompilationFlags

root = {
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
compiled = compile_routine(
    Routine.from_qref(root, _SYMPY_BACKEND), compilation_flags=CompilationFlags.EXPAND_RESOURCES
).routine


def test_resource_rewriter_does_not_change_routine_expr():
    resource_rewriter = ResourceRewriter(routine=compiled, resource="dummy")
    resource_rewriter.assume("b>0").assume("y>0").assume("z>0").assume("c>0").simplify().expand().substitute(
        "y + z", "A"
    )

    # Why `str` here? Because the symbols in the actual expression have assumptions on them!
    assert str(resource_rewriter.expression) == "A + b + c"

    assert resource_rewriter.routine.resource_values["dummy"] == _SYMPY_BACKEND.as_expression(
        "Max(0, b) + Max(0, c) + Max(0, y) + Max(0, z)"
    )


def test_apply_to_whole_routine():
    resource_rewriter = ResourceRewriter(routine=compiled, resource="dummy")
    resource_rewriter.assume("b>0").assume("y>0").assume("z>0").assume("c>0").simplify().expand().substitute(
        "y + z", "A"
    )
    new_routine = resource_rewriter.apply_to_whole_routine()
    assert str(new_routine.resource_values["dummy"]) == str(resource_rewriter.expression)
    assert str(new_routine.children["a"].children["b"].resource_values["dummy"]) == "b"
