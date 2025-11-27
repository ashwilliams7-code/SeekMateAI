"""
SeekMate AI - Build Script
Creates a standalone Windows application
"""
import subprocess
import os
import sys

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

print("=" * 50)
print("  SeekMate AI - Application Builder")
print("=" * 50)
print()

# PyInstaller command
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",                          # Single exe file
    "--windowed",                         # No console window
    "--name=SeekMate AI",                 # App name
    "--icon=seekmate_logo.png",           # App icon (will convert)
    "--add-data=config.json;.",           # Include config
    "--add-data=control.json;.",          # Include control
    "--add-data=seekmate_logo.png;.",     # Include logo
    "--clean",                            # Clean build
    "--noconfirm",                        # Don't ask for confirmation
    "config_gui.py"                       # Main script
]

print("Building SeekMate AI.exe...")
print()

result = subprocess.run(cmd, cwd=BASE_DIR)

if result.returncode == 0:
    print()
    print("=" * 50)
    print("  BUILD SUCCESSFUL!")
    print("=" * 50)
    print()
    print(f"  Your app is ready at:")
    print(f"  {os.path.join(BASE_DIR, 'dist', 'SeekMate AI.exe')}")
    print()
    print("  You can now:")
    print("  1. Copy it to your Desktop")
    print("  2. Pin it to your Taskbar")
    print("  3. Share it with others!")
    print()
else:
    print()
    print("Build failed! Check the errors above.")

input("Press Enter to close...")

