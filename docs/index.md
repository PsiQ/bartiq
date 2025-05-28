# Welcome to Bartiq

## Introduction

Bartiq is a Python library for compiling and analyzing fault-tolerant quantum algorithms to understand their computational requirements. It focuses on Quantum Resource Estimation (QRE), tracking key logical-level resources including T-gates, Toffolis, circuit active volume, and qubit count. In `bartiq`, quantum algorithms are expressed as subroutines with locally defined symbolic resource costs, which are used by its compilation engine to generate global resource costs from these local definitions.

To install `bartiq` via `pip`, run
```bash
pip install bartiq
```
 More detailed instructions can be found on the [installation page](installation.md).

## Quick start
As an example we consider the following circuit, from [Encoding Electronic Spectra in Quantum Circuits with Linear T Complexity](https://journals.aps.org/prx/abstract/10.1103/PhysRevX.8.041015). This circuit prepares an arbitrary state with $L$ unique amplitudes, and is equivalent to classical alias sampling. From Fig. 11 in the paper:

![Alias Sampling](images/alias_sampling_paper.png)

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
After loading the alias sampling JSON file we cast it to the `qref.SchemaV1` type, our [data format](https://github.com/PsiQ/qref) for representing quantum algorithms for the purposes for resource estimation. This provides us with an `uncompiled_routine`, which we can then compile with [`compile_routine`][bartiq.compile_routine]. The compilation engine will propagate the resource costs from low-level subroutines up, to create aggregated global costs for the whole circuit. 

To see, for example, the symbolic $T$-gate count for this circuit:
```python
print(compiled_routine.resources["T_gates"].value)
>>> 4*L + 8*L/multiplicity(2, L) + 4*mu + O(log2(L)) - 8
```

To obtain numeric resource costs we can assign values to our variables $L$ and $\mu$ and then [`evaluate`][bartiq.evaluate] the routine

```python
assignments = {"L": 100, "mu": 10}
evaluated_routine = evaluate(compiled_routine, assignments).routine

print(evaluated_routine.resources["T_gates"].value)
>>> O(log2(100)) + 832
```

As `bartiq` is primarily symbolic in nature, we do not have to assign values for all of our variables:
```python
assignments = { "mu": 10}
evaluated_routine = evaluate(compiled_routine, assignments).routine

print(evaluated_routine.resources["T_gates"].value)
>>> 4*L + 8*L/multiplicity(2, L) + O(log2(L)) + 32
```
## Next steps

- For more comprehensive examples, please see the [tutorials](tutorials/index.md).
- If you are interested in learning more about how the `bartiq` compilation engine works, please see the [compilation](concepts/compilation.md) page.
- For common issues, please check [troubleshooting](troubleshooting.md) section.
- You can find reference documentation for the public API of `bartiq`'s python package, please go to [reference](reference.md).
