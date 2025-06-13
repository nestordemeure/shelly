# Shelly

**Shelly** is an LLM-powered shell assistant that understands and translates natural language into shell commands.
You can describe what you want to do, and Shelly will propose the appropriate shell command, ask for your confirmation, and then execute it.

## Usage

Once installed, run Shelly with:

```sh
$ shelly
```

Or ask it a question directly:

```sh
$ shelly list the files in this folder and its subfolders, by decreasing file size
```

You will find various parameters, such as the model used, in the `config.json` file.

> ⚠️ **Privacy Note:** Shelly reads your recent shell history and local file/folder names before calling Claude-Haiku through their API. If privacy is a concern, consider forking the project and replacing Haiku with a local LLM.

## Installation

### Set Up the Environment

```sh
# Create and activate a virtual environment
python3 -m venv shelly-env
source shelly-env/bin/activate

# Install required dependencies
pip3 install anthropic python-dotenv rich
```

### Configure Your API Key

Create a `.env` file at the root of the project with your Anthropic API key:

```sh
echo "ANTHROPIC_API_KEY=your-api-key-here" > .env
```

### Add Shelly to Your Shell

To use `shelly` as a command in your terminal, add the following function to your `.bashrc`, `.zshrc`, or similar shell configuration file:

```sh
shelly() {
  local SHELLY_DIR="/path/to/your/folder"
  source "$SHELLY_DIR/shelly-env/bin/activate"
  set -a
  [ -f "$SHELLY_DIR/.env" ] && source "$SHELLY_DIR/.env"
  set +a
  python3 "$SHELLY_DIR/shelly.py" "$@"
  deactivate
}
```

## TODO

* no need to display `Restored to original directory: /home/nestor/Downloads/newmann`
* pass OS / shell type to the system prompt
* `_handle_command_result`: the model should see the same thing as the human (modulo truncation) to help with debugging
* does the model see the history? it does not look like it... there is no `.bash_history` file, but there is a `history` command
* refresh readme once all is said and done