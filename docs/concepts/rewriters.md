
# Rewriters

`bartiq` includes a set of utilities for manipulating and simplifying symbolic expressions, known as **rewriters**. This functionality is contained in the `analysis` submodule, and backend-specific rewriters can be imported directly.
```python
from bartiq.analysis import sympy_rewriter
```
Here we will explain the functionality common to all backend rewriters, and the functionality specific to the SymPy backend.

## Motivation

As quantum algorithms increase in complexity their symbolic resource expressions similarly become more complex. For a state of the art algorithm like double factorization (link) the resource expressions can be almost impossible to parse, due to the sheer number of terms and symbols. Making complex expressions more palatable is a primary motivation for rewriters, however we also want to implement standard simplifications. Terms like `max(0, x)` can be simplified if we could just indicate that `x>0`. 

## Overview 

Rewriters are structured as dataclasses with associated methods and properties. The input should be an expression that we wish to modify (or, rewrite). While much of the logic is necessarily tied to a particular backend implementation, the base class enforces some core functionality. The philosophy around rewriters is that they should be _immutable_



Below we list some of the most important attributes, properties and methods. In what follows, the typehint `T` is used to indicate that the type is backend-dependent expression type. For instance in the `sympy_backend`, `T = sympy.Expr`. 

### Attributes
- `expression: T`
    The form of the current expression. This is the attribute updated by rewriting methods.
- `linked_symbols: dict[str, Iterable[str]]`
    When substituting one variable for another, this dictionary tracks the relationships.

### Properties
- `assumptions: tuple[Assumption, ...]`
    A tuple of all assumptions that have been applied to the expression, in chronological order.
- `substitutions: tuple[Substitution, ...]`
    A tuple of all substitutions that have been applied to the expression, in chronological order.
- `original -> Self`
    Return the rewritter instance with the original input expression.
- `free_symbols -> Iterable[T]`
    An iterable of all free symbols (i.e. variables) in the expression.
- `individual_terms -> Iterable[T]`
    Return the expression as an iterable of its individual terms. For example, `a + b` would be returned as `(a, b)`.

### Methods
- `expand() -> Self`
    Expand all brackets in the expression.
- `simplify() -> Self`
    Run the backend simplify functionality.
- `assume(assumption: str | Assumption) -> Self`
    Add an assumption to expression. Assumptions can be passed as strings, i.e. `x > 0`.
- `substitute(expr: str, replace_with: str) -> Self`
    Perform a substitution. As inputs are string only, they will be parsed to the relevant backend. This permits one-to-one substitution as well as pattern matching. 
- `focus(symbols: str | Iterable[str]) -> T`
    Return only terms in the expression that contain the input symbols. This method only hides other terms, it does not delete them.
- `evaluate_expression(assignments: dict[str, int | float | T], functions_map: dict[str, Callable]) -> T | int | float`
    Assign explicit values to some, or all, of the symbols in the expression. This does not store the result, explicit replacement of symbols with values must be done with `substitute`.
- `history() -> list[Instruction]`
    Return a list of `Instruction`s that have been applied to this rewriter instance. 
- `undo_previous(num_operations_to_undo: int = 1) -> Self`
    Undo a number of previous operations applied to this instance.




## SymPy implementation

[`SympyExpressionRewriter`][bartiq.analysis.rewriters.SympyExpressionRewriter] is the concrete
implementation used by bartiq. It understands the SymPy expression tree and provides helpers for
wildcard substitutions, listing functions present in an expression and focusing on particular
symbols.

A convenient constructor [`sympy_rewriter`][bartiq.analysis.rewriters.sympy_rewriter] is provided to
initialise a SymPy based rewriter from either a string or an existing `sympy.Expr`.

## Rewriting routine resources

Resource expressions stored on a compiled routine can be rewritten using
[`ResourceRewriter`][bartiq.analysis.rewriters.ResourceRewriter]. It wraps a routine together with
one of its resources and exposes the same methods as an `ExpressionRewriter`. When the method
[`apply_to_whole_routine`][bartiq.analysis.rewriters.ResourceRewriter.apply_to_whole_routine] is
called, the accumulated instruction history is propagated to every child routine so that the chosen
resource is rewritten consistently throughout the entire routine hierarchy.

The helper [`ResourceRewriter.from_history`][bartiq.analysis.rewriters.ResourceRewriter.from_history]
allows applying a pre-computed list of instructions to a resource expression, for example when the
history was produced elsewhere.
