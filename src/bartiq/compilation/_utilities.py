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

import ast
from typing import Any


def is_single_parameter(expression: Any) -> bool:
    """Returns True if the expression is just a single parameter, else False."""
    try:
        return _is_python_tree_a_single_param(
            ast.parse(
                expression.replace("#", "__hash__").replace(  # Handle hashes in port names
                    "lambda", "__lambda__"
                )  # Handle special case of lambda
            )
        )
    except (TypeError, AttributeError):
        return False  # If it's not a string then certainly it's not a single parameter
    except SyntaxError as e:  # In principle this should not happen
        raise ValueError(
            f"Expression {expression} failed to parse. This is most likely a bug " "in Bartiq, please report it."
        ) from e


def _is_python_tree_a_single_param(tree):
    return (
        # is parsed expression a module?
        isinstance(tree, ast.Module)
        and
        # Having one child?
        len(tree.body) == 1
        and
        # And this only child is an expression?
        isinstance(tree.body[0], ast.Expr)
        and
        # And this expression contains only a variable Name or an Attribute access?
        isinstance(tree.body[0].value, (ast.Name, ast.Attribute))
    )
