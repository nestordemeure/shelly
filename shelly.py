import os
import sys
import subprocess
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ShellTool:
    """Base class for shell tools"""
    def __init__(self, name: str, requires_validation: bool = False):
        self.name = name
        self.requires_validation = requires_validation
    
    def execute(self, args: List[str]) -> Dict[str, Any]:
        """Execute the tool with given arguments"""
        raise NotImplementedError

class LsTool(ShellTool):
    """Tool for listing directory contents"""
    def __init__(self):
        super().__init__("ls", requires_validation=False)
    
    def execute(self, args: List[str]) -> Dict[str, Any]:
        try:
            cmd = ["ls"] + args
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr,
                "command": " ".join(cmd)
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "command": " ".join(["ls"] + args)
            }

class PwdTool(ShellTool):
    """Tool for printing working directory"""
    def __init__(self):
        super().__init__("pwd", requires_validation=False)
    
    def execute(self, args: List[str]) -> Dict[str, Any]:
        try:
            cmd = ["pwd"] + args
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr,
                "command": " ".join(cmd)
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "command": " ".join(["pwd"] + args)
            }

class WhichTool(ShellTool):
    """Tool for locating commands"""
    def __init__(self):
        super().__init__("which", requires_validation=False)
    
    def execute(self, args: List[str]) -> Dict[str, Any]:
        try:
            cmd = ["which"] + args
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr,
                "command": " ".join(cmd)
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "command": " ".join(["which"] + args)
            }

class RunTool(ShellTool):
    """Tool for running arbitrary shell commands"""
    def __init__(self):
        super().__init__("run", requires_validation=True)
    
    def execute(self, command: str) -> Dict[str, Any]:
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr,
                "command": command
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e),
                "command": command
            }

class Shelly:
    """Main Shelly assistant class"""
    
    def __init__(self):
        # Initialize Anthropic client
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")
        
        self.client = anthropic.Anthropic(api_key=api_key)
        
        # Initialize tools
        self.tools = {
            "ls": LsTool(),
            "pwd": PwdTool(),
            "which": WhichTool(),
            "run": RunTool()
        }
        
        # Get last unique shell commands from history
        self.command_history = self._get_command_history()
        
        # Define system prompt
        self.system_prompt = self._create_system_prompt()
    
    def _get_command_history(self, nb_commands:int=100) -> List[str]:
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
            history_section += "\n".join(f"- {cmd}" for cmd in self.command_history)
        
        return f"""You are Shelly, a helpful terminal assistant. Your role is to help users run shell commands effectively.

You have access to the following tools:
- ls: Run ls with any options to list directory contents (no validation needed)
- pwd: Run pwd to show the current working directory (no validation needed)
- which: Run which to locate commands (no validation needed)
- run: Execute arbitrary shell commands (requires user validation)

When using tools, respond with a JSON object in this format:
{{"tool": "tool_name", "args": ["arg1", "arg2"], "command": "full command string"}}

For the 'run' tool, use: {{"tool": "run", "command": "your shell command here"}}

Always explain what each command does before suggesting to run it. Be helpful and educational.
{history_section}

When a user asks you to do something, suggest appropriate commands, explain them, and then try to execute them."""
    
    def _parse_tool_call(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse tool call from assistant response"""
        try:
            # Look for JSON in the response
            import re
            json_match = re.search(r'\{[^{}]*"tool"[^{}]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass
        return None
    
    def _execute_tool(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool based on the parsed call"""
        tool_name = tool_call.get("tool")
        
        if tool_name not in self.tools:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
        
        tool = self.tools[tool_name]
        
        if tool_name == "run":
            command = tool_call.get("command", "")
            if tool.requires_validation:
                print(f"\n🔧 About to run: {command}")
                response = input("Execute this command? (yes/no): ").strip().lower()
                if response not in ["yes", "y"]:
                    reason = input("Why not? (this will help me adjust): ").strip()
                    return {
                        "success": False,
                        "error": f"User declined: {reason}",
                        "command": command
                    }
            return tool.execute(command)
        else:
            args = tool_call.get("args", [])
            return tool.execute(args)
    
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
                # Get response from Claude
                response = self.client.messages.create(
                    model="claude-3-haiku-20240307",
                    system=self.system_prompt,
                    messages=messages,
                    max_tokens=4000
                )
                
                assistant_message = response.content[0].text
                print(f"\n🐚 Shelly: {assistant_message}")
                
                messages.append({"role": "assistant", "content": assistant_message})
                
                # Check for tool call
                tool_call = self._parse_tool_call(assistant_message)
                if tool_call:
                    # Execute the tool
                    result = self._execute_tool(tool_call)
                    
                    # Display the command that was run
                    print(f"\n💻 Command: {result.get('command', 'N/A')}")
                    
                    if result["success"]:
                        if result["output"]:
                            print(f"✅ Output:\n{result['output']}")
                        else:
                            print("✅ Command executed successfully (no output)")
                    else:
                        print(f"❌ Error: {result['error']}")
                    
                    # Add the result to context
                    result_message = f"Command '{result.get('command', 'N/A')}' "
                    if result["success"]:
                        result_message += f"succeeded with output:\n{result['output']}"
                    else:
                        result_message += f"failed with error:\n{result['error']}"
                    
                    messages.append({"role": "user", "content": result_message})
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