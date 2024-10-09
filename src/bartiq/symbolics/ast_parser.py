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

3. Reserved lambda keyword is replaced with __lambda__, e.g.
lambda + gamma -> __lambda__ + gamma

After the preprocessing is done, the resulting expression is also
a valid Python expression. Therefore, we are able to use ast.parse
to construct abstract syntax tree for the expression. This abstract
syntax tree is then walked to assemble an expression object.

Also, the parser here needs substantially less functionallity from
the "interpreter", i.e. something that constructs actual objects
from parsed informations. This is because we actually construct at most
binary expressions, and we assume that operators of the constructed
objects behave like they should with built-in operators.
"""
import ast
import operator
import re
from dataclasses import dataclass
from functools import singledispatch, singledispatchmethod
from typing import Callable
from warnings import warn

from .grammar import Interpreter

_BINARY_OP_MAP = {
    ast.Mult: operator.mul,
    ast.Add: operator.add,
    ast.Div: operator.truediv,
    ast.Sub: operator.sub,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.BitXor: operator.pow,
    ast.FloorDiv: operator.floordiv,
}


_UNARY_OP_MAP = {ast.USub: operator.neg, ast.UAdd: lambda x: +x}


_IDENTIFIER = r"[_a-zA-Z]\w*"
_NAMESPACE_IDENTIFIER = rf"{_IDENTIFIER}(\.{_IDENTIFIER})*"
_PORT_PATTERN = rf"#({_NAMESPACE_IDENTIFIER})"
_WILDCARD_PATTERN = rf"(({_IDENTIFIER})?)~"
_LAMBDA_PATTERN = r"(?<![_A-Za-z])lambda(?![A-Za-z])"
_IN_PATTERN = r"(^|[^\w])in($|[^\w])"

_RESTRICTED_NAMES = {"__lambda__": "lambda", "__in__": "in"}


@dataclass(frozen=True)
class _PreprocessingStage:
    """Class for representing a single step performed during preprocessing.

    Example stages, defined below, include preprocessing expression to replace
    the xor operator (^) with power operator (**), or replacing wildcard
    characters (~) with calls to wildcard() function.

    Attributes:
        matches: Function deciding if given preprocessing step should be run.
           The actuall preprocesssing step will be run if and only if
           matches(expression) is true.
        preprocess: Function performing actual preprocessing work.

    Note:
        The reason why we separate `matches` and `preprocess` is that some
        preprocessing steps are expensive, but not always needed.
        For example, replacing wildcard characters is expensive, because it is
        done with regular expressions. However, not all expressions have wildcards,
        and checking if an expression contains a wildcard is fast.
    """

    matches: Callable[[str], bool]
    preprocess: Callable[[str], str]


def _contains_port(expression):
    return "#" in expression


def _replace_ports(expression):
    return re.sub(_PORT_PATTERN, r"Port(\1)", expression)


# Preprocessing stage replacing port names with calls to `Port` function.
_PORT_REPLACEMENT = _PreprocessingStage(matches=_contains_port, preprocess=_replace_ports)


def _contains_wildcard(expression):
    return "~" in expression


def _replace_wildcards(expression):
    return re.sub(_WILDCARD_PATTERN, r"wildcard(\1)", expression)


# Preprocessing stage replacing wildcard characters with calls to `wildcard` function
_WILDCARD_REPLACEMENT = _PreprocessingStage(matches=_contains_wildcard, preprocess=_replace_wildcards)


def _contains_lambda(expression):
    return "lambda" in expression


def _replace_lambda(expression):
    return re.sub(_LAMBDA_PATTERN, "__lambda__", expression)


# Preprocessing stage replacing symbols named lambda with symbols named __lambda__
_LAMBDA_REPLACEMENT = _PreprocessingStage(matches=_contains_lambda, preprocess=_replace_lambda)


def _contains_xor_op(expression):
    return "^" in expression


def _replace_xor_op(expression):
    warn("Using ^ operator to denote exponentiation is deprecated. Use ** operator instead.", DeprecationWarning)
    return expression.replace("^", "**")


# Preprocessing stage replacing xor operators (^) with power (**) operators.
_XOR_OP_REPLACEMENT = _PreprocessingStage(matches=_contains_xor_op, preprocess=_replace_xor_op)


def _contains_in(expression):
    return re.search(_IN_PATTERN, expression) is not None


def _replace_in(expression):
    return re.sub(_IN_PATTERN, r"\1__in__\2", expression)


# Preprocessing stage replacing "in"s with _in
_IN_REPLACEMENT = _PreprocessingStage(matches=_contains_in, preprocess=_replace_in)

# Sequence of all known preprocessing stages.
# If there are any new preprocessing stages, they should be added here.
# Note that this list is not exposed/configurable by the user, because it wouldn't really make sens -
# if any of those preprocessing stages does not run we would risk having unparseable expression.
_PREPROCESSING_STAGES = (
    _WILDCARD_REPLACEMENT,
    _PORT_REPLACEMENT,
    _LAMBDA_REPLACEMENT,
    _XOR_OP_REPLACEMENT,
    _IN_REPLACEMENT,
)


def _preprocess(expression: str) -> str:
    """Preprocess a given expression to make it suitable for parsing with ast module."""
    for stage in _PREPROCESSING_STAGES:
        if stage.matches(expression):
            expression = stage.preprocess(expression)
    return expression


def _restore_name(name: str) -> str:
    """Given a token (e.g. symbol, or a function) return its name or lambda if it was __lambda__.

    This is to reverse the effects of preprocessing.
    """
    return _RESTRICTED_NAMES.get(name, name)


class _NodeConverter:
    """Converter capable of transforming a given AST node into symbolic expression using given interpreter.

    Attributes:
        interpreter: An interpreter to use for constructing primitives of symbolic expressions.
    """

    def __init__(self, interpreter: Interpreter):
        self.interpreter = interpreter

    @singledispatchmethod
    def convert_node(self, node):
        """Given an AST node convert it into symbolic expression."""
        raise NotImplementedError(f"Uknown node {node}.")

    @convert_node.register
    def _(self, node: ast.Module):
        """Variant of convert_node for ast.Module, which is just a top level node."""
        return self.convert_node(node.body[0])

    @convert_node.register
    def _(self, node: ast.Expr):
        """ "Variant of convert_node for ast.Expr, which is just a wrapper for actuall expression (node.value)."""
        return self.convert_node(node.value)

    @convert_node.register
    def _(self, node: ast.Constant):
        """Variant of convert_node for ast.Constant, which should be converted to a number."""
        return self.interpreter.create_number((node.value,))

    @convert_node.register
    def _(self, node: ast.BinOp):
        """Variant of convert_node for ast.BinOp.

        This is the first of more involved variants. When converting binary operation, we first descend
        down the tree and convert children, and then combine the results using operator as given in
        _BINARY_OP_MAP.
        """
        return _BINARY_OP_MAP[type(node.op)](self.convert_node(node.left), self.convert_node(node.right))

    @convert_node.register
    def _(self, node: ast.UnaryOp):
        """Variant of convert_node for ast.UnaryOp.

        There are only two unary operators supported, namely +x and -x.
        """
        return _UNARY_OP_MAP[type(node.op)](self.convert_node(node.operand))

    @convert_node.register
    def _(self, node: ast.Call):
        """Variant of converet_node for ast.Call.

        Most instances of ast.Call get converted to a regular function call.
        Exception to this are the Port functions, which are converted to port
        designator.
        """
        if isinstance(node.func, ast.Name) and node.func.id == "Port":
            return self.interpreter.create_parameter((f"#{_resolve_value(node.args[0])}",))
        if isinstance(node.func, ast.Attribute) and node.func.attr == "Port":
            return self.interpreter.create_parameter(
                (f"{_resolve_value(node.func.value)}.#{_resolve_value(node.args[0])}",)
            )
        else:
            return self.interpreter.create_function(
                (_resolve_value(node.func), list(map(self.convert_node, node.args)))
            )

    @convert_node.register(ast.Name)
    @convert_node.register(ast.Attribute)
    def _(self, node):
        """Variant of convert_node for ast.Name and ast.Attribute, which are nodes representing parameter."""
        return self.interpreter.create_parameter((_resolve_value(node),))


@singledispatch
def _resolve_value(value_node):
    """Given a node, resolve it to a namespaced name.

    This function works for ast.Name nodes, as well as (possibly nested) ast.Attribute nodes, for
    which it recurses into their value part.
    Also, if an ast.Call node is a part of attribute lookup, this is an error, unless the function
    being called is a wildcard - in which case we simply use ~ symbol in the namespaced symbol name.
    """
    raise NotImplementedError(f"Unexpected node found when resolving attribute lookup: {type(value_node)}")


@_resolve_value.register
def _(value_node: ast.Name):
    return _restore_name(value_node.id)


@_resolve_value.register
def _(value_node: ast.Attribute):
    return f"{_resolve_value(value_node.value)}.{_restore_name(value_node.attr)}"


@_resolve_value.register
def _(value_node: ast.Call):
    # Assertions here are to silence Mypy and describe the expected input.
    # We should never get any assertion errors here, unless the expression doesn't match our grammar.
    assert isinstance(value_node.func, ast.Name)
    if value_node.func.id != "wildcard":
        raise ValueError("Should never encounter function call other than wildcard() in the attribute lookup")
    if value_node.args:
        assert isinstance(value_node.args[0], ast.Name)
        return f"{value_node.args[0].id}~"
    else:
        return "~"


def parse(expression: str, interpreter: Interpreter):
    """Parse given mathematical expression using given interpreter to create expression primitives.

    Args:
        expression: An expression to parse.
        interpreter: An interpreter providing methods for constructing numbers, symbols, and functions.

    Returns:
        A result of interpreting the whole expression (which depends on what the interpreter produces).
    """
    preprocessed_expression = _preprocess(expression)
    return _NodeConverter(interpreter).convert_node(ast.parse(preprocessed_expression))
