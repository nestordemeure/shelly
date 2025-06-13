# Shelly

**Shelly** is an LLM-powered shell assistant that understands and translates natural language into shell commands.  
You can describe what you want to do, and Shelly will propose the appropriate shell commands, ask for your confirmation, and then execute them.

## Usage

Once installed, run Shelly with:

```sh
$ shelly
```

Or ask it a question directly:

```sh
$ shelly list the files in this folder and its subfolders, by decreasing file size
```

The `config.json` file lets you customize things like the model being used and list of greenlighted (read-only by default) commands that can run without requiring user confirmation.

> ⚠️ **Privacy Note:** Shelly reads your recent shell history and local file/folder names before calling Claude-Haiku through their API. If privacy is a concern, consider forking the project and replacing Haiku with a local LLM.

## Installation

```sh
# Clone the repository
git clone https://github.com/nestordemeure/shelly.git
cd shelly

# Create and activate a virtual environment
python3 -m venv shelly-env
source shelly-env/bin/activate

# Install required dependencies
pip3 install anthropic python-dotenv rich
```

Configure your Anthropic API key by either adding it to your shell environment, 
or creating a `.env` file in the project directory:

```sh
echo "ANTHROPIC_API_KEY=your-api-key-here" > .env
```

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


* tweak the prompt (and code) to let the model know the authorisation will be authomaticlaly asked for, no need to do it manually
* does the model see the history? it does not look like it... there is no `.bash_history` file, but there is a `history` command


* refresh readme once all is said and done