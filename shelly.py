import os
import sys
import subprocess
import json
import platform
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from string import Template
import signal
import threading
import queue
import time

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
    
    def __init__(self, shell_path: Optional[str] = None):
        self.shell_executable: str = ""
        self.shell_type: str = ""
        self.process = None
        self.output_queue = queue.Queue()
        self.error_queue = queue.Queue()
        self.output_thread = None
        self.error_thread = None

        if platform.system() == 'Windows':
            if shell_path and 'powershell' in shell_path.lower():
                self.shell_executable = 'powershell.exe'
                self.shell_type = 'powershell'
            elif shell_path and 'cmd' in shell_path.lower():
                self.shell_executable = 'cmd.exe'
                self.shell_type = 'cmd'
            else:
                # Try PowerShell by default
                try:
                    subprocess.run(['powershell.exe', '-Command', 'exit'], capture_output=True, timeout=5, check=True)
                    self.shell_executable = 'powershell.exe'
                    self.shell_type = 'powershell'
                except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                    # Fallback to cmd.exe
                    self.shell_executable = os.environ.get('COMSPEC', 'cmd.exe')
                    self.shell_type = 'cmd'
        else:
            # Non-Windows
            self.shell_executable = shell_path if shell_path else os.environ.get('SHELL', '/bin/bash')
            # Infer shell type from executable name
            executable_name = os.path.basename(self.shell_executable)
            if 'powershell' in executable_name.lower() or 'pwsh' in executable_name.lower(): # pwsh is the typical name for PowerShell Core
                self.shell_type = 'powershell'
            elif 'cmd' in executable_name.lower(): # Unlikely on non-windows, but for completeness
                self.shell_type = 'cmd'
            elif 'bash' in executable_name:
                self.shell_type = 'bash'
            elif 'zsh' in executable_name:
                self.shell_type = 'zsh'
            elif 'sh' in executable_name:
                self.shell_type = 'sh'
            else:
                self.shell_type = 'bash' # Default for other Unix-like shells

        self._start_shell()
    
    def _start_shell(self):
        """Start the shell subprocess"""
        cmd_list = [self.shell_executable]
        if self.shell_type not in ['powershell', 'cmd'] and platform.system() != 'Windows':
            cmd_list.append('-i')

        if platform.system() == 'Windows':
            self.process = subprocess.Popen(
                cmd_list,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0, # Unbuffered
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            # Unix-like
            self.process = subprocess.Popen(
                cmd_list,
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

        if self.shell_type == 'cmd':
            full_command = f"{command}\necho {marker} %ERRORLEVEL%\n"
        elif self.shell_type == 'powershell':
            # Ensure $LASTEXITCODE is captured correctly.
            full_command = f"{command}; $LastExitCodeFromCmd = $LASTEXITCODE; echo \"{marker} $LastExitCodeFromCmd\"\n"
        else: # bash, zsh, sh, etc.
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
                code_str = marker_line.strip()

                if self.shell_type == 'powershell':
                    # PowerShell's echo might add quotes sometimes, e.g., echo "marker 0"
                    if code_str.startswith('"') and code_str.endswith('"'):
                        code_str = code_str[1:-1].strip()
                    # $LASTEXITCODE could be non-integer if a PS command itself fails to set it (e.g. bad cmdlet)
                    # Or if $LastExitCodeFromCmd was not set because command was invalid before it.
                    # We are primarily interested in the exit code of the command itself.

                try:
                    return_code = int(code_str)
                except (ValueError, IndexError):
                    # If marker was found but code is not an int, it implies an issue.
                    # Default to 1 to indicate an error.
                    return_code = 1
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
    
    def __init__(self):
        # Initialize Anthropic client
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in .env file")
        
        self.client = anthropic.Anthropic(api_key=api_key)
        
        # Get system info
        self.os_info = self._get_system_info()
        
        # Initialize persistent shell
        shell_path = os.environ.get('SHELL', '/bin/bash')
        if platform.system() == 'Windows':
            shell_path = os.environ.get('COMSPEC', 'cmd.exe')
        self.shell = PersistentShell(shell_path)
        
        # Get current working directory from the shell
        pwd_command = "pwd"
        if self.shell.shell_type == 'cmd':
            pwd_command = "cd"
        elif self.shell.shell_type == 'powershell':
            pwd_command = "echo (Get-Location).Path"

        stdout, _, _ = self.shell.run_command(pwd_command)
        # For 'cd' in CMD, stdout might contain more than just the path.
        # For 'echo (Get-Location).Path' in PowerShell, stdout is just the path.
        # For 'pwd', stdout is just the path.
        if self.shell.shell_type == 'cmd':
             # 'cd' with no arguments prints the current directory.
             # If 'cd' is used to change directory, e.g. 'cd C:\Users', it doesn't print anything.
             # However, run_command appends an echo marker.
             # A simple 'cd' will have its output (the path) before the marker.
             # We need to be careful if the command itself was 'cd C:\newpath'
             # The current implementation of run_command should handle this by capturing output before marker.
             # For now, assume stdout.strip() is okay.
             self.current_dir = stdout.strip().split('\n')[-1] # Get the last line if 'cd' outputs more
        else:
            self.current_dir = stdout.strip()

        # Get last unique shell commands from history
        self.command_history = self._get_command_history(CONFIG['history']['max_commands'])
        
        # Define system prompt
        self.system_prompt = self._create_system_prompt()
        
        # Define tools for the API
        self.tools = [
            {
                "name": "run_command",
                "description": "Execute a single shell command. Use this for individual commands rather than complex shell scripts.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The shell command to execute"
                        }
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "shell_script",
                "description": "Execute a block of shell script code. Use this for multi-line scripts, complex command sequences with conditionals/loops, or when you need shell-specific features like pipes, redirections, or environment variable manipulation.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "script": {
                            "type": "string",
                            "description": "The shell script code to execute"
                        }
                    },
                    "required": ["script"]
                }
            }
        ]
    
    def _get_system_info(self) -> Dict[str, str]:
        """Get OS and shell information"""
        return {
            "os": f"{platform.system()} {platform.release()}",
            "shell": self.shell.shell_type if hasattr(self, 'shell') else "unknown"
        }
    
    def _get_command_history(self, max_commands: int) -> List[str]:
        """Get last nb_commands unique commands from shell history, adapting to the current shell."""
        commands = []
        seen = set()

        # Helper to process lines into unique commands
        def process_lines(lines: List[str], reverse_order: bool = True):
            processed_commands = []
            # If reverse_order is True, we iterate from newest to oldest.
            # Otherwise, assume lines are already in chronological order.
            iterable = reversed(lines) if reverse_order else lines
            for line in iterable:
                cmd = line.strip()
                if cmd and cmd not in seen:
                    seen.add(cmd)
                    processed_commands.append(cmd)
                    if len(processed_commands) >= max_commands:
                        break
            # If we processed in reverse (newest first), reverse back to chronological.
            if reverse_order:
                processed_commands.reverse()
            return processed_commands

        # 1. Prioritize Shell-Specific Session History for Windows
        if platform.system() == 'Windows':
            history_cmd = None
            if self.shell.shell_type == 'powershell':
                history_cmd = f"Get-History -Count {max_commands} | ForEach-Object {{ $_.CommandLine }}"
            elif self.shell.shell_type == 'cmd':
                history_cmd = "doskey /history"

            if history_cmd:
                try:
                    stdout, _, returncode = self.shell.run_command(history_cmd)
                    if returncode == 0 and stdout:
                        # PowerShell Get-History is newest first, doskey /history is oldest first.
                        # ForEach-Object preserves order of Get-History.
                        # doskey /history output is already chronological.
                        lines = stdout.strip().split('\n')
                        # For PowerShell, Get-History is newest first, so process lines in given order and then reverse.
                        # For CMD, doskey /history is oldest first, so process lines in given order (no reverse needed at the end).
                        if self.shell.shell_type == 'powershell':
                             # Get-History returns newest first. We want to keep the newest unique ones.
                            temp_commands = []
                            temp_seen_for_ps = set()
                            for line in lines: # Iterating from newest to oldest
                                cmd = line.strip()
                                if cmd and cmd not in temp_seen_for_ps:
                                    temp_seen_for_ps.add(cmd)
                                    temp_commands.append(cmd)
                                    if len(temp_commands) >= max_commands:
                                        break
                            temp_commands.reverse() # Back to chronological
                            commands = temp_commands
                            seen.update(temp_seen_for_ps)

                        elif self.shell.shell_type == 'cmd':
                            # doskey /history is oldest first.
                            commands = process_lines(lines, reverse_order=False) # Process in given order

                        if commands:
                            return commands
                except Exception:
                    pass # Fall through to other methods if shell command fails

        # 2. Fallback to File-Based History (Primarily for Unix-like systems, or if Windows failed)
        if not commands:
            history_files = []
            if platform.system() != 'Windows': # Only try file-based on non-Windows by default
                history_files = [Path.home() / ".bash_history", Path.home() / ".zsh_history"]

            for history_file_path in history_files:
                if history_file_path.exists():
                    try:
                        with open(history_file_path, 'r', errors='ignore') as f:
                            lines = f.readlines()
                        # File history is typically oldest first, but some shells might write newest first.
                        # Standard approach is to read all, then get unique from reversed (newest)
                        commands = process_lines(lines, reverse_order=True)
                        if commands:
                            return commands
                    except Exception:
                        pass

        # 3. Fallback to Generic `history` Command (via Persistent Shell)
        if not commands:
            try:
                # This is a generic attempt, might work on some Unix shells if files weren't found/readable.
                # It might not work or give poor output on Windows shells if not already handled.
                stdout, _, returncode = self.shell.run_command(f'history {max_commands}')
                if returncode == 0 and stdout:
                    lines = stdout.strip().split('\n')
                    parsed_history_lines = []
                    for line in lines:
                        # Typical output: "  1  command" or "command"
                        parts = line.strip().split(maxsplit=1)
                        cmd_part = parts[-1] # Take the last part, which should be the command
                        parsed_history_lines.append(cmd_part)

                    # `history` command usually lists oldest first.
                    commands = process_lines(parsed_history_lines, reverse_order=False)
                    if commands:
                        return commands
            except Exception:
                pass # Final fallback will be an empty list
        
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
            history_section = f"\n\nHere are the last {min(len(self.command_history), display_count)} unique commands from the user's shell history for context:\n"
            history_section += "\n".join(f"- {cmd}" for cmd in self.command_history[-display_count:])
        
        # Substitute variables in the template
        return prompt_template.substitute(
            os_info=self.os_info["os"],
            shell_info=self.os_info["shell"],
            history_section=history_section
        )
    
    def _is_greenlisted(self, command: str) -> bool:
        """Check if a command is in the greenlist (safe to run without confirmation),
        and ensure it doesn't contain any shell operators."""
        # 1. Check global validation flag
        if CONFIG.get('validate_all_commands', False):
            return False

        # 2. Disallow shell operators for all commands that are not greenlisted
        # (even if they might be part of a greenlisted command like `doskey /history` later)
        # This check is primarily for the overall command string.
        # The base_command check later will handle specific greenlisted commands.
        shell_operators = [';', '&&', '||', '|', '>', '<', '&', '$(', '`']
        # A more nuanced check for operators might be needed if greenlisted commands themselves
        # legitimately contain them (e.g. a script). For now, this is a general safety measure.
        # We will check the *base_command* against the greenlist.
        # If the command string itself contains operators, but the base_command is greenlisted
        # (e.g. "echo hello > file.txt"), this will currently be blocked.
        # This is a stricter interpretation for safety.
        # If a greenlisted command *needs* an operator (e.g. `doskey /history` is fine, but `echo hi;ls` is not)
        # this logic might need refinement. For now, `doskey /history` is a single "command" for `split()`.

        # We will check for operators *after* extracting the base command and arguments
        # to allow greenlisted commands like "doskey /history".
        
        # Get the base command (first word)
        command_parts = command.strip().split()
        base_command = command_parts[0] if command_parts else ""
        full_command_for_operator_check = command.strip()

        # Check for operators in the full command string, unless the command *itself* is greenlisted
        # and might contain something like a slash (e.g. "doskey /history").
        # The key is that the *entire matched greenlist entry* is what's safe.

        # Determine the key for greenlist lookup
        current_os = platform.system()
        shell_type = self.shell.shell_type
        key = 'default' # Default key

        if shell_type == 'powershell':
            key = 'windows_powershell'
        elif shell_type == 'cmd':
            key = 'windows_cmd'
        elif current_os == 'Linux':
            key = 'linux'
        elif current_os == 'Darwin': # macOS
            key = 'macos'

        all_greenlist_configs = CONFIG.get('greenlist_commands', {})
        greenlist = list(all_greenlist_configs.get(key, [])) # Make a mutable copy

        # Extend with default list if the key is not 'default' itself
        if key != 'default':
            default_greenlist = all_greenlist_configs.get('default', [])
            for item in default_greenlist:
                if item not in greenlist:
                    greenlist.append(item)

        # Now check if the command matches any greenlisted entry.
        # Some greenlisted commands can have spaces (e.g. "doskey /history").
        # So we check against the full command string for multi-word greenlisted items,
        # and against the base_command for single-word greenlisted items.

        is_safe = False
        for green_item in greenlist:
            if " " in green_item: # Multi-word greenlisted command
                if full_command_for_operator_check.startswith(green_item):
                    # Check if the rest of the command after the greenlisted part contains operators
                    remaining_command = full_command_for_operator_check[len(green_item):].strip()
                    if not any(op in remaining_command for op in shell_operators):
                        is_safe = True
                        break
            else: # Single-word greenlisted command
                if base_command == green_item:
                    # Check if arguments contain shell operators
                    args_part = command.strip()[len(base_command):].strip()
                    if not any(op in args_part for op in shell_operators):
                        is_safe = True
                        break
        return is_safe
    
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
    
    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool based on the tool call from Claude"""
        if tool_name == "run_command":
            command = tool_input.get("command", "").strip()
            if not command:
                return {"success": False, "output": "", "error": "No command provided"}
            
            # Check if command needs validation
            needs_validation = not self._is_greenlisted(command)
            
            if needs_validation:
                # Display command to be run
                console.print("\n[bold]Command to execute:[/bold]")
                lexer = "bash" # Default lexer
                if self.shell.shell_type == 'powershell':
                    lexer = 'powershell'
                elif self.shell.shell_type == 'cmd':
                    lexer = 'batch' # 'batch' is typical for cmd.exe syntax
                syntax = Syntax(command, lexer, theme=CONFIG['display']['theme'], line_numbers=CONFIG['display']['show_line_numbers'])
                console.print(syntax)
                
                response = console.input("\n[yellow]Run this command? (yes/no): [/yellow]").strip().lower()
                if response not in ["yes", "y"]:
                    reason = console.input("[yellow]Why not? (this will help me adjust): [/yellow]").strip()
                    return {
                        "success": False,
                        "output": "",
                        "error": f"User declined to run command: {reason}"
                    }
            
            # Execute the command using persistent shell
            try:
                stdout, stderr, returncode = self.shell.run_command(command)
                
                # Update current directory if command was cd
                if command.strip().startswith('cd '): # Ensure it's 'cd' and not 'cde' or similar
                    # After a 'cd' command, query the new current directory
                    pwd_cmd = "pwd"
                    if self.shell.shell_type == 'cmd':
                        pwd_cmd = "cd"
                    elif self.shell.shell_type == 'powershell':
                        pwd_cmd = "echo (Get-Location).Path"

                    # Use a temporary, fresh call to run_command to get the new CWD
                    # This avoids issues with the current command's output processing.
                    # We need to be careful here to avoid recursion if run_command itself calls _execute_tool
                    # However, this is _execute_tool calling run_command, which is fine.

                    # To prevent infinite recursion if pwd_cmd itself is 'cd',
                    # we directly use the shell's method.
                    new_stdout, _, _ = self.shell.run_command(pwd_cmd) # This is fine.

                    if self.shell.shell_type == 'cmd':
                        # 'cd' command output is just the path.
                        self.current_dir = new_stdout.strip().split('\n')[-1]
                    else:
                        # 'pwd' and 'echo (Get-Location).Path' output is just the path.
                        self.current_dir = new_stdout.strip()
                
                # Format output for both display and API
                formatted_output = self._format_command_output(command, stdout, stderr, returncode)
                
                # Truncate if needed
                truncated_output, was_truncated = self._truncate_output(formatted_output)
                
                # Display to user
                console.print()
                output_lexer = "bash" # Default lexer for output
                if self.shell.shell_type == 'powershell':
                    output_lexer = 'powershell'
                elif self.shell.shell_type == 'cmd':
                    output_lexer = 'batch'
                # Using shell-specific lexer for output. This might be too aggressive if output is not shell code.
                # However, often the output can contain command-like structures or be more readable with it.
                syntax = Syntax(truncated_output, output_lexer, theme=CONFIG['display']['theme'], line_numbers=CONFIG['display']['show_line_numbers'])
                console.print(syntax)
                
                # Return same output to API (what user sees is what model gets)
                return {
                    "success": returncode == 0,
                    "output": truncated_output,
                    "error": ""
                }
            except Exception as e:
                error_msg = f"Error executing command: {str(e)}"
                console.print(f"\n[red]❌ {error_msg}[/red]")
                return {"success": False, "output": "", "error": error_msg}
        
        elif tool_name == "shell_script":
            script = tool_input.get("script", "").strip()
            if not script:
                return {"success": False, "output": "", "error": "No script provided"}
            
            # Always require validation for shell scripts
            console.print("\n[bold]Shell script to execute:[/bold]")
            script_lexer = "bash" # Default lexer
            if self.shell.shell_type == 'powershell':
                script_lexer = 'powershell'
            elif self.shell.shell_type == 'cmd':
                script_lexer = 'batch'
            syntax = Syntax(script, script_lexer, theme=CONFIG['display']['theme'], line_numbers=CONFIG['display']['show_line_numbers'])
            console.print(syntax)
            
            response = console.input("\n[yellow]Run this script? (yes/no): [/yellow]").strip().lower()
            if response not in ["yes", "y"]:
                reason = console.input("[yellow]Why not? (this will help me adjust): [/yellow]").strip()
                return {
                    "success": False,
                    "output": "",
                    "error": f"User declined to run script: {reason}"
                }
            
            # Execute the script line by line using persistent shell
            try:
                # Split script into lines and execute each
                lines = script.strip().split('\n')
                all_stdout = []
                all_stderr = []
                last_returncode = 0
                
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#'):  # Skip empty lines and comments
                        stdout, stderr, returncode = self.shell.run_command(line)
                        if stdout:
                            all_stdout.append(stdout)
                        if stderr:
                            all_stderr.append(stderr)
                        last_returncode = returncode
                        
                        # Update current directory if command was cd
                        if line.startswith('cd '): # Ensure it's 'cd' and not 'cde'
                            pwd_cmd = "pwd"
                            if self.shell.shell_type == 'cmd':
                                pwd_cmd = "cd"
                            elif self.shell.shell_type == 'powershell':
                                pwd_cmd = "echo (Get-Location).Path"

                            new_stdout, _, _ = self.shell.run_command(pwd_cmd)

                            if self.shell.shell_type == 'cmd':
                                self.current_dir = new_stdout.strip().split('\n')[-1]
                            else:
                                self.current_dir = new_stdout.strip()
                
                # Format output for both display and API
                combined_stdout = '\n'.join(all_stdout)
                combined_stderr = '\n'.join(all_stderr)
                formatted_output = self._format_command_output("(shell script)", combined_stdout, combined_stderr, last_returncode)
                
                # Truncate if needed
                truncated_output, was_truncated = self._truncate_output(formatted_output)
                
                # Display to user
                console.print()
                output_lexer_script = "bash" # Default lexer for script output
                if self.shell.shell_type == 'powershell':
                    output_lexer_script = 'powershell'
                elif self.shell.shell_type == 'cmd':
                    output_lexer_script = 'batch'
                syntax = Syntax(truncated_output, output_lexer_script, theme=CONFIG['display']['theme'], line_numbers=CONFIG['display']['show_line_numbers'])
                console.print(syntax)
                
                # Return same output to API
                return {
                    "success": last_returncode == 0,
                    "output": truncated_output,
                    "error": ""
                }
            except Exception as e:
                error_msg = f"Error executing script: {str(e)}"
                console.print(f"\n[red]❌ {error_msg}[/red]")
                return {"success": False, "output": "", "error": error_msg}
        
        return {"success": False, "output": "", "error": f"Unknown tool: {tool_name}"}
    
    def cleanup(self):
        """Cleanup method to close the persistent shell"""
        if hasattr(self, 'shell') and self.shell:
            self.shell.close()
    
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
                            "content": result["output"] if result["success"] else result["error"]
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