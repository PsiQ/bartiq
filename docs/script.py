import json

from bartiq import Routine, compile_routine, evaluate

with open("data/basic_example.json", "r") as f:
    routine_dict = json.load(f)

uncompiled_routine = Routine(**routine_dict)
compiled_routine = compile_routine(uncompiled_routine)

assignments = ["N=10"]

evaluated_routine = evaluate(compiled_routine, assignments)
print(compiled_routine.resources["T_gates"].value)
print(evaluated_routine.resources["T_gates"].value)
