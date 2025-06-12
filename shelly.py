#!/usr/bin/env python3
"""
Shelly - An LLM-based terminal assistant powered by Claude Haiku
"""

import os
import sys
import subprocess
from typing import List, Dict, Any, Optional
from pathlib import Path
import anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax

# Load environment variables
load_dotenv()

# Initialize rich console
console = Console()

class Shelly:
    """Main Shelly assistant class"""
    
    def __init__(self):
        # Initialize Anthropic client
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in .env file")
        
        self.client = anthropic.Anthropic(api_key=api_key)
        
        # Get last 100 unique shell commands from history
        self.command_history = self._get_command_history()
        
        # Define system prompt
        self.system_prompt = self._create_system_prompt()
        
        # Define tools for the API
        self.tools = [
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
    
    def _get_command_history(self, nb_commands: int = 100) -> List[str]:
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
                            if len(commands) >= nb_commands:
                                break
                    commands.reverse()
            except Exception:
                pass
        
        return commands
    
    def _create_system_prompt(self) -> str:
        """Create the system prompt for Shelly"""
        history_section = ""
        if self.command_history:
            history_section = f"\n\nHere are the last {len(self.command_history)} unique commands from the user's shell history for inspiration:\n"
            history_section += "\n".join(f"- {cmd}" for cmd in self.command_history[-20:])  # Show last 20 for brevity
        
        return f"""You are Shelly, a helpful terminal assistant. Your role is to help users run shell commands effectively.

You have access to tools to execute shell commands:
- ls: List directory contents (no validation needed)
- pwd: Show current working directory (no validation needed)
- which: Check if commands are installed (no validation needed)
- run: Execute shell commands (requires user validation)

For simple tool calls (ls, pwd, which), be extremely concise - just state what you found or what happened. The user can see the command output directly, so don't repeat or explain it unless specifically asked.

Examples of good responses after tool use:
- "Yes, ImageMagick is installed!" (if which convert succeeds)
- "ImageMagick is not installed." (if which convert fails)
- "Here are your Python files:" (after ls *.py)
- "You're in /home/user/projects" (after pwd)

For the 'run' tool, explain what the commands will do before execution.
{history_section}

When a user asks you to do something, use the appropriate tools to help them."""
    
    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool based on the tool call from Claude"""
        if tool_name == "ls":
            args = tool_input.get("args", [])
            cmd = ["ls"] + args
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                # Display command and output in a code block
                output = f"$ {' '.join(cmd)}\n"
                if result.stdout:
                    output += result.stdout.rstrip()
                elif result.returncode == 0:
                    output += "(no output)"
                else:
                    output += f"Error: {result.stderr.rstrip()}"
                
                syntax = Syntax(output, "bash", theme="monokai", line_numbers=False)
                console.print(syntax)
                
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr
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
                output = f"$ {' '.join(cmd)}\n"
                if result.stdout:
                    output += result.stdout.rstrip()
                elif result.returncode == 0:
                    output += "(no output)"
                else:
                    output += f"Error: {result.stderr.rstrip()}"
                
                syntax = Syntax(output, "bash", theme="monokai", line_numbers=False)
                console.print(syntax)
                
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout,
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
                output = f"$ {' '.join(cmd)}\n"
                if result.stdout:
                    output += result.stdout.rstrip()
                elif result.returncode == 0:
                    output += "(no output)"
                else:
                    output += f"Error: command not found"
                
                syntax = Syntax(output, "bash", theme="monokai", line_numbers=False)
                console.print(syntax)
                
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr
                }
            except Exception as e:
                console.print(f"[red]❌ Error: {str(e)}[/red]")
                return {"success": False, "output": "", "error": str(e)}
        
        elif tool_name == "run":
            commands = tool_input.get("commands", [])
            if not commands:
                return {"success": False, "output": "", "error": "No commands provided"}
            
            # Display commands to be run
            console.print("\n[bold]Commands to execute:[/bold]")
            cmd_display = "\n".join(commands)
            syntax = Syntax(cmd_display, "bash", theme="monokai", line_numbers=False)
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
                    
                    if result.stderr:
                        cmd_output += f"\n{result.stderr.rstrip()}"
                    
                    # Display this command's output
                    syntax = Syntax(cmd_output, "bash", theme="monokai", line_numbers=False)
                    console.print(syntax)
                    
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
    
    def chat(self, initial_message: Optional[str] = None):
        """Start the chat interaction"""
        messages = []
        
        if initial_message:
            console.print(f"[bold cyan]🐚 Shelly:[/bold cyan] Processing your request: '{initial_message}'")
            messages.append({"role": "user", "content": initial_message})
        else:
            console.print("[bold cyan]🐚 Shelly:[/bold cyan] Hi! I'm Shelly, your terminal assistant. Ask me to help you run any shell commands!")
            user_input = console.input("\n[bold green]You:[/bold green] ").strip()
            if not user_input:
                return
            messages.append({"role": "user", "content": user_input})
        
        while True:
            try:
                # Get response from Claude with tools
                response = self.client.messages.create(
                    model="claude-3-haiku-20240307",
                    system=self.system_prompt,
                    messages=messages,
                    max_tokens=4000,
                    tools=self.tools
                )
                
                # Process the response
                assistant_content = []
                tool_results = []
                
                for content in response.content:
                    if content.type == "text":
                        # Use rich markdown for better formatting
                        md = Markdown(content.text)
                        console.print("\n🐚 Shelly:", style="bold cyan")
                        console.print(md)
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
                    console.print("\n[bold cyan]🐚 Shelly:[/bold cyan] Goodbye! Happy coding!")
                    break
                
                messages.append({"role": "user", "content": user_input})
                
            except KeyboardInterrupt:
                console.print("\n\n[bold cyan]🐚 Shelly:[/bold cyan] Goodbye! Happy coding!")
                break
            except Exception as e:
                console.print(f"\n[red]❌ Error: {str(e)}[/red]")
                console.print("Let me try to help you differently...")

def main():
    """Main entry point"""
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

if __name__ == "__main__":
    main()