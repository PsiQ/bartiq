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

import warnings
from dataclasses import dataclass, replace
from functools import singledispatch
from typing import Callable, Generic, Literal, TypeVar, cast

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
        new_multiplier = backend.substitute(self.multiplier, inputs, functions_map)
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
        gamma = backend.func("gamma")
        return (
            self.difference**count
            * gamma(self.initial_term / self.difference + count)
            / gamma(self.initial_term / self.difference)
            * expr**count
        )

    def substitute_symbols(
        self, inputs: dict[str, TExpr[T]], backend: SymbolicBackend[T], functions_map=None
    ) -> ArithmeticSequence[T]:
        if functions_map is None:
            functions_map = {}
        new_initial_term = backend.substitute(self.initial_term, inputs, functions_map)
        new_difference = backend.substitute(self.difference, inputs, functions_map)
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
        new_ratio = backend.substitute(self.ratio, inputs, functions_map)
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
            return expr * backend.substitute(self.sum, inputs, {})
        else:
            raise BartiqCompilationError("Cannot evaluate sum for ClosedFormSequence, as sum is not defined.")

    def get_prod(self, expr: TExpr[T], count: TExpr[T], backend: SymbolicBackend[T]) -> TExpr[T]:
        if self.prod is not None:
            inputs = {backend.serialize(self.num_terms_symbol): count}
            return expr * backend.substitute(self.prod, inputs, {})
        else:
            raise BartiqCompilationError("Cannot evaluate product for ClosedFormSequence, as sum is not defined.")

    def substitute_symbols(
        self, inputs: dict[str, TExpr[T]], backend: SymbolicBackend[T], functions_map=None
    ) -> ClosedFormSequence[T]:
        functions_map = {} if functions_map is None else functions_map
        return replace(
            self,
            sum=None if self.sum is None else backend.substitute(self.sum, inputs, functions_map),
            prod=None if self.prod is None else backend.substitute(self.prod, inputs, functions_map),
            num_terms_symbol=backend.substitute(self.num_terms_symbol, inputs, functions_map),
        )


@dataclass(frozen=True)
class CustomSequence(Generic[T]):
    """Custom sequence.

    For sequences which do not fall into categories defined in other classes, one can use a custom representation.
    It is an explicit representation of a sequence where `term_expression` defines the expression for each term
    in the sequence and `iterator_symbol` is used to represent number of the iteration."""

    type: Literal["custom"]
    term_expression: TExpr[T]
    iterator_symbol: T

    def get_sum(self, expr: TExpr[T], count: TExpr[T], backend: SymbolicBackend[T]) -> TExpr[T]:
        return backend.sum(self.term_expression * expr, self.iterator_symbol, 0, count - 1)

    def get_prod(self, expr: TExpr[T], count: TExpr[T], backend: SymbolicBackend[T]) -> TExpr[T]:
        return backend.prod(self.term_expression * expr, self.iterator_symbol, 0, count - 1)

    def substitute_symbols(
        self, inputs: dict[str, TExpr[T]], backend: SymbolicBackend[T], functions_map=None
    ) -> CustomSequence[T]:
        if functions_map is None:
            functions_map = {}

        symbols_to_substitute = [backend.free_symbols_in(expr) for expr in inputs.values()]
        symbols_to_substitute = [symbol for sublist in symbols_to_substitute for symbol in sublist]
        symbols_to_be_substituted = inputs.keys()
        if backend.serialize(self.iterator_symbol) in [*symbols_to_substitute, *symbols_to_be_substituted]:
            raise BartiqCompilationError(
                f"Tried to replace symbol that's used as iterator symbol in a sequence: {self.iterator_symbol}."
            )

        new_term_expression = backend.substitute(self.term_expression, inputs, functions_map)
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
        new_count = backend.substitute(self.count, inputs)
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

    sum_expr = backend.as_expression(sequence.sum) if sequence.sum is not None else None
    prod_expr = backend.as_expression(sequence.prod) if sequence.prod is not None else None

    return ClosedFormSequence(
        type=sequence.type,
        sum=sum_expr,
        prod=prod_expr,
        num_terms_symbol=backend.as_expression(sequence.num_terms_symbol),
    )


@_sequence_from_qref.register
def _(sequence: CustomSequenceV1, backend: SymbolicBackend[T]) -> CustomSequence:
    return CustomSequence(
        type=sequence.type,
        term_expression=backend.as_expression(sequence.term_expression),
        iterator_symbol=backend.as_expression(sequence.iterator_symbol),
    )


def repetition_from_qref(repetition: RepetitionV1 | None, backend: SymbolicBackend[T]) -> Repetition[T] | None:
    if repetition is not None:
        return Repetition(
            count=backend.as_expression(repetition.count), sequence=_sequence_from_qref(repetition.sequence, backend)
        )
    else:
        return None


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
    return GeometricSequenceV1(type=sequence.type, ratio=backend.as_native(sequence.ratio))


@_sequence_to_qref.register
def _(sequence: ClosedFormSequence, backend: SymbolicBackend) -> ClosedFormSequenceV1:
    return ClosedFormSequenceV1(
        type=sequence.type,
        sum=backend.serialize(sequence.sum),
        prod=backend.serialize(sequence.prod),
        num_terms_symbol=backend.serialize(sequence.num_terms_symbol),
    )


@_sequence_to_qref.register
def _(sequence: CustomSequence, backend: SymbolicBackend) -> CustomSequenceV1:
    return CustomSequenceV1(
        type=sequence.type,
        term_expression=backend.serialize(sequence.term_expression),
        iterator_symbol=backend.serialize(sequence.iterator_symbol),
    )


def repetition_to_qref(repetition: Repetition[T] | None, backend: SymbolicBackend[T]) -> RepetitionV1 | None:
    if repetition is not None:
        count = backend.as_native(repetition.count)
        if isinstance(count, float):
            warnings.warn(
                f"Repetition count evaluated to float {count}. This is either a result of imprecise arithmetic, "
                f"a problem with symbolics expressions used in your routine, or a bug in {type(SymbolicBackend)}."
            )
            count = str(count)  # Otherwise QREf's validation will blow up.
        return RepetitionV1(count=cast(str | int, count), sequence=_sequence_to_qref(repetition.sequence, backend))
    else:
        return None
