# Precompilation

Precompilation is a collection of steps we perform prior to the proper compilation. They apply a series of reasonable assumptions about what the user would have wanted when they have not been explicit in defining their routine.

## Usage


By default precompilation is performed in the `compile_routine` method with a set of default stages. However, API for precompilation has been designed to make customizing precompilation stages easy. 

First, user can define their own precompilation stages. All precompilation stages have the same interface – as inputs they take `Routine` and `SymbolicBackend` and they modify the provided `Routine` object in place. Therefore adding a custom stage requires simply writing a method which complies with this interface.

Second, the choice and order of the stages used can be changed by passing them explicitly through `precompilation_stages` argument of the `compile_routine` method.

Precompilation can also be performed outside of the `compile_routine` by using `precompile` method. 


## Precompilation stages

`bartiq.precompilation` module currently contains the stages listed below. They are applied by default in the order provided.

1. Add default properties: adds default properties for the subroutines of certain type. Right now it only acts on the routines of type `merge`. If the size of the output port is not specified, it sets it to the sume of the sizes of the input ports.

2. Add default additive resources: if the user defined resource of type `additive` anywhere in any of the subroutines, it implies that this resource should be included in their parent as a sum of the resources of their children. An example of an additive resource is T gate – if a routine contains two children A and B, which have resource `T` defined, equal to `N_A` and `N_B`, after performing this stage, the parent will also have resource `T` with the cost equal to `N_A + N_B`.

3. Add passthrough placeholder: passthrough is a situation where we have a routine, which has a connection that goes straight from the input to output port, without touching any subroutines on its way. Currently Bartiq can't handle such cases in the compilation process and in order to get around in the precompilation process we add a "virtual" routine of type `passthrough`, which is not associated with any real operation (it can be thought of as an "identity gate"), but which removes the passthrough from the topology of the routine.

4. Removing non-root non-leaf input register sizes: currently Bartiq cannot handle situation where port get a size assigned twice. For example, the first assigned comes from how the port is defined and the second comes from the connection (i.e. we derive the size of the port based on the fact that we know the size of the port on the other side of the connection). In order to alleviate this issue, in this precompilation step we set to `None` sizes of the input ports of all the routines which are neither root nor leaf.

5. Unroll wildcarded resources: if wildcard symbol (`~`) is detected in the resource, it gets replaced with the proper expression. An example usage would be when a routine has multiple children and we only to add the costs of the children with the name fitting certain pattern, e.g.: `cost = sum(select_~.cost)` would only add `cost` for the children whose names start with `select_` and that have `cost` resource defined.