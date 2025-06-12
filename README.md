# Shelly

*Shelly* is an LLM based shell assistant that knows your usual shell commands.

You can ask it to do an action and it will come up with the corresponding shell command, have you validate its actions, then run them.

Privacy-wise, note that it is allowed to read your previous shell commands, file and folder names.
I would recommand forking the project to switch from Claude-Haiku to a local LLM if you need to keep that data private.

## Usage

### Installing Shelly

Run the following to install Shelly's dependencies:

```sh
# Create a virtual environment
python3 -m venv shelly-env

# Activate the virtual environment
source shelly-env/bin/activate

# Install dependencies
pip3 install anthropic python-dotenv rich
```

TODO: place your anthropics api key in a .env file here

TODO: create a `shelly` alias in your bashrc pointing to the pythin in this env, our dotenv, and the shelly.py file

## Running Shelly

Once Shelly is installed, you can runing by simply calling `shelly` in your terminal.
You can also call it with a question:

```sh
$ shelly list the files in this folder and its subfolders, by decreasing file size.
```