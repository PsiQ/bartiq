
# Rewriters

`bartiq` includes a set of utilities for manipulating and simplifying symbolic expressions, known as **rewriters**. This functionality is contained in the `analysis` submodule, and backend-specific rewriters can be imported directly.
```python
from bartiq.analysis import sympy_rewriter
```
Here we will give an overview of the rewriting functionality currently implemented, with example usage. This document is intended for advanced users seeking to understand in-depth the logic behind rewriters, either for development or debugging purposes. We will soon have a more usage-oriented tutorial. 

## Motivation

As quantum algorithms increase in complexity their symbolic resource expressions similarly become more complex. For a state of the art algorithm like double factorization the resource expressions can be almost impossible to parse, due to the sheer number of terms and symbols. For example, see Fig. 16 in [*Even more eﬃcient quantum computations of chemistry
through tensor hypercontraction*](https://arxiv.org/pdf/2011.03494), and Eq. C39 for the associated Toffoli cost of this circuit. 

Making complex expressions more palatable is a primary motivation for rewriters; gaining insights into closed-form expressions for important resource quantities is vital for fault-tolerant quantum algorithm optimization and design.

## Overview 

Rewriters are structured as dataclasses with associated methods and properties. Instantiation is done through a factory method; the only required input is an expression that we wish to modify (or rewrite). The input can be provided as a string, or as the backend-specific expression type.

While much of the logic is necessarily tied to a particular backend implementation, the base class enforces some core functionality. The philosophy around rewriters is that they should be _immutable_, such that methods that change an expression actually return a new instance of the rewriter class. This allows for method chaining and easy access to previous expression forms if a change was made in error.

Due to the dynamic nature of expression manipulation, rewriters are designed with interactive environments in mind. Rewriters have a `_repr_latex_` method that prints the current expression, meaning the following code in a Jupyter notebook:
```python
sympy_rewriter("a + b")
```
would return a $\LaTeX$ (technically $KaTeX$) expression $a + b$. This, combined with method chaining, means the effect of different methods can be seen immediately.


## Concepts
In designing the rewriter framework we implemented a number of different utility classes. A typical user should not need to interact with these objects directly, but we describe them here for completeness.

#### Instructions
An `Instruction` is an action that marks a change to an expression. The following `Instructions` are implemented:

- `Initial`

    The initial form of the rewriter instance.

- `Simplify`

    A backend-specific 'simplify' command.

- `Expand`

    Expand all brackets in the expression.

- `Assumption`

    Add an assumption onto a symbol.

- `Substitution`

    Substitute a symbol or expression for another.

- `ReapplyAllAssumptions`

    Reapply all previously applied assumptions.

The primary purpose of `Instructions` is to track the history of an expression, and the user may only ever interact with these objects via the `history()` method. Of these classes, only `Assumption` and `Substitution` require special logic; the others have no methods or attributes implemented. We explore `Assumption` and `Substitution` in more detail below.

!!! note "Why not just an `Enum`?"  
    Originally the `Instructions` were implemented as an `Enum`! However, because `Assumptions` and `Substitutions` required special logic it was challenging to enforce strict typing across both an `Enum` and other dataclasses. Creating an empty class `Instruction`, with other classes inheriting from it, resulted in a cleaner implementation.


#### Assumptions
Assumptions about symbols can be input to the expression, and (in the case of SymPy) the backend symbolic engine attempts to simplify the expression with this new knowledge. An assumption requires three arguments:

- `symbol_name: str`

    The symbol to add the assumption to.

- `comparator: Comparator | str`

    The comparison to apply, one of ">", "<", ">=", "<=". 

- `value: int | float`

    The reference value to compare the symbol to.

Alternatively an assumption can be parsed directly from a string:
```python
sympy_rewriter("max(0, X)").assume("X > 0")
>>> X
```

Given an input assumption to a `sympy_rewriter`, the symbol is updated with the relevant SymPy [predicates](https://docs.sympy.org/latest/guides/assumptions.html#predicates). For some symbol `X` the predicates we support are:

- positive: `X > 0`,
- nonnegative: `X >= 0` or `positive`,
- negative: `X < 0`,
- nonpositive: `X<=0` or `negative`,

From these SymPy is able to deduce other predicates. We do not implement predicates that declare if a symbol belongs to a particular number group, i.e. `integer`, `complex`, etc. We found that these kinds of assumptions did little to help simplify expressions. Similarly we do not have support for symbols being declared as infinitely large; if there is a valuable use case for these they could be easily added.


There is unfortunately [no way to input assumptions between different symbols](https://docs.sympy.org/latest/guides/assumptions.html#relations-between-different-symbols). Similarly SymPy does not implement predicates that specify a relationship between a symbol and some nonzero value, i.e. `X > 5`. However, for this latter point, we have implemented a workaround. 

If an assumption like `X > 5` is passed, the following logic occurs:

- Predicates are derived for `X` and applied to the symbol in the expression.
- A 'dummy' symbol `Y` is created with the same predicates. 
- We replace `X -> Y + 5`
- We replace `Y -> X - 5`

The SymPy symbolic engine attempts to simplify the expression at each stage of this process. The drawback is that these kinds of assumptions _do not persist_. Because SymPy lacks the logic to define the relative value of a symbol beyond (non-)positivity/negativity, after this process the symbol `X` will only be defined with predicates from that restricted set. As a result, it can occasionally be useful to reapply all previously applied assumptions in order to repeat the steps lined out above. This can be achieved with the `reapply_all_assumptions()` method. 

Finally, an assumption can also be applied to an expression with the same logic as above; a dummy symbol is created with the relevant predicates and (temporarily) replaces every instance of the expression. 
```python
sympy_rewriter(
    "max(0, log(x)) + max(1, log(x)) + max(2, log(x))"
).assume("log(x) > 2")
>>> 3*log(x)
```
However any symbols within the expression (`x` in this example) _will not_ inherit the predicates that were derived for the expression and associated dummy symbol. 


#### Substitutions

Substitutions are another powerful way of simplifying expressions. Rewriters support generic one-to-one substitutions: 

- symbol to symbol:

    ```python
    sympy_rewriter("a").substitute(expr="a", replace_with="b")
    >>> b
    ```

- symbol to expression:

    ```python
    sympy_rewriter("a").substitute("a", "b + c")
    >>> b + c
    ```

- expression to symbol:

    ```python
    sympy_rewriter("a + b").substitute("a + b", "c")
    >>> c
    ```

- expression to expression:

    ```python
    sympy_rewriter("a + b").substitute("a + b", "c/d")
    >>> c/d
    ```


There are no restrictions on the kind of replacements that can be done. Substitutions can only be passed in via strings in order to unify the API interface.

For `sympy_rewriter`, we also support _wildcard substitutions_. SymPy has [`Wild` symbols](https://docs.sympy.org/latest/modules/core.html#sympy.core.symbol.Wild) which can be used to match patterns in expressions. When using `.substitute`, a symbol prefaced with `$` will be marked as `Wild`, and will match anything that is nonzero. `Wild` symbols that are permitted to be zero can result in unusual, and often unwanted, behaviour. An example of using wildcard substitutions:

```python
sympy_rewriter("log(x + 2) + log(y + 4)").substitute("log($x + $y)", "f(x, y)")
>>> f(2, x) + f(4, y)
```
If symbols were marked as wild in the first argument to `.substitute` and then referenced in the second argument, the corresponding matching pattern is used. If a new, or existing, symbol is referenced, it is replaced as-is. If an existing symbol is used _as a wild symbol_, the corresponding matching pattern takes precedence. 
```python
# Replace a wild pattern with a new symbol
sympy_rewriter("f(x) + f(y) + z").substitute("f($x)", "t")
>>> 2*t + z

# Replace a wild pattern with an existing symbol
sympy_rewriter("f(x) + f(y) + z").substitute("f($x)", "z")
>>> 3*z

# Using an existing symbol as a wild symbol
sympy_rewriter("f(x) + f(y) + z").substitute("f($y)", "y")
>>> x + y + z
```

More precise control over wildcard substitutions is possible. Any lowercase symbol prefaced with `$` will match _anything_ except $0$. An uppercase `N` will match _only numbers_. Any other uppercase letter will match _only symbols_.

```python
# Match anything
sympy_rewriter(
    "log(1 + x) + log(2 + y) + log(z) + log(t)"
).substitute("log($x)", "x")
>>> t + x + y + z + 3

# Match only symbols
sympy_rewriter(
    "log(1 + x) + log(2 + y) + log(z) + log(t)"
).substitute("log($X)", "X")
>>> t + z + log(x + 1) + log(y + 2)

# Match symbols and numbers
sympy_rewriter(
    "log(1 + x) + log(2 + y) + log(z) + log(t)"
).substitute("log($X + $N)", "X/N")
>>> x + y/2 + log(t) + log(z)
```

Finally, it is possible to mix-and-match wild symbols with non-wild symbols:
```python
sympy_rewriter(
    "a*max(0, x) + b*max(0,y) + a*max(0, y)"
).substitute("a*max(0, $x)", "a*x")
>>> a*x + a*y + b*max(0, y)
```

##### Caveats
Here we collect some caveats for wildcard substitutions.
<details><summary>Matching zero arguments</summary>
As mentioned we assume that wildcard symbols are <em>nonzero</em>. This is to prevent perfectly valid, but perhaps unwanted, interactions. For example:
```python
from sympy.abc import x
from sympy import Wild
a = Wild('a') # Can match to zero values
b = Wild('b') # Can match to zero values
expr = x
expr.match(a + b)
>>> {_a: x, _b: 0}
```
While this is correct, if our goal is to <em>only</em> match expressions that are an explicit sum of other expressions, zero-valued <code>Wild</code> symbols can lead to false positives.
<br>
Excluding zero-values from wildcard substitutions in rewriters helps prevent these kinds of events, but it can also introduce other pitfalls:
```python
rewriter = sympy_rewriter("max(0, a) + max(1, b) + max(4, c) + max(5, d)")
```
If we know that our variables <code>a</code>, <code>b</code>, <code>c</code> and <code>d</code> are all large real values, we can just get rid of the <code>max</code> functions with a wildcard subtitution:
```python
rewriter.substitute("max($x, $y)", "y")
>>> max(0, a) + b + c + d
```
Because wild symbols cannot be zero, we did not remove the <code>max(0, a)</code> term. To match to zero, you must provide it explicitly:
```python
rewriter.substitute("max($x, $y)", "y").substitute("max(0, $x)", "x")
>>> a + b + c + d
```
</details>

<details><summary>Ordering of function arguments</summary>
Wildcard substitutions can be extremely powerful but, due to a difference between how SymPy stores expressions internally versus how it displays them, can have some unexpected outcomes. Take for instance the following example:
```python
rewriter = sympy_rewriter("log(x + 2) + log(y + 4)")
rewriter
>>> log(x + 2) + log(y + 4)
rewriter.substitute("log($x + $y)", "f(x, y)")
>>> f(2, x) + f(4, y)
```
Because the expression is displayed with symbols preceding numbers in the `log` arguments, we intutively expect the matching pattern to follow this convention. Instead, it flips their order: this is due to how SymPy prioritises objects in its engine. For more complex arguments it can be difficult to infer in what order SymPy is storing them.
</details>

<details><summary>Mix and matching wild/non-wild symbols</summary>
While mix and matching wild/non-wild symbols is possible, it may not always work as expected. Consider the following SymPy code:
```python
from sympy import Wild, Function, symbols, Max
X = Wild("X")
Y = Wild("Y")
f = Function("f")
a, b, c = symbols("a,b,c")
```
We have defined two <code>Wild</code> symbols <code>X</code> and <code>Y</code> that will match anything, as well as some symbols <code>a</code>, <code>b</code> and <code>c</code>, and a function <code>f</code>.

When attempting to find patterns with <code>Wild</code> symbols, we use the <code>.match</code> method in SymPy. Consider the following interactions.
<br>

<u>Case 1: Wildcard substitution works as expected</u>
```python
expr = Max(a + b, c)
expr.match(Max(X, c))
>>> {X: a + b}
```

<u>Case 2: Wildcard substitution does not work as expected</u>
```python
expr = Max(a + b, f(c))
expr.match(Max(X, f(c)))
>>> None
```
The only change is now we are trying to match <code>f(c)</code> instead of just <code>c</code>. We intuitively expect this to work, as we are accessing the SymPy objects directly. Naively, we can be tempted to conclude that this change in behaviour is related to the function <code>f</code>.
<br>
<u>Case 3: Wildcard substitution works again</u>
```python
expr = Max(a, f(c))
expr.match(Max(X, f(c)))
>>> {X: a}
```
If we remove <code>+ b</code> from the first argument, the matching works again!


To avoid this unexpected behaviour, it is encouraged to be as explicit as possible and provide more <code>Wild</code> symbols rather than fewer:
```python
expr = Max(a + b, f(c))
expr.match(Max(X + Y, f(c)))
>>> {X: a, Y: b}
```
As we rely on this SymPy level code when implementing substitutions through rewriters, it is important to keep these kinds of ineractions in mind.
</details>
<!-- 
## ResourceRewriter

The `ResourceRewriter` class allows you to use a rewriter across an entire `bartiq` `CompiledRoutine` for a specific resource. Where the `sympy_rewriter` accepts only a single expression, `ResourceRewriter` accepts three inputs:

- `routine: CompiledRoutine`
- `resource: str`
- `rewriter_factory: ExpressionRewriterFactory = sympy_rewriter`

The `ResourceRewriter` is backend-independent and inherits functionality from a given rewriter factory method, which defaults to `sympy_rewriter`. Upon instantiation, the `rewriter_factory` input is used to create a `.rewriter` attribute on the expression of the given resource at the top level of the routine. Attribute, property and method calls are then forwarded to the `.rewriter` attribute such that `ResourceRewriter` instances can be used in the same way as a rewriter instance. The caveat is that while rewriters are immutable, such that transformative methods return a new instance, the `ResourceRewriter` is not immutable and the `.rewriter` attribute is updated after each method call. In short, an instance of `ResourceRewriter` will be updated **in-place** whereas an instance of `sympy_rewriter` will not. 

When using a `ResourceRewriter`, changes to the expression are not propagated throughout the entire routine. A method `apply_to_whole_routine()` can be called that inspects the history of the rewriter, and applies those changes to every `resource` expression at every level of the routine. This method returns a new routine instead of updating the existing one. 

It is also possible to instantiate a `ResourceRewriter` from a given history, with `.from_history()`. This class method accepts as inputs:

- `routine: CompiledRoutine`
- `resource: str`
- `history: list[Instruction]`
- `rewriter_factory: ExpressionRewriterFactory = sympy_rewriter`

and returns an instance of `ResourceRewriter` with the history loaded in.  -->

## Implementation details
Below we list some of the most important attributes, properties and methods of rewriters. In what follows, the typehint `T` is used to indicate that the type is backend-dependent expression type. For instance in the `sympy_backend`, `T = sympy.Expr`. 

There are broadly two kinds of methods: those that implement an `Instruction`, and thus modify the expression, and those that display information about the expression or update it temporarily. Methods that are typehinted to return `Self` return a new rewriter instance, and thus implement an `Instruction`.

### Attributes
- `expression: T`

    The form of the current expression. This is the attribute updated by rewriting methods and displayed by the `_repr_latex_` method in Jupyter notebooks.

    ```python
    sympy_rewriter("a + b + c").expression
    >>> a + b + c
    ```

- `linked_symbols: dict[str, Iterable[str]]`

    When substituting one symbol for another, this dictionary tracks the relationships.

    ```python
    rewriter = sympy_rewriter("a + b + c").substitute("a + b + c", "x")
    rewriter.linked_symbols
    >>> {'x': ("a", "b", "c")}
    ```


### Properties
- `assumptions: tuple[Assumption, ...]`

    A tuple of all assumptions that have been applied to the expression, in chronological order.

    ```python
    rewriter = (sympy_rewriter("a + b + c")
                .assume("a>5")
                .assume("b<-1")
                .assume("c>=10"))
    rewriter.assumptions
    >>> (
    >>>     Assumption(symbol_name='a', comparator='>', value=5),
    >>>     Assumption(symbol_name='b', comparator='<', value=-1),
    >>>     Assumption(symbol_name='c', comparator='>=', value=10)
    >>> )
    ```

- `substitutions: tuple[Substitution, ...]`

    A tuple of all substitutions that have been applied to the expression, in chronological order.
    ```python
    rewriter = (sympy_rewriter("a")
                .substitute("a", "x")
                .substitute("x", "y")
                .substitute("y", "z"))
    rewriter.substitutions
    >>> ( 
    >>>     Substitution(expr='a', replacement='x', backend='SympyBackend'),
    >>>     Substitution(expr='x', replacement='y', backend='SympyBackend'),
    >>>     Substitution(expr='y', replacement='z', backend='SympyBackend')
    >>> ) 
    ```

- `original -> Self`

    Return the rewritter instance with the original input expression.

    ```python
    rewriter = (sympy_rewriter("a")
                .substitute("a", "x")
                .substitute("x", "y")
                .substitute("y", "z"))
    assert rewriter.original == sympy_rewriter("a")
    ```

- `free_symbols -> Iterable[T]`

    An iterable of all free symbols (i.e. variables) in the expression.

    ```python
    sympy_rewriter("a + b + c").free_symbols
    >>> {a, b, c}
    ```

- `individual_terms -> Iterable[T]`

    Return the expression as an iterable of its individual terms. Ordering is not conserved.

    ```python
    sympy_rewriter("a*b + c*d + e + f*log(1 + g)").individual_terms
    >>> (
    >>>     e,
    >>>     a*b,
    >>>     c*d,
    >>>     f*log(1 + g),
    >>> )
    ```

### Methods
- `expand() -> Self`

    Expand all brackets in the expression.

    ```python
    sympy_rewriter("(a + b)*c - (d + e)").expand()
    >>> a*c + b*c - d - e
    ```

- `simplify() -> Self`

    Run the backend simplify functionality.

    ```python
    sympy_rewriter("x*sin(y)**2 + x*cos(y)**2").simplify()
    >>> x
    ```

    As we are calling the SymPy method `.simplify` on the expression, we encourage the user to read the [documentation](https://docs.sympy.org/latest/modules/simplify/simplify.html#sympy.simplify.simplify.simplify) on this functionality.


- `assume(assumption: str | Assumption) -> Self`

    Add an assumption to the expression. Assumptions can be passed as strings, i.e. `x > 0`.

    ```python
    sympy_rewriter("max(5, a)").assume("a > 5")
    >>> a
    ```

- `substitute(expr: str, replace_with: str) -> Self`

    Perform a substitution. As inputs are string only, they will be parsed to the relevant backend. This permits one-to-one substitution as well as pattern matching with wildcards. 

    One-to-one substitution:
    ```python
    sympy_rewriter("a*b*c").substitute("b*c", "y")
    >>> a*y
    ```

    Wildcard substitution:
    ```python
    sympy_rewriter(
        "log(x + 1) + log(y + 4) + log(z + 6)"
    ).substitute("log($x + $y)", "f(x, y)")
    >>> f(1, x) + f(4, y) + f(6, z)
    ```


- `focus(symbols: str | Iterable[str]) -> T`
    
    Return only terms in the expression that contain the input symbols, grouped if possible. This method only hides other terms, it does not delete them.

    ```python
    sympy_rewriter("a*b + a*c + a*d + b*e + d*c").focus("a")
    >>> a*(b + c + d)
    ```

- `evaluate_expression(assignments: dict[str, int | float | T], functions_map: dict[str, Callable]) -> T | int | float`

    Assign explicit values to some, or all, of the symbols in the expression. This does not store the result, explicit replacement of symbols with values must be done with `substitute`. This method calls the `backend.substitute` [method](https://github.com/PsiQ/bartiq/blob/d653889e57c4637db7e4f08a698b08252f0cb1e1/src/bartiq/symbolics/backend.py#L95). 

    ```python
    sympy_rewriter("a").evaluate_expression(assignments: {"a": 10})
    >>> 10
    ```

- `history() -> list[Instruction]`

    Return a list of `Instruction`s that have been applied to this rewriter instance. 

    ```python
    (sympy_rewriter("a + b")
        .assume("a > 10")
        .substitute("b", "c")
        .expand()
        .simplify()
        .history())
    >>> [ 
    >>>     Initial(),
    >>>     Assumption(symbol_name='a', comparator='>', value=10),
    >>>     Substitution(expr=''b'', replacement='c', backend='SympyBackend'),
    >>>     Expand(),
    >>>     Simplify()
    >>> ]
    ```

- `undo_previous(num_operations_to_undo: int = 1) -> Self`

    Undo a number of previous operations applied to this instance.

    ```python
    (sympy_rewriter("a")
        .substitute("a", "x")
        .substitute("x", "y")
        .substitute("y", "z")
        .undo_previous(2))
    >>> x
    ```


### SymPy Specific Methods
While the base class enforces some functionality, SymPy allows us to extend this and implement other helpful methods. The following methods are specific to the SymPy rewriter class.

- `get_symbol(symbol_name: str) -> Symbol | None`

    Return a SymPy `Symbol` from `expression` given its name. If it doesn't exist, return `None`.


    ```python
    sympy_rewriter("a*log(x + b)/d").get_symbol("d")
    >>> d
    ```

- `all_functions_and_arguments() -> set[Expr]`

    Return a set of all functions and their arguments in the `expression` attribute. This includes nested functions.

    ```python
    sympy_rewriter(
        "a*log(x + 1) + max(b, max(c, d)) + ceiling(y/z)"
    ).all_functions_and_arguments()
    >>> {
    >>>     log(x + 1),
    >>>     max(c, d),
    >>>     max(b, max(c, d)),
    >>>     ceiling(y, z),
    >>> }
    ```

- `list_arguments_of_function(function_name: str) -> list[tuple[Expr, ...] | Expr]`

    Given a function name, return a list of all of its arguments in the `expression`. If the function takes multiple arguments, they are returned as a tuple in the order they appear.

    ```python
        sympy_rewriter(
        "a*log(x + 1) + max(b, max(c, d)) + ceiling(y/z)"
    ).list_arguments_of_function("max")
    >>> [
    >>>     (b, max(c, d)),
    >>>     (c, d),
    >>> ]
    ```

### ResourceRewriter Methods

The `ResourceRewriter` class has only two methods, and inherits the others from the input `rewriter_factory`. 

- `apply_to_whole_routine() -> CompiledRoutine`

    Apply all previously applied instructions onto every relevant resource expression at every level of the routine hierarchy. 

    The following code snippets describes a potential workflow for this method. A `CompiledRoutine` object is loaded into the `ResourceRewriter`, and we specify that we wish to rewrite the `active_volume` resource. We call methods on the instance (recall `ResourceRewriters` are updated in place) and return a new routine from `.apply_to_whole_routine()`. In this `CompiledRoutine` object, the `active_volume` expression of every subroutine has had `.simplify()` applied to it.

    ```python
    routine: CompiledRoutine = CompiledRoutine(...)
    av_resource_rewriter = ResourceRewriter(
        routine=routine, 
        resource="active_volume"
    )
    av_resource_rewriter.simplify()
    new_routine: CompiledRoutine = resource_rewriter.apply_to_whole_routine()
    ```

- `from_history(routine: CompiledRoutine, resource: str, history: list[Instruction], rewriter_factory: ExpressionRewriterFactory = sympy_rewriter) -> ResourceRewriter`

    This `classmethod` is able to instantiate a `ResourceRewriter` class from a given list of instructions. Using the above example:

    ```python
    routine: CompiledRoutine = CompiledRoutine(...)
    av_resource_rewriter = ResourceRewriter(
        routine=routine, 
        resource="active_volume"
    )
    av_resource_rewriter.simplify()
    qubit_highwater_resource_rewriter = ResourceRewriter.from_history(
        routine=routine, 
        resource="qubit_highwater", 
        history=av_resource_rewriter.history()
    )

    ```