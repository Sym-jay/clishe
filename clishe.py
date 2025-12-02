#!/usr/bin/env python3
import json
import os
import readline
from sklearn.tree import DecisionTreeClassifier
import numpy as np

class ClisheML:
    def __init__(self, progress_file="clishe_progress.json", data_file="clishe_data.json"):
        self.progress_file = progress_file
        self.data_file = data_file

        # Supported Linux commands with brief descriptions
        self.command_help = {
            "ls": "Lists directory contents. Usage: ls [options] [path]",
            "cd": "Changes the directory. Usage: cd <directory>",
            "pwd": "Prints the current working directory.",
            "mkdir": "Creates a new directory. Usage: mkdir <directory_name>",
            "rm": "Removes files or directories. Usage: rm [options] <file>",
            "cp": "Copies files or directories. Usage: cp [options] <source> <destination>",
            "echo": "Displays a line of text/string. Usage: echo <text>",
            "cat": "Outputs the content of a file. Usage: cat <file>",
            "touch": "Creates an empty file or updates timestamp. Usage: touch <file>"
        }

        # Fallback static suggestions for next commands
        self.suggestions = {
            "ls": ["cd", "pwd", "mkdir"],
            "cd": ["ls", "pwd", "mkdir"],
            "mkdir": ["ls", "cd"],
            "rm": ["ls", "pwd"],
            "cp": ["ls", "pwd"],
            "echo": ["cat", "ls"],
            "cat": ["ls", "touch"],
            "touch": ["ls", "cat"],
        }

        # Common error messages mapped to friendly advice
        self.errors = {
            "command not found": "Check if command is typed correctly or use 'help <command>' to learn commands.",
            "No such file or directory": "Verify the file/directory exists or check the path.",
            "Permission denied": "Try with appropriate permissions or use 'sudo' if necessary."
        }

        self.user_history = []
        self.command_sequences = []
        self.model = None

        self.load_progress()
        self.load_data()

        # Setup readline for tab completion
        readline.parse_and_bind("tab: complete")
        self.completions = list(self.command_help.keys())
        readline.set_completer(self.complete)

    def load_progress(self):
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r') as f:
                    self.user_history = json.load(f)
            except json.JSONDecodeError:
                self.user_history = []

    def save_progress(self):
        with open(self.progress_file, 'w') as f:
            json.dump(self.user_history, f)

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    self.command_sequences = json.load(f)
            except json.JSONDecodeError:
                self.command_sequences = []
        if self.command_sequences:
            self.train_model()

    def save_data(self):
        with open(self.data_file, 'w') as f:
            json.dump(self.command_sequences, f)

    def train_model(self):
        X = []
        y = []
        label_map = {}
        label_counter = 0

        for seq in self.command_sequences:
            if len(seq) < 2:
                continue
            for i in range(len(seq) - 1):
                current_cmd = seq[i]
                next_cmd = seq[i + 1]
                if current_cmd not in label_map:
                    label_map[current_cmd] = label_counter
                    label_counter += 1
                X.append([label_map[current_cmd]])
                y.append(next_cmd)

        if X:
            self.model = DecisionTreeClassifier()
            self.model.fit(X, y)
        else:
            self.model = None

    def update_sequences(self, new_command):
        if not self.command_sequences or len(self.command_sequences[-1]) > 5:
            self.command_sequences.append([new_command])
        else:
            self.command_sequences[-1].append(new_command)
        self.save_data()
        self.train_model()

    def recognize_command(self, command):
        cmd = command.strip().split()[0]
        return cmd if cmd in self.command_help else None

    def provide_help(self, command):
        return self.command_help.get(command, "Sorry, that command is not recognized.")

    def suggest_commands(self, command):
        if self.model:
            try:
                label_map = {v: k for k, v in enumerate(self.model.classes_)}
                if command in label_map:
                    pred = self.model.predict([[label_map[command]]])
                    return [pred[0]]
            except Exception:
                return self.suggestions.get(command, [])
        else:
            return self.suggestions.get(command, [])

    def track_command(self, command):
        if command not in self.user_history:
            self.user_history.append(command)
        self.update_sequences(command)
        self.save_progress()

    def parse_error(self, error_msg):
        for key in self.errors:
            if key in error_msg:
                return self.errors[key]
        return "Error occurred: " + error_msg

    def run_command(self, command):
        try:
            os.system(command)
        except Exception as e:
            print(self.parse_error(str(e)))

    def complete(self, text, state):
        options = [cmd for cmd in self.completions if cmd.startswith(text)]
        if state < len(options):
            return options[state]
        else:
            return None

    def display_welcome(self):
        print("Welcome to Clishe - Your Smart Linux CLI Assistant!")
        print("\nSupported commands:")
        for cmd, desc in self.command_help.items():
            print(f" - {cmd}: {desc}")
        print("\nType 'help <command>' for detailed help, or press Tab for command suggestions.")
        print("Type 'history' to see your used commands, or 'exit' to quit.\n")

    def run(self):
        self.display_welcome()

        while True:
            try:
                user_input = input("Clishe> ").strip()
                if user_input.lower() == "exit":
                    print("Goodbye! Keep practicing Linux commands.")
                    break

                if user_input.lower() == "history":
                    print("Commands used so far:")
                    for cmd in self.user_history:
                        print(" -", cmd)
                    continue

                if user_input.startswith("help "):
                    cmd = user_input[5:].strip()
                    print(self.provide_help(cmd))
                    continue

                cmd = self.recognize_command(user_input)
                if cmd:
                    self.track_command(cmd)
                    print(f"Info: Help for '{cmd}':")
                    print(self.provide_help(cmd))
                    suggestions = self.suggest_commands(cmd)
                    if suggestions:
                        print("You might want to try next: " + ", ".join(suggestions))
                    self.run_command(user_input)
                else:
                    print("Command not recognized. Try 'help <command>' or check your input.")
            except KeyboardInterrupt:
                print("\nInterrupt detected. Type 'exit' to quit.")
            except EOFError:
                print("\nEOF detected. Exiting.")
                break

if __name__ == "__main__":
    clishe = ClisheML()
    clishe.run()

