import os
import sys
import subprocess
import json
import platform
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
        
        # Get system info
        self.os_info = self._get_system_info()
        
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
        
        # If no history file or it's empty, try using the history command
        if not commands:
            try:
                result = subprocess.run(['history', str(max_commands)], 
                                      capture_output=True, text=True, shell=True)
                if result.returncode == 0 and result.stdout:
                    # Parse history output (typically "NUMBER COMMAND")
                    seen = set()
                    for line in result.stdout.strip().split('\n'):
                        # Remove leading number and whitespace
                        parts = line.strip().split(maxsplit=1)
                        if len(parts) > 1:
                            cmd = parts[1]
                            if cmd and cmd not in seen:
                                seen.add(cmd)
                                commands.append(cmd)
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
            # Use a default prompt if file not found
            prompt_template = Template("""You are Shelly, a helpful terminal assistant (running on $os_info with $shell_info shell). Your role is to help users run shell commands effectively.

You have access to two tools:

**run_command**: Execute a single shell command
- Use for individual commands

**shell_script**: Execute a block of shell script code
- Use for complex scripts, loops, conditionals, or multi-line operations

When you use these tools, explain what the command or script will do before executing it, especially for non-trivial operations. This helps users understand what will happen.

If a user stops a command or script from running, they'll provide feedback explaining why. Use this feedback to understand their concerns and adjust your approach accordingly.

$history_section

When a user asks you to do something, use the appropriate tools to help them.""")
        
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
        """Check if a command is in the greenlist (safe to run without confirmation)"""
        # Get the base command (first word)
        base_command = command.strip().split()[0] if command.strip() else ""
        
        # Get greenlist from config, default to read-only commands
        greenlist = CONFIG.get('greenlist_commands', [
            'ls', 'pwd', 'which', 'grep', 'find', 'cat', 'head', 'tail',
            'wc', 'du', 'tree', 'echo', 'date', 'whoami', 'hostname',
            'uname', 'id', 'groups', 'env', 'printenv', 'type', 'file',
            'stat', 'readlink', 'basename', 'dirname', 'realpath'
        ])
        
        return base_command in greenlist
    
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
                syntax = Syntax(command, "bash", theme=CONFIG['display']['theme'], line_numbers=CONFIG['display']['show_line_numbers'])
                console.print(syntax)
                
                response = console.input("\n[yellow]Run this command? (yes/no): [/yellow]").strip().lower()
                if response not in ["yes", "y"]:
                    reason = console.input("[yellow]Why not? (this will help me adjust): [/yellow]").strip()
                    return {
                        "success": False,
                        "output": "",
                        "error": f"User declined to run command: {reason}"
                    }
            
            # Execute the command
            try:
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
                
                # Format output for both display and API
                formatted_output = self._format_command_output(command, result.stdout, result.stderr, result.returncode)
                
                # Truncate if needed
                truncated_output, was_truncated = self._truncate_output(formatted_output)
                
                # Display to user
                console.print()
                syntax = Syntax(truncated_output, "bash", theme=CONFIG['display']['theme'], line_numbers=CONFIG['display']['show_line_numbers'])
                console.print(syntax)
                
                # Return same output to API (what user sees is what model gets)
                return {
                    "success": result.returncode == 0,
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
            syntax = Syntax(script, "bash", theme=CONFIG['display']['theme'], line_numbers=CONFIG['display']['show_line_numbers'])
            console.print(syntax)
            
            response = console.input("\n[yellow]Run this script? (yes/no): [/yellow]").strip().lower()
            if response not in ["yes", "y"]:
                reason = console.input("[yellow]Why not? (this will help me adjust): [/yellow]").strip()
                return {
                    "success": False,
                    "output": "",
                    "error": f"User declined to run script: {reason}"
                }
            
            # Execute the script
            try:
                result = subprocess.run(script, shell=True, capture_output=True, text=True)
                
                # Format output for both display and API
                formatted_output = self._format_command_output("(shell script)", result.stdout, result.stderr, result.returncode)
                
                # Truncate if needed
                truncated_output, was_truncated = self._truncate_output(formatted_output)
                
                # Display to user
                console.print()
                syntax = Syntax(truncated_output, "bash", theme=CONFIG['display']['theme'], line_numbers=CONFIG['display']['show_line_numbers'])
                console.print(syntax)
                
                # Return same output to API
                return {
                    "success": result.returncode == 0,
                    "output": truncated_output,
                    "error": ""
                }
            except Exception as e:
                error_msg = f"Error executing script: {str(e)}"
                console.print(f"\n[red]❌ {error_msg}[/red]")
                return {"success": False, "output": "", "error": error_msg}
        
        return {"success": False, "output": "", "error": f"Unknown tool: {tool_name}"}
    
    def cleanup(self):
        """Cleanup method to restore original directory"""
        try:
            os.chdir(self.original_dir)
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