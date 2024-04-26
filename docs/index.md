# Welcome to Bartiq

## Intro

Bartiq is a library that allows to analyze a quantum algorithms and calculate symbolic expressions for quantum resource estimates (QRE).

## Installation

To install `bartiq` run: `pip install bartiq`. For more details follow instructions on the [installation page](installation.md).

## Quick start

In Bartiq we can take a quantum algorithm expressed as a collection of subroutines, each with it's costs expressed as symbolic expressions, and compile it to get cost expression for the whole algorithm.

As an example we can use Alias Sampling – an algorithm proposed by [Babbush et al.](https://journals.aps.org/prx/abstract/10.1103/PhysRevX.8.041015). Here's how it's depicted in the paper:

![Alias Sampling](images/alias_sampling_paper.png)

In order to quickly get started with `bartiq`, you can load Alias Sampling as an example routine and use it as follows (click here to download <a href="/data/alias_sampling_basic.json" download>`alias_sampling_basic.json`</a>):


```python
import json
from bartiq import Routine, compile_routine, evaluate

with open("alias_sampling_basic.json", "r") as f:
    routine_dict = json.load(f)

uncompiled_routine = Routine(**routine_dict)
compiled_routine = compile_routine(uncompiled_routine)

assignments = ["L=100", "mu=10"]

evaluated_routine = evaluate(compiled_routine, assignments)
```

Now in order to inspect the results you can do:

```
print(compiled_routine.resources["T_gates"].value)
print(evaluated_routine.resources["T_gates"].value)
```

which returns both symbolic the expression for the T-count as well as result for specific values of `L` and `mu`:

```
4*L + 4*mu + swap.O(log2(L)) + 8*ceiling(log2(L/multiplicity(2, L))) - 8
swap.O(log2(100)) + 480
```

To go step by step through the process and see how you can use Bartiq for your algorithms, please take a look at [our tutorials](tutorials/index.md). 


## Next steps

- For a more comprehensive examples please see [tutorials](tutorials/index.md)!
- If you are interested in learning more about how `bartiq` works under the hood, please check out concepts tab in the menu.
- For common issues, please check [troubleshooting](troubleshooting.md) section.
- You can find reference documation for the public API of `bartiq`'s python package, please go to [reference](reference.md).