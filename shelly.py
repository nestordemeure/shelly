import os
import sys
import subprocess
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from string import Template

# Load environment variables
load_dotenv()

# Initialize rich console
console = Console()

# Load configuration
config_path = Path(__file__).parent / "config.json"
try:
    with open(config_path, 'r') as f:
        CONFIG = json.load(f)
except FileNotFoundError:
    console.print(f"[red]Error: config.json not found at {config_path}[/red]")
    sys.exit(1)
except json.JSONDecodeError as e:
    console.print(f"[red]Error: Invalid JSON in config.json: {e}[/red]")
    sys.exit(1)

class Shelly:
    """Main Shelly assistant class"""
    
    def __init__(self):
        # Initialize Anthropic client
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in .env file")
        
        self.client = anthropic.Anthropic(api_key=api_key)
        
        # Store original directory to restore on exit
        self.original_dir = os.getcwd()
        
        # Get last unique shell commands from history
        self.command_history = self._get_command_history(CONFIG['history']['max_commands'])
        
        # Define system prompt
        self.system_prompt = self._create_system_prompt()
        
        # Define tools for the API
        self.tools = [
            {
                "name": "cd",
                "description": "Change the current working directory",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to change to (use ~ for home, .. for parent)",
                            "default": "~"
                        }
                    }
                }
            },
            {
                "name": "ls",
                "description": "List directory contents with any options",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Arguments to pass to ls command",
                            "default": []
                        }
                    }
                }
            },
            {
                "name": "pwd",
                "description": "Print working directory",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Arguments to pass to pwd command",
                            "default": []
                        }
                    }
                }
            },
            {
                "name": "which",
                "description": "Locate a command and check if it's installed. Use this to verify if programs like 'convert' (ImageMagick) are available.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The command name to locate"
                        }
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "grep",
                "description": "Search for patterns in files. Supports recursive search with -r, case-insensitive with -i, and many other options.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "The pattern to search for"
                        },
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Additional arguments like -r, -i, -n, -l, etc.",
                            "default": []
                        },
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Files or directories to search in",
                            "default": ["."]
                        }
                    },
                    "required": ["pattern"]
                }
            },
            {
                "name": "find",
                "description": "Search for files and directories by name, type, size, or other criteria",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Starting directory for the search",
                            "default": "."
                        },
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Find arguments like -name, -type, -size, etc.",
                            "default": []
                        }
                    }
                }
            },
            {
                "name": "cat",
                "description": "Display contents of files",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Files to display"
                        },
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Additional arguments like -n for line numbers",
                            "default": []
                        }
                    },
                    "required": ["files"]
                }
            },
            {
                "name": "head",
                "description": "Display first lines of files (default: 10 lines)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Files to display"
                        },
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Arguments like -n 20 to show 20 lines",
                            "default": []
                        }
                    },
                    "required": ["files"]
                }
            },
            {
                "name": "tail",
                "description": "Display last lines of files (default: 10 lines)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Files to display"
                        },
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Arguments like -n 20 or -f for follow",
                            "default": []
                        }
                    },
                    "required": ["files"]
                }
            },
            {
                "name": "wc",
                "description": "Count lines, words, and characters in files",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Files to count",
                            "default": []
                        },
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Arguments like -l (lines), -w (words), -c (bytes)",
                            "default": []
                        }
                    }
                }
            },
            {
                "name": "du",
                "description": "Display disk usage of files and directories",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Paths to check",
                            "default": ["."]
                        },
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Arguments like -h (human readable), -s (summary)",
                            "default": ["-h"]
                        }
                    }
                }
            },
            {
                "name": "tree",
                "description": "Display directory structure as a tree (if installed)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory to display",
                            "default": "."
                        },
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Arguments like -L 2 (depth), -a (all files)",
                            "default": []
                        }
                    }
                }
            },
            {
                "name": "run",
                "description": "Execute one or more shell commands sequentially (requires user validation)",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "commands": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of shell commands to execute in sequence"
                        }
                    },
                    "required": ["commands"]
                }
            }
        ]
    
    def _get_command_history(self, max_commands: int) -> List[str]:
        """Get last nb_commands unique commands from shell history"""
        history_file = Path.home() / ".bash_history"
        if not history_file.exists():
            history_file = Path.home() / ".zsh_history"
        
        commands = []
        if history_file.exists():
            try:
                with open(history_file, 'r', errors='ignore') as f:
                    lines = f.readlines()
                    # Get unique commands
                    seen = set()
                    for line in reversed(lines):
                        cmd = line.strip()
                        if cmd and cmd not in seen:
                            seen.add(cmd)
                            commands.append(cmd)
                            if len(commands) >= max_commands:
                                break
                    commands.reverse()
            except Exception:
                pass
        
        return commands
    
    def _create_system_prompt(self) -> str:
        """Create the system prompt for Shelly"""
        # Load prompt template from file
        prompt_path = Path(__file__).parent / "prompt.md"
        try:
            with open(prompt_path, 'r') as f:
                prompt_template = Template(f.read())
        except FileNotFoundError:
            console.print(f"[red]Error: prompt.md not found at {prompt_path}[/red]")
            raise ValueError("prompt.md file is required")
        
        # Prepare history section
        history_section = ""
        if self.command_history:
            display_count = CONFIG['history']['display_count']
            history_section = f"\n\nHere are the last {min(len(self.command_history), display_count)} unique commands from the user's shell history for inspiration:\n"
            history_section += "\n".join(f"- {cmd}" for cmd in self.command_history[-display_count:])
        
        # Substitute variables in the template
        return prompt_template.substitute(history_section=history_section)
    
    def _truncate_output(self, output: str) -> tuple[str, bool]:
        """Truncate output if it's too long, return (truncated_output, was_truncated)"""
        max_lines = CONFIG['output_truncation']['max_lines']
        max_chars = CONFIG['output_truncation']['max_characters']
        
        lines = output.split('\n')
        
        # Check if we need to truncate by lines
        if len(lines) > max_lines:
            truncated_lines = lines[:max_lines//2] + ['', '... (output truncated) ...', ''] + lines[-max_lines//2:]
            output = '\n'.join(truncated_lines)
            was_truncated = True
        else:
            was_truncated = False
        
        # Check if we still need to truncate by characters
        if len(output) > max_chars:
            output = output[:max_chars//2] + '\n\n... (output truncated) ...\n\n' + output[-max_chars//2:]
            was_truncated = True
        
        return output, was_truncated
    
    def _get_list_param(self, tool_input: Dict[str, Any], param_name: str, default: List[str] = None) -> List[str]:
        """Safely get a list parameter from tool input, handling string inputs"""
        if default is None:
            default = []
        
        value = tool_input.get(param_name, default)
        
        # If it's already a list, return it
        if isinstance(value, list):
            return [str(item) for item in value]  # Ensure all items are strings
        
        # If it's a string, wrap it in a list
        if isinstance(value, str):
            return [value]
        
        # For any other type, return the default
        return default
    
    def _handle_command_result(self, cmd: List[str], result: subprocess.CompletedProcess, 
                              success_codes: List[int] = [0], no_output_msg: str = "(no output)") -> Dict[str, Any]:
        """Handle command result display and API response consistently"""
        # Display command and output
        console.print()
        display_output = f"$ {' '.join(cmd)}\n"
        
        if result.stdout:
            display_output += result.stdout.rstrip()
        elif result.returncode in success_codes:
            display_output += no_output_msg
        else:
            # For errors, show stderr or a generic error message
            if result.stderr:
                display_output += result.stderr.rstrip()
            else:
                display_output += f"Error: Command failed with exit code {result.returncode}"
        
        syntax = Syntax(display_output, "bash", theme=CONFIG['display']['theme'], line_numbers=CONFIG['display']['show_line_numbers'])
        console.print(syntax)
        
        # Prepare API response with full error information
        is_success = result.returncode in success_codes
        
        # For API, include both stdout and stderr when there's an error
        if is_success:
            api_output, was_truncated = self._truncate_output(result.stdout)
            if was_truncated:
                api_output = f"[Output truncated]\n{api_output}"
            api_error = ""
        else:
            # For errors, provide full context to the model
            api_output = result.stdout if result.stdout else ""
            api_error = result.stderr if result.stderr else f"Command failed with exit code {result.returncode}"
            
            # If both stdout and stderr exist, combine them for context
            if result.stdout and result.stderr:
                combined = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
                combined_truncated, was_truncated = self._truncate_output(combined)
                if was_truncated:
                    api_error = f"[Output truncated]\n{combined_truncated}"
                else:
                    api_error = combined
        
        return {
            "success": is_success,
            "output": api_output,
            "error": api_error
        }
    
    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool based on the tool call from Claude"""
        if tool_name == "cd":
            path = tool_input.get("path", "~")
            # Expand ~ to home directory
            path = os.path.expanduser(path)
            
            try:
                # Store current directory before changing
                old_dir = os.getcwd()
                
                # Change directory
                os.chdir(path)
                new_dir = os.getcwd()
                
                # Display the change
                console.print()
                display_output = f"$ cd {tool_input.get('path', '~')}\n"
                display_output += f"{old_dir} → {new_dir}"
                
                syntax = Syntax(display_output, "bash", theme=CONFIG['display']['theme'], line_numbers=CONFIG['display']['show_line_numbers'])
                console.print(syntax)
                
                return {
                    "success": True,
                    "output": f"Changed directory to {new_dir}",
                    "error": ""
                }
            except FileNotFoundError:
                console.print()
                console.print(f"[red]❌ Error: Directory '{path}' not found[/red]")
                return {"success": False, "output": "", "error": f"Directory not found: {path}"}
            except PermissionError:
                console.print()
                console.print(f"[red]❌ Error: Permission denied for '{path}'[/red]")
                return {"success": False, "output": "", "error": f"Permission denied: {path}"}
            except Exception as e:
                console.print()
                console.print(f"[red]❌ Error: {str(e)}[/red]")
                return {"success": False, "output": "", "error": str(e)}
        
        elif tool_name == "ls":
            args = tool_input.get("args", [])
            # Ensure args is a list
            if isinstance(args, str):
                args = [args]
            elif not isinstance(args, list):
                args = []
            cmd = ["ls"] + args
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                # Display command and output in a code block
                console.print()  # Add linebreak before code block
                display_output = f"$ {' '.join(cmd)}\n"
                if result.stdout:
                    display_output += result.stdout.rstrip()
                elif result.returncode == 0:
                    display_output += "(no output)"
                else:
                    display_output += f"Error: {result.stderr.rstrip()}"
                
                syntax = Syntax(display_output, "bash", theme=CONFIG['display']['theme'], line_numbers=CONFIG['display']['show_line_numbers'])
                console.print(syntax)
                
                # Truncate output for the API if needed
                api_output, was_truncated = self._truncate_output(result.stdout if result.returncode == 0 else result.stderr)
                if was_truncated:
                    api_output = f"[Output was truncated for brevity. Full output shown to user.]\n{api_output}"
                
                return {
                    "success": result.returncode == 0,
                    "output": api_output if result.returncode == 0 else "",
                    "error": result.stderr if result.returncode != 0 else ""
                }
            except Exception as e:
                console.print(f"[red]❌ Error: {str(e)}[/red]")
                return {"success": False, "output": "", "error": str(e)}
        
        elif tool_name == "pwd":
            args = tool_input.get("args", [])
            cmd = ["pwd"] + args
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                # Display command and output in a code block
                console.print()  # Add linebreak before code block
                display_output = f"$ {' '.join(cmd)}\n"
                if result.stdout:
                    display_output += result.stdout.rstrip()
                elif result.returncode == 0:
                    display_output += "(no output)"
                else:
                    display_output += f"Error: {result.stderr.rstrip()}"
                
                syntax = Syntax(display_output, "bash", theme=CONFIG['display']['theme'], line_numbers=CONFIG['display']['show_line_numbers'])
                console.print(syntax)
                
                # Truncate output for the API if needed
                api_output, was_truncated = self._truncate_output(result.stdout)
                if was_truncated:
                    api_output = f"[Output was truncated for brevity. Full output shown to user.]\n{api_output}"
                
                return {
                    "success": result.returncode == 0,
                    "output": api_output,
                    "error": result.stderr
                }
            except Exception as e:
                console.print(f"[red]❌ Error: {str(e)}[/red]")
                return {"success": False, "output": "", "error": str(e)}
        
        elif tool_name == "which":
            command = tool_input.get("command", "")
            cmd = ["which", command]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                # Display command and output in a code block
                console.print()  # Add linebreak before code block
                display_output = f"$ {' '.join(cmd)}\n"
                if result.stdout:
                    display_output += result.stdout.rstrip()
                elif result.returncode == 0:
                    display_output += "(no output)"
                else:
                    display_output += f"Error: command not found"
                
                syntax = Syntax(display_output, "bash", theme=CONFIG['display']['theme'], line_numbers=CONFIG['display']['show_line_numbers'])
                console.print(syntax)
                
                # Truncate output for the API if needed
                api_output, was_truncated = self._truncate_output(result.stdout)
                if was_truncated:
                    api_output = f"[Output was truncated for brevity. Full output shown to user.]\n{api_output}"
                
                return {
                    "success": result.returncode == 0,
                    "output": api_output,
                    "error": result.stderr
                }
            except Exception as e:
                console.print(f"[red]❌ Error: {str(e)}[/red]")
                return {"success": False, "output": "", "error": str(e)}
        
        elif tool_name == "grep":
            pattern = tool_input.get("pattern", "")
            args = self._get_list_param(tool_input, "args")
            paths = self._get_list_param(tool_input, "paths", ["."])
            cmd = ["grep"] + args + [pattern] + paths
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                # grep returns 1 for no matches, which is not an error
                return self._handle_command_result(cmd, result, success_codes=[0, 1], no_output_msg="(no matches found)")
            except Exception as e:
                console.print(f"[red]❌ Error: {str(e)}[/red]")
                return {"success": False, "output": "", "error": str(e)}
        
        elif tool_name == "find":
            path = tool_input.get("path", ".")
            args = self._get_list_param(tool_input, "args")
            cmd = ["find", path] + args
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                return self._handle_command_result(cmd, result, no_output_msg="(no results)")
            except Exception as e:
                console.print(f"[red]❌ Error: {str(e)}[/red]")
                return {"success": False, "output": "", "error": str(e)}
        
        elif tool_name == "cat":
            files = self._get_list_param(tool_input, "files")
            args = self._get_list_param(tool_input, "args")
            cmd = ["cat"] + args + files
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                return self._handle_command_result(cmd, result, no_output_msg="(empty file)")
            except Exception as e:
                console.print(f"[red]❌ Error: {str(e)}[/red]")
                return {"success": False, "output": "", "error": str(e)}
        
        elif tool_name == "head":
            files = self._get_list_param(tool_input, "files")
            args = self._get_list_param(tool_input, "args")
            cmd = ["head"] + args + files
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                return self._handle_command_result(cmd, result)
            except Exception as e:
                console.print(f"[red]❌ Error: {str(e)}[/red]")
                return {"success": False, "output": "", "error": str(e)}
        
        elif tool_name == "tail":
            files = self._get_list_param(tool_input, "files")
            args = self._get_list_param(tool_input, "args")
            cmd = ["tail"] + args + files
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                return self._handle_command_result(cmd, result)
            except Exception as e:
                console.print(f"[red]❌ Error: {str(e)}[/red]")
                return {"success": False, "output": "", "error": str(e)}
        
        elif tool_name == "wc":
            files = self._get_list_param(tool_input, "files")
            args = self._get_list_param(tool_input, "args")
            cmd = ["wc"] + args + files
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                return self._handle_command_result(cmd, result)
            except Exception as e:
                console.print(f"[red]❌ Error: {str(e)}[/red]")
                return {"success": False, "output": "", "error": str(e)}
        
        elif tool_name == "du":
            paths = self._get_list_param(tool_input, "paths", ["."])
            args = self._get_list_param(tool_input, "args", ["-h"])
            cmd = ["du"] + args + paths
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                return self._handle_command_result(cmd, result)
            except Exception as e:
                console.print(f"[red]❌ Error: {str(e)}[/red]")
                return {"success": False, "output": "", "error": str(e)}
        
        elif tool_name == "tree":
            path = tool_input.get("path", ".")
            args = self._get_list_param(tool_input, "args")
            cmd = ["tree"] + args + [path]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                return self._handle_command_result(cmd, result)
            except Exception as e:
                console.print(f"[red]❌ Error: {str(e)}[/red]")
                return {"success": False, "output": "", "error": str(e)}
        
        elif tool_name == "run":
            commands = tool_input.get("commands", [])
            
            # Handle case where a single string is passed instead of an array
            if isinstance(commands, str):
                commands = [commands]
            elif not isinstance(commands, list):
                return {"success": False, "output": "", "error": "Invalid commands format"}
            
            # Ensure all items in commands are strings
            commands = [str(cmd) for cmd in commands]
            
            if not commands:
                return {"success": False, "output": "", "error": "No commands provided"}
                return {"success": False, "output": "", "error": "No commands provided"}
            
            # Display commands to be run
            console.print("\n[bold]Commands to execute:[/bold]")
            cmd_display = "\n".join(commands)
            syntax = Syntax(cmd_display, "bash", theme=CONFIG['display']['theme'], line_numbers=CONFIG['display']['show_line_numbers'])
            console.print(syntax)
            
            response = console.input("\n[yellow]Run? (yes/no): [/yellow]").strip().lower()
            if response not in ["yes", "y"]:
                reason = console.input("[yellow]Why not? (this will help me adjust): [/yellow]").strip()
                return {
                    "success": False,
                    "output": "",
                    "error": f"User declined: {reason}"
                }
            
            # Execute commands and display output
            console.print()
            all_output = []
            all_successful = True
            
            for cmd in commands:
                try:
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    
                    # Build output for this command
                    cmd_output = f"$ {cmd}\n"
                    if result.stdout:
                        cmd_output += result.stdout.rstrip()
                    elif result.returncode == 0:
                        cmd_output += "(no output)"
                    
                    if result.stderr and result.returncode != 0:
                        cmd_output += f"\n{result.stderr.rstrip()}"
                    
                    # Display this command's output
                    syntax = Syntax(cmd_output, "bash", theme=CONFIG['display']['theme'], line_numbers=CONFIG['display']['show_line_numbers'])
                    console.print(syntax)
                    
                    # Truncate for API if needed
                    api_output, was_truncated = self._truncate_output(result.stdout)
                    if was_truncated:
                        all_output.append(f"[Output truncated]\n{api_output}")
                    else:
                        all_output.append(result.stdout if result.stdout else "")
                    
                    if result.returncode != 0:
                        all_successful = False
                        break
                except Exception as e:
                    console.print(f"[red]❌ Error: {str(e)}[/red]")
                    all_successful = False
                    break
            
            return {
                "success": all_successful,
                "output": "\n".join(all_output),
                "error": "" if all_successful else "Command failed"
            }
        
        return {"success": False, "output": "", "error": f"Unknown tool: {tool_name}"}
    
    def cleanup(self):
        """Cleanup method to restore original directory"""
        try:
            os.chdir(self.original_dir)
            #console.print(f"\n[dim]Restored to original directory: {self.original_dir}[/dim]")
        except Exception:
            pass  # Silently fail if we can't restore
    
    def chat(self, initial_message: Optional[str] = None):
        """Start the chat interaction"""
        messages = []
        
        if initial_message:
            messages.append({"role": "user", "content": initial_message})
        else:
            console.print(f"[bold cyan]🐚 Shelly:[/bold cyan] {CONFIG['prompts']['welcome_message']}")
            user_input = console.input("\n[bold green]You:[/bold green] ").strip()
            if not user_input:
                return
            messages.append({"role": "user", "content": user_input})
        
        while True:
            try:
                # Get response from Claude with tools
                response = self.client.messages.create(
                    model=CONFIG['model']['name'],
                    system=self.system_prompt,
                    messages=messages,
                    max_tokens=CONFIG['model']['max_tokens'],
                    tools=self.tools
                )
                
                # Process the response
                assistant_content = []
                tool_results = []
                
                for content in response.content:
                    if content.type == "text":
                        # Use rich markdown for better formatting
                        console.print(f"\n[bold cyan]🐚 Shelly:[/bold cyan] {content.text}")
                        assistant_content.append({
                            "type": "text",
                            "text": content.text
                        })
                    elif content.type == "tool_use":
                        # Execute the tool
                        result = self._execute_tool(content.name, content.input)
                        
                        # Add tool use to assistant content
                        assistant_content.append({
                            "type": "tool_use",
                            "id": content.id,
                            "name": content.name,
                            "input": content.input
                        })
                        
                        # Prepare tool result
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": content.id,
                            "content": result["output"] if result["success"] else f"Error: {result['error']}"
                        })
                
                # Add assistant message to history
                messages.append({
                    "role": "assistant",
                    "content": assistant_content
                })
                
                # If there were tool uses, add the results and continue
                if tool_results:
                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })
                    continue
                
                # Get next user input
                user_input = console.input("\n[bold green]You:[/bold green] ").strip()
                if not user_input or user_input.lower() in ["exit", "quit", "bye"]:
                    console.print(f"\n[bold cyan]🐚 Shelly:[/bold cyan] {CONFIG['prompts']['goodbye_message']}")
                    self.cleanup()
                    break
                
                messages.append({"role": "user", "content": user_input})
                
            except KeyboardInterrupt:
                console.print(f"\n\n[bold cyan]🐚 Shelly:[/bold cyan] {CONFIG['prompts']['goodbye_message']}")
                self.cleanup()
                break
            except Exception as e:
                console.print(f"\n[red]❌ Error: {str(e)}[/red]")
                console.print(CONFIG['prompts']['error_message'])

def main():
    """Main entry point"""
    shelly = None
    try:
        shelly = Shelly()
        
        # Check if called with arguments
        if len(sys.argv) > 1:
            initial_message = " ".join(sys.argv[1:])
            shelly.chat(initial_message)
        else:
            shelly.chat()
            
    except ValueError as e:
        console.print(f"[red]❌ Configuration error: {e}[/red]")
        console.print("Please make sure you have a .env file with ANTHROPIC_API_KEY set.")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]❌ Unexpected error: {e}[/red]")
        sys.exit(1)
    finally:
        # Ensure cleanup happens even on unexpected exit
        if shelly:
            shelly.cleanup()

if __name__ == "__main__":
    main()