# Shelly 🐚

A smart terminal assistant that translates natural language into shell commands.

Describe what you want in plain English, and Shelly will figure out the right commands, explain what they do, and run them for you.

```sh
# Instead of remembering complex commands...
$ find . -type f -exec ls -la {} \; | sort -k5 -rn | head -20

# Just ask Shelly:
$ shelly show me the 20 largest files in this directory tree
```

> ⚠️ **Warning:** This branch covers specifics to get `shelly` running on NERSC systems using the [Cborg API](https://cborg.lbl.gov/api_examples/). Including installation instructions and a [`nersc.md`](./plugins/nersc.md) dedicated plugin.

## Installation

Clone the repository and install dependencies:

```sh
# Clone and enter the repository
git clone https://github.com/nestordemeure/shelly.git
cd shelly

# Set up Python environment
module load python
python3 -m venv shelly-env
source shelly-env/bin/activate

# Install dependencies
pip install llm python-dotenv rich
```

Configure llm to use CBORG, adding out model of choice (here `openai/gpt-4.1-mini`, check the [CBorg Models page](https://cborg.lbl.gov/models/) for a list of models currently available with tool use) to its configuration file (do not forget to also set it in [`config.json`](./config.json)):

```sh
# Load the env
source shelly-env/bin/activate

# Register your CBORG API key
llm keys set cborg

# Locate the LLM configuration file
LLM_DIR=$(dirname "$(llm logs path)")
CONFIG_FILE="$LLM_DIR/extra-openai-models.yaml"

# Create a local shortcut to the config file for ease of use
ln -s "$CONFIG_FILE" llm_models.yaml

# Write our model configuration to the YAML file
# Note the use of the (here openai) pass-throught in the url to enable tool use
cat <<EOF > "$CONFIG_FILE"
- model_id: cborg-gpt-4.1-mini
  model_name: openai/gpt-4.1-mini
  api_base: "https://api.cborg.lbl.gov"
  api_key_name: cborg
  supports_tools: True
  supports_schema: True
EOF

# Check that we did add our model to the list
llm models
```

To add a `shelly` command to your terminal, add this function to your `.bashrc` or `.zshrc`:

```sh
shelly() {
  local SHELLY_DIR="/path/to/shelly"  # Update this path
  source "$SHELLY_DIR/shelly-env/bin/activate"
  set -a
  [ -f "$SHELLY_DIR/.env" ] && source "$SHELLY_DIR/.env"
  set +a
  python3 "$SHELLY_DIR/shelly.py" --plugins slurm,lmod,slog "$@"
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
shelly find all Python files modified in the last week
shelly what's eating up disk space in my home directory?
shelly set up a new git repo with a Python .gitignore
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
