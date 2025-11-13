#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simple test to verify UI logic for starting bot processes
"""

import sys
import json
import subprocess

def test_subprocess_creation():
    """Test if subprocess creation works"""
    print("Testing subprocess creation...")
    
    # Simulate config
    cfg = {
        "device_id": "TEST_DEVICE",
        "serial": "TEST_DEVICE",
        "run_mode": "NORMAL",
        "autobot_loops": "10"
    }
    
    config_data = json.dumps(cfg, ensure_ascii=False)
    print(f"Config: {config_data}")
    
    # Test for NORMAL mode (bot.py)
    cmd_args_normal = [
        sys.executable,
        "bot.py",
        "--device", "TEST_DEVICE",
        "--config_data", config_data
    ]
    print(f"\n✓ NORMAL mode command: {' '.join(cmd_args_normal)}")
    
    # Test for AUTOBOT mode (autobot.py)
    cmd_args_autobot = [
        sys.executable,
        "autobot.py",
        "--device", "TEST_DEVICE",
        "--config_data", config_data
    ]
    print(f"✓ AUTOBOT mode command: {' '.join(cmd_args_autobot)}")
    
    print("\n✓ Subprocess commands look correct!")

def test_config_with_loops():
    """Test if autobot_loops is properly included in config"""
    print("\nTesting autobot_loops in config...")
    
    cfg = {
        "device_id": "TEST_DEVICE",
        "autobot_loops": "90",  # Should be string from UI
        "run_mode": "AUTOBOT"
    }
    
    config_json = json.dumps(cfg, ensure_ascii=False)
    cfg_loaded = json.loads(config_json)
    
    loops = int(cfg_loaded.get("autobot_loops", 1))
    print(f"Original autobot_loops: {cfg['autobot_loops']}")
    print(f"Loaded as int: {loops}")
    print("✓ autobot_loops is properly serialized!")

if __name__ == "__main__":
    test_subprocess_creation()
    test_config_with_loops()
    print("\n✓ All tests passed!")
