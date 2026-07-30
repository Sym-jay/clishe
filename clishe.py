#!/usr/bin/env python3
"""
Clishe Brain - Backend for natural language command mapping and prediction
"""
import argparse
import json
import sys
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# File paths
KB_FILE = Path.home() / '.clishe_kb.json'
DATA_FILE = Path.home() / '.clishe_data.json'

# Minimum number of stored sequences before we bother training a predictor
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
            # Don't crash the whole CLI just because the state file got corrupted.
            print(f"Warning: could not read {path.name} ({e}); starting fresh.",
                  file=sys.stderr)
            return default

    def _save_json(self, path, payload):
        try:
            # Write to a temp file then replace, so a crash mid-write can't
            # corrupt the real file.
            tmp_path = path.with_suffix(path.suffix + '.tmp')
            with open(tmp_path, 'w') as f:
                json.dump(payload, f, indent=2)
            tmp_path.replace(path)
        except OSError as e:
            print(f"Warning: could not save {path.name} ({e})", file=sys.stderr)

    def load_kb(self):
        """Load knowledge base (phrase -> command) from JSON."""
        return self._load_json(KB_FILE, {})

    def save_kb(self):
        self._save_json(KB_FILE, self.kb)

    def load_data(self):
        """Load command sequences from JSON."""
        return self._load_json(DATA_FILE, {'sequences': [], 'current': []})

    def save_data(self):
        self._save_json(DATA_FILE, self.data)

    # ---------- actions ----------

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
        """Log a command to the current sequence."""
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
        """Predict next command based on historical sequences.

        Uses a lightweight frequency count (what command most often follows
        `last_command`) instead of retraining a classifier on every call.
        This is cheap, has no extra dependencies, and is easy to reason about.
        """
        sequences = self.data.get('sequences', [])
        if len(sequences) < MIN_SEQUENCES_FOR_PREDICTION:
            return ''

        follow_counts = {}
        for seq in sequences:
            for i in range(len(seq) - 1):
                if seq[i] == last_command:
                    nxt = seq[i + 1]
                    follow_counts[nxt] = follow_counts.get(nxt, 0) + 1

        if not follow_counts:
            return ''

        # Most frequent follower, excluding predicting the same command again
        candidates = {k: v for k, v in follow_counts.items() if k != last_command}
        if not candidates:
            return ''

        best = max(candidates, key=candidates.get)
        return best


def main():
    parser = argparse.ArgumentParser(description='Clishe Brain - NLP Command Backend')
    parser.add_argument('--action', required=True,
                         choices=['query', 'learn', 'log', 'predict'],
                         help='Action to perform')
    parser.add_argument('--phrase', default='', help='Natural language phrase')
    parser.add_argument('--command', default='', help='Bash command')

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


if __name__ == '__main__':
    main()
