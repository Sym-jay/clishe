#!/usr/bin/env python3
"""
Clishe Brain - Backend for natural language command mapping and prediction
"""

import argparse
import json
import os
from pathlib import Path
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from sklearn.preprocessing import LabelEncoder
import warnings

warnings.filterwarnings('ignore')

# File paths
KB_FILE = Path.home() / '.clishe_kb.json'
DATA_FILE = Path.home() / '.clishe_data.json'

class ClisheBrain:
    def __init__(self):
        self.kb = self.load_kb()
        self.data = self.load_data()
        self.encoder = LabelEncoder()
        
    def load_kb(self):
        """Load knowledge base from JSON"""
        if KB_FILE.exists():
            with open(KB_FILE, 'r') as f:
                return json.load(f)
        return {}
    
    def save_kb(self):
        """Save knowledge base to JSON"""
        with open(KB_FILE, 'w') as f:
            json.dump(self.kb, f, indent=2)
    
    def load_data(self):
        """Load command sequences from JSON"""
        if DATA_FILE.exists():
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        return {'sequences': [], 'current': []}
    
    def save_data(self):
        """Save command sequences to JSON"""
        with open(DATA_FILE, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def query(self, phrase):
        """Query the knowledge base for a command"""
        phrase_lower = phrase.lower().strip()
        return self.kb.get(phrase_lower, '')
    
    def learn(self, phrase, command):
        """Learn a new phrase-command mapping"""
        phrase_lower = phrase.lower().strip()
        self.kb[phrase_lower] = command
        self.save_kb()
        return True
    
    def log(self, command):
        """Log a command to the current sequence"""
        self.data['current'].append(command)
        
        # If sequence gets too long, save it and start new
        if len(self.data['current']) >= 10:
            if len(self.data['current']) > 1:
                self.data['sequences'].append(self.data['current'])
            self.data['current'] = []
        
        self.save_data()
        return True
    
    def predict(self, last_command):
        """Predict next command based on historical sequences"""
        if not self.data['sequences'] or len(self.data['sequences']) < 3:
            return ''
        
        # Flatten all commands to get unique set
        all_commands = []
        for seq in self.data['sequences']:
            all_commands.extend(seq)
        
        unique_commands = list(set(all_commands))
        
        if len(unique_commands) < 2:
            return ''
        
        # Build training data
        X_train = []
        y_train = []
        
        for seq in self.data['sequences']:
            for i in range(len(seq) - 1):
                X_train.append(seq[i])
                y_train.append(seq[i + 1])
        
        if len(X_train) < 2:
            return ''
        
        try:
            # Encode commands as numbers
            self.encoder.fit(unique_commands)
            X_encoded = self.encoder.transform(X_train).reshape(-1, 1)
            y_encoded = self.encoder.transform(y_train)
            
            # Train classifier
            clf = DecisionTreeClassifier(max_depth=5, random_state=42)
            clf.fit(X_encoded, y_encoded)
            
            # Predict next command
            if last_command in unique_commands:
                last_encoded = self.encoder.transform([last_command]).reshape(-1, 1)
                pred_encoded = clf.predict(last_encoded)
                prediction = self.encoder.inverse_transform(pred_encoded)[0]
                
                # Don't predict the same command
                if prediction != last_command:
                    return prediction
        except Exception:
            pass
        
        return ''

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
        result = brain.query(args.phrase)
        print(result)
    
    elif args.action == 'learn':
        brain.learn(args.phrase, args.command)
        print('learned')
    
    elif args.action == 'log':
        brain.log(args.command)
        print('logged')
    
    elif args.action == 'predict':
        prediction = brain.predict(args.command)
        print(prediction)

if __name__ == '__main__':
    main()