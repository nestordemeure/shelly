import os
import sys
import subprocess
import json
import platform
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import llm
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from string import Template
import signal
import threading
import queue
import time
import argparse

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

class PersistentShell:
    """Manages a persistent shell subprocess that maintains state across commands"""
    
    def __init__(self, shell_path: str):
        self.shell_path = shell_path
        self.process = None
        self.output_queue = queue.Queue()
        self.error_queue = queue.Queue()
        self.output_thread = None
        self.error_thread = None
        self._start_shell()
    
    def _start_shell(self):
        """Start the shell subprocess"""
        # Start an interactive shell
        if platform.system() == 'Windows':
            # Windows: use cmd.exe or powershell
            self.process = subprocess.Popen(
                [self.shell_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if platform.system() == 'Windows' else 0
            )
        else:
            # Unix-like: use the specified shell in interactive mode
            self.process = subprocess.Popen(
                [self.shell_path, '-i'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,
                preexec_fn=os.setsid if platform.system() != 'Windows' else None
            )
        
        # Start threads to read output
        self.output_thread = threading.Thread(target=self._read_output, daemon=True)
        self.error_thread = threading.Thread(target=self._read_error, daemon=True)
        self.output_thread.start()
        self.error_thread.start()
        
        # Give shell time to initialize and consume any startup messages
        time.sleep(0.5)
        self._clear_queues()
    
    def _read_output(self):
        """Read stdout in a separate thread"""
        while self.process and self.process.poll() is None:
            try:
                line = self.process.stdout.readline()
                if line:
                    self.output_queue.put(line)
            except:
                break
    
    def _read_error(self):
        """Read stderr in a separate thread"""
        while self.process and self.process.poll() is None:
            try:
                line = self.process.stderr.readline()
                if line:
                    self.error_queue.put(line)
            except:
                break
    
    def _clear_queues(self):
        """Clear any pending output from queues"""
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except queue.Empty:
                break
        while not self.error_queue.empty():
            try:
                self.error_queue.get_nowait()
            except queue.Empty:
                break
    
    def _collect_output(self, timeout: float = 0.5) -> tuple[str, str]:
        """Collect output from queues with a timeout"""
        stdout_lines = []
        stderr_lines = []
        end_time = time.time() + timeout
        
        # Keep collecting until timeout or both queues are empty
        while time.time() < end_time:
            got_output = False
            
            # Collect stdout
            try:
                while True:
                    line = self.output_queue.get_nowait()
                    stdout_lines.append(line)
                    got_output = True
            except queue.Empty:
                pass
            
            # Collect stderr
            try:
                while True:
                    line = self.error_queue.get_nowait()
                    stderr_lines.append(line)
                    got_output = True
            except queue.Empty:
                pass
            
            # If we got output, reset the timeout to wait for more
            if got_output:
                end_time = time.time() + 0.1
            else:
                time.sleep(0.01)
        
        return ''.join(stdout_lines), ''.join(stderr_lines)
    
    def run_command(self, command: str) -> tuple[str, str, int]:
        """Run a command and return stdout, stderr, and return code"""
        if not self.process or self.process.poll() is not None:
            self._start_shell()
        
        # Clear any pending output
        self._clear_queues()
        
        # Send command with a unique marker to detect completion
        marker = f"SHELLY_MARKER_{time.time()}"
        full_command = f"{command}\necho {marker} $?\n"
        
        try:
            self.process.stdin.write(full_command)
            self.process.stdin.flush()
        except (BrokenPipeError, OSError):
            # Shell died, restart it
            self._start_shell()
            self.process.stdin.write(full_command)
            self.process.stdin.flush()
        
        # Collect output until we see our marker
        stdout_lines = []
        stderr_lines = []
        return_code = 0
        marker_found = False
        
        timeout = 30  # Maximum time to wait for command completion
        start_time = time.time()
        
        while not marker_found and (time.time() - start_time) < timeout:
            stdout_part, stderr_part = self._collect_output(0.1)
            
            # Check if marker is in stdout
            if marker in stdout_part:
                parts = stdout_part.split(marker)
                stdout_lines.append(parts[0])
                # Extract return code
                marker_line = parts[1].strip().split('\n')[0]
                try:
                    return_code = int(marker_line.strip())
                except (ValueError, IndexError):
                    return_code = 0
                marker_found = True
            else:
                stdout_lines.append(stdout_part)
            
            stderr_lines.append(stderr_part)
        
        stdout = ''.join(stdout_lines).rstrip()
        stderr = ''.join(stderr_lines).rstrip()
        
        return stdout, stderr, return_code
    
    def close(self):
        """Close the shell subprocess"""
        if self.process:
            try:
                self.process.stdin.write("exit\n")
                self.process.stdin.flush()
                self.process.wait(timeout=2)
            except:
                # Force kill if exit doesn't work
                if platform.system() == 'Windows':
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.process.pid)], 
                                 capture_output=True)
                else:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            finally:
                self.process = None

class Shelly:
    """Main Shelly assistant class"""
    
    def __init__(self, plugins: Optional[List[str]] = None):
        # Get model from config or use default
        model_name = CONFIG['model']['name']
        
        # Try to get the model
        try:
            self.model = llm.get_model(model_name)
        except llm.UnknownModelError:
            console.print(f"[yellow]Warning: Model '{model_name}' not found. Using default model.[/yellow]")
            self.model = llm.get_model()
        
        # Get system info
        self.os_info = self._get_system_info()
        
        # Initialize persistent shell
        shell_path = os.environ.get('SHELL', '/bin/bash')
        if platform.system() == 'Windows':
            shell_path = os.environ.get('COMSPEC', 'cmd.exe')
        self.shell = PersistentShell(shell_path)
        
        # Get last unique shell commands from history
        self.command_history = self._get_command_history(CONFIG['shell_history_size'])
        
        # Load plugin files if specified
        self.custom_plugins = self._load_plugins(plugins) if plugins else ""
        
        # Define system prompt
        self.system_prompt = self._create_system_prompt()
        
        # Define tools for the API
        self.tools = [self.run_command, self.shell_script]
    
    def run_command(self, command: str) -> str:
        """Execute a single shell command. Use this for individual commands rather than complex shell scripts."""
        if not command.strip():
            return "Error: No command provided"
        
        # Check if command needs validation
        needs_validation = not self._is_greenlisted(command)
        
        if needs_validation:
            # Display command to be run
            console.print()  # Add blank line before code block
            syntax = Syntax(command, "sh", theme=CONFIG['display']['theme'], line_numbers=CONFIG['display']['show_line_numbers'])
            console.print(syntax)
            
            response = console.input("[yellow]Run this command? (yes/no): [/yellow]").strip().lower()
            if response not in ["yes", "y"]:
                reason = console.input("[yellow]Why not? (this will help me adjust): [/yellow]").strip()
                return f"User declined to run command: {reason}"
        
        # Execute the command using persistent shell
        try:
            stdout, stderr, returncode = self.shell.run_command(command)
            
            # Format output for both display and API
            formatted_output = self._format_command_output(command, stdout, stderr, returncode)
            
            # Truncate if needed
            truncated_output, was_truncated = self._truncate_output(formatted_output)
            
            # Display to user
            console.print()
            syntax = Syntax(truncated_output, "bash", theme=CONFIG['display']['theme'], line_numbers=CONFIG['display']['show_line_numbers'])
            console.print(syntax)
            
            # Return output
            if returncode != 0:
                return f"Command failed with exit code {returncode}:\n{truncated_output}"
            return truncated_output
        except Exception as e:
            error_msg = f"Error executing command: {str(e)}"
            console.print(f"\n[red]❌ {error_msg}[/red]")
            return error_msg
    
    def shell_script(self, script: str) -> str:
        """Execute a block of shell script code. Use this for multi-line scripts, complex command sequences with conditionals/loops, or when you need shell-specific features like pipes, redirections, or environment variable manipulation."""
        if not script.strip():
            return "Error: No script provided"
        
        # Always require validation for shell scripts
        console.print()  # Add blank line before code block
        syntax = Syntax(script, "sh", theme=CONFIG['display']['theme'], line_numbers=CONFIG['display']['show_line_numbers'])
        console.print(syntax)
        
        response = console.input("[yellow]Run this script? (yes/no): [/yellow]").strip().lower()
        if response not in ["yes", "y"]:
            reason = console.input("[yellow]Why not? (this will help me adjust): [/yellow]").strip()
            return f"User declined to run script: {reason}"
        
        # Execute the entire script as a single command
        try:
            # For multi-line scripts, we need to pass them as a single command
            # This preserves shell constructs like loops, conditionals, etc.
            stdout, stderr, returncode = self.shell.run_command(script)
            
            # Format output for both display and API
            formatted_output = self._format_command_output("(shell script)", stdout, stderr, returncode)
            
            # Truncate if needed
            truncated_output, was_truncated = self._truncate_output(formatted_output)
            
            # Display to user
            console.print()
            syntax = Syntax(truncated_output, "bash", theme=CONFIG['display']['theme'], line_numbers=CONFIG['display']['show_line_numbers'])
            console.print(syntax)
            
            # Return output
            if returncode != 0:
                return f"Script failed with exit code {returncode}:\n{truncated_output}"
            return truncated_output
        except Exception as e:
            error_msg = f"Error executing script: {str(e)}"
            console.print(f"\n[red]❌ {error_msg}[/red]")
            return error_msg
    
    def _load_plugins(self, plugin_names: List[str]) -> str:
        """Load plugin files from the plugins directory"""
        plugins_dir = Path(__file__).parent / "plugins"
        loaded_plugins = []
        
        for plugin_name in plugin_names:
            # Remove .md extension if provided
            if plugin_name.endswith('.md'):
                plugin_name = plugin_name[:-3]
            
            plugin_path = plugins_dir / f"{plugin_name}.md"
            
            if plugin_path.exists():
                try:
                    with open(plugin_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        loaded_plugins.append(f"---\n\n{content}")
                        console.print(f"[green]✓ Loaded plugin: {plugin_name}[/green]")
                except Exception as e:
                    console.print(f"[yellow]⚠ Warning: Could not load {plugin_path}: {e}[/yellow]")
            else:
                console.print(f"[yellow]⚠ Warning: Plugin file not found: {plugin_path}[/yellow]")
        
        return "\n\n".join(loaded_plugins) if loaded_plugins else ""
    
    def _get_system_info(self) -> Dict[str, str]:
        """Get OS and shell information"""
        shell = os.environ.get('SHELL', 'unknown')
        if shell == 'unknown' and platform.system() == 'Windows':
            shell = os.environ.get('COMSPEC', 'cmd.exe')
        
        return {
            "os": f"{platform.system()} {platform.release()}",
            "shell": os.path.basename(shell)
        }
    
    def _get_command_history(self, max_commands: int) -> List[str]:
        """Get last nb_commands unique commands from shell history"""
        history_file = Path.home() / ".bash_history"
        if not history_file.exists():
            history_file = Path.home() / ".zsh_history"
        
        all_commands = []
        
        # First, collect all commands from history file
        if history_file.exists():
            try:
                with open(history_file, 'r', errors='ignore') as f:
                    lines = f.readlines()
                    for line in reversed(lines):
                        cmd = line.strip()
                        if cmd:
                            all_commands.append(cmd)
            except Exception:
                pass
        
        # If no history file or it's empty, try using the history command
        if not all_commands:
            try:
                # Use the persistent shell to get history
                stdout, _, returncode = self.shell.run_command('history')
                if returncode == 0 and stdout:
                    # Parse history output (typically "NUMBER COMMAND")
                    for line in stdout.strip().split('\n'):
                        # Remove leading number and whitespace
                        parts = line.strip().split(maxsplit=1)
                        if len(parts) > 1:
                            cmd = parts[1]
                            if cmd:
                                all_commands.append(cmd)
            except Exception:
                pass
        
        # Filter out ignored commands and get max_commands unique commands
        ignored_commands = CONFIG.get('ignored_history_commands', [])
        filtered_commands = []
        seen = set()
        for cmd in all_commands:
            # Check if command starts with any ignored command
            should_ignore = any(cmd.startswith(ignored_cmd) for ignored_cmd in ignored_commands)
            if cmd not in seen and not should_ignore:
                seen.add(cmd)
                filtered_commands.append(cmd)
                if len(filtered_commands) >= max_commands:
                    break
        
        return filtered_commands
    
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
            history_section = f"\n\nHere are the last {len(self.command_history)} unique commands from the user's shell history for context:\n"
            history_section += "\n".join(f"- {cmd}" for cmd in self.command_history)
        
        # Substitute variables in the template
        prompt = prompt_template.substitute(
            os_info=self.os_info["os"],
            shell_info=self.os_info["shell"],
            history_section=history_section
        )
        
        # Append custom plugins if loaded
        if self.custom_plugins:
            prompt += "\n\n" + self.custom_plugins
        
        return prompt
    
    def _is_greenlisted(self, command: str) -> bool:
        """Check if a command is in the greenlist (safe to run without confirmation),
        and ensure it doesn't contain any shell operators or suspicious arguments.
        Note that this piece of code is purposefuly restrictive."""
        # Check if the user wants to validate each and every command
        if CONFIG['validate_all_commands']:
            return False

        # Disallow shell operators
        shell_operators = [';', '&&', '||', '|', '>', '<', '&', '$(', '`']
        if any(operator in command for operator in shell_operators):
            return False
        
        # Disallow flags or arguments (or parts of those) that might write/delete/execute for some shell commands
        disallowed_args = ['-exec', '-delete', '-o', '-w', '-f', '-y', '-i', '-a']
        if any(d_arg in command for d_arg in disallowed_args):
            return False

        # Get greenlist from config, default to read-only commands
        greenlist = CONFIG['greenlist_commands']
        return (command in greenlist) or any((command.startswith(greenlisted + ' ')) for greenlisted in CONFIG['greenlist_commands'])
            
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
    
    def _format_command_output(self, command: str, stdout: str, stderr: str, returncode: int) -> str:
        """Format command output for display"""
        output = f"$ {command}\n"
        
        if stdout:
            output += stdout.rstrip()
        
        if stderr and returncode != 0:
            if stdout:
                output += "\n"
            output += f"Error: {stderr.rstrip()}"
        
        if not stdout and not stderr:
            if returncode == 0:
                output += "(no output)"
            else:
                output += f"Error: Command failed with exit code {returncode}"
        
        return output
    
    def cleanup(self):
        """Cleanup method to close the persistent shell"""
        if hasattr(self, 'shell') and self.shell:
            self.shell.close()
    
    def chat(self, initial_message: Optional[str] = None):
        """Start the chat interaction"""
        conversation = self.model.conversation(tools=self.tools)
        
        if initial_message:
            user_input = initial_message
        else:
            console.print(f"[bold cyan]🐚 Shelly:[/bold cyan] {CONFIG['prompts']['welcome_message']}")
            user_input = console.input("\n[bold green]You:[/bold green] ").strip()
            if not user_input:
                return
        
        while True:
            try:
                # Get response from the model with tool use
                response = conversation.chain(user_input, system_fragments=[self.system_prompt])
                
                # Display the response
                console.print(f"\n[bold cyan]🐚 Shelly:[/bold cyan]", end=" ")
                for chunk in response:
                    console.print(chunk, end="")
                console.print()  # New line after response
                
                # Get next user input
                user_input = console.input("\n[bold green]You:[/bold green] ").strip()
                if not user_input or user_input.lower() in ["exit", "quit", "bye"]:
                    console.print(f"\n[bold cyan]🐚 Shelly:[/bold cyan] {CONFIG['prompts']['goodbye_message']}")
                    self.cleanup()
                    break
                
            except KeyboardInterrupt:
                console.print(f"\n\n[bold cyan]🐚 Shelly:[/bold cyan] {CONFIG['prompts']['goodbye_message']}")
                self.cleanup()
                break
            except Exception as e:
                console.print(f"\n[red]❌ Error: {str(e)}[/red]")
                console.print(CONFIG['prompts']['error_message'])

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Shelly - A smart terminal assistant that translates natural language into shell commands",
        epilog="Example usage:\n"
               "  shelly                                      # Start interactive mode\n"
               "  shelly find all python files                # Natural language request\n"
               "  shelly show me the largest files here       # Another request\n"
               "  shelly --plugins git,docker deploy my app   # Use multiple user-provided plugins",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '-p', '--plugins',
        type=str,
        help='Comma-separated list of plugin files (e.g., git,docker,ffmpeg) to load from the /plugins folder'
    )
    
    parser.add_argument(
        'request',
        nargs='*',
        help='Natural language request describing what you want to do (if not provided, starts interactive mode)'
    )
    
    return parser.parse_args()

def main():
    """Main entry point"""
    args = parse_arguments()
    
    # Parse plugins if provided
    plugins = None
    if args.plugins:
        plugins = [plugin.strip() for plugin in args.plugins.split(',') if plugin.strip()]
    
    shelly = None
    try:
        shelly = Shelly(plugins=plugins)
        
        # Check if called with request arguments
        if args.request:
            initial_message = " ".join(args.request)
            shelly.chat(initial_message)
        else:
            shelly.chat()
            
    except ValueError as e:
        console.print(f"[red]❌ Configuration error: {e}[/red]")
        console.print("Please make sure you have configured your API keys using 'llm keys set' command.")
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