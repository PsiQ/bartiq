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

import operator
from functools import lru_cache
from warnings import warn

from sympy import (
    Function,
    Heaviside,
    Integer,
    LambertW,
    Max,
    Min,
    Mod,
    Number,
    Product,
    Sum,
    Symbol,
    acos,
    acosh,
    acot,
    acoth,
    acsc,
    acsch,
    asec,
    asech,
    asin,
    asinh,
    atan,
    atanh,
    cbrt,
    ceiling,
    cos,
    cosh,
    cot,
    coth,
    csc,
    csch,
    exp,
    floor,
    frac,
    gamma,
    im,
    log,
)
from sympy import multiplicity as orig_multiplicity
from sympy import prod, re, sec, sech, sin, sinh, sqrt, tan, tanh
from sympy.codegen.cfunctions import exp2, log2, log10
from sympy.core.numbers import S as sympy_constants

from .grammar import WILDCARD_CHARACTER, Interpreter, debuggable, make_parser


@lru_cache
def parse_to_sympy(string, debug=False):
    """Parses a string to a sympy expression.

    Args:
        string (str): The string to parse.
        debug (bool, optional): If ``True``, debug information is printed on failure. Default is ``False``.

    Returns:
        sympy.Basic: Some sympy expression.
    """
    warn(
        "Legacy, pyparsing based sympy parser is deprecated, use default sympy_backend when calling compile_routine "
        "and evaluate",
        DeprecationWarning,
    )
    interpreter = SympyInterpreter(debug=debug)
    parser = make_parser(interpreter)
    return parser.parse_string(string)[0]


BINARY_OPS = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
    "//": operator.floordiv,
    "^": operator.pow,
    "**": operator.pow,
    "%": operator.mod,
}

SPECIAL_PARAMS = {
    "PI": sympy_constants.Pi,
    "Infinity": sympy_constants.Infinity,
    "NegativeInfinity": sympy_constants.NegativeInfinity,
    "ComplexInfinity": sympy_constants.ComplexInfinity,
    "oo": sympy_constants.Infinity,
    "noo": sympy_constants.NegativeInfinity,
    "zoo": sympy_constants.ComplexInfinity,
}

EPSILON = 1e-12


def better_prod(*args):
    """Defines a version of product which has sane zero- and one-argument defaults."""
    if len(args) == 0:
        return 1
    elif len(args) == 1:
        return args[0]
    return prod(args)


class Round(Function):
    """Defines a delayed-evaluation version of Round."""

    @classmethod
    def eval(cls, x, ndigits=None):
        """Define the function's immediate evaluation in the case where the input is a number."""
        # Evaluate for explicit number x
        if x.is_number:
            if ndigits is None:
                return round(x)
            elif ndigits.is_integer:
                return round(x, ndigits=ndigits)

    def doit(self, deep=True, **hints):
        """Define the delayed evaluation in the case where the input is not yet defined."""
        x, *other_args = self.args

        assert len(other_args) <= 1, f"Expected at most only a single extra argument; found {other_args}."
        ndigits = other_args[0] if other_args else Number(0)

        # If deep, propagate the evaluation downwards
        if deep:
            x = x.doit(deep=True, **hints)
            ndigits = ndigits.doit(deep=True, **hints)

        # Check we're ready to boogie
        # NOTE: don't use ``not x.is_number`` to deal with Nones. See below for more info:
        # https://docs.sympy.org/latest/guides/custom-functions.html#best-practices-for-eval
        if not x.is_number:
            raise TypeError(f"Input x must be a number; found {x}")
        if not ndigits.is_integer:
            raise TypeError(f"Input ndigits must be an integer; found {ndigits}")

        # Boogie down
        return round(x, ndigits=ndigits)


class multiplicity(Function):
    @classmethod
    def eval(cls, p, n):
        return orig_multiplicity(p, n) if isinstance(p, Integer) and isinstance(n, Integer) else None


class nlz(Function):
    @classmethod
    def eval(cls, n):
        if isinstance(n, Integer):
            n = int(n)
            return (n & -n).bit_length() - 1


SPECIAL_FUNCS = {
    "mod": Mod,
    "max": Max,
    "min": Min,
    "sum": lambda *args: sum(args) if args else 0,
    "sum_over": lambda x, i, start, end: Sum(x, (i, start, end)),
    "prod_over": lambda x, i, start, end: Product(x, (i, start, end)),
    "round": Round,
    "abs": abs,
    "sgn": lambda a: -1 if a < -EPSILON else 1 if a > EPSILON else 0,
    "sin": sin,
    "cos": cos,
    "tan": tan,
    "cot": cot,
    "sec": sec,
    "csc": csc,
    "asin": asin,
    "acos": acos,
    "atan": atan,
    "acot": acot,
    "asec": asec,
    "acsc": acsc,
    "sinh": sinh,
    "cosh": cosh,
    "tanh": tanh,
    "coth": coth,
    "sech": sech,
    "csch": csch,
    "asinh": asinh,
    "acosh": acosh,
    "atanh": atanh,
    "acoth": acoth,
    "asech": asech,
    "acsch": acsch,
    "sqrt": sqrt,
    "cbrt": cbrt,
    "prod": better_prod,
    "exp": exp,
    "log": log,
    "ceil": ceiling,
    "ceiling": ceiling,
    "floor": floor,
    "re": re,
    "im": im,
    "frac": frac,
    "exp2": exp2,
    "log2": log2,
    "log_2": log2,
    "log10": log10,
    "log_10": log10,
    "lambertw": LambertW,
    "gamma": gamma,
    "heaviside": Heaviside,
    "multiplicity": multiplicity,
    "nlz": nlz,
}


class SympyInterpreter(Interpreter):
    """An interpreter for parsing to Sympy expressions."""

    @debuggable
    def create_number(self, tokens):
        """Return a sympy number."""
        return Number(tokens[0])

    @debuggable
    def create_parameter(self, tokens):
        """Return a sympy Symbol."""
        param = tokens[0]
        if param in SPECIAL_PARAMS:
            return SPECIAL_PARAMS[param]
        return Symbol(param)

    @debuggable
    def create_function(self, tokens):
        """Return a sympy function."""
        name, args = tokens

        # Case 1: if the function has a wildcard, don't evaluate it yet
        # We do this because the wildcard is really a single symbol placeholder for zero or more others, and so sympy
        # will fail to evaluate it correctly, e.g. sum(~.X) being evaluated to ~.X
        if _contains_wildcard_arg(args):
            func = Function(name)

        # Case 2: If a known function, use that
        elif name.lower() in SPECIAL_FUNCS:
            func = SPECIAL_FUNCS[name.lower()]

        # Case 3: If nothing else works, just cast to a generic function
        else:
            func = Function(name)

        return func(*args)

    @debuggable
    def create_expression(self, tokens):
        """Return a sympy expression."""
        lhs = tokens.pop(0)
        while tokens:
            op, *rhs = tokens.pop(0)
            rhs = self.create_expression(rhs)
            lhs = BINARY_OPS[op](lhs, rhs)
        return lhs

    @debuggable
    def create_unary_atom(self, tokens):
        """Return a non-unary atom."""
        prefactor = 1
        while (token := tokens.pop(0)) in ["+", "-"]:
            prefactor *= int(f"{token}1")
        assert len(tokens) == 0, f"Expected a single token remaining, found {tokens}."
        return prefactor * token


def _contains_wildcard_arg(args):
    """Returns ``True`` if any argument contains the wildcard character."""
    return any(WILDCARD_CHARACTER in str(arg) for arg in args)
