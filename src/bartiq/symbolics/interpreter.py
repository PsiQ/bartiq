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

from abc import ABC, abstractmethod
from functools import wraps


class Interpreter(ABC):
    """Abstract base class for interpreting the Bartiq grammar."""

    def __init__(self, debug: bool = False):
        """Initialise the interpreter.

        Args:
            debug (bool, optional): If ``True``, debug information is printed for the interpreter. Default is ``False``.
        """
        self.debug = debug

    @abstractmethod
    def create_parameter(self, tokens):
        """Abstract method for interpreting parameter."""

    @abstractmethod
    def create_number(self, tokens):
        """Abstract method for interpreting numbers."""

    @abstractmethod
    def create_function(self, tokens):
        """Abstract method for interpreting functions."""


def debuggable(method):
    """A decorator for making interpreter methods easily debuggable."""

    @wraps(method)
    def debuggable_method(self: Interpreter, tokens):
        output = method(self, tokens)
        if self.debug:
            print(method.__name__)
            print(f"tokens={tokens}")
            print(f"parsed as: {output}\n")

        return output

    return debuggable_method
