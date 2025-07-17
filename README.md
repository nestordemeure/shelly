# Shelly 🐚

A smart terminal assistant that translates natural language into shell commands.

Describe what you want in plain English, and Shelly will figure out the right commands, explain what they do, and run them for you.

```sh
# Instead of remembering complex commands...
$ find . -type f -exec ls -la {} \; | sort -k5 -rn | head -20

# Just ask Shelly:
$ shelly show me the 20 largest files in this directory tree
```

## Installation

Clone the repository and install dependencies:

```sh
# Clone and enter the repository
git clone https://github.com/nestordemeure/shelly.git
cd shelly

# Set up Python environment
python3 -m venv shelly-env
source shelly-env/bin/activate

# Install dependencies
pip install llm python-dotenv rich
```

To add a `shelly` command to your terminal, add this function to your `.bashrc` or `.zshrc`:

```sh
shelly() {
  local SHELLY_DIR="/path/to/shelly"  # Update this path
  source "$SHELLY_DIR/shelly-env/bin/activate"
  set -a
  [ -f "$SHELLY_DIR/.env" ] && source "$SHELLY_DIR/.env"
  set +a
  python3 "$SHELLY_DIR/shelly.py" "$@"  # Add --plugins default to auto-load your plugins/default.md
  deactivate
}
```

Finally, you will need to place your API key in your environment, in a `.env` file in the `shelly` folder, or [directly into llm](https://llm.datasette.io/en/latest/setup.html#api-keys):

```sh
# Optionally, register your API key
echo "OPENAI_API_KEY=your-api-key-here" > .env
```

Shelly defaults to OpenAI models, but you can easily switch to [most model providers](https://llm.datasette.io/en/latest/plugins/directory.html) ([Anthropic](https://github.com/simonw/llm-anthropic), [Gemini](https://github.com/simonw/llm-gemini), [local models](https://llm.datasette.io/en/latest/plugins/directory.html#local-models), etc.) by installing the corresponding [llm plugin](https://llm.datasette.io/en/latest/plugins/installing-plugins.html), changing the model name in [`config.json`](./config.json), and adding the proper API key (if any) to your environment.

## Usage

Start an interactive session:

```sh
$ shelly
🐚 Shelly: Hi! I'm Shelly, your terminal assistant. Ask me to help you run any shell commands!
You: find all python files modified in the last week
🐚 Shelly: I'll search for Python files modified in the last 7 days...
```

Or run one-off commands:

```sh
$ shelly find all Python files modified in the last week
$ shelly what's eating up disk space in my home directory?
$ shelly set up a new git repo with a Python .gitignore
```

Safe commands (`ls`, `cat`, `grep`, etc.) run automatically. Everything else asks for confirmation first. You can always say no and explain why, Shelly will adjust.

Shelly automatically looks up manual pages for complex commands to ensure accurate parameter usage, especially for system-specific tools like `ffmpeg`, `slurm`, and `docker`.

You can also provide Shelly with custom instructions (defined as markdown files in the [plugins/](./plugins/) directory) about your preferred tools and workflows, using the `--plugins` (or `-p`) flag:

```sh
# Use specific plugin
$ shelly --plugins ffmpeg convert this video to mp4

# Load multiple plugin files
$ shelly --plugins git,docker,kubernetes set up a containerized app with CI/CD
```

Edit [`config.json`](./config.json) to change the model (defaults to `gpt-4.1-mini`) or customize which commands run without confirmation.

> ⚠️ **Privacy Note:** By default, Shelly processes your requests, which might include your recent shell history, through the model's API. If privacy is a concern, you will want to [switch to a local model](https://llm.datasette.io/en/latest/plugins/directory.html#local-models).

## TODO

* shelly seem to remove the current python env when started then killed, why?
