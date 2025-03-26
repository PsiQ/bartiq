# Known limitations

This page lists some prominent limitations and missing features. Please keep in mind that `bartiq` is currently under active development, so some of these might soon be resolved. For an up-to-date list of all planned features, please see the [GitHub issues page](https://github.com/PsiQ/bartiq/issues).

## Balance between exact and approximate costs

For some quantum algorithms, the expression for their cost might depend on the inputs. For example the uncontrolled SWAP gate can be implemented with just 3 CNOTs (no T gates), but the controlled version requires using T gates, depending on the number of controls. This effectively introduces a conditional cost. It can be modelled using bartiq in a couple of ways:
- using a step function (Heaviside theta) allows us to model cases where the cost has different values depending if a given parameter is below or above certain threshold.
- using [piecewise sympy function](https://docs.sympy.org/latest/modules/functions/elementary.html#piecewise)
- using user-defined functions instead of sympy expressions

However, all these methods introduce additional complexities which may or may not be appropriate for a given use-case. Ultimately, bartiq does not provide any native approach for dynamic definition of routines based on the topology, so users are responsible for such decision-making prior to compilation.


## Keeping track of where given register is being used

Bartiq operates purely on ports and connections between routines and hence does not have a concept of persistent qubits registers which exist beyond a single connection. This gives more flexibility in connecting routines and not having to deal with qubit allocation and deallocation. However, it also means that it is not natively possible to query whether the qubits referenced by a given connection correspond to any persistent quantum register or variable.
