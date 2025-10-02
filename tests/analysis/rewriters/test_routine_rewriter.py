from bartiq.analysis.rewriters.routine_rewriter import rewrite_routine_resources
from bartiq.analysis.rewriters.sympy_expression import sympy_rewriter


def test_rewrite_routine_resources(dummy_compiled_routine, backend):
    resources = ["dummy_a", "dummy_b"]
    rewriter = sympy_rewriter(dummy_compiled_routine.resource_values["dummy_a"])
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
    new_routine = rewrite_routine_resources(dummy_compiled_routine, resources, rewriter.history(), sympy_rewriter)

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
