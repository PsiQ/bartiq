from dataclasses import dataclass

from qref.functools import accepts_all_qref_types
from qref.schema_v1 import RoutineV1


@dataclass
class RepetitionsVerificationOutput:
    """Dataclass containing the output of the repetitions verification"""

    problems: list[str]

    @property
    def is_valid(self):
        return len(self.problems) == 0

    def __bool__(self) -> bool:
        return self.is_valid


@accepts_all_qref_types
def verify_uncompiled_repetitions(routine: RoutineV1) -> RepetitionsVerificationOutput:
    """Checks whether program has correct repetitions structure.

    This means that each routine with repetitions doesn't have any costs on its own
    and has exactly one child.

    Args:
        routine: Routine or program to be verified.
    """
    problems = _verify_routine_repetition(routine)
    return RepetitionsVerificationOutput(problems)


def _verify_routine_repetition(routine: RoutineV1, ancestor_path: tuple[str, ...] = ()) -> list[str]:
    return [
        *_ensure_one_child(routine, ancestor_path),
        *_ensure_no_resources(routine, ancestor_path),
        *[
            problem
            for child in routine.children
            for problem in _verify_routine_repetition(child, ancestor_path + (routine.name,))
        ],
    ]


def _ensure_one_child(routine: RoutineV1, ancestor_path: tuple[str, ...] = ()) -> list[str]:
    routine_path = ancestor_path + (routine.name,)
    if len(routine.children) == 0 and routine.repetition is not None:
        return [f"Routine with repetition doesn't contain any children: {routine_path}."]
    elif len(routine.children) > 1 and routine.repetition is not None:
        return [f"Routine with repetition contains more than one child: {routine_path}."]
    else:
        return []


def _ensure_no_resources(routine: RoutineV1, ancestor_path: tuple[str, ...] = ()) -> list[str]:
    routine_path = ancestor_path + (routine.name,)
    if len(routine.resources) != 0 and routine.repetition is not None:
        return [
            f"Routine with repetition should not contain any resources: {routine_path}, "
            f"resources: {[resource.name for resource in routine.resources]}."
        ]
    else:
        return []
