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

# Load environment variables
load_dotenv()

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

For simple tool calls (ls, pwd, which), just execute them directly without explaining what the tool does - the user knows what these basic commands do. Only explain the results if they're noteworthy or if the user asked a specific question about them.

For the 'run' tool, explain what the commands will do before execution.
{history_section}

When a user asks you to do something, use the appropriate tools to help them."""
    
    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool based on the tool call from Claude"""
        if tool_name == "ls":
            args = tool_input.get("args", [])
            cmd = ["ls"] + args
            print(f"Running {' '.join(cmd)}")
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr
                }
            except Exception as e:
                return {"success": False, "output": "", "error": str(e)}
        
        elif tool_name == "pwd":
            args = tool_input.get("args", [])
            cmd = ["pwd"] + args
            print(f"Running {' '.join(cmd)}")
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr
                }
            except Exception as e:
                return {"success": False, "output": "", "error": str(e)}
        
        elif tool_name == "which":
            command = tool_input.get("command", "")
            cmd = ["which", command]
            print(f"Running {' '.join(cmd)}")
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr
                }
            except Exception as e:
                return {"success": False, "output": "", "error": str(e)}
        
        elif tool_name == "run":
            commands = tool_input.get("commands", [])
            if not commands:
                return {"success": False, "output": "", "error": "No commands provided"}
            
            # Ask for user validation
            print("\n```bash")
            for cmd in commands:
                print(cmd)
            print("```")
            response = input("\nRun? (yes/no): ").strip().lower()
            if response not in ["yes", "y"]:
                reason = input("Why not? (this will help me adjust): ").strip()
                return {
                    "success": False,
                    "output": "",
                    "error": f"User declined: {reason}"
                }
            
            # Execute commands
            outputs = []
            errors = []
            all_successful = True
            
            for cmd in commands:
                try:
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    if result.stdout:
                        outputs.append(result.stdout.rstrip())
                    if result.stderr:
                        errors.append(result.stderr.rstrip())
                    if result.returncode != 0:
                        all_successful = False
                        break
                except Exception as e:
                    errors.append(str(e))
                    all_successful = False
                    break
            
            return {
                "success": all_successful,
                "output": "\n".join(outputs),
                "error": "\n".join(errors)
            }
        
        return {"success": False, "output": "", "error": f"Unknown tool: {tool_name}"}
    
    def chat(self, initial_message: Optional[str] = None):
        """Start the chat interaction"""
        messages = []
        
        if initial_message:
            print(f"🐚 Shelly: Processing your request: '{initial_message}'")
            messages.append({"role": "user", "content": initial_message})
        else:
            print("🐚 Shelly: Hi! I'm Shelly, your terminal assistant. Ask me to help you run any shell commands!")
            user_input = input("\nYou: ").strip()
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
                        print(f"\n🐚 Shelly: {content.text}")
                        assistant_content.append({
                            "type": "text",
                            "text": content.text
                        })
                    elif content.type == "tool_use":
                        # Execute the tool
                        result = self._execute_tool(content.name, content.input)
                        
                        # Display output for run tool
                        if content.name == "run" and result["success"]:
                            if result["output"]:
                                print(f"\n```\n{result['output']}\n```")
                        elif content.name == "run" and not result["success"]:
                            if "User declined" not in result["error"]:
                                print(f"\n❌ Error: {result['error']}")
                        
                        # Display output for other tools
                        elif content.name in ["ls", "pwd", "which"]:
                            if result["success"] and result["output"]:
                                print(result['output'].rstrip())
                            elif not result["success"]:
                                print(f"❌ Error: {result['error']}")
                        
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
                user_input = input("\nYou: ").strip()
                if not user_input or user_input.lower() in ["exit", "quit", "bye"]:
                    print("\n🐚 Shelly: Goodbye! Happy coding!")
                    break
                
                messages.append({"role": "user", "content": user_input})
                
            except KeyboardInterrupt:
                print("\n\n🐚 Shelly: Goodbye! Happy coding!")
                break
            except Exception as e:
                print(f"\n❌ Error: {str(e)}")
                print("Let me try to help you differently...")

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
        print(f"❌ Configuration error: {e}")
        print("Please make sure you have a .env file with ANTHROPIC_API_KEY set.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()