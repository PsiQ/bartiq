# Symbolics

Symbolics is a core subsystem in `bartiq` that provides the foundation for parsing, manipulating, and evaluating symbolic mathematical expressions. This system powers most of `bartiq`'s capabilities for handling resource expressions, port sizes, and mathematical constraints in quantum programs.

Please keep in mind, that while we try to keep this page up-to-date, in the end the code is the only source-of-truth. If you notice any discrepancies between what is described here and how `bartiq` behaves, please [create an issue](https://github.com/PsiQ/bartiq/issues)!

## Overview

The symbolics subsystem consists of several key components that work together to provide a flexible and extensible symbolic computation framework:

- **Expression Parser**: Converts string representations of mathematical expressions into internal representations
- **Symbolic Backend**: Provides an interface for symbolic computation operations (currently implemented using SymPy)
- **Expression Serializer**: Converts symbolic expressions back to string format
- **Special Syntax Support**: Handles Bartiq-specific syntax like port references (`#port_name`), wildcards (`~`), and path expressions

## Expression Syntax

`bartiq` supports a rich mathematical expression syntax that extends standard mathematical notation with quantum-specific features.

### Basic Mathematical Operations

```
x + y           # Addition
x - y           # Subtraction
x * y           # Multiplication
x / y           # Division
x ^ y           # Exponentiation (also x ** y)
x % y           # Modulo
```

### Functions

The system supports a comprehensive set of mathematical functions:

#### Arithmetic Functions
```
abs(x)          # Absolute value
sgn(x)          # Sign function
ceil(x)         # Ceiling
floor(x)        # Floor
round(x)        # Round to nearest integer
```

#### Trigonometric Functions
```
sin(x), cos(x), tan(x)
asin(x), acos(x), atan(x)
sinh(x), cosh(x), tanh(x)
asinh(x), acosh(x), atanh(x)
```

#### Logarithmic and Exponential Functions
```
exp(x)          # Exponential
log(x)          # Natural logarithm
log2(x)         # Base-2 logarithm
log10(x)        # Base-10 logarithm
sqrt(x)         # Square root
cbrt(x)         # Cube root
```

#### Aggregate Functions
```
sum(a, b, c)    # Sum of arguments
prod(a, b, c)   # Product of arguments
min(a, b, c)    # Minimum value
max(a, b, c)    # Maximum value
```

#### Sequence Operations
```
sum_over(expr, iterator, start, end)    # Summation over range
prod_over(expr, iterator, start, end)   # Product over range
```

Example:
```
sum_over(x^2, x, 1, N)  # Equivalent to ∑(x², x=1 to N)
```

### Mathematical Constants

Built-in constants are available:
```
PI              # π (3.14159...)
E               # e (2.71828...)
```

### Bartiq-Specific Syntax

#### Port References
Port sizes can be referenced using the `#` prefix:
```
#in_0           # Size of input port 0
#out_1          # Size of output port 1
```

#### Path Expressions
Variables can be referenced with hierarchical paths:
```
parent.child.parameter
root.subroutine.#port_size
some.deep.path.to.variable
```

#### Wildcards
The `~` character represents wildcards for pattern matching:
```
~.resource      # Wildcard resource reference
parent~         # Wildcard parent reference
```

## The Symbolic Backend

The symbolic backend provides a uniform interface for symbolic computation operations. Currently, `bartiq` uses SymPy as its primary backend, but the architecture allows for different backends.

### Key Backend Operations

```python
from bartiq.symbolics import sympy_backend

# Parse expression from string
expr = sympy_backend.as_expression("x^2 + 2*x + 1")

# Substitute variables
result = sympy_backend.substitute(expr, {"x": 3})

# Get free symbols
symbols = sympy_backend.free_symbols_in(expr)

# Evaluate numerically if possible
value = sympy_backend.value_of(expr)

# Serialize back to string
string_repr = sympy_backend.serialize(expr)
```

### Expression Substitution

One of the most important operations is substitution, which allows replacing symbols with values or other expressions:

```python
# Variable substitution
expr = sympy_backend.as_expression("N^2 + 2*N")
result = sympy_backend.substitute(expr, {"N": 10})  # Returns 120

# Function substitution
expr = sympy_backend.as_expression("f(x) + g(y)")
result = sympy_backend.substitute(
    expr, 
    {"x": 2, "y": 3},
    {"f": lambda x: x**2, "g": lambda y: y + 1}
)
```

### Constant Parsing

The backend can automatically recognize and parse mathematical constants:

```python
# Case-insensitive constant recognition
expr1 = sympy_backend.parse_constant(sympy_backend.as_expression("pi"))
expr2 = sympy_backend.parse_constant(sympy_backend.as_expression("PI"))
expr3 = sympy_backend.parse_constant(sympy_backend.as_expression("Pi"))
# All result in the mathematical constant π
```

## Expression Preprocessing

Before parsing, expressions undergo several preprocessing stages to handle Bartiq-specific syntax:

### Port Reference Preprocessing
```
#in_0 → Port(in_0)
a.#out_1 → a.Port(out_1)
```

### Wildcard Preprocessing
```
~.resource → wildcard().resource
parent~ → wildcard(parent)
```

### Lambda Symbol Handling
```
lambda → __lambda__  # Avoids conflicts with Python's lambda keyword
```

### Operator Normalization
```
x ^ y → x ** y  # Converts caret to standard exponentiation
```

## Usage in Bartiq

The symbolics system is used throughout `bartiq` for:

### Resource Expressions
```yaml
resources:
  T_gates: "N^2 + 2*N + 1"
  ancilla_qubits: "ceil(log2(N))"
```

### Port Size Definitions
```yaml
ports:
  - name: in_0
    size: "N"
  - name: out_0  
    size: "2 * #in_0"  # References input port size
```

### Compilation Constraints
```yaml
constraints:
  - "N >= 1"
  - "#in_0 == #out_0"
```

## Error Handling

The symbolics system provides helpful error detection:

### Undefined Function Detection
```python
# Detects misspelled function names and suggests corrections
expr = sympy_backend.as_expression("celing(x)")  # Should be "ceiling"
errors = sympy_backend.find_undefined_functions(expr)
# Returns [("celing", "ceiling")]
```

### Syntax Validation
Invalid expressions are caught during parsing:
```python
# This will raise a parsing error
expr = sympy_backend.as_expression("x + + y")  # Invalid syntax
```

## Advanced Features

### Custom Function Definition
Users can define custom functions during substitution:
```python
def custom_function(x):
    return x**2 + 1

expr = sympy_backend.as_expression("f(N)")
result = sympy_backend.substitute(expr, {}, {"f": custom_function})
```

### Expression Comparison
```python
expr1 = sympy_backend.as_expression("x + 1")
expr2 = sympy_backend.as_expression("1 + x")
comparison = sympy_backend.compare(expr1, expr2)
# Returns ComparisonResult.EQUAL
```

### Sequence Expressions
Complex summations and products:
```python
# Create sum from 1 to N of i^2
term = sympy_backend.as_expression("i^2")
iterator = sympy_backend.as_expression("i")
start = sympy_backend.as_expression("1")
end = sympy_backend.as_expression("N")

sum_expr = sympy_backend.sequence_sum(term, iterator, start, end)
```

## Best Practices

1. **Use meaningful variable names**: Prefer `num_qubits` over `n`
2. **Leverage path expressions**: Use hierarchical naming for clarity
3. **Be explicit with parentheses**: Avoid relying on operator precedence
4. **Use appropriate functions**: Prefer `ceil(log2(N))` over manual ceiling calculations
5. **Test expressions**: Verify expressions evaluate correctly for expected inputs

## Limitations

- Expression complexity can impact compilation performance
- Some advanced mathematical operations may not be supported
- Wildcard expressions have limited evaluation capabilities
- Circular dependencies in expressions are not allowed

The symbolics system provides a powerful foundation for expressing and manipulating the mathematical relationships that are central to quantum resource analysis in `bartiq`.