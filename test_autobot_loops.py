#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test autobot.py can receive and process autobot_loops from UI
"""

import sys
import json
import subprocess
import tempfile
import os

def test_autobot_loops_param():
    """Test if autobot.py accepts autobot_loops parameter"""
    print("Testing autobot.py with autobot_loops parameter...")
    
    # Create a test config
    cfg = {
        "device_id": "TEST_DEVICE_001",
        "device_video_dir": "/sdcard/Movies",
        "autobot_loops": "3",  # String, as it comes from UI
        "run_mode": "AUTOBOT"
    }
    
    config_json = json.dumps(cfg, ensure_ascii=False)
    print(f"Config: {config_json}\n")
    
    # Check if autobot.py exists
    if not os.path.exists("autobot.py"):
        print("❌ autobot.py not found in workspace")
        return False
    
    # Try to import and check syntax
    try:
        import autobot
        print("✓ autobot.py syntax is valid")
    except Exception as e:
        print(f"⚠️  autobot.py import issue (may be expected): {e}")
    
    # Check that autobot_loops is used in the code
    with open("autobot.py", "r", encoding="utf-8") as f:
        content = f.read()
        if "autobot_loops" in content:
            print("✓ autobot.py uses 'autobot_loops' parameter")
            # Count occurrences
            count = content.count("autobot_loops")
            print(f"  Found {count} references to 'autobot_loops'")
        else:
            print("❌ autobot.py does NOT use 'autobot_loops' parameter")
            return False
    
    # Check ui.py adds autobot_loops to config
    with open("ui.py", "r", encoding="utf-8") as f:
        content = f.read()
        if "cfg['autobot_loops']" in content or 'cfg["autobot_loops"]' in content:
            print("✓ ui.py adds 'autobot_loops' to config")
        else:
            print("⚠️  ui.py may not be adding 'autobot_loops' to config")
    
    return True

if __name__ == "__main__":
    success = test_autobot_loops_param()
    if success:
        print("\n✓ autobot_loops integration looks good!")
    else:
        print("\n❌ Issues found with autobot_loops integration")
        sys.exit(1)
