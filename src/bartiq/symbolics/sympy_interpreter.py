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
import warnings
from typing import Any, Callable

from sympy import (
    Float,
    Function,
    Heaviside,
    Integer,
    LambertW,
    Min,
    Mod,
    Number,
    Product,
    Rational,
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
from sympy.core.sorting import ordered

from .interpreter import Interpreter, debuggable

WILDCARD_CHARACTER: str = "~"

BINARY_OPS = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
    "//": operator.floordiv,
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
        """Define the delayed evaluation in the case where the input is not yet defined.

        Raises:
            TypeError: If the input is not a number or if ndigits is not an integer.
        """
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

    @staticmethod
    def _imp_(x, ndigits=None):
        return round(x, ndigits)


class multiplicity(Function):
    @classmethod
    def eval(cls, p, n):
        return orig_multiplicity(p, n) if isinstance(p, Integer) and isinstance(n, Integer) else None

    @staticmethod
    def _imp_(p, n):
        if not isinstance(p, int) or not isinstance(n, int):
            msg = f"Both arguments to multiplicity have to be integers but {p} and {n} was passed."
            raise ValueError(msg)
        return int(multiplicity(p, n))


class ntz(Function):
    @classmethod
    def eval(cls, n):
        """Returns the number of trailing zeros in the binary representation of n.

        Only defined for non-negative integers.
        For n = 0 returns -1.
        For symbolic input, returns unevaluated ntz(n).

        Raises:
            TypeError: If input is not an integer (when numeric).
            ValueError: If input is a negative integer.
        """
        # Numeric evaluation
        if n.is_number:
            if not n.is_integer:
                raise TypeError(f"ntz requires integer argument; found {n}")
            n = int(n)
            if n < 0:
                raise ValueError(f"ntz requires non-negative integer; found {n}")
            return (n & -n).bit_length() - 1

    @staticmethod
    def _imp_(n):
        try:
            m = int(n)
            if n != m:
                raise TypeError()  # This is to trigger the one below
            n = m
        except TypeError:
            raise TypeError(f"ntz requires integer argument; found {n}")
        if n < 0:
            raise ValueError(f"ntz requires non-negative integer; found {n}")
        return (n & -n).bit_length() - 1


class nlz(ntz):
    """Deprecated alias for ntz; use ntz instead."""

    def __new__(cls, n, *args, **kwargs):
        warnings.warn(
            "nlz is deprecated and will be removed in a future release; use ntz instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return super().__new__(cls, n, *args, **kwargs)


class Max(Function):
    """A custom implementation of Max.

    We use a custom Max because for our use cases, Sympy's simplification efforts are usually
    fruitless. Not doing any advanced simplifications saves us significant amount of time,
    especially when computing highwater with lots of nested maximums.
    """

    def __new__(cls, *args, **assumptions):
        args = ordered(set(args))
        return Function.__new__(cls, *args, **assumptions)

    @classmethod
    def eval(cls, *args):

        if not args:
            return sympy_constants.NegativeInfinity
        elif len(args) == 1:
            return args[0]
        elif all(isinstance(n, (Integer, Float, Rational)) for n in args):
            return max(args)


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
    "log10": log10,
    "lambertw": LambertW,
    "gamma": gamma,
    "heaviside": Heaviside,
    "multiplicity": multiplicity,
    "ntz": ntz,
    "nlz": nlz,
}


class SympyInterpreter(Interpreter):
    """An interpreter for parsing to Sympy expressions."""

    def __init__(
        self,
        function_overrides: dict[str, Callable[[Any], Any]],
        debug=False,
    ):
        super().__init__(debug)
        self.function_map = SPECIAL_FUNCS | function_overrides

    @debuggable
    def create_number(self, tokens) -> Number:
        """Return a sympy number."""
        return Number(tokens[0])

    @debuggable
    def create_parameter(self, tokens) -> Symbol:
        """Return a sympy Symbol."""
        param = tokens[0]
        if param in SPECIAL_PARAMS:
            return SPECIAL_PARAMS[param]
        return Symbol(param)

    @debuggable
    def create_function(self, tokens: tuple[str, Any]) -> Function:
        """Return a sympy function.

        If the function arguments contain a wildcard, we delay evaluation as sympy may
        fail to evaluate it correctly, e.g. sum(~X) being evaluated to ~.X.

        If the function is known, apply that function.

        If neither of these cases trigger, cast to a generic function.

        """
        name, args = tokens
        if _contains_wildcard_arg(args):
            func = Function(name)
        elif known_function := self.function_map.get(name.lower(), None):
            func = known_function
        else:
            func = Function(name)
        return func(*args)


def _contains_wildcard_arg(args):
    """Returns ``True`` if any argument contains the wildcard character."""
    return any(WILDCARD_CHARACTER in str(arg) for arg in args)
