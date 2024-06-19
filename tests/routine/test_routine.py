# Copyright 2024 PsiQuantum, Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest

from bartiq._routine import Routine


class TestFindingChildren:
    def test_selector_without_dot_finds_direct_child(self):
        routine_a = Routine(name="a", type=None, children={"b": Routine(name="b", type=None)})
        root = Routine(name="", children={"a": routine_a}, type=None)

        assert root.find_descendant("a") is routine_a

    def test_empty_selector_finds_self(self):
        root = Routine(name="", type=None)
        assert root.find_descendant("") is root

    def test_selector_with_dot_finds_grand_child(self):
        routine_b = Routine(name="b", type=None)
        root = Routine(
            name="",
            children={"a": Routine(name="a", type=None, children={"b": routine_b})},
            type=None,
        )

        assert root.find_descendant("a.b") is routine_b

    @pytest.mark.parametrize("selector", ["ddd", "a.ddd"], ids=["Missing child", "Missing grand child"])
    def test_attempt_to_find_nonexisting_child_raises_value_error_containing_selector(self, selector: str):
        root = Routine(
            name="",
            children={"a": Routine(name="a", type=None, children={"b": Routine(name="b", type=None)})},
            type=None,
        )

        with pytest.raises(ValueError) as err_info:
            root.find_descendant(selector)
            assert selector in str(err_info.errisinstance)


class TestFindingRelativePathFromAncestor:
    def test_can_find_correct_path_from_direct_parent(self):
        child = Routine(name="child", type=None)
        parent = Routine(name="", children={"child": child}, type=None)

        assert child.relative_path_from(parent) == "child"

    def test_can_find_correct_path_from_grand_parent(self):
        grand_child = Routine(name="a", type=None)
        root = Routine(
            name="",
            type=None,
            children={"b": Routine(name="b", type=None, children={"a": grand_child})},
        )

        assert grand_child.relative_path_from(root) == "b.a"

    def test_can_find_correct_path_from_ancestor_which_is_not_root(self):
        routine_d = Routine(name="d", type=None)
        routine_c = Routine(name="c", type=None, children={"d": routine_d})
        routine_b = Routine(name="b", type=None, children={"c": routine_c})
        _ = Routine(name="root", type=None, children={"b": routine_b})

        assert routine_d.relative_path_from(routine_b) == "c.d"

    def test_raises_value_error_on_attempt_to_find_path_from_non_ancestor(self):
        routine_d = Routine(name="d", type=None)
        routine_c = Routine(name="c", type=None)
        routine_b = Routine(name="b", type=None, children={"c": routine_c, "d": routine_d})
        _ = Routine(name="root", type=None, children={"b": routine_b})

        with pytest.raises(ValueError):
            routine_d.relative_path_from(routine_c)


class TestGettingAbsolutePath:
    def test_gets_absolute_path_with_root_name_by_default(self):
        child = Routine(name="child", type=None)
        parent = Routine(name="root", children={"child": child}, type=None)

        assert child.absolute_path() == "root.child"
        assert child.absolute_path(exclude_root_name=True) == "child"
        assert parent.absolute_path() == "root"
        assert parent.absolute_path(exclude_root_name=True) == ""


class TestRoutineEquality:
    def _example_routine(self):
        # The reason it is not a fixture is that we need it two times in the same
        # test function.
        return Routine(
            name="a",
            type=None,
            ports={"in.0": {"name": "in.0", "direction": "input", "size": "N"}},
            children={
                "child_1": Routine(
                    name="child_1",
                    type="childtype",
                    ports={
                        "in.0": {"name": "in.0", "direction": "input", "size": "N-2"},
                        "out.0": {"name": "in.1", "direction": "output", "size": "N-2"},
                    },
                ),
                "child_2": Routine(
                    name="child_2",
                    type="childtype",
                    ports={
                        "in.0": {"name": "in.0", "direction": "input", "size": 2},
                        "out.0": {"name": "in.1", "direction": "output", "size": 2},
                    },
                ),
            },
        )

    def test_routine_is_equal_to_itself(self):
        routine = self._example_routine()

        assert routine == routine

    def test_routine_is_equal_to_the_same_routine(self):
        routine_1 = self._example_routine()
        routine_2 = self._example_routine()

        assert routine_1 == routine_2

    def test_routine_with_empty_fields_is_equal_to_routine_with_unset_fields(self):
        routine_1 = self._example_routine()
        # The second routine is the same, but its linked params are explicitly set
        # to an empty list.
        # We cannot do it in initializer, because we sanitize inputs to exclude empty
        # colllections, so we mutate object in place instead. Keep in mind that it's not a
        # recommended approach for constructing an instance of PyDantic models. Avoid
        # mutations and provide nonenpty fields as arguments to __init__ wnen using
        # Routine in production code.
        routine_2 = self._example_routine()
        routine_2.linked_params = {}

        assert routine_1 == routine_2

    def test_routine_differing_only_in_parrent_are_equal(self):
        routine_1 = Routine(name="root", type=None, children={"a": self._example_routine()})
        routine_2 = Routine(name="root2", type="root_routine", children={"a": self._example_routine()})

        assert routine_1.children["a"] == routine_2.children["a"]

    def test_difference_in_field_other_than_parent_makes_two_routines_unequal(self):
        routine_1 = Routine(name="root", type=None, children={"a": self._example_routine()})
        routine_2 = Routine(name="root2", type="root_routine", children={"a": self._example_routine()})

        assert routine_1 != routine_2


def _dummy_routine_dict(name):
    return {
        "name": name,
        "type": "dummy",
        "ports": {
            "in_0": {"name": "in_0", "direction": "input", "size": 1},
            "out_0": {"name": "out_0", "direction": "output", "size": 1},
        },
    }


class TestRoutineWalkRespectsDepthFirstTopologicalOrder:
    # Note: test cases in this test class all use distinct names for the children
    # so that we are able to construct simple and readable assertions using names only.
    # Constructing the same assertions using Routine objects would be a nightmare.

    def test_parent_is_visited_after_children_are_visited(self):
        root = Routine(
            **_dummy_routine_dict("root"),
            children={
                "a": _dummy_routine_dict("a"),
                "b": {
                    **_dummy_routine_dict("b"),
                    "children": {"c": _dummy_routine_dict("c"), "d": _dummy_routine_dict("d")},
                },
            },
        )

        visited_names = [op.name for op in root.walk()]

        assert visited_names in [
            ["a", "c", "d", "b", "root"],  # Visited child a first
            # Same, but b's children are in different order
            ["a", "d", "c", "b", "root"],
            ["c", "d", "b", "a", "root"],  # b visited before a
            # Same, but b's children are in different order
            ["d", "c", "b", "a", "root"],
        ]

    def test_linearly_ordered_children_are_always_enumerated_in_topological_order(self):
        root = Routine(
            **_dummy_routine_dict("root"),
            children={name: _dummy_routine_dict(name) for name in ("a", "b", "c", "d")},
            connections=[
                {"source": src, "target": dst}
                for src, dst in [
                    ("d.out_0", "c.in_0"),
                    ("c.out_0", "a.in_0"),
                    ("a.out_0", "b.in_0"),
                ]
            ],
        )

        visited_names = [op.name for op in root.walk()]

        assert visited_names == ["d", "c", "a", "b", "root"]

    def test_each_chain_of_linearly_connected_children_is_enumerated_in_topological_order(self):
        root = Routine(
            **_dummy_routine_dict("root"),
            children={name: _dummy_routine_dict(name) for name in ("a", "b", "c", "d")},
            connections=[
                {"source": "a.out_0", "target": "d.in_0"},
                {"source": "c.out_0", "target": "b.out_0"},
            ],
        )

        visited_names = [op.name for op in root.walk()]

        assert visited_names in [
            ["a", "d", "c", "b", "root"],
            ["c", "b", "a", "d", "root"],
            # Yes, even if it's not intuitive, the orderings below are also valid
            ["a", "c", "d", "b", "root"],
            ["a", "c", "b", "d", "root"],
            ["c", "a", "b", "d", "root"],
            ["c", "a", "d", "b", "root"],
        ]

    def test_deeply_nested_routines_are_enumerated_in_correct_order(self):
        root = Routine(
            **_dummy_routine_dict("root"),
            children={
                "a": _dummy_routine_dict("a"),
                "b": {
                    **_dummy_routine_dict("b"),
                    "children": {
                        "c": {
                            **_dummy_routine_dict("c"),
                            "children": {"e": _dummy_routine_dict("e")},
                        },
                        "d": _dummy_routine_dict("d"),
                    },
                    "connections": [{"source": "c.out_0", "target": "d.in_0"}],
                },
                # f does not use _dummy_routine_dict because it has more than one output
                "f": {
                    "name": "f",
                    "type": "dummy",
                    "ports": {
                        "in_0": {"name": "in_0", "direction": "input", "size": 1},
                        "out_0": {"name": "out_0", "direction": "output", "size": 1},
                        "out_1": {"name": "out_1", "direction": "output", "size": 1},
                    },
                },
                "g": _dummy_routine_dict("g"),
            },
            connections=[
                {"source": "f.out_0", "target": "a.in_0"},
                {"source": "f.out_1", "target": "b.in_0"},
                {"source": "b.out_0", "target": "g.in_0"},
            ],
        )

        visited_names = [op.name for op in root.walk()]

        assert len(visited_names) == 8
        assert set(visited_names) == {"a", "b", "c", "d", "e", "f", "g", "root"}

        # In this testcase we don't enumerate all possibilities, instead we only test
        # for the relationships that have to hold
        edges = [("f", "a"), ("f", "b"), ("b", "g"), ("c", "d")]

        for src, dst in edges:
            assert visited_names.index(src) < visited_names.index(dst)

    def test_walk_raises_error_when_cycle_is_present(self):
        root = Routine(
            **_dummy_routine_dict("root"),
            children={name: _dummy_routine_dict(name) for name in ("a", "b", "c")},
            connections=[
                {"source": "a.out_0", "target": "c.in_0"},
                {"source": "c.out_0", "target": "b.in_0"},
                {"source": "b.out_0", "target": "a.in_0"},
            ],
        )

        with pytest.raises(ValueError):
            list(root.walk())  # Wrapped in list to actually consume an iterator

    def test_walk_over_routine_with_multiple_connections(self):
        root = Routine(
            **{
                "name": "root",
                "type": "dummy",
                "ports": {
                    "in_0": {"name": "in_0", "direction": "input", "size": 1},
                    "in_1": {"name": "in_1", "direction": "input", "size": 1},
                    "out_0": {"name": "out_0", "direction": "output", "size": 1},
                },
                "children": {
                    "child": {
                        "name": "child",
                        "type": "dummy",
                        "ports": {
                            "in_0": {"name": "in_0", "direction": "input", "size": 1},
                            "in_1": {"name": "in_1", "direction": "input", "size": 1},
                            "out_0": {"name": "out_0", "direction": "output", "size": 1},
                        },
                    }
                },
                "connections": [
                    {"source": "in_0", "target": "child.in_0"},
                    {"source": "in_1", "target": "child.in_1"},
                    {"source": "child.out_0", "target": "out_0"},
                ],
            }
        )

        visited_names = [op.name for op in root.walk()]

        assert visited_names == ["child", "root"]
