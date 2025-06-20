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

import pytest

from bartiq.symbolics import sympy_backend


# To add more backends to tests, simply parametrize this fixture.
@pytest.fixture
def backend():
    """Backend used for manipulating symbolic expressions."""
    return sympy_backend


def pytest_addoption(parser):
    parser.addoption(
        "--no-perf-tests",
        action="store_true",
        default=False,
        help="skip tests marked perftest",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--no-perf-tests"):
        return
    skip = pytest.mark.skip(reason="skipped perftest (use without --no-perf-tests to run)")
    for item in items:
        if "perftest" in item.keywords:
            item.add_marker(skip)
