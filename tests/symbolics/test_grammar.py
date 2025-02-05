"""
..  Copyright © 2023-2024 PsiQuantum Corp.  All rights reserved.
    PSIQUANTUM CORP. CONFIDENTIAL
    This file includes unpublished proprietary source code of PsiQuantum Corp.
    The copyright notice above does not evidence any actual or intended publication
    of such source code. Disclosure of this source code or any related proprietary
    information is strictly prohibited without the express written permission of
    PsiQuantum Corp.

Tests for our parsing grammar.
"""

import pytest

from bartiq.symbolics.grammar import Interpreter, debuggable


@pytest.mark.parametrize(
    "expression, expected_error",
    [
        # No empty expressions
        ("", "  (at char 0)"),
        # No param-less port paths
        ("some.path.to.#port", "found '.'  (at char 4)"),
        # No doubled port paths
        ("some.path.#to.#port.x", "found '#'  (at char 14)"),
        # No port functions
        ("some.path.to.#port.Foo()", "found '('  (at char 22)"),
        # No whitespace between path fragments
        ("some path.to.param", "found 'path'  (at char 5)"),
        # No whitespace between function name and parens
        ("foo ()", "found '('  (at char 4)"),
        # Double dot in path
        ("a..b.c", "found '.'  (at char 1)"),
        # Hash-dot in path
        ("a#.b.c", "found '#'  (at char 1)"),
        # Dot-separated variables, but with a sneaky float in there
        ("3.141 * a.3.141.b", "found '.'  (at char 9)"),
    ],
)
class DummyInterpreter(Interpreter):
    """An interpreter stub for testing the parser."""

    @debuggable
    def create_parameter(self, tokens):
        """Dummy method."""

    @debuggable
    def create_number(self, tokens):
        """Dummy method."""

    @debuggable
    def create_function(self, tokens):
        """Dummy method."""
