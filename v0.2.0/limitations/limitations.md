# Known limitations

This page lists some prominent limitations and missing features. Please keep in mind that `bartiq` is currently under active development, so some of these might soon be resolved. For an up-to-date list of all planned features, please see the [GitHub issues page](https://github.com/PsiQ/bartiq/issues).

## Balance between exact and approximate costs

For some quantum algorithms, the expression for their cost might depend on the inputs. For example, the uncontrolled SWAP gate can be implemented with just 3 CNOTs (no T gates), but the controlled version requires using T gates, depending on the number of controls. This effectively introduces a conditional cost. It can be modelled using bartiq in a couple of ways:
- using a step function (Heaviside theta) allows to model cases where the cost has different values depending if given parameter is below or above certain threshold.
- using [piecewise sympy function](https://docs.sympy.org/latest/modules/functions/elementary.html#piecewise)
- using user-defined functions instead of sympy expressions


However, all these methods introduce additional complexities which may or may not be appropriate for a given use-case. Ultimately, bartiq does not provide any native approach for dynamic definition of routines based on the topology, so users are responsible for such decision-making prior to compilation.


## Non-trivial port sizes

Right now bartiq does not support use of arbitrary expressions for input port sizes, but rather requires input port sizes to be constant or defined by as a single parameter. In the case that this isn't sufficient, it can be somewhat circumvented by introducing `local_variables`, but it's not elegant solution and might cause some unforeseen issues in the compilation process. Please reach out to a `bartiq` core developers if you are interested in this use-case and we will support you as needed.

## Qubit counts

While finding the size of a particular port/register in bartiq is simple, getting the full qubit count needed for a given algorithm is currently not something that bartiq natively supports, and rather requires such expressions to be defined by user-provided expressions. This is because there are typically subtleties involving counting ancillary qubits which are difficult or impossible to automate, such as algorithmic design choices concerning clean or dirty qubit reuse, etc. 

(N.B. we hope to support automatic qubit cost tabulation in the future, and so have included `qubits` as one of the native cost types, although at present it's not being used in any meaningful way.)

## Keeping track of where given register is being used

Bartiq operates purely on ports and connections between routines and hence does not have a concept of persistent qubits registers which exist beyond a single connection. This gives more flexibility in connecting routines and not having to deal with qubits allocation and deallocation. However, it also means that it is not natively possible to query whether the qubits referenced by a given connection correspond to any persistent quantum register or variable.

## Repeated subroutines

Currently bartiq has limited capability to support a case where a particular subroutine is repeated multiple times.
It can be done for a simple case where all the repetitions act on the same qubit registers. However, routines where target register change or we have a recursive definition (such as controlled unitaries in QPE) are not something one can natively support in Bartiq.