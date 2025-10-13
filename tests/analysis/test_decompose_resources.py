import pytest

from bartiq.analysis.decompose_resources import DecomposeResources, _decompose_resource

resource = "dummy_a"


def _decomposed(compiled_routine):
    return {
        child_name: val
        for child_name, child_rout in compiled_routine.children.items()
        if resource in child_rout.resource_values and (val := child_rout.resource_values[resource]) != 0
    }


class TestDecomposeResources:
    @pytest.fixture(scope="function")
    def decompose_resources(self, dummy_compiled_routine):
        return DecomposeResources(compiled_routine=dummy_compiled_routine, resource=resource)

    def test_total(self, decompose_resources, dummy_compiled_routine):
        assert decompose_resources.total == dummy_compiled_routine.resource_values[resource]

    def test_decomposition(self, decompose_resources, dummy_compiled_routine):
        assert decompose_resources.decomposition == _decomposed(dummy_compiled_routine)

    @pytest.mark.parametrize("child", ["a", "x"])
    def test_descend(self, decompose_resources, child):
        one_layer_down = decompose_resources.descend(child)
        assert one_layer_down.routine.name == child
        assert one_layer_down.total == decompose_resources.routine.children[child].resource_values[resource]
        assert one_layer_down.decomposition == _decomposed(decompose_resources.routine.children[child])

    def test_descend_multi_layer(self, decompose_resources):
        assert decompose_resources.descend("a").descend("b").routine.name == "b"


def test_decompose_resource(dummy_compiled_routine):
    total, decomposition = _decompose_resource(dummy_compiled_routine, resource)
    assert total == dummy_compiled_routine.resource_values[resource]
    assert decomposition == _decomposed(dummy_compiled_routine)
