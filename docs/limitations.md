# Known limitations

On this page we'd like to list some most prominent limitations and missing features. Please keep in mind that bartiq is under constant development, so some of these might soon be resolved. We keep track of them in the [issues tab on our GitHub](https://github.com/PsiQ/bartiq/issues). For more detailed and most up-to-date discussion please go there.


## Balance between exact and approximate costs

For some quantum algorithms, the expression for their cost might depend on the inputs. For example, the uncontrolled SWAP gate can be implemented with just 3 CNOTs (no T gates), but the controlled version requires using T gates, depending on the number of controls. This effectively introduces a conditional cost. It can be modelled using bartiq in a couple of ways:
- using Heaviside theta
- using [piecewise sympy function](https://docs.sympy.org/latest/modules/functions/elementary.html#piecewise)
- using user-defined functions instead of sympy expressions


However, all these methods introduce additional complexities. In the end, a person writing the algorithm needs to make a call, whether they want to have an expression that's very complicated and accurate or rather one that might have some minor issues, but is much easier for a human to understand and analyze.


## Non-trivial port sizes

Right now bartiq does not support expressions for port sizes, only constants and symbols. It can be somewhat circumvented by introducing `local_variables`, but it's not elegant solution and might cause some unforseen issues in the compilation process.

## Qubit counts

While getting a size of a particular register in bartiq is simple, getting the full qubit count needed for a given algorithm is currently not something that bartiq natively supports. There are subtelties involving counting ancilla qubits, deciding which qubits need to be allocated at the same time, etc., which need to be taken into account. 

You might have noticed that we have `qubits` as one of the cost types, but unfortunately, it's not being used in any meaningful way yet.

## Keeping track of where given register is being used

Bartiq operates on "ports and connections" and it does not have a concept of "qubits registers". This gives more flexibility in connecting routines and not having to deal with qubits allocation and deallocation. However, it also means that answering a question like: "Tell me which subroutines used given qubit register" is impossible with bartiq.