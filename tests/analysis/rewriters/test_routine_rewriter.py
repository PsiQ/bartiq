import pytest

from bartiq import Routine, compile_routine
from bartiq.analysis.rewriters.routine_rewriter import rewrite_routine_resources
from bartiq.analysis.rewriters.sympy_expression import sympy_rewriter
from bartiq.compilation import CompilationFlags


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
    assert new_routine.resource_values["dummy_a"] == rewriter.expression

    resources = {
        "a": (a := new_routine.children["a"]).resource_values,
        "x": (x := new_routine.children["x"]).resource_values,
        "ab": a.children["b"].resource_values,
        "ac": a.children["c"].resource_values,
        "xz": x.children["z"].resource_values,
    }

    def assert_matches_text(actual, expected):
        assert backend.serialize(actual) == backend.serialize(backend.as_expression(expected))

    # Test that the history has percolated through the children correctly.
    # Dummy A resource
    assert_matches_text(resources["ab"]["dummy_a"], "b")
    assert_matches_text(resources["xz"]["dummy_a"], "z")

    assert_matches_text(resources["a"]["dummy_a"], "b+c")
    assert_matches_text(resources["x"]["dummy_a"], "A")

    # Dummy B resource
    assert resources["ac"]["dummy_b"] == 2
    assert resources["xz"]["dummy_b"] == 1

    assert_matches_text(resources["a"]["dummy_b"], "log(b+1)+2")
    assert_matches_text(resources["x"]["dummy_b"], "y+1")
