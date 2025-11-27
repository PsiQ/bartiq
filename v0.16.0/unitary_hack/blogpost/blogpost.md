# Unitary Hack Blogpost

## Introduction

Fault-tolerant quantum computing (FTQC) isn’t a far-off goal anymore: PsiQuantum is committed to building a utility-scale computer in Australia by the end of 2027, and many other hardware companies have designed their roadmaps to reach utility-scale by the end of the decade. This machine will be able to run programs that classical computers simply cannot, but only if we have the algorithms that are ready to be run.

Writing quantum algorithms for fault-tolerant quantum computers is difficult enough, and it’s made harder by a lack of usable infrastructure. Most research teams still rely on custom scripts, manual derivations, or one-off tools for estimating how many logical qubits or gates their algorithms will require. These workflows are hard to share and scale, and almost impossible to standardize.

![Figure 1](unitary_hack_image_1.png){style="display:block; margin:0 auto;"}
***Figure 1.** a) An example simple algorithm that takes in a register of n qubits and performs routines A and B on them. b) Representation of the algorithm as a directional graph that is written in the QREF format and then processed by Bartiq to output the total QRE for the algorithm. The costs of routines A and B are separately defined in the QREF file.*

At PsiQuantum, we built Bartiq to address this problem directly. It’s an open-source engine for creating modular, symbolic quantum resource estimates, which helps researchers gain insight about how their algorithms scale.

These tools are just the start. In addition, researchers need better interfaces, smarter integrations, and more input from the broader software community. If you care about building developer infrastructure and want to work on something that directly accelerates the future of computing, we would love your help.


## Gap in the available tools for FTQC algorithm creation

Before dedicated tools existed, researchers pieced together quantum resource estimates (QREs) the way a carpenter might build a bookshelf: using hand tools, trial and error, and a lot of “sawdust” in the Appendix, leading to a situation where estimating the cost of running a quantum algorithm on a fault-tolerant quantum computer was more of an artisanal craft than a standardized engineering process. Researchers relied on a combination of custom Python and Mathematica scripts, manual derivations, and hand-assembled tables that ended up in lengthy appendices, resulting in papers with 60+ pages that take weeks to months to be properly understood. Moreover, many interesting new techniques ended up buried in some appendix and rarely revisited. These one-off resource estimates were good enough for papers, conferences, or internal prototypes, but they weren’t easy to compare or designed to be shared and built upon by other researchers in the community.

![Figure 2](unitary_hack_image_2.png){style="display:block; margin:0 auto;"}
***Figure 2.** Circuit (a) and directional-graph (b) representation of the state-preparation algorithm from Fig. 11 of Babbush et al.; Phys. Rev. X 8, 041015 (2018). Separate subroutines of the algorithm are framed in different colors for easier orientation. Without QREF and Bartiq, defining and processing such a large circuit would be challenging.*

As the FTQC-algorithms ecosystem grows, especially given the recent momentum toward FTQC hardware, the need for automation and structure in the development process is growing in parallel. The growth of the ecosystem also increases the number of connections between participants, which creates more opportunities for collaboration and exchange of information. Individual researchers also need to more easily understand how their routines scale and how they can be reused across applications to accelerate the development of FTQC algorithms.

This has prompted the development of new QRE tools. Across the quantum landscape, multiple companies and research groups are working on software to improve resource estimation. At PsiQuantum, our work in this space revealed two especially persistent problems. First, tools often couldn’t talk to each other – there was no shared format for representing QREs across tools and enabling interoperability. Second, there was no scalable method for managing the symbolic resource expressions that arise when making QREs. Addressing these two gaps led us to the development of QREF and Bartiq, respectively.


## QREF – the open-source format for FTQC algorithm distribution

The first gap that we addressed was interoperability. Even though more QRE tools are coming online, there is no consistent way for them to exchange algorithm information. That makes it difficult to combine tools, compare outputs, or build larger workflows across research teams. QREF (Quantum Resource Estimation Format) was designed to solve this.

QREF is a lightweight, open-source format based on YAML that describes a quantum algorithm’s structure and associated resource estimates. It includes support for symbolic cost expressions and parameterized inputs, and it is intentionally limited in scope: it doesn’t try to enable circuit simulation or low-level compilation details; instead, it focuses on providing a blueprint-style description of a quantum algorithm that can be easily shared, parsed, and reused.

With QREF, an algorithm defined by one researcher can be picked up by another, or integrated into another tool, without needing to reinterpret or reimplement the logic. This makes it possible to treat QREs as composable software artifacts rather than one-time exports buried in an appendix of a paper. That opens the door to more consistent benchmarking, higher-quality algorithm libraries,
and easier collaboration between research groups and across QRE tools.

The QREF format is just the start of the conversation; please raise an issue in the [QREF repo](https://github.com/PsiQ/qref) if you have any feedback.


## Bartiq – the open-source tool for gaining insight into QRE scalability

Interoperability solves part of the problem — but quantum algorithms don’t need to produce just numbers; it could be helpful to produce symbolic cost expressions that describe how resources grow with the problem’s size. That’s where Bartiq comes in.

Bartiq is a Python-based, open-source engine for compiling and analyzing symbolic quantum resource estimates. Researchers can define subroutines in terms of their costs, e.g., “this subroutine requires 2n*log n T-gates”, and then to combine those subroutines into full algorithms. As the subroutines are combined, Bartiq tracks and manipulates the symbolic expressions representing various resource metrics, e.g., qubit count, gate depth, T-count, etc.

Under the hood, Bartiq uses SymPy to manage algebraic expressions and substitutions. The result is a workflow where resource models remain composable and scalable, rather than collapsing into numeric estimates too soon. This is especially useful when comparing algorithm variants, analyzing bottlenecks or scaling of the algorithms.

Importantly, Bartiq and QREF both operate at the logical circuit level. If you’ve designed an algorithm and can describe it in high-level logical operations, you can export it to QREF, analyze it with Bartiq, and begin estimating and optimizing its fault-tolerant cost profile.


## Invitation to contribute to Bartiq’s development
Both QREF and Bartiq are open-source, Python-based tools, and they’re still evolving. The goal is to support the FTQC community by providing infrastructure that makes algorithm development faster, more transparent, and more easily reusable. However, reaching that goal has some dependance on the contributions from the community itself.

That could mean contributing to new subroutines or cost models, improving the compilation engine, or helping with the integration into other tool chains. It could also mean just trying the tools, providing feedback, or proposing new use cases. Every contribution, large or small, helps strengthen the foundation for scalable FTQC algorithm development.
We are actively developing Bartiq to improve its usability, expand the integration possibilities, and enhance its documentation. This effort is shaped by feedback from adopters and collaborators with the long-term vision being to build shared pipelines and libraries, which is the kind of infrastructure FTQC-algorithm-development software needs to become more like classical software engineering.

We invite the community to explore, build, and improve because building better tools together now is how we will unlock the full potential of FTQC in the future.
