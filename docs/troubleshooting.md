# Troubleshooting

Debugging `bartiq` is not always straightforward, so please see below for a number of best practices and common issues:


- Bartiq routines can get pretty complicated very quickly, especially if nested subroutines are involved. Therefore when you get an error, try isolating the issue and work on a smaller example:
	- First make sure that each child subroutine compiles correctly on its own. If not, this might suggest where the issue is.
	- Try removing all the unnecessary fields, children, connections, etc. and prepare a minimal failing example.

- Take a look at [the list of issues on GitHub](https://github.com/PsiQ/bartiq/issues) and see if other users have a similar problem!
	- If not, consider creating one!
	- Submitting issues is the most transparent way to give us feedback – even if something works, but is extremely unintuitive, we want to make it easier to use. The goal of this tool is to save you time, not waste it on unhelpful error messages.
