#!/usr/bin/env bash

set -uo pipefail

ISORT=false
BLACK=false
FLAKE8=false
MYPY=false

ISORT_RC=0
BLACK_RC=0
FLAKE8_RC=0
MYPY_RC=0

if [ $# -eq 0 ]; then
    ISORT=true
    BLACK=true
    FLAKE8=true
    MYPY=true
else
    for arg in "$@"; do
        case "$arg" in
            --isort) ISORT=true ;;
            --black) BLACK=true ;;
            --flake8) FLAKE8=true ;;
            --mypy) MYPY=true ;;
            --help|-h)
                echo "Usage: $0 [--isort] [--black] [--flake8] [--mypy]"
                echo "If no arguments are passed, all checks are run."
                exit 0
                ;;
            *) echo "Unknown option: $arg" && exit 1 ;;
        esac
    done
fi

if [ "$ISORT" = true ]; then
    printf "\nRunning isort...\n"
    poetry run isort --filter-files --profile=black src/ || ISORT_RC=$?
    poetry run isort --filter-files --profile=black tests/ || ISORT_RC=$?
fi

if [ "$BLACK" = true ]; then
    printf "\nRunning black...\n"
    poetry run black -l 120 . || BLACK_RC=$?
fi

if [ "$FLAKE8" = true ]; then
    printf "\nRunning flake8...\n"
    poetry run flake8 --config=.flake8 src/ || FLAKE8_RC=$?
fi

if [ "$MYPY" = true ]; then
    printf "\nRunning mypy...\n"
    poetry run mypy --install-types --non-interactive src/ || MYPY_RC=$?
fi

# Summary
printf "\nLint summary:\n"
[ "$ISORT" = true ] && echo "isort:  $([ $ISORT_RC -eq 0 ] && echo PASS || echo FAIL)"
[ "$BLACK" = true ] && echo "black:  $([ $BLACK_RC -eq 0 ] && echo PASS || echo FAIL)"
[ "$FLAKE8" = true ] && echo "flake8: $([ $FLAKE8_RC -eq 0 ] && echo PASS || echo FAIL)"
[ "$MYPY" = true ] && echo "mypy:   $([ $MYPY_RC -eq 0 ] && echo PASS || echo FAIL)"

# Exit code: sum of individual failures (any nonzero means failure)
EXIT_CODE=$((ISORT_RC + BLACK_RC + FLAKE8_RC + MYPY_RC))
exit $EXIT_CODE
