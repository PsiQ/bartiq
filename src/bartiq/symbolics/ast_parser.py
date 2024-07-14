# Copyright 2024 PsiQuantum, Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""AST-based expression parser.

Contrary to pyparsing-based grammar from grammar.py, this module
utilizes ast to parse an arithmetic expression as Python expresson.
Since not all expressions that we use are correct Python expressions,
the parser first preprocesses expressions and replaces unallowed
syntax with carefully crafted function calls. In particular:

1. Port designations are converted to Port function call, e.g.

#in_0 -> Port(in_0)
a.b.#out_1 -> a.b.Port(out_1)

2. Wildcards are replaced by a call to wildcard function, e.g.

~.a -> wildcard().a
a~.b -> wildcard(a).b

Also, the parser here needs substantially less functionallity from
the "interpreter", i.e. something that constructs actual objects
from parsed informations.
"""
import re
from dataclasses import dataclass
from typing import Callable

_IDENTIFIER = r"[_a-zA-Z]\w*"
_NAMESPACE_IDENTIFIER = rf"{_IDENTIFIER}(\.{_IDENTIFIER})*"
_PORT_NAME = rf"#({_NAMESPACE_IDENTIFIER})"
_WILDCARD_PATTERN = rf"(({_IDENTIFIER})?)~"


@dataclass(frozen=True)
class PreprocessingStage:
    matches: Callable[[str], bool]
    preprocess: Callable[[str], str]


def _contains_port_name(expression):
    return "#" in expression


def _replace_port_names(expression):
    return re.sub(_PORT_NAME, r"Port(\1)", expression)


_PORT_NAME_REPLACEMENT = PreprocessingStage(matches=_contains_port_name, preprocess=_replace_port_names)


def _contains_wildcard(expression):
    return "~" in expression


def _replace_wildcards(expression):
    return re.sub(_WILDCARD_PATTERN, r"wildcard(\1)", expression)


_WILDCARD_REPLACEMENT = PreprocessingStage(matches=_contains_wildcard, preprocess=_replace_wildcards)


# If there are any new preprocessing stages, they should be added here
_PREPROCESSING_STAGES = (_WILDCARD_REPLACEMENT, _PORT_NAME_REPLACEMENT)


def _preprocess(expression):
    """Preprocess a given expression to make it suitable for parsing."""
    for stage in _PREPROCESSING_STAGES:
        if stage.matches(expression):
            expression = stage.preprocess(expression)
    return expression
