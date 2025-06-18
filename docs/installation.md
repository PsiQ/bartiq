# Installation

## Via `pip`

To install `bartiq` run:

```bash
pip install bartiq
```

`bartiq` also has a number of optional extras, which can be installed with the following commands:

```bash
# To use jupyter integrations
pip install "bartiq[jupyter]"

# To use optimization tooling
pip install "bartiq[optimization]"

# To use a full suite of interactive tools
pip install "bartiq[interactive]"
```
Installing `bartiq[interactive]` encapsulates the `bartiq[jupyter]` install, with additional packages for interactive plotting of routines. Multiple extras can be installed with comma separation inside the square brackets, i.e. `bartiq[jupyter,optimization]`.

!!! note

    To use the [QREF](https://github.com/PsiQ/qref/) rendering tool in Jupyter Notebook, ensure the Graphviz software is installed on your OS and that its executables are included in your system variables. For installation instructions, please refer to the [Graphviz download page](https://graphviz.org/download/).


## From Source

For a source install run:

```bash
# Clone bartiq repo (you can use HTTP link as well)
git clone git@github.com:PsiQ/bartiq.git
cd bartiq
pip install .
```
With a source install optional extras can be installed via `pip install ".[jupyter]"` and similarly for `optimization`, `interactive`.


## Development

For development we recommend installing using `poetry`:

```bash
git clone git@github.com:PsiQ/bartiq.git
cd bartiq
pip install poetry
poetry install
```

With `poetry`, install extras with `poetry install -E jupyter`, and similarly for `optimization`, `interactive`.

This will create a virtual environment for you and install all developer and
docs dependencies within it. For Poetry 2.0 and above, you can enter this environment by running:
```bash
$(poetry env activate)
```
or, for Poetry 1.x:
```bash
poetry shell
```

We encourage the use of `pre-commit` hooks in `bartiq` development to maintain code quality standards. You can view the documentation for `pre-commit` [here](https://pre-commit.com). WPrior to committing anything to your branch, run the following commands:
```bash
poetry run pre-commit install
```
This will ensure that any committed changes conform to `bartiq` development standards. 

To run all `pre-commit` hooks locally:
```bash
poetry run pre-commit run --all
```
This command will print a summary of the current code quality in your branch.

!!!warning
    If using Visual Studio Code, the `git` integration in Source Control does not detect `pre-commit` hooks. To use these, `git` commands must be run through the terminal in the installed `bartiq` virtual environment.

### Tests

To run the test suite, from the project root directory run:

```bash
poetry run pytest
```

### Documentation

To build docs, from the project root directory run:

```bash
poetry run mkdocs serve
```
