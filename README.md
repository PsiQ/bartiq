<h1><img src="https://raw.githubusercontent.com/PsiQ/bartiq/main/docs/assets/logo.png" width=23> Bartiq</h1>

## What is bartiq

Bartiq is a library that allows one to analyze quantum algorithms and calculate symbolic expressions for quantum resource estimates (QRE).

## Installation

To install `bartiq` run: `pip install bartiq`.

In order to install it from source clone the repo by running `git clone https://github.com/PsiQ/bartiq.git` and then run `pip install .` from the main directory.

```bash
# Clone bartiq repo (you can use SSH link as well)
git clone https://github.com/PsiQ/bartiq.git
cd bartiq
pip install .
```

## Quick start

In bartiq we can take a quantum algorithm expressed as a collection of subroutines, each with its costs expressed as symbolic expressions, and compile it to get cost expression for the whole algorithm.

As an example we can use Alias Sampling – an algorithm proposed by [Babbush et al.](https://journals.aps.org/prx/abstract/10.1103/PhysRevX.8.041015). Here's how it's depicted in the paper:

![Alias Sampling](https://raw.githubusercontent.com/PsiQ/bartiq/main/docs/images/alias_sampling_paper.png?token=GHSAT0AAAAAACFPHUU4MIKWTFLBJ5PLG2MCZRMBP4Q)

In order to quickly get started with `bartiq`, you can load Alias Sampling as an example routine and use it as follows (click here to download <a href="https://raw.githubusercontent.com/PsiQ/bartiq/main/docs/data/alias_sampling_basic.json" download>`alias_sampling_basic.json`</a>):


```python
import json
from bartiq import compile_routine, evaluate
from qref import SchemaV1

with open("docs/data/alias_sampling_basic.json", "r") as f:
    routine_dict = json.load(f)

uncompiled_routine = SchemaV1(**routine_dict)
compiled_routine = compile_routine(uncompiled_routine).routine

assignments = {"L": 100, "mu": 10}

evaluated_routine = evaluate(compiled_routine, assignments).routine
```

Now in order to inspect the results you can do:

```python
print(compiled_routine.resources["T_gates"].value)
print(evaluated_routine.resources["T_gates"].value)
```

which returns both symbolic the expression for the T-count as well as result for specific values of `L` and `mu`:

```
4*L + 8*L/multiplicity(2, L) + 4*mu + swap.O(log2(L)) - 8
swap.O(log2(100)) + 832
```

To go step by step through the process and see how you can use bartiq for your algorithms, please take a look at our tutorials, starting with [basic example](https://psiq.github.io/bartiq/latest/tutorials/01_basic_example/). 


## Documentation

Documentation for `bartiq` can be found [here](https://psiq.github.io/bartiq/).
