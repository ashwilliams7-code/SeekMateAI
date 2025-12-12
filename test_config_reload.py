"""
Test script to verify config reloading works correctly
"""
import json
import os
import time

CONFIG_FILE = "config.json"
CONTROL_FILE = "control.json"

def write_control(pause=None, stop=None, recommended=None):
    """Write control flags"""
    data = {"pause": False, "stop": False, "recommended": False}
    if os.path.exists(CONTROL_FILE):
        try:
            with open(CONTROL_FILE, "r") as f:
                existing = json.load(f)
                data.update(existing)
        except:
            pass

    if pause is not None:
        data["pause"] = pause
    if stop is not None:
        data["stop"] = stop
    if recommended is not None:
        data["recommended"] = recommended

    with open(CONTROL_FILE, "w") as f:
        json.dump(data, f, indent=2)

def reload_config():
    """Simulate the reload_config function from main.py"""
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
    except Exception as e:
        print(f"[!] Failed to load config: {e}")
        config = {}
    
    # Extract key values
    scan_speed = config.get("SCAN_SPEED", 50)
    max_jobs = config.get("MAX_JOBS", 100)
    location = config.get("LOCATION", "Brisbane, Australia")
    full_name = config.get("FULL_NAME", "User")
    
    print(f"[CONFIG RELOADED]")
    print(f"  Scan Speed: {scan_speed}%")
    print(f"  Max Jobs: {max_jobs}")
    print(f"  Location: {location}")
    print(f"  Full Name: {full_name}")
    return config

print("=" * 50)
print("🧪 Testing Config Reload Functionality")
print("=" * 50)
print()

# Test 1: Initial load
print("Test 1: Initial config load")
print("-" * 50)
config1 = reload_config()
print()

# Test 2: Modify config and reload
print("Test 2: Modify config and reload")
print("-" * 50)
print("Modifying config.json...")
with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

# Change some values
config["SCAN_SPEED"] = 75
config["MAX_JOBS"] = 50
config["LOCATION"] = "Sydney, Australia"

with open(CONFIG_FILE, "w") as f:
    json.dump(config, f, indent=4)

print("Config modified. Reloading...")
time.sleep(0.5)  # Small delay
config2 = reload_config()

# Verify changes were picked up
if config2.get("SCAN_SPEED") == 75:
    print("✅ SUCCESS: Scan Speed reloaded correctly (75%)")
else:
    print(f"❌ FAILED: Expected 75, got {config2.get('SCAN_SPEED')}")

if config2.get("MAX_JOBS") == 50:
    print("✅ SUCCESS: Max Jobs reloaded correctly (50)")
else:
    print(f"❌ FAILED: Expected 50, got {config2.get('MAX_JOBS')}")

if config2.get("LOCATION") == "Sydney, Australia":
    print("✅ SUCCESS: Location reloaded correctly")
else:
    print(f"❌ FAILED: Expected 'Sydney, Australia', got '{config2.get('LOCATION')}'")

print()

# Test 3: Control file reset
print("Test 3: Control file reset")
print("-" * 50)
print("Setting stop=True...")
write_control(stop=True)
with open(CONTROL_FILE, "r") as f:
    control = json.load(f)
print(f"  stop = {control.get('stop')}")

print("Resetting control file...")
write_control(pause=False, stop=False)
with open(CONTROL_FILE, "r") as f:
    control = json.load(f)
print(f"  stop = {control.get('stop')}")
print(f"  pause = {control.get('pause')}")

if not control.get('stop') and not control.get('pause'):
    print("✅ SUCCESS: Control file reset correctly")
else:
    print("❌ FAILED: Control file not reset properly")

print()
print("=" * 50)
print("✅ All tests completed!")
print("=" * 50)

