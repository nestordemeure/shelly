# Prompt

This was developed using Claude (Opus) and the following prompts, plus some manual cleaning:

````md
Write a `shelly.py` Python file. It will be an LLM-based terminal assistant.

Its system prompt tells it it is called "Shelly" and is there to run shell commands for the user.
It is given the last 100 unique user shell commands, to serve as inspiration when running things for the user.

It has access to the following tools:
* `ls` which can run ls with any options, to find out about files available (no user validation needed)
* `pwd` which can run pwd with any options, to find out about paths (no user validation needed)
* `which` which can run which with any options, to find out about commands available (no user validation needed)
* `run` which can run arbitrary sequences of shell commands (this one asks for user validation, in case of a "no" the user is invited to explain why not so that the model can adjust)

It can be called by itself, in which case it starts the chat inviting the user to ask a question.
Or, it can be called with a question (ie `$ shelly list the ifles in the current folder`) in which case that question becomes the user's first message.
Either way it is there to suggest shell commands (or series of commands), explaining them, then trying to run them / having them validated by the user if need be.

Any command ran is displayed for the user to see what is happening.

It will be based on Claude-Haiku, via the Anthropics API, using a dotfile (`.env`) to load the credentials.
````

````md
I cleaned up the file following my specifications. Let's work on the tools a bit.

Improve on the `which` tool documentation to mention that it can be used to both locate a command, and ascertain whether it is available (ie, to see if a user has `convert` installed).

The `run` command should be able to run a *list* of commands, instead of being restricted to one. That way we can get a single validation from the user for a block of code.
````

````md
Great! Now let's make tool calling less verbose.

When calling a tool, I only want what will be calle dto be displayed in a code block then, after the user (optionally) acceps to run the tool, and the tool returns, the output to also be displayed.
````