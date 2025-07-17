# Shelly Project Overview

Shelly is a smart terminal assistant that translates natural language into shell commands. It uses AI models to understand user requests and execute appropriate shell commands with safety confirmations.

## Architecture

- **Main file**: `shelly.py` - Contains the core Shelly class and PersistentShell class
- **Configuration**: `config.json` - Model settings, command validation, display preferences
- **System prompt**: `prompt.md` - Template for the AI assistant's behavior
- **Plugins**: `plugins/` directory - Custom instruction files in markdown format

## Key Components

### PersistentShell Class
- Manages a persistent shell subprocess that maintains state across commands
- Handles command execution with proper output collection and error handling
- Uses threading to read stdout/stderr asynchronously
- Supports both Unix-like systems and Windows

### Shelly Class
- Main assistant that interfaces with LLM models via the `llm` library
- Provides three main tools: `run_command()`, `shell_script()`, and `man()`
- Implements safety features with command validation and user confirmation
- Loads custom plugins and integrates shell history for context

### Available Tools

#### `run_command(command: str)`
- Executes single shell commands with optional user confirmation
- Used for individual commands like `ls`, `git status`, etc.
- Checks against greenlist for automatic execution of safe commands

#### `shell_script(script: str)`
- Executes multi-line shell scripts with pipes, redirections, and complex logic
- Always requires user confirmation due to complexity
- Preserves shell constructs like loops and conditionals

#### `man(command: str)`
- Retrieves manual page information for commands
- Shows user `📖 man command` indicator but content stays with LLM
- **Automatically used** before complex commands (ffmpeg, slurm, docker, etc.)
- Used when commands fail due to incorrect parameters
- Helps LLM understand system-specific command behavior and syntax

## Configuration Features

### Model Configuration
- Default model: `gpt-4.1-mini`
- Supports any model available through the `llm` library ecosystem
- Easy switching between OpenAI, Anthropic, Gemini, local models, etc.

### Safety Features
- **Greenlist commands**: Safe commands that run without confirmation (ls, cat, grep, etc.)
- **Command validation**: Dangerous commands require user approval
- **Shell operator detection**: Prevents automatic execution of complex shell constructs
- **Output truncation**: Limits output size (1000 lines, 80000 characters)

### Display Options
- **Theme**: Configurable syntax highlighting theme (default: monokai)
- **Line numbers**: Optional line numbers in code blocks
- **Rich formatting**: Uses the Rich library for beautiful terminal output

## Plugin System

Plugins are markdown files in the `plugins/` directory that provide custom instructions:
- Load with `--plugins plugin1,plugin2` or `-p plugin1,plugin2`
- Example: `shelly --plugins ffmpeg convert video to mp4`
- Plugins add domain-specific knowledge and preferences

## Dependencies

- `llm` - Core LLM integration library
- `python-dotenv` - Environment variable management
- `rich` - Terminal formatting and display
- Standard library: `subprocess`, `threading`, `json`, `pathlib`

## Usage Patterns

### Interactive Mode
```bash
shelly
# Starts interactive session with welcome message
```

### One-shot Commands
```bash
shelly find all Python files modified this week
shelly what's using disk space in my home directory?
```

### With Plugins
```bash
shelly --plugins git,docker set up a new containerized project
```

## Development Notes

### Testing
- No specific test framework detected - check README or ask user for test commands
- Should run any lint/typecheck commands after modifications

### Code Style
- Uses type hints throughout
- Rich console for all user output
- Proper error handling with try/catch blocks
- Clean separation between shell execution and AI logic

## Security Considerations

- Validates commands before execution
- Maintains greenlist of safe commands
- Requires user confirmation for potentially dangerous operations
- Processes user data through external APIs (privacy consideration noted in README)

## Installation Requirements

- Python 3.x with venv support
- API key for chosen LLM provider (OpenAI by default)
- Unix-like system or Windows with appropriate shell

## Command History Integration

- Reads from `.bash_history` or `.zsh_history`
- Filters out configured ignored commands (like 'shelly', 'code')
- Provides context to AI for better command suggestions
- Configurable history size (default: 500 commands)