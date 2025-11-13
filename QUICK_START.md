# 📖 UI.PY - Quick Start Guide

## 🎯 Mode Selection & Running

### NORMAL Mode (bot.py)
- **ใช้สำหรับ:** Single device posting
- **Button:** "รัน ▶" (Run Single) หรือ "รัน All" (Run All)
- **Script:** `bot.py`
- **Output:** Logs display realtime in device console & global log

```
Steps:
1. Select device(s) via checkbox
2. Click "รัน ▶" or "รัน All"
3. Watch logs in console tab
4. Logs saved to: logs/{date}/{device_id}_NORMAL_{timestamp}.log
```

### AUTOBOT Mode (autobot.py)
- **ใช้สำหรับ:** Automated flow with configurable loops
- **Button:** "Autobot ▶" (Single) หรือ "Autobot All"
- **Script:** `autobot.py`
- **Loops:** Set via "จำนวน Loop" field (default: 90)
- **Output:** Logs display realtime + file saved

```
Steps:
1. Select device(s) via checkbox
2. Set "จำนวน Loop" value (e.g., 90)
3. Click "Autobot ▶" or "Autobot All"
4. Watch logs in console tab
5. Logs saved to: logs/{date}/{device_id}_AUTOBOT_{timestamp}.log
```

---

## 🔧 Configuration Flow

### How Config Gets to Bot/Autobot:

```
UI Variable (e.g., var_autobot_loops)
  ↓
_collect_device_config() reads all variables
  ↓
Creates dict {device_id, autobot_loops, ...}
  ↓
Serializes to JSON string
  ↓
Passes as --config_data to subprocess
  ↓
bot.py / autobot.py parses JSON
  ↓
Uses config values for operation
```

---

## 📊 Log File Locations

### Log Directory Structure:
```
logs/
├── 2025-11-13/
│   ├── R52N619SH8J_NORMAL_140230.log
│   ├── R52N619SH8J_AUTOBOT_140245.log
│   └── ...
├── 2025-11-14/
│   ├── R52N619SH8J_NORMAL_090000.log
│   └── ...
```

### File Format:
- **Name:** `{device_id}_{MODE}_{timestamp}.log`
- **Encoding:** UTF-8
- **Content:** Realtime output from bot/autobot

### View Logs:
- **In UI:** Console tab displays realtime
- **On Disk:** `logs/{date}/{filename}.log`

---

## 🎮 Control Buttons

### Per-Device Controls:
- **🟢 ▶ Run** - Start normal mode
- **🟠 Autobot** - Start autobot mode
- **⏸ Pause** - Pause (creates flags/{device}.pause)
- **⏯ Resume** - Resume from pause
- **⛔ Stop** - Stop (creates flags/{device}.stop)

### Signals via Flag Files:
```
flags/
├── R52N619SH8J.pause    # Created when pause button clicked
├── R52N619SH8J.stop     # Created when stop button clicked
└── ...
```

Bot/Autobot check these flags and respond appropriately.

---

## ✅ Troubleshooting

### Issue: Logs not appearing in UI
**Solution:**
1. Check if device_log_widgets is initialized for that device
2. Verify console tab is visible
3. Check terminal for any startup errors

### Issue: autobot_loops not being used
**Solution:**
1. Verify "จำนวน Loop" field has a value
2. Check AUTOBOT mode is selected (not NORMAL)
3. Check ui.py has `cfg['autobot_loops'] = self.var_autobot_loops.get()`

### Issue: Log file not created
**Solution:**
1. Verify `logs/` directory is writable
2. Check file permissions
3. Verify UTF-8 encoding support

### Issue: Subprocess doesn't start
**Solution:**
1. Verify bot.py/autobot.py exist in workspace
2. Check Python environment is set up
3. Review console for error messages

---

## 🔍 Code Reference

### Key Functions:
- `_run_bot_wrapper()` - Dispatcher for NORMAL/AUTOBOT
- `_start_bot_process()` - Actual subprocess runner with realtime logging
- `_collect_device_config()` - Config builder (includes autobot_loops)
- `_append_to_device_log()` - Thread-safe log display

### Key Variables:
- `self.var_autobot_loops` - Number of autobot loops
- `self.device_log_widgets` - Per-device console widgets
- `self.global_log_text` - Global log display
- `self.device_states` - Device status tracking

---

## 📝 Example Config Flow

```python
# In UI:
self.var_autobot_loops = tk.StringVar(value="90")

# When user clicks "Autobot ▶":
cfg = self._collect_device_config(serial)
# cfg now contains: {..., "autobot_loops": "90", ...}

# Serialize to JSON:
config_data = json.dumps(cfg, ensure_ascii=False)
# Result: '{"device_id": "...", "autobot_loops": "90", ...}'

# Pass to subprocess:
cmd = ["python", "autobot.py", "--config_data", config_data]
subprocess.Popen(cmd, ...)

# In autobot.py:
cfg_data = json.loads(args.config_data)
total_loops = int(cfg_data.get("autobot_loops", 1))
# Now can use total_loops in run_autobot_flow()
```

---

## 🚀 Best Practices

1. **Always check logs** - UI console shows realtime output
2. **Use appropriate mode** - NORMAL for single posts, AUTOBOT for flows
3. **Monitor progress** - Check device state indicators
4. **Save logs** - Logs auto-saved to disk for troubleshooting
5. **Use pause/resume** - For safe device interaction without stopping
