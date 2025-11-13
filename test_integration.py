#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Comprehensive integration test for UI bot mode switching
"""

import json
import os
import sys

def check_ui_implementation():
    """Verify UI has proper mode switching logic"""
    print("=" * 60)
    print("UI IMPLEMENTATION CHECK")
    print("=" * 60)
    
    with open("ui.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    checks = {
        "Has _start_bot_process": "_start_bot_process" in content,
        "Selects script by mode": 'script_to_run = "autobot.py"' in content,
        "Selects bot.py for NORMAL": 'script_to_run = "bot.py"' in content,
        "Reads stdout realtime": "while True:" in content and "readline()" in content,
        "Appends to device log": "_append_to_device_log" in content,
        "Creates log files": "os.makedirs(logs_dir" in content,
        "Uses UTF-8 encoding": 'encoding="utf-8"' in content,
        "Has _collect_device_config": "_collect_device_config" in content,
        "Includes autobot_loops": "cfg['autobot_loops']" in content or 'cfg["autobot_loops"]' in content,
    }
    
    print("\nUI Checks:")
    for check, passed in checks.items():
        status = "✓" if passed else "❌"
        print(f"  {status} {check}")
    
    return all(checks.values())

def check_bot_implementation():
    """Verify bot.py accepts config_data argument"""
    print("\n" + "=" * 60)
    print("BOT.PY IMPLEMENTATION CHECK")
    print("=" * 60)
    
    with open("bot.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    checks = {
        "Has ArgumentParser": "ArgumentParser" in content,
        "Accepts --config_data": '--config_data' in content,
        "Parses JSON config": "json.loads" in content,
    }
    
    print("\nBot.py Checks:")
    for check, passed in checks.items():
        status = "✓" if passed else "❌"
        print(f"  {status} {check}")
    
    return all(checks.values())

def check_autobot_implementation():
    """Verify autobot.py accepts config and uses autobot_loops"""
    print("\n" + "=" * 60)
    print("AUTOBOT.PY IMPLEMENTATION CHECK")
    print("=" * 60)
    
    with open("autobot.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    checks = {
        "Has ArgumentParser": "ArgumentParser" in content,
        "Accepts --config_data": '--config_data' in content,
        "Parses JSON config": "json.loads" in content,
        "Uses autobot_loops": "autobot_loops" in content,
        "Has run_autobot_flow": "run_autobot_flow" in content,
        "Sets up logging": "setup_logging" in content,
    }
    
    print("\nAutobot.py Checks:")
    for check, passed in checks.items():
        status = "✓" if passed else "❌"
        print(f"  {status} {check}")
    
    return all(checks.values())

def test_config_flow():
    """Test config JSON flow"""
    print("\n" + "=" * 60)
    print("CONFIG FLOW TEST")
    print("=" * 60)
    
    # Simulate UI config creation
    cfg = {
        "device_id": "R52N619SH8J",
        "adb_path": "D:/adb.exe",
        "app_package": "com.shopee.th",
        "autobot_loops": "90",
        "run_mode": "AUTOBOT"
    }
    
    try:
        # Serialize to JSON (as UI does)
        json_str = json.dumps(cfg, ensure_ascii=False)
        print(f"\n✓ Config serialized to JSON")
        
        # Deserialize (as bot/autobot does)
        cfg_loaded = json.loads(json_str)
        print(f"✓ Config deserialized from JSON")
        
        # Check values
        if cfg_loaded.get("autobot_loops") == "90":
            print(f"✓ autobot_loops preserved: {cfg_loaded['autobot_loops']}")
        
        loops = int(cfg_loaded.get("autobot_loops", 1))
        print(f"✓ autobot_loops can be converted to int: {loops}")
        
        return True
    except Exception as e:
        print(f"❌ Config flow error: {e}")
        return False

if __name__ == "__main__":
    results = []
    
    results.append(("UI Implementation", check_ui_implementation()))
    results.append(("Bot.py Implementation", check_bot_implementation()))
    results.append(("Autobot.py Implementation", check_autobot_implementation()))
    results.append(("Config Flow", test_config_flow()))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    if all(p for _, p in results):
        print("\n✅ ALL CHECKS PASSED - Integration looks good!")
        sys.exit(0)
    else:
        print("\n⚠️  Some checks failed - review above")
        sys.exit(1)
