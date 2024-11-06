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

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import singledispatch
from typing import Callable, Generic, Literal, TypeVar

from qref.schema_v1 import (
    ArithmeticSequenceV1,
    ClosedFormSequenceV1,
    ConstantSequenceV1,
    CustomSequenceV1,
    GeometricSequenceV1,
    RepetitionV1,
)

from .errors import BartiqCompilationError
from .symbolics.backend import SymbolicBackend, TExpr

# We need it because type `T` doesn't define any arithmetic operations.
# mypy: disable-error-code="operator"
T = TypeVar("T")


FunctionsMap = dict[str, Callable[[TExpr[T]], TExpr[T]]]


# TODO: copied from _common.py
# TODO: perhaps move to backend and rename to sth reasonable?
def _evaluate_and_define_functions(
    expr: TExpr[T], inputs: dict[str, TExpr[T]], custom_funcs: FunctionsMap[T], backend: SymbolicBackend[T]
) -> TExpr[T]:
    expr = backend.substitute_all(expr, inputs)
    for func_name, func in custom_funcs.items():
        expr = backend.define_function(expr, func_name, func)
    return value if (value := backend.value_of(expr)) is not None else expr


@dataclass(frozen=True)
class ConstantSequence(Generic[T]):
    """Constant sequence.
    In a constant sequence we repeat an element `multiplier` times in each iteration."""

    type: Literal["constant"]
    multiplier: TExpr[T]

    def get_sum(self, expr: TExpr[T], count: TExpr[T], backend: SymbolicBackend[T]) -> TExpr[T]:
        return count * self.multiplier * expr

    def get_prod(self, expr: TExpr[T], count: TExpr[T], backend: SymbolicBackend[T]) -> TExpr[T]:
        return expr ** (count * self.multiplier)

    def substitute_symbols(
        self, inputs: dict[str, TExpr[T]], backend: SymbolicBackend[T], functions_map=None
    ) -> ConstantSequence[T]:
        if functions_map is None:
            functions_map = {}
        new_multiplier = _evaluate_and_define_functions(self.multiplier, inputs, functions_map, backend)
        return replace(self, multiplier=new_multiplier)


@dataclass(frozen=True)
class ArithmeticSequence(Generic[T]):
    """Arithmetic sequence.
    In an arithmetic sequence we start from `initial_term` repetitions of an element,
    and in each iteration we increase it by `difference`."""

    type: Literal["arithmetic"]
    initial_term: TExpr[T]
    difference: TExpr[T]

    def get_sum(self, expr: TExpr[T], count: TExpr[T], backend: SymbolicBackend[T]) -> TExpr[T]:
        return 0.5 * count * (2 * self.initial_term + (count - 1) * self.difference) * expr

    def get_prod(self, expr: TExpr[T], count: TExpr[T], backend: SymbolicBackend[T]) -> TExpr[T]:
        return (
            self.difference**count
            * backend.as_expression(f"gamma({backend.serialize(self.initial_term / self.difference + count)})")
            / backend.as_expression(f"gamma({backend.serialize(self.initial_term / self.difference)})")
            * expr**count
        )

    def substitute_symbols(
        self, inputs: dict[str, TExpr[T]], backend: SymbolicBackend[T], functions_map=None
    ) -> ArithmeticSequence[T]:
        if functions_map is None:
            functions_map = {}
        new_initial_term = _evaluate_and_define_functions(self.initial_term, inputs, functions_map, backend)
        new_difference = _evaluate_and_define_functions(self.difference, inputs, functions_map, backend)
        return replace(self, initial_term=new_initial_term, difference=new_difference)


@dataclass(frozen=True)
class GeometricSequence(Generic[T]):
    """Geometric sequence.
    In a geometric sequence we start from 1 repetition of an element,
    and in each iteration we multiply it by `ratio`."""

    type: Literal["geometric"]
    ratio: TExpr[T]

    def get_sum(self, expr: TExpr[T], count: TExpr[T], backend: SymbolicBackend[T]) -> TExpr[T]:
        return expr * (1 - self.ratio ** (count)) / (1 - self.ratio)

    def get_prod(self, expr: TExpr[T], count: TExpr[T], backend: SymbolicBackend[T]) -> TExpr[T]:
        return expr * (count + 1) * self.ratio ** ((count) * (count + 1) / 2)

    def substitute_symbols(self, inputs, backend: SymbolicBackend[T], functions_map=None) -> GeometricSequence[T]:
        if functions_map is None:
            functions_map = {}
        new_ratio = _evaluate_and_define_functions(self.ratio, inputs, functions_map, backend)
        return replace(self, ratio=new_ratio)


@dataclass(frozen=True)
class ClosedFormSequence(Generic[T]):
    """Sequence with known closed-form for a sum or product.
    If `sum`/`prod` are specified, they can be used to calculate these values for a given sequence.
    Expressions for `sum`/`prod` should use `num_terms_symbol` to represent the total number of terms."""

    type: Literal["closed_form"]
    sum: TExpr[T] | None
    prod: TExpr[T] | None
    num_terms_symbol: TExpr[T]

    def get_sum(self, expr: TExpr[T], count: TExpr[T], backend: SymbolicBackend[T]) -> TExpr[T]:
        if self.sum is not None:
            inputs = {backend.serialize(self.num_terms_symbol): count}
            return expr * _evaluate_and_define_functions(self.sum, inputs, {}, backend)
        else:
            raise BartiqCompilationError("Cannot evaluate sum for ClosedFormSequence, as sum is not defined.")

    def get_prod(self, expr: TExpr[T], count: TExpr[T], backend: SymbolicBackend[T]) -> TExpr[T]:
        if self.prod is not None:
            inputs = {backend.serialize(self.num_terms_symbol): count}
            return expr * _evaluate_and_define_functions(self.prod, inputs, {}, backend)
        else:
            raise BartiqCompilationError("Cannot evaluate product for ClosedFormSequence, as sum is not defined.")

    def substitute_symbols(
        self, inputs: dict[str, TExpr[T]], backend: SymbolicBackend[T], functions_map=None
    ) -> ArithmeticSequence[T]:
        if functions_map is None:
            functions_map = {}
        if self.sum is not None:
            new_sum = _evaluate_and_define_functions(self.sum, inputs, functions_map, backend)
        if self.prod is not None:
            new_prod = _evaluate_and_define_functions(self.prod, inputs, functions_map, backend)
        new_num_terms = _evaluate_and_define_functions(self.num_terms_symbol, inputs, functions_map, backend)

        return replace(self, sum=new_sum, prod=new_prod, num_terms_symbol=new_num_terms)


@dataclass(frozen=True)
class CustomSequence(Generic[T]):
    """Custom sequence.
    For sequences which do not fall into categories defined in other classes, one can use a custom representation.
    It is an explicit representation of a sequence where `term_expression` defines the expression for each term
    in the sequence and `iterator_symbol` is used to represent number of the iteration."""

    type: Literal["custom"]
    term_expression: TExpr[T]
    iterator_symbol: str = "i"

    def get_sum(self, expr: TExpr[T], count: TExpr[T], backend: SymbolicBackend[T]) -> TExpr[T]:
        return backend.sum(self.term_expression * expr, self.iterator_symbol, 0, count - 1)

    def get_prod(self, expr: TExpr[T], count: TExpr[T], backend: SymbolicBackend[T]) -> TExpr[T]:
        return backend.prod(self.term_expression * expr, self.iterator_symbol, 0, count - 1)

    def substitute_symbols(
        self, inputs: dict[str, TExpr[T]], backend: SymbolicBackend[T], functions_map=None
    ) -> ArithmeticSequence[T]:
        if functions_map is None:
            functions_map = {}

        if self.iterator_symbol in inputs.values():
            raise BartiqCompilationError(
                f"Tried to replace symbol that's used as iterator symbol in a sequence: {self.iterator_symbol}."
            )

        new_term_expression = _evaluate_and_define_functions(self.term_expression, inputs, functions_map, backend)
        return replace(self, term_expression=new_term_expression)


@dataclass(frozen=True)
class Repetition(Generic[T]):
    """Defines rules for repeated structures within a routine."""

    count: TExpr[T]
    sequence: ConstantSequence | ArithmeticSequence | GeometricSequence | ClosedFormSequence | CustomSequence

    def sequence_sum(self, expr: TExpr[T], backend: SymbolicBackend[T]) -> TExpr[T]:
        """Returns an expression representing a sum of a sequence."""
        return self.sequence.get_sum(expr, self.count, backend)

    def sequence_prod(self, expr: TExpr[T], backend: SymbolicBackend[T]) -> TExpr[T]:
        """Returns an expression representing a product of a sequence."""
        return self.sequence.get_prod(expr, self.count, backend)

    def substitute_symbols(
        self, inputs: dict[str, TExpr[T]], backend: SymbolicBackend[T], functions_map=None
    ) -> Repetition[T]:
        new_count = backend.substitute_all(self.count, inputs)
        new_sequence = self.sequence.substitute_symbols(inputs, backend, functions_map)
        return replace(self, count=new_count, sequence=new_sequence)


@singledispatch
def _sequence_from_qref(sequence, backend: SymbolicBackend[T]):
    pass


@_sequence_from_qref.register
def _(sequence: ConstantSequenceV1, backend: SymbolicBackend[T]) -> ConstantSequence:
    return ConstantSequence(type=sequence.type, multiplier=backend.as_expression(sequence.multiplier))


@_sequence_from_qref.register
def _(sequence: ArithmeticSequenceV1, backend: SymbolicBackend[T]) -> ArithmeticSequence:
    return ArithmeticSequence(
        type=sequence.type,
        initial_term=backend.as_expression(sequence.initial_term),
        difference=backend.as_expression(sequence.difference),
    )


@_sequence_from_qref.register
def _(sequence: GeometricSequenceV1, backend: SymbolicBackend[T]) -> GeometricSequence:
    return GeometricSequence(
        type=sequence.type,
        ratio=backend.as_expression(sequence.ratio),
    )


@_sequence_from_qref.register
def _(sequence: ClosedFormSequenceV1, backend: SymbolicBackend[T]) -> ClosedFormSequence:
    return ClosedFormSequence(
        type=sequence.type,
        sum=backend.as_expression(sequence.sum),
        prod=backend.as_expression(sequence.prod),
        num_terms_symbol=backend.as_expression(sequence.num_terms_symbol),
    )


@_sequence_from_qref.register
def _(sequence: CustomSequenceV1, backend: SymbolicBackend[T]) -> CustomSequence:
    return CustomSequence(
        type=sequence.type,
        term_expression=backend.as_expression(sequence.term_expression),
        iterator_symbol=backend.as_expression(sequence.iterator_symbol),
    )


def _repetition_from_qref(repetition: RepetitionV1 | None, backend: SymbolicBackend[T]) -> Repetition[T]:
    if repetition is not None:
        return Repetition(
            count=backend.as_expression(repetition.count), sequence=_sequence_from_qref(repetition.sequence, backend)
        )


@singledispatch
def _sequence_to_qref(sequence, backend: SymbolicBackend):
    pass


@_sequence_to_qref.register
def _(sequence: ConstantSequence, backend: SymbolicBackend) -> ConstantSequenceV1:
    return ConstantSequenceV1(type=sequence.type, multiplier=sequence.multiplier)


@_sequence_to_qref.register
def _(sequence: ArithmeticSequence, backend: SymbolicBackend) -> ArithmeticSequenceV1:
    return ArithmeticSequenceV1(type=sequence.type, initial_term=sequence.initial_term, difference=sequence.difference)


@_sequence_to_qref.register
def _(sequence: GeometricSequence, backend: SymbolicBackend) -> GeometricSequenceV1:
    return GeometricSequenceV1(type=sequence.type, ratio=sequence.ratio)


@_sequence_to_qref.register
def _(sequence: ClosedFormSequence, backend: SymbolicBackend) -> ClosedFormSequenceV1:
    return ClosedFormSequenceV1(
        type=sequence.type, sum=sequence.sum, prod=sequence.prod, num_terms_symbol=sequence.num_terms_symbol
    )


@_sequence_to_qref.register
def _(sequence: ClosedFormSequence, backend: SymbolicBackend) -> CustomSequenceV1:
    return ClosedFormSequenceV1(
        type=sequence.type, term_expression=sequence.term_expression, iterator_symbol=sequence.iterator_symbol
    )


def _repetition_to_qref(repetition: Repetition[T], backend: SymbolicBackend[T]) -> RepetitionV1:
    if repetition is not None:
        return RepetitionV1(
            count=backend.as_native(repetition.count), sequence=_sequence_to_qref(repetition.sequence, backend)
        )
