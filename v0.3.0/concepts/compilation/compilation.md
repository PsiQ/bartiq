# Compilation

Here we will describe how the compilation process in Bartiq works.
Please keep in mind, that while we try to keep this page up-to-date, in the end the code is the only source-of-truth. If you notice any discrepancies, between what's described here and how Bartiq behaves, please [create an issue](https://github.com/PsiQ/bartiq/issues)!

## Bird's eye perspective on compilation

Compilation consists of the following steps:

1. Precompilation - ensures that Routine has all the components needed for the rest of the compilation process.
2. Routine-to-function conversion – maps routine to functions (see glossary), on which compilation is performed.
3. Function compilation – compiles all the functions to a 


## Step 1 – precompilation

This stage "precompiles" the routine by making a series of reasonable assumptions about what the user would have
wanted when they have not been explicit. For example, insertion of "trivial" routines for known subroutines or
"filling out" routines which have only been partially defined. It is expected that this precompilation stage will
grow as more sensible defaults are requested by users. For more details please visit [precompilation page](precompilation.md).

## Step 2 – routine to function conversion

Before being compiled, routines must first be mapped to compilable function objects (see glossary).
At this stage, we perform a number of steps to map the routines into functions that are ready for
compilation:

1. Map routines to "local" functions: first, we simply map the routines to functions in a local manner, whereby they
   are unaware of their location within the full definition. To do this we convert `Routine` objects to `RoutineWithFunction`, which augments Routine class with a `symbolic_function` field.
2. Map "local" functions to "global" functions: we tell the functions where they live in the definition, thereby
   making each parameter and any named functions unique within the definition by prepending it with its full path from the root.
3. Pull in input register sizes: in order to allow for input register sizes to be compiled properly, low-level input
   register sizes must be renamed by the size parameters used by high-level registers. This process is referred to as
   "pulling in" those high-level register sizes.
4. Push out output register sizes: to ensure correct compilation for output register sizes, those associated with
   low-level routines must be "push out" to either other low-level routines or eventually high-level routines.
5. Parameter inheritance: lastly, any high-level routines parameters are passed down to low-level routines by
   substituting the low-level routine parameters with the high-level ones.

Once this is complete, each subroutine has an associated function, which is expressed in terms of global variables.

## Step 3 – functions compilation

At the start of this stage routine is annotated with functions which contain all the required information in the global namespace. Compilation starts from the leafs, each routine can only be compiled once all of its children have been compiled ("bottom-up"). This stage contains a number of sub-steps:

1. Compile functions of self and children (non-leaves only): for leaves, no function compilation is necessary, but
   non-leaves need to update information in associated function with the information contained in their children's functions.
2. Undo register size pulling and pushing: to ensure a correct local estimate, we must "undo" the pulling in and pushing
   out of register size params done during routine-to-function conversion.
3. Derefence global namespace: again, to ensure a correct local routine definition, we dereference the global
   namespace. This means dropping the path prefix from all the variables: e.g.: `root.child.gchild.N` would become `N`.
4. Map function to routine: lastly, once the correct local function has been compiled, we map the function object
   back to a routine by updating routine's attribute and removing associated function object.


## Glossary

- **Function**: functions are objects defined with `SymbolicFunction` class. Each function has a defined set of inputs and outputs. Inputs are independent variables, whic are basically bare symbols, without any structure. Outputs are dependent variables, meaning they are variables defined by expressions which are dependent on the input variables.
- **Global and local**: in this context "global" means "defined at the root-level of the routine we compile". Local, on the contrary, means "defined for the subroutine currently being operated on". Intuitively, global parameters are those that correspond to the domain of the problem that we are trying to solve, e.g.: number of bits of precision of QPE. On the other hand, local parameters correspond to the implementation details of the algorithm we are analyzing, e.g.: size of the QFT routine in QPE. Compilation process allows us to express all the local parameters in the algorithm in terms of the global parameters.


