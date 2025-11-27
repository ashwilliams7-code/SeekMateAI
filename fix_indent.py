#!/usr/bin/env python3
"""Fix indentation issues in config_gui.py"""

with open('config_gui.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix lines 1967 and 1972 (0-indexed: 1966 and 1971)
lines[1966] = '            self.config["MAX_JOBS"] = int(self.max_entry.get().strip())\n'
lines[1971] = '            self.config["EXPECTED_SALARY"] = int(self.salary_entry.get().strip())\n'

with open('config_gui.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Fixed indentation!')
