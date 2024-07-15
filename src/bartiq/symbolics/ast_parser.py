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

"""AST-based expression parser.

Contrary to pyparsing-based grammar from grammar.py, this module
utilizes ast to parse an arithmetic expression as Python expresson.
Since not all expressions that we use are correct Python expressions,
the parser first preprocesses expressions and replaces unallowed
syntax with carefully crafted function calls. In particular:

1. Port designations are converted to Port function call, e.g.

#in_0 -> Port(in_0)
a.b.#out_1 -> a.b.Port(out_1)

2. Wildcards are replaced by a call to wildcard function, e.g.

~.a -> wildcard().a
a~.b -> wildcard(a).b

Also, the parser here needs substantially less functionallity from
the "interpreter", i.e. something that constructs actual objects
from parsed informations.
"""
import ast
import operator
import re
from dataclasses import dataclass
from functools import singledispatch, singledispatchmethod
from typing import Callable, TypeVar

from .grammar import Interpreter
from .sympy_interpreter import SympyInterpreter

op_map = {
    ast.Mult: operator.mul,
    ast.Add: operator.add,
    ast.Div: operator.truediv,
    ast.Sub: operator.sub,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.BitXor: operator.pow,
}


unary_op_map = {ast.USub: operator.neg}


TExpr = TypeVar("TExpr")

_IDENTIFIER = r"[_a-zA-Z]\w*"
_NAMESPACE_IDENTIFIER = rf"{_IDENTIFIER}(\.{_IDENTIFIER})*"
_PORT_NAME = rf"#({_NAMESPACE_IDENTIFIER})"
_WILDCARD_PATTERN = rf"(({_IDENTIFIER})?)~"


@dataclass(frozen=True)
class PreprocessingStage:
    matches: Callable[[str], bool]
    preprocess: Callable[[str], str]


def _contains_port_name(expression):
    return "#" in expression


def _replace_port_names(expression):
    return re.sub(_PORT_NAME, r"Port(\1)", expression)


_PORT_NAME_REPLACEMENT = PreprocessingStage(matches=_contains_port_name, preprocess=_replace_port_names)


def _contains_wildcard(expression):
    return "~" in expression


def _replace_wildcards(expression):
    return re.sub(_WILDCARD_PATTERN, r"wildcard(\1)", expression)


_WILDCARD_REPLACEMENT = PreprocessingStage(matches=_contains_wildcard, preprocess=_replace_wildcards)


# If there are any new preprocessing stages, they should be added here
_PREPROCESSING_STAGES = (_WILDCARD_REPLACEMENT, _PORT_NAME_REPLACEMENT)


def _preprocess(expression):
    """Preprocess a given expression to make it suitable for parsing."""
    for stage in _PREPROCESSING_STAGES:
        if stage.matches(expression):
            expression = stage.preprocess(expression)
    return expression


class NodeConverter:

    def __init__(self, interpreter: Interpreter):
        self.interpreter = interpreter

    @singledispatchmethod
    def convert_node(self, node):
        raise NotImplementedError(f"Uknown node {node}.")

    @convert_node.register
    def _(self, node: ast.Module):
        return self.convert_node(node.body[0])

    @convert_node.register
    def _(self, node: ast.Expr):
        return self.convert_node(node.value)

    @convert_node.register
    def _(self, node: ast.Constant):
        return self.interpreter.create_number((node.value,))

    @convert_node.register
    def _(self, node: ast.BinOp):
        return op_map[type(node.op)](self.convert_node(node.left), self.convert_node(node.right))

    @convert_node.register
    def _(self, node: ast.UnaryOp):
        return unary_op_map[type(node.op)](self.convert_node(node.operand))

    @convert_node.register
    def _(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            if node.func.id == "Port":
                return self.interpreter.create_parameter((f"#{_resolve_value(node.args[0])}",))
            return self.interpreter.create_function((node.func.id, list(map(self.convert_node, node.args))))
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "Port":
                return self.interpreter.create_parameter(
                    (f"{_resolve_value(node.func.value)}.#{_resolve_value(node.args[0])}",)
                )
        else:
            raise NotImplementedError("Invalid function call, encountered unexpected node {node.func} as the callee.")

    @convert_node.register
    def _(self, node: ast.Name):
        return self.interpreter.create_parameter((node.id,))

    @convert_node.register
    def _(self, node: ast.Attribute):
        return self.interpreter.create_parameter((_resolve_value(node),))


@singledispatch
def _resolve_value(value_node):
    raise NotImplementedError(f"Unexpected node found when resolving attribute lookup: {type(value_node)}")


@_resolve_value.register
def _(value_node: ast.Name):
    return value_node.id


@_resolve_value.register
def _(value_node: ast.Attribute):
    return f"{_resolve_value(value_node.value)}.{value_node.attr}"


@_resolve_value.register
def _(value_node: ast.Call):
    if value_node.func.id != "wildcard":
        raise ValueError("Should never encounter function call other than wildcard() in the attribute lookup")
    return f"{value_node.args[0].id}~" if value_node.args else "~"


def parse(expression: str, interpreter: Interpreter):
    preprocessed_expression = _preprocess(expression)
    return NodeConverter(interpreter).convert_node(ast.parse(preprocessed_expression))


def parse_to_sympy(expression: str, debug=False):
    return parse(expression, interpreter=SympyInterpreter(debug=debug))
