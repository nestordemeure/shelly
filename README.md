# Shelly 🐚

A smart terminal assistant that translates natural language into shell commands. Powered by Claude.

Describe what you want in plain English, and Shelly will figure out the right commands, explain what they do, and run them for you.

```sh
# Instead of remembering complex commands...
$ find . -type f -exec ls -la {} \; | sort -k5 -rn | head -20

# Just ask Shelly:
$ shelly show me the 20 largest files in this directory tree
```

## Installation

Clone the repository and install dependencies. You'll need Python 3.7+ and an [Anthropic API key](https://console.anthropic.com/).

```sh
# Clone and enter the repository
git clone https://github.com/nestordemeure/shelly.git
cd shelly

# Set up Python environment
python3 -m venv shelly-env
source shelly-env/bin/activate

# Install dependencies
pip install anthropic python-dotenv rich

# Optionally, register your Anthropic API key
echo "ANTHROPIC_API_KEY=your-api-key-here" > .env
```

To use `shelly` from anywhere, add this function to your `.bashrc` or `.zshrc`:

```bash
shelly() {
  local SHELLY_DIR="/path/to/shelly"  # Update this path
  source "$SHELLY_DIR/shelly-env/bin/activate"
  set -a
  [ -f "$SHELLY_DIR/.env" ] && source "$SHELLY_DIR/.env"
  set +a
  python3 "$SHELLY_DIR/shelly.py" "$@"  # Add --docs default to auto-load your docs/default.md
  deactivate
}
```

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

Safe commands (`ls`, `cat`, `grep`, etc.) run automatically. Everything else asks for confirmation first. You can always say no and explain why, and Shelly will adjust.

Edit `config.json` to change the model (defaults to Claude Haiku) or customize which commands run without confirmation.

You can also provide Shelly with custom documentation (defined as markdown files in the in the [docs/](./docs/) directory) about your preferred tools and workflows using the `--docs` (or `-d`) flag:

```sh
# Use specific documentation
$ shelly --docs ffmpeg convert this video to mp4

# Load multiple documentation files
$ shelly --docs git,docker,kubernetes set up a containerized app with CI/CD
```

> ⚠️ **Privacy Note:** Shelly processes your requests, which might include your recent shell history, through Anthropic's API. If privacy is a concern, you will want to use a local model.

## TODO

* Switch to [llm](https://llm.datasette.io/en/latest/python-api.html) as a backend to open the door to other APIs / local models?