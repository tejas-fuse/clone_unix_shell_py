import os
import sys
import subprocess
from pathlib import Path
import shlex
import readline
from io import StringIO


class Shell:

    def __init__(self):
        self.running = True
        self.builtins = {"echo", "exit", "type", "pwd", "cd", "history"}
        self.last_appended_history_len = 0 # Tracks history length after last append/write

        # Load history from HISTFILE on startup
        histfile = os.environ.get("HISTFILE")
        if histfile:
            try:
                with open(histfile, 'r') as f:
                    for line in f:
                        readline.add_history(line.strip())
                # After loading, update last_appended_history_len
                self.last_appended_history_len = readline.get_current_history_length()
            except FileNotFoundError:
                # If HISTFILE doesn't exist, that's fine, just start with empty history
                pass
            except Exception as e:
                print(f"Error loading history from {histfile}: {e}", file=sys.stderr)

    def run(self):
        """Main shell loop"""
        while self.running:
            try:
                # The prompt is now handled by input() in _get_user_input
                # sys.stdout.write("$ ")
                # sys.stdout.flush()

                command = self._get_user_input("$ ")
                if command:
                    self._execute_command(command)
            except (EOFError, KeyboardInterrupt):
                print()
                break

    def _get_user_input(self, prompt_string="$ "):
        """Get and parse user input"""
        readline.set_completer(self._handle_autocomplete)
        readline.parse_and_bind("tab: complete")
        readline.parse_and_bind("set show-all-if-ambiguous off")
        readline.parse_and_bind("set completion-query-items -1")
        readline.set_completer_delims(" \t\n;")
        readline.set_completion_display_matches_hook(self._display_matches)

        user_input = input(prompt_string).strip()



        # Handle redirection using system shell
        if ">" in user_input or "1>" in user_input:
            os.system(user_input)
            return None

        return shlex.split(user_input) if user_input else []

    def _display_matches(self, substitution, matches, longest_match_length):
        sys.stdout.write("\n")
        sys.stdout.write(" ".join(matches) + "\n")
        buffer = readline.get_line_buffer()
        sys.stdout.write(f"$ {buffer}")
        sys.stdout.flush()

    def _execute_command(self, command):
        """Execute the given command"""
        if not command:
            return

        # If the command contains a pipe, always send to _run_program
        if "|" in command:
            self._run_program(command)
            return

        cmd_name = command[0]
        match cmd_name:
            case "exit":
                self._handle_exit(command)
            case "type":
                self._handle_type(command)
            case "echo":
                self._handle_echo(command)
            case "pwd":
                self._handle_pwd()
            case "cd":
                self._handle_cd(command)
            case "history":
                self._handle_history(command)
            case _:
                found_path = self._check_PATH(cmd_name)
                if found_path:
                    self._run_program(command)
                else:
                    self._handle_unknown_commands(command)

    def _handle_exit(self, command):
        """Handle exit command"""
        self.running = False

        histfile = os.environ.get("HISTFILE")
        if histfile:
            try:
                with open(histfile, 'w') as f: # 'w' mode creates/overwrites the file
                    history_len = readline.get_current_history_length()
                    for i in range(1, history_len + 1):
                        cmd = readline.get_history_item(i)
                        f.write(cmd + '\n') # Write each command followed by a newline
            except Exception as e:
                print(f"Error saving history to {histfile}: {e}", file=sys.stderr)

    def _handle_type(self, command, stdout=None):
        """Handle type command"""
        if stdout is None:
            stdout = sys.stdout
        if len(command) < 2:
            print("type: missing argument", file=stdout)
            return

        cmd_name = command[1]
        if cmd_name in self.builtins:
            print(f"{cmd_name} is a shell builtin", file=stdout)
        else:
            found_path = self._check_PATH(cmd_name)
            if found_path:
                print(f"{cmd_name} is {found_path}", file=stdout)
            else:
                print(f"{cmd_name}: not found", file=stdout)

    def _handle_echo(self, command, stdout=None, input_text=None):
        """Handle echo command"""
        if stdout is None:
            stdout = sys.stdout
        # As per standard shell behavior, echo ignores stdin and prints its arguments.
        print(" ".join(command[1:]), file=stdout)

    def _handle_pwd(self, stdout=None):
        """Print present working directory"""
        if stdout is None:
            stdout = sys.stdout
        print(os.getcwd(), file=stdout)

    def _handle_cd(self, command):
        """Change directory"""
        if len(command) < 2:
            return
        path = command[1]
        if path == "~":
            os.chdir(Path.home())
            return
        if os.path.isdir(path):
            os.chdir(path)
        else:
            print(f"cd: {path}: No such file or directory")

    def _handle_history(self, command, stdout=None):
        """Handle history command"""
        if stdout is None:
            stdout = sys.stdout

        # Check for 'history -r <path>'
        if len(command) >= 3 and command[1] == "-r":
            file_path = command[2]
            try:
                with open(file_path, 'r') as f:
                    for line in f:
                        readline.add_history(line.strip())
            except FileNotFoundError:
                print(f"history: {file_path}: No such file or directory", file=stdout)
            except Exception as e:
                print(f"history: error reading file {file_path}: {e}", file=stdout)
            return

        # Check for 'history -w <path>'
        if len(command) >= 3 and command[1] == "-w":
            file_path = command[2]
            try:
                with open(file_path, 'w') as f: # 'w' mode creates/overwrites the file
                    history_len = readline.get_current_history_length()
                    for i in range(1, history_len + 1):
                        cmd = readline.get_history_item(i)
                        f.write(cmd + '\n') # Write each command followed by a newline
                self.last_appended_history_len = readline.get_current_history_length() # Update after writing all
            except Exception as e:
                print(f"history: error writing to file {file_path}: {e}", file=stdout)
            return

        # Check for 'history -a <path>'
        if len(command) >= 3 and command[1] == "-a":
            file_path = command[2]
            try:
                with open(file_path, 'a') as f: # 'a' mode for appending
                    current_history_len = readline.get_current_history_length()
                    # Iterate only over new commands since last append
                    for i in range(self.last_appended_history_len + 1, current_history_len + 1):
                        cmd = readline.get_history_item(i)
                        f.write(cmd + '\n')
                # Update last_appended_history_len after successful append
                self.last_appended_history_len = current_history_len
            except Exception as e:
                print(f"history: error appending to file {file_path}: {e}", file=stdout)
            return

        # Existing logic for 'history' and 'history <n>'
        history_len = readline.get_current_history_length()
        
        start_index = 1 # Default to start from the beginning
        end_index = history_len # Default to end at the last item

        if len(command) > 1:
            try:
                n = int(command[1])
                if n < 0:
                    print("history: invalid argument: negative number", file=stdout)
                    return
                
                if n > history_len:
                    pass 
                else:
                    start_index = history_len - n + 1
            except ValueError:
                print(f"history: invalid argument: '{command[1]}'", file=stdout)
                return

        for i in range(start_index, end_index + 1):
            cmd = readline.get_history_item(i)
            stdout.write(f"{i: >5}  {cmd}\n")

    def _handle_unknown_commands(self, command):
        """Handle unknown commands"""
        print(f"{' '.join(command)}: command not found")

    def _check_PATH(self, cmd_name):
        """Check for executable files in PATH and return the first match"""
        PATH_dirs = os.environ.get("PATH", "").split(":")
        for directory in PATH_dirs:
            if directory:
                full_path = os.path.join(directory, cmd_name)
                if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                    return full_path
        return None

    def _run_program(self, command):
        """Run commands, handling single external commands and pipelines."""
        if "|" not in command:
            subprocess.run(command)
            return

        commands = self._split_by_pipe(command)

        # Check if all commands in the pipeline are external
        all_external = all(cmd[0] not in self.builtins for cmd in commands)

        if all_external:
            self._run_external_pipeline(commands)
        else:
            self._run_mixed_pipeline(commands)

    def _split_by_pipe(self, command):
        """Splits a command list by the pipe symbol '|'."""
        commands = []
        current_command = []
        for arg in command:
            if arg == "|":
                if current_command:
                    commands.append(current_command)
                current_command = []
            else:
                current_command.append(arg)
        if current_command:
            commands.append(current_command)
        return commands

    def _run_external_pipeline(self, commands):
        """Runs a pipeline of only external commands concurrently."""
        processes = []
        pipe_input = sys.stdin
        for i, cmd in enumerate(commands):
            is_last = i == len(commands) - 1
            pipe_output = sys.stdout if is_last else subprocess.PIPE

            proc = subprocess.Popen(cmd, stdin=pipe_input, stdout=pipe_output, text=True)
            processes.append(proc)

            if pipe_input != sys.stdin:
                pipe_input.close()

            pipe_input = proc.stdout

        for proc in processes:
            proc.wait()

    def _run_mixed_pipeline(self, commands):
        """Runs a pipeline with mixed builtin and external commands sequentially."""
        next_input = None  # This will be a string

        for i, cmd_list in enumerate(commands):
            is_last = i == len(commands) - 1
            cmd_name = cmd_list[0]

            if cmd_name in self.builtins:
                stdout_dest = sys.stdout if is_last else StringIO()
                self._execute_builtin(cmd_list, stdout=stdout_dest, input_text=next_input)
                if not is_last:
                    next_input = stdout_dest.getvalue()
            else:  # External command
                if is_last:
                    subprocess.run(cmd_list, input=next_input, text=True, check=False)
                else:
                    result = subprocess.run(
                        cmd_list,
                        input=next_input,
                        text=True,
                        capture_output=True,
                        check=False,
                    )
                    next_input = result.stdout

    def _execute_builtin(self, command, stdout=None, input_text=None):
        """Executes a builtin command, handling input and output."""
        cmd_name = command[0]
        match cmd_name:
            case "echo":
                self._handle_echo(command, stdout=stdout, input_text=input_text)
            case "pwd":
                self._handle_pwd(stdout=stdout)
            case "type":
                self._handle_type(command, stdout=stdout)
            case "cd":
                self._handle_cd(command)
            case "exit":
                self._handle_exit(command)
            case "history":
                self._handle_history(command, stdout=stdout)

    def _handle_autocomplete(self, inputText: str, state: int):
        matchedWord = [
            word + " "
            for word in self.builtins
            if word.lower().startswith(inputText.lower())
        ]
        if len(matchedWord) > state:
            return matchedWord[state]
        else:
            matchedCommand = self._extract_command_from_env(inputText)
            index = state - len(matchedWord)
            if index < len(matchedCommand):
                return matchedCommand[index] + " "
            return None

    def _extract_command_from_env(self, inputText: str):
        matches = []
        path = os.getenv("PATH", "")
        for directory in path.split(":"):
            if not os.path.isdir(directory):
                continue
            for file in os.listdir(directory):
                if file.startswith(inputText):
                    matches.append(file)
        return matches


def main():
    shell = Shell()
    shell.run()


if __name__ == "__main__":
    main()
