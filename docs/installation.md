# Installation

## Basic

To install `bartiq` run: 

```bash
pip install bartiq
```

## From Source

For a source install run:

```bash
# Clone bartiq repo (you can use HTTP link as well)
git clone git@github.com:PsiQ/bartiq.git
cd bartiq
pip install .
```

## Development

For development we recommend installing using `poetry`: 

```bash
git clone git@github.com:PsiQ/bartiq.git
cd bartiq
pip install poetry "poetry-dynamic-versioning[plugin]"
poetry install
```

This will create a virtual environment for you and install all developer and docs dependencies within it.

To enter this environment run:

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
