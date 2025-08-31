# QCE25 tutorials

Here are the notebooks for the TUT03 — Using Bartiq for Symbolic Resource Estimation of Fault-Tolerant Quantum Algorithms, taking place on Sunday August 31st 2025 at IEEE Quantum Week in Albuquerque.


## Installation instructions

In order to run the notebooks please follow these steps:

0. Create a new virtual environment!

If you know how to do it, please use youre preffered way.
If not, here's the simplest way to do it:
`python -m venv bartiq_venv`

On Unix systems:
`source bartiq_venv/bin/activate`

On Windows:
`.\bartiq_venv\Scripts\Activate`

1. Clone Bartiq repository with either:

`git clone git@github.com:PsiQ/bartiq.git` 

or 

`git clone https://github.com/PsiQ/bartiq.git` 

2. Run: `pip install "bartiq[optimization, interactive]" jupyterlab ipykernel matplotlib`

3. Navigate to this directory:

`cd bartiq/docs/tutorials/2025_ieee_qw`

4. Run `python -m ipykernel install --user --name bartiq_venv`.

5. Run `jupyter lab` and select `bartiq_venv` as the kernel.

### Optional dependencies:
- The "Intro to Bartiq" notebook can be transformed into a presentation using `jupyterlab_rise` library.
- For visualizations of QREF routines you might want to install [graphviz](https://graphviz.org/).