#!/usr/bin/env python3
"""
Shell - A Claude-powered terminal assistant
Usage: Shell [optional command]
Example: Shell list the files in this folder
"""

import os
import sys
import subprocess
import anthropic
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.syntax import Syntax
import json
from pathlib import Path
from collections import OrderedDict
from dotenv import load_dotenv

console = Console()

class ShellAssistant:
    def __init__(self):
        # Load .env file from the script's parent directory
        script_path = Path(__file__).resolve()
        root_dir = script_path.parent
        env_path = root_dir / '.env'
        
        # Load environment variables from .env file
        load_dotenv(env_path)
        
        # Get API key from environment
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            console.print("[red]Error: ANTHROPIC_API_KEY not found[/red]")
            console.print(f"Please add ANTHROPIC_API_KEY to your .env file at: {env_path}")
            console.print("\nExample .env file content:")
            console.print("ANTHROPIC_API_KEY=your-api-key-here")
            sys.exit(1)
        
        self.client = anthropic.Anthropic(api_key=api_key)
        self.history = self.get_command_history()
        self.conversation = []
        self.cwd = os.getcwd()
        self.dir_contents = self.get_directory_contents()

    def get_directory_contents(self):
        """Get contents of current directory"""
        try:
            items = []
            for item in os.listdir(self.cwd):
                path = os.path.join(self.cwd, item)
                if os.path.isdir(path):
                    items.append(f"{item}/ (directory)")
                else:
                    items.append(item)
            return sorted(items)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not list directory contents: {e}[/yellow]")
            return []
        
    def get_command_history(self):
        """Get last 100 unique commands from shell history"""
        history_file = None
        shell = os.environ.get('SHELL', '').split('/')[-1]
        
        # Determine history file based on shell
        home = Path.home()
        if shell == 'zsh':
            history_file = home / '.zsh_history'
        elif shell == 'bash':
            history_file = home / '.bash_history'
        elif shell == 'fish':
            history_file = home / '.local/share/fish/fish_history'
        else:
            # Try common locations
            for f in ['.zsh_history', '.bash_history', '.history']:
                candidate = home / f
                if candidate.exists():
                    history_file = candidate
                    break
        
        if not history_file or not history_file.exists():
            console.print("[yellow]Warning: Could not find shell history file[/yellow]")
            return []
        
        try:
            with open(history_file, 'r', errors='ignore') as f:
                lines = f.readlines()
            
            # Parse commands based on shell format
            commands = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Handle zsh format (: timestamp:0;command)
                if line.startswith(':') and ';' in line:
                    cmd = line.split(';', 1)[1]
                # Handle fish format (- cmd: command)
                elif line.startswith('- cmd:'):
                    cmd = line[6:].strip()
                else:
                    cmd = line
                
                if cmd and not cmd.startswith('#'):
                    commands.append(cmd)
            
            # Get unique commands while preserving order (most recent first)
            seen = set()
            unique_commands = []
            for cmd in reversed(commands):
                if cmd not in seen:
                    seen.add(cmd)
                    unique_commands.append(cmd)
                    if len(unique_commands) >= 100:
                        break
            
            return unique_commands
        
        except Exception as e:
            console.print(f"[yellow]Warning: Error reading history: {e}[/yellow]")
            return []
    
    def create_prompt(self, task):
        """Create the initial prompt for Claude"""
        history_context = "\n".join([f"- {cmd}" for cmd in self.history])
        dir_context = "\n".join([f"- {item}" for item in self.dir_contents])
        
        return f"""You are Shelly, a helpful terminal command assistant. The user wants to: {task}

Current working directory: {self.cwd}
Operating system: {sys.platform}

Directory contents:
{dir_context}

Here are their last unique terminal commands for context:
{history_context}

Please suggest ONE specific command that would accomplish their task. Consider their command history to match their style and commonly used tools. 

You can run `ls` (with any arguments) and `pwd` commands directly without asking for permission to gather more information if needed.

Format your response as:
1. Brief explanation of what the command will do
2. The command in a code block
3. Any warnings or notes if applicable

Do not suggest multiple alternatives - pick the best single command."""

    def run_command(self, command):
        """Execute a command and return its output"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'stdout': '',
                'stderr': 'Command timed out after 30 seconds',
                'returncode': -1
            }
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def extract_command(self, response):
        """Extract command from Claude's response"""
        lines = response.split('\n')
        in_code_block = False
        command_lines = []
        
        for line in lines:
            if line.strip().startswith('```'):
                if in_code_block:
                    break
                in_code_block = True
                continue
            elif in_code_block:
                command_lines.append(line)
        
        return '\n'.join(command_lines).strip()
    
    def chat(self, initial_task=None):
        """Start the chat interface"""
        console.print(Panel.fit(
            "[bold cyan]Shell Assistant[/bold cyan]\n"
            "I'll help you run terminal commands. Type 'exit' to quit.",
            border_style="cyan"
        ))
        
        if initial_task:
            task = initial_task
        else:
            task = Prompt.ask("\n[bold]What would you like to do?[/bold]")
        
        while task.lower() not in ['exit', 'quit', 'q']:
            console.print("\n[dim]Thinking...[/dim]")
            
            # Prepare messages
            messages = [{"role": "user", "content": self.create_prompt(task)}]
            
            # Add conversation history
            for msg in self.conversation[-4:]:  # Keep last 4 exchanges
                messages.append(msg)
            
            messages.append({"role": "user", "content": task})
            
            try:
                # Get Claude's response
                response = self.client.messages.create(
                    model="claude-3-5-haiku-20241022",
                    max_tokens=8000,
                    messages=messages
                )
                
                assistant_message = response.content[0].text
                
                # Display response with markdown
                console.print("\n[bold cyan]Claude:[/bold cyan]")
                console.print(Markdown(assistant_message))
                
                # Extract command
                command = self.extract_command(assistant_message)
                
                if command:
                    # Check if it's an auto-allowed command
                    is_auto_allowed = (command.strip().startswith('ls') or 
                                     command.strip() == 'pwd' or 
                                     command.strip().startswith('pwd '))
                    
                    if is_auto_allowed:
                        console.print(f"\n[bold]Running command automatically:[/bold]")
                        console.print(Syntax(command, "bash", theme="monokai"))
                        confirm = True
                    else:
                        console.print(f"\n[bold]Suggested command:[/bold]")
                        console.print(Syntax(command, "bash", theme="monokai"))
                        confirm = Confirm.ask("\nRun this command?", default=True)
                    
                    if confirm:
                        console.print("\n[dim]Running command...[/dim]\n")
                        
                        result = self.run_command(command)
                        
                        # Display output
                        if result['stdout']:
                            console.print("[bold green]Output:[/bold green]")
                            console.print(result['stdout'])
                        
                        if result['stderr']:
                            console.print("[bold red]Error:[/bold red]")
                            console.print(result['stderr'])
                        
                        if result['success']:
                            console.print(f"\n[green]✓ Command completed successfully[/green]")
                        else:
                            console.print(f"\n[red]✗ Command failed with exit code {result['returncode']}[/red]")
                        
                        # Update directory contents if ls was run
                        if command.strip().startswith('ls'):
                            self.dir_contents = self.get_directory_contents()
                        
                        # Add to conversation history
                        self.conversation.append({"role": "user", "content": task})
                        self.conversation.append({"role": "assistant", "content": assistant_message})
                        self.conversation.append({
                            "role": "user", 
                            "content": f"Command output:\n{result['stdout']}\n{result['stderr']}"
                        })
                    else:
                        console.print("[yellow]Command cancelled[/yellow]")
                else:
                    console.print("\n[yellow]No command found in response[/yellow]")
                
            except Exception as e:
                console.print(f"[red]Error communicating with Claude: {e}[/red]")
            
            # Get next task
            task = Prompt.ask("\n[bold]What would you like to do next?[/bold]")
        
        console.print("\n[cyan]Goodbye![/cyan]")

def main():
    # Get initial command from arguments
    initial_task = None
    if len(sys.argv) > 1:
        initial_task = ' '.join(sys.argv[1:])
    
    # Create and run assistant
    assistant = ShellAssistant()
    assistant.chat(initial_task)

if __name__ == "__main__":
    main()