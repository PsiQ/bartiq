# Troubleshooting

We know that debugging `bartiq` can sometimes be challenging. That's why we collected here some the best practices and common issues that you might run into.


- Bartiq routines can get pretty complicated very quickly, especially if nested subroutines are involved. Therefore when you get an error, try isolating the issue and work on a smaller example:
	- First make sure that each child subroutine compiles correctly on its own. If not, this might suggest where the issue is.
	- Try removing all the unnecessary fields, children, connections, etc. and prepare a minimal failing example.

- Take a look at [the list of issues on GitHub](https://github.com/PsiQ/bartiq/issues) and see if other didn't have a similar problem!
	- If not, consider creating one!
	- Submitting issue is the most transparent way to give us feedback – even if something works, but is extremely unintuitive, we want to make it easier to use. The goal of this tool is to save you time, not waste it on unhelpful error messages.

- If you see a `passthrough` in your error message, but you don't know where it came from, passthroughs are added automatically during one of the precompilation stages.