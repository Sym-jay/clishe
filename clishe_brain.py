#!/usr/bin/env python3
"""
Clishe Brain - Backend for natural language command mapping, prediction,
and (new) AI-provider-backed phrase resolution / command explanation.
"""
import argparse
import json
import sys
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Make sure the script's own directory is importable regardless of the
# caller's cwd (clishe.sh may be invoked from anywhere).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import load_config
from providers import build_provider_chain, ProviderError
from knowledge import lookup_command, format_explanation, diagnose_error

# File paths
KB_FILE = Path.home() / '.clishe_kb.json'
DATA_FILE = Path.home() / '.clishe_data.json'

# Minimum number of stored sequences before we bother predicting
MIN_SEQUENCES_FOR_PREDICTION = 3
# How many commands we keep in the "current" rolling buffer before archiving
SEQUENCE_FLUSH_LENGTH = 10


class ClisheBrain:
    def __init__(self):
        self.kb = self.load_kb()
        self.data = self.load_data()

    # ---------- persistence helpers ----------

    def _load_json(self, path, default):
        """Load JSON from disk, falling back to `default` on missing/corrupt file."""
        if not path.exists():
            return default
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: could not read {path.name} ({e}); starting fresh.",
                  file=sys.stderr)
            return default

    def _save_json(self, path, payload):
        try:
            tmp_path = path.with_suffix(path.suffix + '.tmp')
            with open(tmp_path, 'w') as f:
                json.dump(payload, f, indent=2)
            tmp_path.replace(path)
        except OSError as e:
            print(f"Warning: could not save {path.name} ({e})", file=sys.stderr)

    def load_kb(self):
        return self._load_json(KB_FILE, {})

    def save_kb(self):
        self._save_json(KB_FILE, self.kb)

    def load_data(self):
        return self._load_json(DATA_FILE, {'sequences': [], 'current': []})

    def save_data(self):
        self._save_json(DATA_FILE, self.data)

    # ---------- KB / prediction actions ----------

    def query(self, phrase):
        """Query the knowledge base for a command."""
        phrase_lower = phrase.lower().strip()
        return self.kb.get(phrase_lower, '')

    def learn(self, phrase, command):
        """Learn a new phrase-command mapping."""
        phrase_lower = phrase.lower().strip()
        if not phrase_lower or not command.strip():
            return False
        self.kb[phrase_lower] = command.strip()
        self.save_kb()
        return True

    def log(self, command):
        if not command.strip():
            return False
        self.data.setdefault('current', []).append(command)

        if len(self.data['current']) >= SEQUENCE_FLUSH_LENGTH:
            if len(self.data['current']) > 1:
                self.data.setdefault('sequences', []).append(self.data['current'])
            self.data['current'] = []

        self.save_data()
        return True

    def predict(self, last_command):
        """Predict next command via simple frequency count over past sequences."""
        sequences = self.data.get('sequences', [])
        if len(sequences) < MIN_SEQUENCES_FOR_PREDICTION:
            return ''

        follow_counts = {}
        for seq in sequences:
            for i in range(len(seq) - 1):
                if seq[i] == last_command:
                    nxt = seq[i + 1]
                    follow_counts[nxt] = follow_counts.get(nxt, 0) + 1

        candidates = {k: v for k, v in follow_counts.items() if k != last_command}
        if not candidates:
            return ''
        return max(candidates, key=candidates.get)

    # ---------- AI provider actions ----------

    def resolve(self, phrase):
        """Ask configured providers (in priority order) to translate an
        unknown phrase into a shell command. Returns a dict:
          {"status": "ok", "command": ..., "provider": ...}
          {"status": "declined", "provider": ...}   - model understood but wouldn't answer
          {"status": "unavailable"}                  - no provider could be reached
        On success, also caches the mapping into the KB so we never pay for
        the same phrase twice.
        """
        config = load_config()
        chain = build_provider_chain(config)

        if not chain:
            return {"status": "unavailable"}

        for provider in chain:
            try:
                command = provider.resolve_command(phrase)
            except ProviderError as e:
                print(f"[{provider.name}] {e}", file=sys.stderr)
                continue  # try the next provider in the chain

            if command:
                self.learn(phrase, command)  # cache so KB handles it next time, free
                return {"status": "ok", "command": command, "provider": provider.name}
            else:
                # This provider understood the request but declined to answer
                # (unclear/unsafe) - that's a real answer, don't keep trying
                # other providers for the same unsafe request.
                return {"status": "declined", "provider": provider.name}

        return {"status": "unavailable"}

    def explain(self, command):
        """Explain a shell command. Checks the offline built-in dictionary
        first (free, instant, no network) - only falls through to AI
        providers if the base command isn't in the dictionary."""
        entry = lookup_command(command)
        if entry:
            return {
                "status": "ok",
                "explanation": format_explanation(entry),
                "provider": "offline dictionary",
            }

        config = load_config()
        chain = build_provider_chain(config)

        for provider in chain:
            try:
                explanation = provider.explain_command(command)
            except ProviderError as e:
                print(f"[{provider.name}] {e}", file=sys.stderr)
                continue

            if explanation:
                return {"status": "ok", "explanation": explanation, "provider": provider.name}

        return {"status": "unavailable"}

    def diagnose(self, error_text):
        """Translate a command's stderr output into a plain-English hint,
        using offline pattern matching only - no AI call, since this needs
        to be instant and available even with no providers configured."""
        hint = diagnose_error(error_text)
        if hint:
            return {"status": "ok", "hint": hint}
        return {"status": "unmatched"}


def main():
    parser = argparse.ArgumentParser(description='Clishe Brain - Command Backend')
    parser.add_argument('--action', required=True,
                         choices=['query', 'learn', 'log', 'predict', 'resolve', 'explain', 'diagnose'],
                         help='Action to perform')
    parser.add_argument('--phrase', default='', help='Natural language phrase')
    parser.add_argument('--command', default='', help='Bash command')
    parser.add_argument('--error', default='', help='Captured stderr text to diagnose')

    args = parser.parse_args()
    brain = ClisheBrain()

    if args.action == 'query':
        print(brain.query(args.phrase))

    elif args.action == 'learn':
        ok = brain.learn(args.phrase, args.command)
        print('learned' if ok else 'error')

    elif args.action == 'log':
        ok = brain.log(args.command)
        print('logged' if ok else 'error')

    elif args.action == 'predict':
        print(brain.predict(args.command))

    elif args.action == 'resolve':
        # Line-based STATUS=/COMMAND=/PROVIDER= output so clishe.sh can parse
        # it with plain bash, no JSON tool required.
        result = brain.resolve(args.phrase)
        print(f"STATUS={result['status']}")
        if result['status'] == 'ok':
            print(f"COMMAND={result['command']}")
            print(f"PROVIDER={result['provider']}")
        elif result['status'] == 'declined':
            print(f"PROVIDER={result['provider']}")

    elif args.action == 'explain':
        result = brain.explain(args.command)
        print(f"STATUS={result['status']}")
        if result['status'] == 'ok':
            # Explanations can be multi-line (flags list, example, danger
            # note) - encode newlines so the bash side can decode them
            # cleanly with a single-line KEY=value parser.
            encoded = result['explanation'].replace("\n", "\\n")
            print(f"EXPLANATION={encoded}")
            print(f"PROVIDER={result['provider']}")

    elif args.action == 'diagnose':
        result = brain.diagnose(args.error)
        print(f"STATUS={result['status']}")
        if result['status'] == 'ok':
            print(f"HINT={result['hint']}")


if __name__ == '__main__':
    main()
