<h1><img src="https://raw.githubusercontent.com/PsiQ/bartiq/main/docs/assets/logo.png" width=23> Bartiq</h1>

## What is bartiq

Bartiq allows for the compilation and analysis of fault tolerant quantum algorithms, in order to better understand what resources they require to run on a quantum computer. Quantum resource estimation (QRE) focuses on key logical-level resources like $T$-gates, Toffolis, circuit active volume, and qubit count. In `bartiq`, quantum algorithms are expressed as a collection of subroutines, each of which can have its local resource cost expressed symbolically. The compilation engine in `bartiq` creates global resource costs from these local definitions. 

## Installation

To install `bartiq` run:
```bash
pip install bartiq
```
 

## Documentation

Complete documentation for `bartiq` can be found [here](https://psiq.github.io/bartiq/).



## Quick start

In `bartiq` we can express a quantum algorithm as a collection of subroutines, each of which has a respective symbolic resource cost, and compile it to get a global symbolic resource cost for the whole algorithm.

As an example we consider the following circuit, from [Encoding Electronic Spectra in Quantum Circuits with Linear T Complexity](https://journals.aps.org/prx/abstract/10.1103/PhysRevX.8.041015). This circuit prepares an arbitrary state with $L$ unique amplitudes, and is equivalent to classical alias sampling. From Fig. 11 in the paper:

![Alias Sampling](docs/images/alias_sampling_paper.png)

In order to quickly get started with `bartiq`, you can load this as an example routine and use it as follows (click here to download <a href="https://raw.githubusercontent.com/PsiQ/bartiq/main/docs/data/alias_sampling_basic.json" download>`alias_sampling_basic.json`</a>):


```python
import json
from bartiq import compile_routine, evaluate
from qref import SchemaV1

with open("alias_sampling_basic.json", "r") as f:
    routine_dict = json.load(f)

uncompiled_routine = SchemaV1(**routine_dict)
compiled_routine = compile_routine(uncompiled_routine).routine
```
After loading the alias sampling JSON file we cast it to the `qref.SchemaV1` type, our [data format](https://github.com/PsiQ/qref) for representing quantum algorithms for the purposes for resource estimation. This provides us with an `uncompiled_routine`, which we can then compile with `bartiq`. The compilation engine will propagate the resource costs from low-level subroutines up, to create aggregated global costs for the whole circuit. 

To see, for example, the symbolic $T$-gate count for this circuit:
```python
print(compiled_routine.resources["T_gates"].value)
>>> 4*L + 8*L/multiplicity(2, L) + 4*mu + O(log2(L)) - 8
```

To obtain numeric resource costs we can assign values to our variables $L$ and $\mu$ and then `evaluate` the routine

```python
assignments = {"L": 100, "mu": 10}
evaluated_routine = evaluate(compiled_routine, assignments).routine

print(evaluated_routine.resources["T_gates"].value)
>>> O(log2(100)) + 832
```

To go step by step through the process and see how you can use `bartiq` for your algorithms please take a look at our tutorials, starting with a [basic example](https://psiq.github.io/bartiq/latest/tutorials/01_basic_example/). 


