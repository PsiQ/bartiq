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

from abc import ABC, abstractmethod
from functools import wraps

from pyparsing import (
    Combine,
    Forward,
    Group,
    Literal,
    OneOrMore,
    Opt,
    ParseResults,
    StringEnd,
    StringStart,
    Suppress,
    ZeroOrMore,
    delimited_list,
    pyparsing_common,
)

WILDCARD_CHARACTER = "~"


def make_parser(interpreter):
    """Construct a parser for our grammar."""
    # Define parameter prefixes
    name = pyparsing_common.identifier.set_name("name")
    port_name = Combine(Literal("#") + name).set_name("port name")
    path_separator = Literal(".")
    routine_path_prefix = Combine(OneOrMore(Combine(name + path_separator))).set_name("path prefix")
    port_path_prefix = Combine(Opt(routine_path_prefix) + port_name + path_separator).set_name("port path prefix")
    wildcard = Literal(WILDCARD_CHARACTER)
    wildcarded_prefix = Combine(Opt(name) + wildcard + path_separator).set_name("wildcard_name")

    # This allows only for expression of form "string_1~.string_2"
    # We intentionally restricted the scope of use of wildcards to this case.
    wildcarded_parameter = Combine(wildcarded_prefix + name).set_name("wildcard parameter")
    routine_parameter = Combine(
        Opt(routine_path_prefix) + name,
    ).set_name("routine parameter")
    port_parameter = Combine(Opt(port_path_prefix) + name).set_name("port parameter")

    parameter = (
        (wildcarded_parameter | routine_parameter | port_parameter)
        .set_name("parameter")
        .set_parse_action(interpreter.create_parameter)
    )

    # Define numbers
    number = pyparsing_common.number.set_name("number").set_parse_action(interpreter.create_number)

    # Define functions
    function = Forward().set_name("function")
    expression = Forward().set_name("expression")
    arguments = delimited_list(expression, delim=",").set_name("function arguments")
    lpar, rpar = map(Suppress, "()")
    function_name = Combine(Opt(routine_path_prefix) + name)
    function <<= (
        (Combine(function_name + lpar) + Group(Opt(arguments)) + rpar)
        .set_name("function")
        .set_parse_action(interpreter.create_function)
    )

    # Define binary expressions
    add, sub, mul, true_div, exp_caret, mod = map(Literal, "+-*/^%")
    floor_div = Literal("//")
    add_sub_op = add | sub
    mul_div_mod_op = mul | floor_div | true_div | mod
    exp_op = exp_caret | Combine("**")
    factor = Forward().set_name("factor")
    parenthesised_expression = (lpar + expression + rpar).set_name("parenthesised expression")
    atom = (
        (ZeroOrMore(add_sub_op) + (function | parameter | number | parenthesised_expression))
        .set_parse_action(interpreter.create_unary_atom)
        .set_name("atom")
    )
    factor <<= (atom + ZeroOrMore(Group(exp_op + factor))).set_name("factor")
    term = (factor + ZeroOrMore(Group(mul_div_mod_op + factor))).set_name("term")
    expression <<= (
        (term + ZeroOrMore(Group(add_sub_op + term)))
        .set_name("expression")
        .set_parse_action(interpreter.create_expression)
    )

    # Define complete expression
    complete_expression = (Suppress(StringStart()) + expression + Suppress(StringEnd())).set_name("complete expression")

    return complete_expression


class Interpreter(ABC):
    """Abstract base class for interpreting the Bartiq grammar."""

    def __init__(self, debug=False):
        """Initialise the interpreter.

        Args:
            debug (bool, optional): If ``True``, debug information is printed for the interpreter. Default is ``False``.
        """
        self.debug = debug

    @abstractmethod
    def create_parameter(self, tokens):
        """Abstract method for interpreting parameter."""

    @abstractmethod
    def create_number(self, tokens):
        """Abstract method for interpreting numbers."""

    @abstractmethod
    def create_function(self, tokens):
        """Abstract method for interpreting functions."""

    @abstractmethod
    def create_expression(self, tokens):
        """Abstract method for interpreting expressions."""

    @abstractmethod
    def create_unary_atom(self, tokens):
        """Abstract method for interpreting atoms with unary operator prefixes."""


def debuggable(method):
    """A decorator for making interpreter methods easily debuggable."""

    @wraps(method)
    def debuggable_method(self, tokens):
        if self.debug:
            print(method.__name__)
            tokens_str = [token.as_list() if isinstance(token, ParseResults) else token for token in tokens]
            print(f"tokens={tokens_str}")

        output = method(self, tokens)

        if self.debug:
            print(f"parsed as: {output}\n")

        return output

    return debuggable_method
