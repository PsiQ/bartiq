"""
..  Copyright © 2023-2024 PsiQuantum Corp.  All rights reserved.
    PSIQUANTUM CORP. CONFIDENTIAL
    This file includes unpublished proprietary source code of PsiQuantum Corp.
    The copyright notice above does not evidence any actual or intended publication
    of such source code. Disclosure of this source code or any related proprietary
    information is strictly prohibited without the express written permission of
    PsiQuantum Corp.

Tests for the sympy interpreter.
"""

import string

import pytest
from sympy import (
    Float,
    Function,
    Heaviside,
    Integer,
    LambertW,
    Min,
    Mod,
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
    prod,
    re,
    sec,
    sech,
    sin,
    sinh,
    sqrt,
    tan,
    tanh,
)
from sympy.codegen.cfunctions import exp2, log2, log10
from sympy.core.numbers import S as sympy_constants

from bartiq.symbolics.sympy_backend import parse_to_sympy
from bartiq.symbolics.sympy_interpreter import (
    SPECIAL_PARAMS,
    Max,
    Round,
    multiplicity,
    nlz,
)
from bartiq.symbolics.sympy_serializer import serialize_expression


def define_alphabet():
    """Build an alphabet to test over."""
    # Define english alphabet
    english_alphabet_full = list(string.ascii_letters)

    # Define greek alphabet
    greek_alphabet_upper = [
        "Alpha",
        "Beta",
        # "Gamma", # Removing gamma as there exists a special function with name "gamma"
        "Delta",
        "Epsilon",
        "Zeta",
        "Eta",
        "Theta",
        "Iota",
        "Kappa",
        "Lambda",
        "Mu",
        "Nu",
        "Xi",
        "Omicron",
        "Pi",
        "Rho",
        "Sigma",
        "Tau",
        "Upsilon",
        "Phi",
        "Chi",
        "Psi",
        "Omega",
    ]
    greek_alphabet_lower = list(map(str.lower, greek_alphabet_upper))
    greek_alphabet_full = greek_alphabet_upper + greek_alphabet_lower

    # Define Hebrew alphabet
    hebrew_alphabet = [
        "aleph",
        "bet",
        "gimel",
        "dalet",
        "he",
        "waw",
        "vav",
        "zayin",
        "chet",
        "tet",
        "yod",
        "kaf",
        "lamed",
        "mem",
        "nun",
        "samech",
        "ayin",
        "pe",
        "tsadi",
        "qof",
        "resh",
        "shin",
        "tav",
    ]

    alphabet_full = english_alphabet_full + greek_alphabet_full + hebrew_alphabet
    alphabet_supported = list(filter(lambda letter: letter not in SPECIAL_PARAMS, alphabet_full))

    return alphabet_supported


def make_alphabet_test_cases(use):
    """Build sets of alphabetic test cases based on whether we're using them for symbols or functions."""
    alphabet = define_alphabet()

    # Define alphabet test cases
    test_cases_no_paths = [make_alphabet_test_case(letter, use) for letter in alphabet]

    alphabet_with_paths = list(map(add_routine_path, alphabet))
    # NOTE: functions can't be port-pathed, but symbols can be
    if use == "symbol":
        alphabet_with_paths += list(map(add_port_path, alphabet))
    test_cases_with_paths = [make_alphabet_test_case(letter, use) for letter in alphabet_with_paths]

    return [
        *test_cases_no_paths,
        *test_cases_with_paths,
    ]


def make_alphabet_test_case(letter, use):
    """Make a single letter symbol or function test case."""
    # Build the expressions' elements
    if use == "symbol":
        string_x = letter
        sympy_x = Symbol(letter)
    elif use == "function":
        string_x = f"{letter}(0)"
        sympy_x = Function(letter)(0)
    else:
        raise ValueError(f"Unknown use {use}.")

    # Build the expressions
    string_expression = make_string_expression(string_x)
    sympy_expression = make_sympy_expression(sympy_x)

    return (string_expression, sympy_expression)


def make_string_expression(x):
    """Create an expression string that contains all the possible operators."""
    return f"{x} + {x} * {x} - {x} / {x} ^ {x} % {x}"


def make_sympy_expression(x):
    """Create a sympy expression that contains all the possible operators."""
    return x + x * x - x / x**x % x


def add_port_path(symbol):
    return f"some.other.#port.{symbol}"


def add_routine_path(symbol):
    return f"some.other.routine.{symbol}"


x = Symbol("x")
y = Symbol("y")
z = Symbol("z")
Foo = Function("Foo")
Bar = Function("Bar")
Pi = sympy_constants.Pi
E = sympy_constants.Exp1

PARSE_TEST_CASES = [
    # Dot-separated variables
    ("a.b.c", Symbol("a.b.c")),
    # Dot-separated variables with annoying substring nonsense
    ("b.c + a.b.c.d", Symbol("b.c") + Symbol("a.b.c.d")),
    # Dot-separated variables, but with float
    ("3.141 * a.b.c", 3.141 * Symbol("a.b.c")),
    # Hash-prefixed variables
    ("#foo.bar", Symbol("#foo.bar")),
    # Deep hash-path variables
    ("some.other.routines.#foo.bar", Symbol("some.other.routines.#foo.bar")),
    # Deep lambda
    ("some.other.routines.lambda", Symbol("some.other.routines.lambda")),
    # Big-O notation
    ("O(n) + O(m)", Function("O")(Symbol("n")) + Function("O")(Symbol("m"))),
    # Mmmmmm, three-tiered pi
    ("Pi * pi * PI", Symbol("Pi") * Symbol("pi") * Pi),
    # Ignore subscripts
    ("N_x + N_y + N_z + N", Symbol("N_x") + Symbol("N_y") + Symbol("N_z") + Symbol("N")),
    # Can use all letters of the English and Greek alphabets (with and without path prefixes) as Symbol
    *make_alphabet_test_cases(use="symbol"),
    # Can use all letters of the English and Greek alphabets (with and without path prefixes) as functions
    *make_alphabet_test_cases(use="function"),
    # Numbers
    ("9", 9),
    ("-9", -9),
    ("--9", 9),
    ("+9", 9),
    ("++9", 9),
    ("+-+-+-9", -9),
    ("42", 42),
    ("3.141", 3.141),
    ("9 + 3 + 6", 18),
    ("9 + 3 / 11", Rational(102, 11)),
    ("(9 + 3)", 12),
    ("(9 + 3) / 11", Rational(12, 11)),
    ("9 - 12 - 6", -9),
    ("9 - (12 - 6)", 3),
    ("2 * 3.14159", 6.28318),
    ("3.141 * 3.141 / 10", Float(0.9865881)),
    ("PI * PI / 10", Pi * Pi / 10),
    ("PI ^ 2", Pi**2),
    ("round(PI ^ 2)", 10),
    ("6.02E23 * 8.048", 4.844896e24),
    ("sin(PI / 2)", 1),
    ("10 + sin(PI / 4) ^ 2", Rational(21, 2)),
    ("exp(0)", 1),
    ("exp(1)", E),
    ("2 ^ 3 ^ 2", 512),
    ("(2 ^ 3) ^ 2", 64),
    ("2 ^ 3 + 2", 10),
    ("2 ^ 3 + 5", 13),
    ("2 ^ 9", 512),
    ("sgn(-2)", -1),
    ("sgn(0)", 0),
    ("sgn(0.1)", 1),
    ("sgn(cos(PI / 4))", 1),
    ("sgn(cos(PI / 2))", 0),
    ("sgn(cos(PI * 3 / 4))", -1),
    ("+(sgn(cos(PI / 4)))", 1),
    ("-(sgn(cos(PI / 4)))", -1),
    ("10 / 3 // 3", 1),
    # Special functions
    ("mod(x, y)", Mod(x, y)),
    ("max()", sympy_constants.NegativeInfinity),
    ("max(x, 1)", Max(x, 1)),
    ("max(-42, 42, 0)", 42),
    ("min()", sympy_constants.Infinity),
    ("min(x, 1)", Min(x, 1)),
    ("min(-42, 42, 0)", -42),
    ("sum()", 0),
    ("sum(-1, 42, 0)", 41),
    ("sum(-1, 42, x)", 41 + x),
    ("sum_over(x^2, x, 1, y)", Sum(x**2, (x, 1, y))),
    ("prod_over(x^2, x, 1, y)", Product(x**2, (x, 1, y))),
    ("round(1.49999999)", 1),
    ("round(1.50000001)", 2),
    ("round(x)", Round(x)),
    ("abs(0)", 0),
    ("abs(-42)", 42),
    ("abs(42)", 42),
    ("abs(-x)", abs(x)),
    ("abs(x)", abs(x)),
    ("sin(x)", sin(x)),
    ("cos(x)", cos(x)),
    ("tan(x)", tan(x)),
    ("cot(x)", cot(x)),
    ("cot(x)", cot(x)),
    ("sec(x)", sec(x)),
    ("csc(x)", csc(x)),
    ("asin(x)", asin(x)),
    ("acos(x)", acos(x)),
    ("atan(x)", atan(x)),
    ("acot(x)", acot(x)),
    ("asec(x)", asec(x)),
    ("acsc(x)", acsc(x)),
    ("sinh(x)", sinh(x)),
    ("cosh(x)", cosh(x)),
    ("tanh(x)", tanh(x)),
    ("coth(x)", coth(x)),
    ("sech(x)", sech(x)),
    ("csch(x)", csch(x)),
    ("asinh(x)", asinh(x)),
    ("acosh(x)", acosh(x)),
    ("atanh(x)", atanh(x)),
    ("acoth(x)", acoth(x)),
    ("asech(x)", asech(x)),
    ("acsch(x)", acsch(x)),
    ("sqrt(x)", sqrt(x)),
    ("cbrt(x)", cbrt(x)),
    ("prod()", 1),
    ("prod(x)", x),
    ("prod(x, y)", prod([x, y])),
    ("exp(x)", exp(x)),
    ("log(x)", log(x)),
    ("ceil(x)", ceiling(x)),
    ("floor(x)", floor(x)),
    ("re(x)", re(x)),
    ("im(x)", im(x)),
    ("frac(x)", frac(x)),
    ("exp2(x)", exp2(x)),
    ("log2(x)", log2(x)),
    ("log10(x)", log10(x)),
    ("LambertW(x)", LambertW(x)),
    ("LambertW(x, y)", LambertW(x, y)),
    ("gamma(x)", gamma(x)),
    ("Heaviside(x)", Heaviside(x)),
    # Parameters
    ("x", x),
    ("some.path.to.param", Symbol("some.path.to.param")),
    ("some.path.to.#port.param", Symbol("some.path.to.#port.param")),
    # Functions
    ("Foo()", Foo()),
    ("Foo(x)", Foo(x)),
    ("Foo(x, y)", Foo(x, y)),
    ("some.path.to.Foo()", Function("some.path.to.Foo")()),
    # Simply binary expressions
    ("x + y", x + y),
    ("x+y", x + y),
    ("Foo() + y", Foo() + y),
    ("Foo() + Bar()", Foo() + Bar()),
    ("Foo(x, y) + Bar(x + y)", Foo(x, y) + Bar(x + y)),
    ("a.x + b.y", Symbol("a.x") + Symbol("b.y")),
    ("a.b.x + c.d.Foo()", Symbol("a.b.x") + Function("c.d.Foo")()),
    ("a.b.#c.x + c.d.Foo()", Symbol("a.b.#c.x") + Function("c.d.Foo")()),
    # Operator precedence
    ("x + y + z", x + y + z),
    ("x - y - z", x - y - z),
    ("x * y * z", x * y * z),
    ("x / y / z", (x / y) / z),
    ("x // y // z", (x // y) // z),
    ("x ^ y ^ z", x ** (y**z)),
    ("x + y - z", ((x + y) - z)),
    ("x * y / z", ((x * y) / z)),
    ("x / y * z", ((x / y) * z)),
    ("x * y // z", ((x * y) // z)),
    ("x // y * z", ((x // y) * z)),
    # Pathological cases
    ("x / y // z", (x / y) // z),
    ("x ^ y ** z", x ** (y**z)),
    # Special functions
    ("multiplicity(x, y)", multiplicity(x, y)),
    ("multiplicity(x, 2)", multiplicity(x, 2)),
    ("multiplicity(2, y)", multiplicity(2, y)),
    ("multiplicity(2, 40)", multiplicity(2, 40)),
    # Expressions with wildcard
    ("sum(~.X)", Function("sum")(Symbol("~.X"))),
    ("max(~.X)", Function("max")(Symbol("~.X"))),
    ("min(~.X)", Function("min")(Symbol("~.X"))),
    # Expressions containing "in" keyword
    ("in", Symbol("in")),
    ("a.in", Symbol("a.in")),
    ("a.in.b", Symbol("a.in.b")),
    ("in.b", Symbol("in.b")),
    # Lambda as a part of function name
    ("calc_lambda(x)", Function("calc_lambda")(Symbol("x"))),
]


@pytest.mark.parametrize("expression, expected_sympy_expression", PARSE_TEST_CASES)
@pytest.mark.filterwarnings(r"ignore:Using \^ operator to denote exponentiation is deprecated\.")
@pytest.mark.filterwarnings(r"ignore:Results for using BigO with multiple #variables might be unreliable\.")
def test_parse_to_sympy(expression, expected_sympy_expression):
    """Tests for the sympy expression parser."""
    sympy_expression = parse_to_sympy(expression, debug=True)
    assert sympy_expression == expected_sympy_expression

    # Test round-trip via cast to string
    new_expression = serialize_expression(sympy_expression)
    sympy_expression = parse_to_sympy(new_expression)
    assert sympy_expression == expected_sympy_expression


def test_sympy_interpreter_warns_about_using_caret_sign_for_exponentiation():
    expr = "x ^ 2"
    with pytest.warns(match=r"Using \^ operator to denote exponentiation is deprecated\."):
        _ = parse_to_sympy(expr)


@pytest.mark.parametrize(
    "value,expected,raises,match",
    [
        (0, 0, None, None),
        (1, 0, None, None),
        (2, 1, None, None),
        (4, 2, None, None),
        (8, 3, None, None),
        (16, 4, None, None),
        (Integer(0), 0, None, None),
        (Integer(1), 0, None, None),
        (Integer(2), 1, None, None),
        (Integer(4), 2, None, None),
        (Integer(8), 3, None, None),
        (Integer(16), 4, None, None),
        (1.5, None, TypeError, r"nlz requires integer argument; found 1\.5+"),
        (10.0, None, TypeError, r"nlz requires integer argument; found 10\.0+"),
        (Symbol("x"), nlz(Symbol("x")), None, None),
        (-1, None, ValueError, "nlz requires non-negative integer; found -1"),
        (Integer(-5), None, ValueError, "nlz requires non-negative integer; found -5"),
    ],
)
def test_nlz_parametrized(value, expected, raises, match):
    if raises:
        with pytest.raises(raises, match=match):
            nlz(value)
    else:
        assert nlz(value) == expected
