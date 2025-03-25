# Installation

## Via `pip`

To install `bartiq` run:

```bash
pip install bartiq
```

!!! info

    If you wish to use the package's jupyter integrations, run `pip install "bartiq[jupyter]"` instead.

## From Source

For a source install run:

```bash
# Clone bartiq repo (you can use HTTP link as well)
git clone git@github.com:PsiQ/bartiq.git
cd bartiq
pip install .
```

!!! info

    If you wish to use the package's jupyter integrations, run `pip install ".[jupyter]"` instead.

## Development

For development we recommend installing using `poetry`:

```bash
git clone git@github.com:PsiQ/bartiq.git
cd bartiq
pip install poetry
poetry install
```

!!! info

    If you wish to use the package's jupyter integrations, run `poetry install -E jupyter` instead.

This will create a virtual environment for you and install all developer and
docs dependencies within it. For Poetry 2.0 and above, you can enter this environment by running:
```bash
$(poetry env activate)
```
or, for Poetry 1.x:
```bash
poetry shell
```

### Tests

To run the test suite, from the project root directory run:

```bash
poetry shell  # If not already in the venv
pytest
```

### Documentation

To build docs, from the project root directory run:

```bash
poetry shell  # If not already in the venv
mkdocs serve
```
