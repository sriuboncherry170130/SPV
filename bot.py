from __future__ import annotations
# (วางไว้บนๆ ใกล้ๆ import)
class PostLimitException(Exception):
    """Exception เพื่อสั่งหยุดบอทเมื่อถึงขีดจำกัดการโพสต์"""
    pass


# ---------------- helpers (patch: adb/u2) ----------------
def resolve_adb_path(adb_path: str) -> str:
    """
    พยายามหา adb.exe อัตโนมัติเมื่อ path ที่รับมาไม่ถูกต้อง/ว่าง:
    - ใช้ค่าเดิมถ้ามีและไฟล์มีจริง
    - มองหาในโฟลเดอร์ยอดนิยม
    - มองหาใน ANDROID_HOME / ANDROID_SDK_ROOT
    - มองหาใน PATH
    คืน path ที่ใช้ได้ หรือ string ว่างหากไม่พบ
    """
    import shutil, os
    def is_ok(p):
        return bool(p) and os.path.isfile(p)

    # 1) ใช้ค่าเดิมถ้าโอเค
    if is_ok(adb_path):
        return adb_path

    # 2) โฟลเดอร์ยอดนิยม
    common = [
        r"D:\Shopee\usb_driver\adb.exe",
        r"C:\Android\platform-tools\adb.exe",
        r"C:\Users\%USERNAME%\AppData\Local\Android\Sdk\platform-tools\adb.exe",
        r"C:\platform-tools\adb.exe",
    ]
    for p in common:
        p2 = os.path.expandvars(p)
        if is_ok(p2):
            return p2

    # 3) จาก ANDROID_HOME / ANDROID_SDK_ROOT
    for envvar in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        root = os.environ.get(envvar, "")
        if root:
            cand = os.path.join(root, "platform-tools", "adb.exe")
            if is_ok(cand):
                return cand

    # 4) หาใน PATH
    found = shutil.which("adb.exe") or shutil.which("adb")
    if is_ok(found):
        return found

    return ""


def setup_u2_input_ime(d):
    """ตั้งค่า IME แบบสั้น กระชับ ไม่เรียกย้อนกลับไป safe_setup_u2_settings"""
    try:
        if hasattr(d, "set_input_ime"):
            d.set_input_ime(True)
            return True
    except Exception:
        pass
    try:
        if hasattr(d, "set_fastinput_ime"):
            d.set_fastinput_ime(True)
            return True
    except Exception:
        pass
    return False


def safe_setup_u2_settings(d):
    """ตั้งค่า settings ขั้นพื้นฐาน โดยไม่เรียกกลับไป setup_u2_input_ime"""
    try:
        _ = d.window_size()
    except Exception:
        return False
    try:
        s = getattr(d, "settings", None)
        if s and hasattr(s, "set"):
            # ลด delay ให้เร็วขึ้น แต่ยังไม่ aggressive เกินไป
            s.set("operation_delay", 0.01)
            s.set("operation_delay_methods", ["click", "swipe"])
    except Exception:
        pass
    return True


# ---------------- end helpers ----------------

import time
from pathlib import Path

# (สร้าง Exception นี้ไว้บนสุดของไฟล์)
class StopRequestedException(Exception):
    pass

# (สร้างฟังก์ชันตัวเช็กนี้)
def check_bot_signals(device_id: str):
    """
    ฟังก์ชันที่ "หัวใจหลัก" ของบอทต้องเรียกใช้
    """
    stop_flag = Path("flags") / f"{device_id}.stop"
    pause_flag = Path("flags") / f"{device_id}.pause"

    # 1. เช็ก "หยุดถาวร" (สำคัญที่สุด)
    if stop_flag.exists():
        log("WARNING", f"[{device_id}] ตรวจพบ .stop flag! ยุติการทำงาน...")
        try: stop_flag.unlink() # (ลบ)
        except: pass
        raise StopRequestedException(f"UI สั่งหยุด {device_id}")

    # 2. เช็ก "หยุดชั่วคราว"
    if pause_flag.exists():
        log("INFO", f"[{device_id}] Paused! (พบ .pause flag) กำลังรอ...")
        # (วนลูป "รอ" จนกว่าไฟล์ .pause จะหายไป)
        while pause_flag.exists():
            time.sleep(2) # (รอ 2 วิ แล้วเช็กใหม่)
            
            # (ต้องเช็ก stop flag ซ้ำในนี้ด้วย เผื่อผู้ใช้กด Stop ตอน Pause)
            if stop_flag.exists():
                log("WARNING", f"[{device_id}] ตรวจพบ .stop flag (ขณะ Pause)!")
                try: stop_flag.unlink()
                except: pass
                raise StopRequestedException(f"UI สั่งหยุด {device_id}")
        
        log("INFO", f"[{device_id}] Resumed! (.pause flag หายไป) ทำงานต่อ...")

# ---------------- post-upload verification helper ----------------
def _post_upload_verification(d, device_id: str, timeout_sec: int = 30) -> bool:
    """
    รอข้อความยืนยันหลังโพสต์สำเร็จ เช่น 'อัปโหลดสำเร็จ' ภายใน timeout_sec วินาที
    ถ้าเจอแล้วคืนค่า True, ถ้าเจอข้อความล้มเหลว/ผิดพลาดให้ False, ถ้าหมดเวลาให้ False
    """
    try:
        ok_texts = ["อัปโหลดสำเร็จ", "เผยแพร่แล้ว", "โพสต์เสร็จ", "Published", "Upload complete"]
        bad_texts = ["อัปโหลดไม่สำเร็จ", "โพสต์ไม่สำเร็จ", "ล้มเหลว", "ไม่สามารถ", "ข้อผิดพลาด", "Failed", "Error"]
        prog_texts = ["กำลังอัปโหลด", "กำลังโพสต์", "Uploading", "กำลังเผยแพร่"]

        start = time.time()
        while (time.time() - start) < max(3, int(timeout_sec)):
            if any(d(textContains=t).exists for t in ok_texts):
                log("INFO", "ตรวจพบข้อความยืนยันอัปโหลดสำเร็จ")
                return True
            if any(d(textContains=t).exists for t in bad_texts):
                log("WARN", "ตรวจพบข้อความล้มเหลวในการอัปโหลด")
                return False
            if any(d(textContains=t).exists for t in prog_texts):
                sleep_s(1.0)
                continue
            sleep_s(1.0)
        log("WARN", "ไม่พบข้อความยืนยันอัปโหลดสำเร็จภายในเวลาที่กำหนด")
        return False
    except Exception as e:
        log("WARN", f"post-upload verification exception: {e}")
        return False


def _normalize_steps_to_dict(raw_steps):
    """แปลง steps ที่เป็น list/dict ให้เป็น dict เสมอ เพื่อให้ logic เดิมใช้งานได้"""
    import re
    if isinstance(raw_steps, dict):
        return raw_steps
    out = {}
    if not isinstance(raw_steps, list):
        return out

    def slug(s: str) -> str:
        s = (s or "").strip()
        s = re.sub(r"\s+", "_", s)
        return s or "step"

    for i, s in enumerate(raw_steps, 1):
        if not isinstance(s, dict):
            continue
        key = s.get("name") or s.get("key")
        if not key:
            if isinstance(s.get("id"), int):
                key = f"step_{s['id']:02d}"
            elif s.get("label"):
                key = slug(s["label"])
            else:
                key = f"step_{i:02d}"
        # ใช้ ID จาก YAML เป็น Key หลัก
        if s.get("id"):
            key = str(s["id"])
        out[str(key)] = s
    return out


# -*- coding: utf-8 -*-
"""
# Shopee Video Bot — รองรับ TapEngine (AUTO/ADB/U2) + ADB connect (USB/Wi-Fi)

# อัปเดตครั้งนี้ (เฉพาะส่วนที่เกี่ยวกับปัญหา):
# - **FINAL FIX**: แก้ไข NameError (cfg) ใน _ensure_channels_alive โดยการส่ง cfg เข้าไป
# - **FIXED**: แก้ไข Tap XY ไม่ทำงาน: เพิ่มการเรียกใช้ฟังก์ชัน do_tap() ใน process_posts
# - **FIXED**: แก้ไข NameError (step_data) โดยการจัด Indentation ใน process_posts
# - **FIXED**: แก้ไข NameError (cfg) และ Indentation Error ใน tap_key_flow
# - **CRITICAL FIX**: เพิ่ม Logic บังคับป้อนข้อความโดยตรง (d.send_keys) หลัง Tap XY สำหรับขั้นตอน Caption/Link ที่ขาด block 'keys'
# - **CONFIG FIX**: แก้ไข default ของ delay_between_posts จาก 300 เป็น 30 และบังคับแปลงเป็น float
# - **CRITICAL IndentationError FIX**: แก้ไขการเยื้องบรรทัดที่ 436 ใน _ensure_channels_alive
# - **NEW FEATURE**: เพิ่มการรีสตาร์ทแอป (เคลียร์ RAM) ทุก 10 โพสต์ที่สำเร็จ
"""

import sys, os, csv, time, shlex, subprocess, argparse, pathlib, random, re, json, traceback
from datetime import datetime

# 1. ประกาศ global counters
global successful_posts
global failed_posts
global skipped_retry
global skipped_missing


# --- Global counters (auto-inserted) ---
# Ensure these are defined early so process_posts and summary printing can use them.
# --- Global counters (ensure defined early) ---
try:
    successful_posts
except Exception:
    successful_posts = 0
try:
    failed_posts
except Exception:
    failed_posts = 0
try:
    skipped_retry
except Exception:
    skipped_retry = 0
try:
    skipped_missing
except Exception:
    skipped_missing = 0
# ------------------------------------------------

# --- end global counters ---
# ------------------------------------------------------------
# TapEngineState helper + normalize helper
# (วางไว้ต้นไฟล์ หลัง imports)
# ------------------------------------------------------------
# TapEngineState helper + normalize helper
# (วางไว้ต้นไฟล์ หลัง imports)
# ------------------------------------------------------------
class TapEngineState:
    """
    Container for tap mode state.
    Fields:
      - mode: 'u2'|'adb'|'auto'
      - use_adb_this_round: bool
      - last_tap_xy: last coords or None
    """
    def __init__(self, mode: str = "u2"):
        self.mode = (mode or "u2").lower()
        self.use_adb_this_round = False
        self.last_tap_xy = None

def normalize_tap_state(ts, default_mode: str = "u2"):
    """
    Ensure returned object is TapEngineState.
    Accepts:
      - None -> new instance
      - TapEngineState -> returned as is
      - dict -> convert to instance (legacy)
    """
    if ts is None:
        return TapEngineState(default_mode)
    if isinstance(ts, TapEngineState):
        return ts
    try:
        if isinstance(ts, dict):
            mode = ts.get("mode", default_mode)
            obj = TapEngineState(mode=mode)
            if "use_adb_this_round" in ts:
                obj.use_adb_this_round = bool(ts.get("use_adb_this_round"))
            if "last_tap_xy" in ts:
                obj.last_tap_xy = ts.get("last_tap_xy")
            return obj
    except Exception:
        pass
    return TapEngineState(default_mode)

# ------------------------------------------------------------

# ------------------------------------------------------------

# ------------------------------------------------------------


# ---------- logging (timestamp + device prefix) ----------
from datetime import datetime as __dt__
def now() -> str:
    return __dt__.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

# safe CP874-friendly logging used by the bot
def log(level: str, msg: str):
    try:
        prefix = globals().get('_DEV_PREFIX', '')
        out = f"{now()} {prefix}{level:<7} | {msg}"
        # On Windows try to use buffer write to avoid encoding issues
        if os.name == 'nt' and hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write((out + "\n").encode('utf-8', errors='replace'))
            sys.stdout.flush()
            return
    except Exception:
        pass
    print(f"{now()} {prefix}{level:<7} | {msg}", flush=True)

# ---------- end logging ----------

# ------------- fast media global flag -------------
FAST_MEDIA_INDEX = globals().get('FAST_MEDIA_INDEX', False)


def ensure_media_indexed_select(
        adb_path: str,
        device_id: str,
        device_video_dir: str,
        filename: str,
        fast: bool = None
) -> str:
    """
    สแกนสั้น-ยาว เลือกตามแฟล็ก fast:
      - fast=True  -> SCAN_FILE แล้วรอแค่ ~2.5s
      - fast=False -> SCAN_FILE แล้วรอ ~5.0s (ชัวร์ขึ้นเล็กน้อย)
    ไม่ทำ SCAN_DIR / mv / cp (ตัดออกเพื่อความเร็ว/ลด error)
    คืนค่า dev_src (path บนอุปกรณ์) เพื่อใช้ต่อ
    """
    try:
        import urllib.parse
    except Exception:
        pass

    if fast is None:
        # ถ้ามี global/จาก UI จะมาเป็น FAST_MEDIA_INDEX
        fast = bool(globals().get("FAST_MEDIA_INDEX", True))

    dev_src = f"{device_video_dir.rstrip('/')}/{filename}"
    uri = "file://" + urllib.parse.quote(dev_src, safe="/:")

    # ยิง SCAN_FILE อย่างเดียว (เร็วสุดและพอสำหรับ Gallery ส่วนใหญ่)
    adb_shell(adb_path, device_id,
              f"am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d {uri}")

    # รอให้ MediaScanner ลงทะเบียน (สั้นลงเมื่อ fast)
    sleep_s(2.5 if fast else 5.0,
            "หลัง push/scan (FAST)" if fast else "หลัง push/scan")

    return dev_src


import urllib.parse  # encode path เป็น URI ให้ MEDIA_SCANNER
import yaml
import uiautomator2 as u2
from uiautomator2 import UiAutomationError
from tkinter import messagebox, Tk

# Global counter สำหรับสถานะการเชื่อมต่อ
global CONNECTION_FAILURE_COUNT
CONNECTION_FAILURE_COUNT = 0
MAX_CONNECTION_FAILURES = 5  # จำนวนครั้งสูงสุดที่ยอมให้ขาดการเชื่อมต่อก่อนยกเลิกงาน


import sys
import os
from datetime import datetime

_DEV_PREFIX = ""  # จะถูกเซ็ตใน main() หลังรู้ device_id

def now_ms() -> str:
    """เวลาพร้อม ms สำหรับใช้ใน log"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def log(level: str, msg: str):
    """
    Logger กลางตัวเดียว:
    - มี timestamp
    - มี prefix ตาม device_id (ถ้าเซ็ตแล้ว)
    - ไม่เล่นสี เพื่อให้ UI/ไฟล์ log อ่านง่าย
    """
    prefix = _DEV_PREFIX  # เช่น [R52N619SH8J] หรือ "" ถ้ายังไม่เซ็ต
    line = f"{now_ms()} {prefix}{level}: {msg}"
    try:
        # เขียนลง stdout ปกติ บอท UI จะอ่านจากตรงนี้
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
    except Exception:
        # fallback กัน console เพี้ยน
        print(line, flush=True)



# ------------------------------------


def _cleanup_pause_flag():
    """ล้างไฟล์ pause_flag ถ้ายังค้างอยู่"""
    try:
        _cfg = globals().get("CFG") or {}
        _p = _cfg.get("pause_flag")
        if _p and os.path.exists(_p):
            os.remove(_p)
            log("INFO", "ลบ pause flag แล้ว")
    except Exception:
        pass


def fatal(msg: str, device_id: str = ""):
    print(f"[{device_id}] CRITICAL: {msg}", flush=True)
    log("CRITICAL", msg)
    sys.exit(1)


# ---------- helpers ----------
import time
from pathlib import Path

# ... (existing imports)

def sleep_s_responsive(seconds: float, device_id: str = None, poll_interval: float = 0.2):
    """
    Sleep ที่ตอบสนองต่อ .pause และ .stop flags.
    - device_id: ถ้าระบุ จะตรวจ flags/{device_id}.pause และเรียก check_bot_signals(device_id) เพื่อเช็ก .stop
    - poll_interval: ช่วงเวลาตรวจเป็นวินาที (ค่าต่ำเพื่อ responsiveness)
    """
    start = time.time()
    flags_dir = Path("flags")
    while True:
        elapsed = time.time() - start
        if elapsed >= seconds:
            break

        # ถ้ามี device_id ให้เช็ก stop flag ผ่าน check_bot_signals (ฟังก์ชันนี้มีใน bot.py ของคุณ)
        if device_id is not None:
            try:
                # check_bot_signals ควร raise StopRequestedException เมื่อพบ stop
                check_bot_signals(device_id)
            except Exception:
                # ถ้า StopRequestedException -> bubble up
                raise

            # ถ้าพบ pause flag ให้รอจนกว่าจะถูกลบ แต่ยังคงเช็ก stop ทุก poll_interval
            pause_file = flags_dir / f"{device_id}.pause"
            if pause_file.exists():
                # รอจนไฟล์หาย
                while pause_file.exists():
                    # จะ raise StopRequestedException ถ้ามี stop
                    check_bot_signals(device_id)
                    time.sleep(poll_interval)
                # after pause removed, continue counting remaining time
                start = time.time() - elapsed  # preserve elapsed so total sleep ~ seconds
                # continue loop
                continue

        # ถ้าไม่มี device_id หรือไม่อยู่ใน pause ให้นอนสั้น ๆ
        time.sleep(min(poll_interval, seconds - elapsed))

# (วางทับฟังก์ชัน sleep_s เดิมใน bot.py)

def sleep_s(s: float, reason: str = ""):
    """
    (ฟังก์ชัน "sleep" ที่ "แก้ไขแล้ว" v2)
    ฟังก์ชันหน่วงเวลาที่ "ตอบสนอง" ต่อ .stop/.pause flag
    จะหน่วงเวลาทีละ 1 วินาที และคอยเช็กสัญญาณ
    """
    global CFG
    # (เราต้องการ device_id เพื่อส่งให้ตัวเช็ก)
    try:
        device_id = CFG.get('device_id', '') 
    except Exception:
        device_id = "" # (ถ้า CFG ยังไม่ถูกสร้าง ก็ไม่เป็นไร)
        
    if reason:
        log("DEBUG", f"หน่วง {s:.2f}s ({reason})")
    else:
        log("DEBUG", f"หน่วง {s:.2f}s")

    start_time = time.time()
    while (time.time() - start_time) < s:
        # --- [นี่คือหัวใจของ Pause/Resume] ---
        # (เช็กสัญญาณทุก 0.5 - 1 วินาที)
        check_bot_signals(device_id) 
        # --- [จบส่วนหัวใจ] ---
        
        # (นอนหลับทีละน้อย)
        time_left = s - (time.time() - start_time)
        sleep_chunk = min(1.0, time_left) # (หลับทีละ 1 วิ หรือน้อยกว่า)
        if sleep_chunk > 0:
            time.sleep(sleep_chunk)
        else:
            break # (เผื่อเวลาเป็น 0)
        
    # (เมื่อครบเวลา ก็เช็กอีกรอบก่อนออก)
    check_bot_signals(device_id)


def adb_shell(adb_path: str, device_id: str, cmd: str) -> bool:
    if not adb_path or not device_id:
        log("ERROR", "ADB Path หรือ Device ID ว่าง")
        return False
    # ใช้ shlex.split ในการแยกคำสั่ง เพื่อรองรับ path ที่มี space
    cmd_full = shlex.split(f'"{adb_path}" -s {device_id} shell {cmd}')
    try:
        subprocess.run(cmd_full, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("INFO", f"ADB: {cmd}")
        return True
    except subprocess.CalledProcessError as e:
        log("ERROR", f"ADB ล้มเหลว: {e}")
        return False


def ensure_media_indexed(adb_path: str, device_id: str, device_video_dir: str, filename: str) -> str:
    try:
        import urllib.parse  # เผื่อไฟล์นี้ยังไม่ได้ import ด้านบน
    except Exception:
        pass

    dev_src = f"{device_video_dir}/{filename}"
    uri = "file://" + urllib.parse.quote(dev_src, safe="/:")
    # ยิงสแกนไฟล์แบบเร็วที่สุด
    adb_shell(adb_path, device_id, f"am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d {uri}")
    # รอไม่นาน (แค่ให้ MediaScanner ลงทะเบียน)
    sleep_s(2.5 if FAST_MEDIA_INDEX else 5.0, "หลัง push/scan (FAST)" if FAST_MEDIA_INDEX else "หลัง push/scan")
    return dev_src


def ensure_media_visible(adb_path: str, device_id: str, device_video_dir: str, filename: str):
    """
    สแกนไฟล์วิดีโอเข้าคลังภาพแบบเร็ว:
    - ใช้ SCAN_FILE เสมอ (เร็วสุดและเสถียร)
    - โหมดเร็ว (FAST_MEDIA_INDEX=True): sleep ~2.5s
      โหมดปกติ: sleep ~5.0s
    """
    try:
        import urllib.parse
    except Exception:
        pass

    dev_src = f"{device_video_dir}/{filename}"
    uri = "file://" + urllib.parse.quote(dev_src, safe="/:")
    # ยิงสแกนไฟล์แบบเร็ว
    adb_shell(adb_path, device_id, f"am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d {uri}")
    # หน่วงสั้นลงหากเป็นโหมดเร็ว
    try:
        wait_s = 2.5 if FAST_MEDIA_INDEX else 5.0
    except NameError:
        wait_s = 5.0
    sleep_s(wait_s, "หลัง push/scan (FAST)" if wait_s < 3 else "หลัง push/scan")
    return dev_src


def adb_shell(adb_path: str, device_id: str, cmd: str) -> bool:
    if not adb_path or not device_id:
        log("ERROR", "ADB Path หรือ Device ID ว่าง")
        return False
    # ใช้ shlex.split ในการแยกคำสั่ง เพื่อรองรับ path ที่มี space
    cmd_full = shlex.split(f'"{adb_path}" -s {device_id} shell {cmd}')
    try:
        subprocess.run(cmd_full, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("INFO", f"ADB: {cmd}")
        return True
    except subprocess.CalledProcessError as e:
        log("ERROR", f"ADB ล้มเหลว: {e}")
        return False


# ---------- ADB helpers: safe, no global kill for single-run ----------
import shlex, subprocess, time, re


def _run(adb_path, args, timeout=10, capture=True):
    cmd = shlex.split(f'"{adb_path}" ' + args)
    return subprocess.run(
        cmd,
        timeout=timeout,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace"
    )


def _adb_get_state(adb_path: str, serial: str) -> str:
    try:
        out = _run(adb_path, f"-s {serial} get-state", timeout=6)
        state = (out.stdout or out.stderr or "").strip()
        return state
    except Exception:
        return ""


def _wait_device_state(adb_path: str, serial: str, want="device", total_wait_s=30, step_s=1.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < total_wait_s:
        st = _adb_get_state(adb_path, serial)
        if st == want:
            return True
        time.sleep(step_s)
    return False


def ensure_adb_connection(adb_path: str, device_id: str, conn_mode: str, allow_server_restart: bool = False) -> bool:
    """
    ปรับใหม่: โหมดรันเฉพาะเครื่อง (allow_server_restart=False) จะไม่ kill-server
    - ตรวจเวอร์ชัน (log เฉยๆ)
    - ถ้าเชื่อมต่อ Wi-Fi: ใช้ 'adb connect'
    - รอให้ get-state -> device ภายใน 30s
    - ใช้ 'start-server' ได้ แต่ไม่ทำลาย server เดิม
    """
    if not adb_path or not device_id:
        log("CRITICAL", f"ADB path/device ว่าง: adb={adb_path} device={device_id}")
        return False

    # 1) version (log เฉยๆ)
    try:
        ver = _run(adb_path, "version", timeout=6)
        ver_text = (ver.stdout or ver.stderr or "").strip()
        log("INFO", f"ADB version: {ver_text}")
    except Exception as e:
        log("WARN", f"ตรวจเวอร์ชัน ADB ไม่สำเร็จ: {e}")

    # 2) start-server แบบไม่ทำลายการเชื่อมต่อเดิม
    try:
        _run(adb_path, "start-server", timeout=6, capture=False)
    except Exception as e:
        log("WARN", f"start-server ไม่สำเร็จ: {e}")

    # 3) Wi-Fi connect (ถ้ากำหนด)
    mode = (conn_mode or "usb").lower()
    if mode == "wifi" and ":" in device_id:
        try:
            out = _run(adb_path, f"connect {device_id}", timeout=8)
            msg = (out.stdout or out.stderr or "").strip()
            log("INFO", f"ADB connect {device_id}: {msg}")
        except Exception as e:
            log("WARN", f"ADB connect exception: {e}")

    # 4) รอ state=device แบบเจาะจง serial
    ok = _wait_device_state(adb_path, device_id, want="device", total_wait_s=30, step_s=1.0)
    if ok:
        log("INFO", f"ADB state OK: {device_id} -> device")
        return True

    # 5) กรณีไม่ขึ้น device: debug devices -l
    try:
        dl = _run(adb_path, "devices -l", timeout=8)
        raw = (dl.stdout or dl.stderr or "").strip()
        log("ERROR", "adb devices -l (raw):\n" + raw)
    except Exception:
        pass

    # 6) สุดท้าย (อนุญาตจริงๆ เท่านั้น) — อาจทำให้ทุกดีไวซ์หลุด
    if allow_server_restart:
        log("WARN", "ลอง restart server (อนุญาต) → อาจทำให้ทุกดีไวซ์หลุด")
        try:
            _run(adb_path, "kill-server", timeout=6, capture=False)
            time.sleep(0.6)
            _run(adb_path, "start-server", timeout=8, capture=False)
        except Exception as e:
            log("WARN", f"restart server exception: {e}")
            ok2 = _wait_device_state(adb_path, device_id, want="device", total_wait_s=20, step_s=1.0)
        if ok2:
            log("INFO", f"ADB state OK (หลัง restart): {device_id} -> device")
            return True

    return False


def ensure_app_foreground(adb_path: str, serial: str, pkg: str, wait_s: float = 8.0) -> bool:
    """เรียก monkey เปิด pkg แล้วรอจน dumpsys โชว์เป็น mResumedActivity ของ pkg"""
    try:
        subprocess.run(
            shlex.split(f'"{adb_path}" -s {serial} shell monkey -p {pkg} -c android.intent.category.LAUNCHER 1'),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        return False
    pat = re.compile(r"mResumedActivity.*" + re.escape(pkg))
    t0 = time.time()
    while time.time() - t0 < wait_s:
        try:
            out = subprocess.run(
                shlex.split(f'"{adb_path}" -s {serial} shell dumpsys activity activities'),
                capture_output=True, text=True, timeout=4
            )
            if pat.search(out.stdout or ""):
                return True
        except Exception:
            pass
        sleep_s_responsive(0.4)
    return False


def send_text_or_abort(d: u2.Device, text: str, abort_on_fail: bool = False):
    """ฟังก์ชัน helper สำหรับป้อนข้อความโดยตรง"""
    short = text[:60] + ("..." if len(text) > 60 else "")
    log("INFO", f"พิมพ์: {short}")
    try:
        d.send_keys(text)
    except AttributeError:
        log("WARN", "send_keys ใช้ไม่ได้ -> set_text")
        d.set_text(text)
    except Exception as e:
        if abort_on_fail:
            raise
        log("ERROR", f"ส่งข้อความล้มเหลว: {e}")
    sleep_s(1, "หลังพิมพ์")


def check_app_is_running(d: u2.Device, package_name: str) -> bool:
    try:
        cur = d.app_current().get("package")
        return cur == package_name
    except Exception:
        return True  # เช็คไม่ได้ ไม่หยุดงาน


def restart_app(d: u2.Device, package_name: str):
    log("WARN", f"รีสตาร์ทแอป: {package_name}")
    try:
        d.app_stop(package_name)
        sleep_s(1.5)
        d.app_start(package_name)
        sleep_s(4.5)
        log("INFO", "รีสตาร์ทสำเร็จ")
    except Exception as e:
        log("ERROR", f"รีสตาร์ทล้มเหลว: {e}")


def ensure_media_indexed_fast(adb_path: str, device_id: str, device_video_dir: str, filename: str) -> str:
    """

def ensure_media_indexed_select(adb_path: str, device_id: str, device_video_dir: str, filename: str, fast: bool = True) -> str:
    """
    #     เลือกใช้ fast/slow ตามสวิตช์ fast_media_index
    """
    if fast:
        return ensure_media_indexed_fast(adb_path, device_id, device_video_dir, filename)
    return ensure_media_indexed_slow(adb_path, device_id, device_video_dir, filename)


#     FAST: สแกนไฟล์ให้โผล่แกลเลอรี่แบบไว
#     - ส่ง SCAN_FILE 1 ครั้ง
#     - รอ 1.2s (รวม jitter ภายใน)
#     - ส่ง SCAN_DIR 1 ครั้ง รอ 0.4s เพื่อ nudge บางรุ่น
#     ไม่มีลูปตรวจซ้ำ ไม่ย้าย/ก็อป/เปลี่ยนชื่อไฟล์
    """
    import urllib.parse, time, os, shlex, subprocess
    dev_src = f"{device_video_dir}/{filename}"
    file_uri = "file://" + urllib.parse.quote(dev_src, safe="/:")
    # SCAN_FILE (เร็วสุด)
    subprocess.run(shlex.split(
        f'"{adb_path}" -s {device_id} shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d {file_uri}'),
                   timeout=6, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # รอสั้น ๆ ให้ MediaProvider ทำงาน
    sleep_s_responsive(1.2)
    # เสริม: SCAN_DIR (nudge เร็ว)
    dir_uri = "file://" + urllib.parse.quote(device_video_dir.rstrip("/"), safe="/:")
    subprocess.run(shlex.split(
        f'"{adb_path}" -s {device_id} shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_DIR -d {dir_uri}'),
                   timeout=6, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sleep_s_responsive(0.4)
    return dev_src


############################
#  MEDIA SCAN – ENHANCED  #
############################

def _content_query_has_video(adb_path: str, device_id: str, dev_src: str) -> bool:
    """ตรวจว่าไฟล์ dev_src ถูก index ลง MediaStore แล้วหรือยัง (เทียบด้วยชื่อไฟล์)"""
    import shlex, subprocess, os
    fname = os.path.basename(dev_src)
    like = f"'%/{fname}'"
    cmd = (f'content query --uri content://media/external/video/media '
           f'--projection _data --where "_data LIKE {like}"')
    try:
        out = subprocess.run(
            shlex.split(f'"{adb_path}" -s {device_id} shell {cmd}'),
            capture_output=True, text=True, timeout=8
        )
        txt = (out.stdout or "") + (out.stderr or "")
        return fname.lower() in txt.lower()
    except Exception:
        return False


def _scan_file(adb_path: str, device_id: str, dev_src: str):
    import urllib.parse
    uri = "file://" + urllib.parse.quote(dev_src, safe="/:")
    adb_shell(adb_path, device_id, f"am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d {uri}")


def _scan_dir(adb_path: str, device_id: str, dev_dir: str):
    import urllib.parse
    uri = "file://" + urllib.parse.quote(dev_dir.rstrip("/"), safe="/:")
    adb_shell(adb_path, device_id, f"am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_DIR -d {uri}")


def _cmd_media_rescan(adb_path: str, device_id: str, dev_dir: str):
    import shlex, subprocess
    for sub in ("scan", "rescan"):
        try:
            subprocess.run(
                shlex.split(f'"{adb_path}" -s {device_id} shell cmd media {sub} {dev_dir!s}'),
                timeout=6, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception:
            pass


def _touch_flip(adb_path: str, device_id: str, dev_src: str):
    """บังคับให้ไฟล์เปลี่ยนชื่อไป-กลับ เพื่อกระตุ้น media observer"""
    tmp = dev_src + ".tmp"
    adb_shell(adb_path, device_id, f'mv "{dev_src}" "{tmp}"')
    sleep_s(0.5)
    adb_shell(adb_path, device_id, f'mv "{tmp}" "{dev_src}"')


def _copy_to_dcim_then_scan(adb_path: str, device_id: str, dev_src: str) -> str | None:
    """Fallback: คัดลอกไป DCIM/Camera และสแกน"""
    import os
    fname = os.path.basename(dev_src)
    dcim = f"/sdcard/DCIM/Camera/{fname}"
    adb_shell(adb_path, device_id, 'mkdir -p "/sdcard/DCIM/Camera"')
    adb_shell(adb_path, device_id, f'cp "{dev_src}" "{dcim}"')
    _scan_file(adb_path, device_id, dcim)
    return dcim


def show_popup(title: str, message: str):
    root = Tk();
    root.withdraw()
    try:
        messagebox.showinfo(title, message)
    finally:
        root.destroy()


# ----------------------------------
# (วางทับ def _build_steps_flow_from_cfg เดิม)
def _build_steps_flow_from_cfg(cfg, steps_override=None):
    """
    (แก้ไขใหม่) โหลด steps ตามคอนเซ็ปต์ 1-2-3
    1. ลองไฟล์จาก UI (cfg['steps_yaml'])
    2. ถ้าว่าง/ไม่มี/เป็น config.yaml ให้ลอง 'steps_default.yaml'
    3. ถ้าไม่เจอทั้งคู่ -> ล้มเหลว
    """
    import pathlib, yaml
    steps_raw = {}
    retry_policy = {}
    recovery_policy = {}
    
    DEFAULT_YAML_NAME = "steps_default.yaml" 
    p_default = pathlib.Path(DEFAULT_YAML_NAME)
    device_id = cfg.get("device_id") # (ดึง ID มาใช้ใน fatal)

    final_path_to_load = None # (ตัวแปรเก็บ Path ที่จะใช้จริง)
    
    path_from_ui = str(cfg.get("steps_yaml") or "").strip()
    p_ui = pathlib.Path(path_from_ui)
    ui_filename = p_ui.name.lower() # (เอาแค่ชื่อไฟล์ เช่น "config.yaml")
    
    # (ตรรกะใหม่)
    if path_from_ui and ui_filename != "config.yaml":
        # (1) ผู้ใช้ระบุไฟล์มา
        log("INFO", f"[YAML] (1) กำลังใช้ไฟล์ที่ระบุจาก UI: {path_from_ui}")
        if p_ui.exists():
            final_path_to_load = p_ui
        else:
            # (FIX) ถ้าหาไม่เจอ -> ต้องล้มเหลวทันที ห้ามไปต่อ
            fatal(f"ไม่พบไฟล์ steps_yaml ที่ระบุจาก UI: {path_from_ui}", device_id)
            return {}, {}, {} # <--- หยุดทันที
    else:
        # (2) ผู้ใช้ไม่ได้ระบุ (หรือเป็น "config.yaml") -> หาไฟล์กลาง
        log("INFO", f"[YAML] (2) กำลังค้นหาไฟล์กลาง (default): {DEFAULT_YAML_NAME}")
        if p_default.exists():
            final_path_to_load = p_default
        else:
            # (3) ไม่เจอไฟล์กลาง
            log("INFO", f"[YAML] (3) ไม่พบไฟล์กลาง {DEFAULT_YAML_NAME}")

    # 4. (ถ้าเจอไฟล์) โหลด Steps
    if final_path_to_load:
        try:
            log("INFO", f"[YAML] กำลังโหลด Steps จาก: {final_path_to_load.name}")
            data = yaml.safe_load(final_path_to_load.read_text(encoding="utf-8")) or {}
            
            if isinstance(data, dict):
                raw = data.get("steps", [])
                steps_raw = _normalize_steps_to_dict(raw)
                retry_policy = data.get("retry_policy", {}) or {}
                recovery_policy = data.get("recovery_policy", {}) or {}
            elif isinstance(data, list):
                steps_raw = _normalize_steps_to_dict(data)
                retry_policy, recovery_policy = {}, {}
            else:
                log("ERROR", "YAML format ไม่รองรับ (ต้องเป็น dict มี 'steps' หรือ list)")
        except Exception as e:
            log("ERROR", f"YAML parse error: {e}")

    if not steps_raw and steps_override:
        steps_raw = _normalize_steps_to_dict(steps_override)
        
    # สร้าง steps_flow ตามลำดับที่ต้องการ
    flow_seq = cfg.get("flow_sequence")
    if flow_seq:
        steps_flow = {k: steps_raw[k] for k in flow_seq if k in steps_raw}
    else:
        try:
            sorted_keys = sorted(steps_raw.keys(), key=lambda k: int(k))
            steps_flow = {k: steps_raw[k] for k in sorted_keys}
        except ValueError:
            steps_flow = dict(sorted(steps_raw.items()))

    return steps_flow, retry_policy, recovery_policy
# (removed duplicate _normalize_steps_to_dict)



def resolve_step_sequence(steps: dict, seq_in_cfg, DEFAULT_FLOW=None):
    if isinstance(seq_in_cfg, list) and seq_in_cfg:
        return seq_in_cfg
    ordered = [k for k in DEFAULT_FLOW if k in steps]
    extras = [k for k in steps.keys() if k not in ordered]
    return ordered + extras


KNOWN_POPUPS = [
    {"texts": ["อนุญาต", "Allow", "ตกลง", "OK"]},
    {"texts": ["ยอมรับ", "ปิด", "ยกเลิก", "Cancel"]},
]


def _exists_any_text(d, texts):
    try:
        for t in texts or []:
            if not t:
                continue
            if d(text=t).exists or d(description=t).exists:
                return True
            if d(textContains=t).exists or d(descriptionContains=t).exists:
                return True
    except Exception:
        pass
    return False


def _current_package_is(d, pkg: str | None) -> bool:
    if not pkg:
        return True
    try:
        cur = d.app_current().get("package")
        return cur == pkg
    except Exception:
        return True


def _wait_expectations(d, pkg, expects: dict | None, step_name: str) -> bool:
    if not expects:
        return True
    timeout_s = float(expects.get("timeout_s", 6.0))
    want_texts = expects.get("any_text") or []
    want_pkg = expects.get("activity") or None
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        ok_pkg = _current_package_is(d, pkg if want_pkg else None)
        ok_text = True if not want_texts else _exists_any_text(d, want_texts)
        if ok_pkg and ok_text:
            return True
        sleep_s_responsive(0.4)
    log("WARN", f"EXPECT timeout at '{step_name}' (pkg={want_pkg}, texts={want_texts})")
    return False


def _dismiss_known_popups(d: object) -> bool:
    """
    พยายามปิด popup ที่รู้จักแล้วเล็กน้อย เช่น permission / ข้อความชั่วคราว
    คืนค่า True ถ้าทำการ dismiss ได้อย่างน้อยหนึ่งครั้ง
    (ปรับเพิ่ม selector ตามที่เจอจริงในเครื่องคุณ)
    """
    try:
        # ตัวอย่าง selectors ที่มักโผล่: ปุ่ม 'ตกลง', 'อนุญาต', 'ปิด'
        for txt in ("ตกลง", "อนุญาต", "ปิด", "OK", "ALLOW"):
            try:
                if d(text=txt).exists:
                    d(text=txt).click()
                    sleep_s_responsive(0.2)
                    return True
            except Exception:
                pass
        return False
    except Exception:
        return False

#---------------------------------------------
def wait_upload_result(d, timeout: float = 90.0) -> str:
    """
    Robust wait for upload result popup (fast selector + xml fallback).
    Returns: "success" | "fail" | "timeout" | "unknown"
    """
    start = time.time()
    last_log = 0.0

    success_markers = ("อัปโหลดสำเร็จ", "อัปโหลดเรียบร้อย", "อัปโหลดเสร็จ", "Upload successful", "Upload complete", "Upload success", "คลิกที่นี่เพื่อดูวิดีโอ")
    fail_markers = ("อัปโหลดล้มเหลว", "Upload failed", "ไม่สามารถอัปโหลด", "Upload failed.")
    in_progress_markers = ("กำลังอัปโหลด", "กำลังอัพโหลด", "Uploading", "กำลังส่ง")

    try:
        while time.time() - start < float(timeout):
            # dismiss known blocking popups so they don't hide the success popup
            try:
                if _dismiss_known_popups(d):
                    sleep_s_responsive(0.1)
                    # continue checking immediately
            except Exception:
                pass

            # 1) fast selectors: try to detect success/fail quickly
            for m in success_markers:
                try:
                    if d(textContains=m).exists(timeout=0.25):
                        return "success"
                except Exception:
                    pass
            for m in fail_markers:
                try:
                    if d(textContains=m).exists(timeout=0.25):
                        return "fail"
                except Exception:
                    pass

            # 2) whole-hierarchy fallback: check xml string (catches fast transient toasts)
            try:
                xml = d.dump_hierarchy(compressed=True) or ""
                # convert to simple str
                for m in success_markers:
                    if m in xml:
                        return "success"
                for m in fail_markers:
                    if m in xml:
                        return "fail"
                # if in-progress markers seen, just continue waiting
            except Exception:
                # if dump fails, ignore and continue; selector checks still run
                pass

            # periodic debug log
            if time.time() - last_log > 5.0:
                last_log = time.time()
                log("DEBUG", f"Waiting upload popup... elapsed {int(time.time()-start)}s")

            sleep_s_responsive(0.3)

        # timeout
        return "timeout"
    except Exception as e:
        log("WARN", f"wait_upload_result exception: {e}")
        return "unknown"

# Replace both older functions with this single robust helper


def _detect_bot_protect(d) -> bool:
    suspicious = ["captcha", "ยืนยันตัวตน", "ลากจิ๊กซอ", "โปรดเลื่อนเพื่อยืนยัน"]
    return _exists_any_text(d, suspicious)

def u2_alive(d: u2.Device) -> bool:
    try:
        # ใช้ window_size เพื่อตรวจสอบการเชื่อมต่อ
        _ = d.window_size()
        return True
    except Exception:
        return False


def try_recover_u2(d: u2.Device) -> bool:
    try:
        if u2_alive(d):
            return True
        log("WARN", "กู้ u2 ด้วย healthcheck()")
        d.healthcheck()
        for _ in range(8):
            sleep_s(1.0)
            if u2_alive(d):
                log("INFO", "กู้ u2 สำเร็จ")
                return True
        log("ERROR", "กู้ u2 ไม่สำเร็จในเวลาที่กำหนด")
        return False
    except Exception as e:
        log("ERROR", f"healthcheck ล้มเหลว: {e}")
        return False


def do_tap(d, adb_path: str, device_id: str, x: int, y: int, delay_s: float, tap_state):
    x, y = int(x), int(y)
    tap_state = normalize_tap_state(tap_state, default_mode="u2")
    # if forced to adb for this round -> use adb tap directly
    try:
        if tap_state.mode == "adb" or tap_state.use_adb_this_round:
            adb_shell(adb_path, device_id, f"input tap {x} {y}")
            sleep_s(delay_s, f"หลังแตะ ADB {x},{y}")
            return
    except Exception:
        # defensive: if attribute missing, wrap again
        tap_state = normalize_tap_state(tap_state, default_mode="u2")

    try:
        d.click(x, y)
        sleep_s(delay_s, f"หลังแตะ u2 {x},{y}")
    except Exception as e:
        # fallback to adb, but keep tap_state as object
        tap_state = normalize_tap_state(tap_state)
        tap_state.use_adb_this_round = True
        log("WARN", f"u2.click ล้มเหลว ({e}) -> AUTO ใช้ ADB รอบนี้")
        adb_shell(adb_path, device_id, f"input tap {x} {y}")
        sleep_s(delay_s, "หลัง fallback ADB")



# *** FIX: เพิ่ม cfg: dict ใน argument เพื่อแก้ NameError: name 'cfg' is not defined ***
def _ensure_channels_alive(d, adb_path, device_id, conn_mode, cfg: dict) -> bool:
    if not u2_alive(d):
        log("WARN", "u2 not alive -> healthcheck")
        if not try_recover_u2(d):
            return False
    # adb
    try:
        out = subprocess.run(shlex.split(f'"{adb_path}" -s {device_id} get-state'), capture_output=True, text=True,
                             timeout=4)
        if "device" not in (out.stdout or ""):
            log("WARN", f"ADB state '{(out.stdout or out.stderr or '').strip()}' -> reconnect")
            # แก้ไข: ดึง ip_port จาก cfg ที่ส่งเข้ามา
            ip_port = cfg.get('wifi_ip_port', '')
            # เรียก ensure_adb_connection ด้วย argument ที่ครบถ้วน
            ensure_adb_connection(adb_path, device_id, conn_mode, False)
    except Exception:
        log("WARN", "ADB get-state exception, trying reconnect")
        # แก้ไข: ดึง ip_port จาก cfg ที่ส่งเข้ามา
        ip_port = cfg.get('wifi_ip_port', '')
        # เรียก ensure_adb_connection ด้วย argument ที่ครบถ้วน
        # *** FIX: แก้ไข IndentationError ที่นี่ (ลบการเยื้อง 1 ระดับ) ***
        ensure_adb_connection(adb_path, device_id, conn_mode, False)
    return True


# -----------------------------------------------------------------
# EDITED: Tap Engine พร้อม Retry และ Watchdog
# -----------------------------------------------------------------
# *** แก้ไขจุดที่ 1: เพิ่ม caption_val: str, link_val: str ใน function signature ***
def tap_key_flow(d: u2.Device, key: dict, step_name: str, step_type: str, adb_path: str, conn_mode: str,
                 app_package: str, ip_port: str, caption_val: str, link_val: str) -> bool:
    """
#     สั่งงานอุปกรณ์ (tap/click/set_text) พร้อมระบบ Retry 3 ครั้ง และ Error Handling (ใช้ resourceId)
#     - รับ adb_path, conn_mode, app_package, ip_port จาก process_posts
    """
    global CONNECTION_FAILURE_COUNT
    MAX_TAP_RETRY = 3
    device_id = d.serial  # ใช้ d.serial สำหรับ device_id

    # ------------------ 1. การจัดการการเชื่อมต่อ (Watchdog) ------------------
    if not d.alive:
        log("WARN", f"[{step_name}] D.alive=False, พยายามเชื่อมต่อใหม่...")
        d_new = ensure_adb_connection(adb_path, device_id, conn_mode, False)
        if not d_new:
            CONNECTION_FAILURE_COUNT += 1
            log("ERROR",
                f"[{step_name}] เชื่อมต่อไม่สำเร็จ ({CONNECTION_FAILURE_COUNT}/{MAX_CONNECTION_FAILURES} ครั้ง)")
            if CONNECTION_FAILURE_COUNT >= MAX_CONNECTION_FAILURES:
                _cleanup_pause_flag()
                fatal(f"การเชื่อมต่อขาดเกิน {MAX_CONNECTION_FAILURES} ครั้ง", device_id)
            return False
        else:
            d = d_new

            # ------------------ 2. การสั่งงานและ Retry ------------------
    for retry in range(1, MAX_TAP_RETRY + 1):
        try:
            # 1. อ่าน/รอก่อนสั่งงาน (ถ้ามี 'expects')
            if 'expects' in key:
                # แก้ไข: ใช้ expects เป็น resourceId หรือ text ในการรอ
                expect_id_or_text = key['expects']
                if not (d(resourceId=expect_id_or_text).wait(timeout=10.0) or d(text=expect_id_or_text).wait(
                        timeout=10.0)):
                    log("WARN", f"[{step_name}] รอหน้าจอ ('expects': {expect_id_or_text}) ไม่สำเร็จ")
                    if step_type in ["mandatory", "tap"]:
                        log("CRITICAL", f"[{step_name}] ERROR: ข้าม Flow ไม่ได้! (expects fail)")
                        return False
                        # ถ้าไม่ใช่ mandatory ก็แค่เตือนและลองสั่งงานต่อ (หรือ break ถ้าไม่ต้องการ)
                    # For safety, let's break and fail if it's not text input
                    if step_type not in ["text"]:
                        break

            # 2. สั่งงานหลัก (Tap/Click/SetText)

            # *** แก้ไขจุดที่ 2: เปลี่ยน Logic การป้อนข้อความ ***
            if step_type == "text":
                # *** FIX: ดึงค่าที่ถูกต้องมาใช้ตามชื่อ step ***
                if step_name in ["tap_focus_caption", "text_caption", "8"]:  # 8 = ID ของ "แตะช่อง เพิ่มแคปชัน"
                    text_to_input = caption_val
                elif step_name in ["tap_focus_link", "text_link", "12"]:  # 12 = ID ของ "โฟกัสช่องว่าง กลางจอ"
                    text_to_input = link_val
                else:
                    # ถ้า step_type เป็น 'text' แต่ไม่มี step_name ตรงกับที่กำหนด ให้ข้าม
                    log("WARN", f"[{step_name}] ข้าม: Step type 'text' ไม่มี Step Name ที่กำหนด (Caption/Link)")
                    break  # ออกจาก retry loop

                if not d(resourceId=key['resourceId']).exists:
                    log("WARN", f"[{step_name}] ไม่พบ resourceId สำหรับ text input")
                    if retry == MAX_TAP_RETRY:
                        break
                    sleep_s_responsive(1)
                    continue

                # *** FIX: เปลี่ยนการใช้ key['value'] เป็น text_to_input ***
                d(resourceId=key['resourceId']).set_text(text_to_input)
                log("INFO", f"[{step_name}] INPUT (Retry {retry}): {text_to_input[:30]}...")

            elif step_type in ["tap", "mandatory"]:
                if not d(resourceId=key['resourceId']).exists:
                    log("WARN", f"[{step_name}] ไม่พบ resourceId สำหรับ tap")
                    if retry == MAX_TAP_RETRY:
                        break
                    sleep_s_responsive(1)
                    continue

                d(resourceId=key['resourceId']).click(timeout=10.0)
                log("INFO", f"[{step_name}] TAP (Retry {retry})")

            # 3. สั่งงานสำเร็จแล้ว
            CONNECTION_FAILURE_COUNT = 0
            return True

        # ------------------ 3. การจัดการข้อผิดพลาด ------------------
        except UiAutomationError as e:
            log("WARN", f"[{step_name}] U2 Error (Retry {retry}/{MAX_TAP_RETRY}): {e}")
            if retry < MAX_TAP_RETRY:
                sleep_s_responsive(random.uniform(2, 5))
            else:
                log("CRITICAL", f"[{step_name}] U2 Error เกิน {MAX_TAP_RETRY} ครั้ง")
                break

        except Exception as e:
            log("ERROR", f"[{step_name}] Unknown Error (Retry {retry}/{MAX_TAP_RETRY}): {e}")
            if retry < MAX_TAP_RETRY:
                sleep_s_responsive(random.uniform(5, 10))
            else:
                log("CRITICAL", f"[{step_name}] Unknown Error เกิน {MAX_TAP_RETRY} ครั้ง")
                break

                # ถ้าหลุดจากลูป Retry แสดงว่าล้มเหลว
    log("FAIL", f"[{step_name}] สั่งงานล้มเหลวทั้งหมด ({step_type})")
    return False


# -----------------------------------------------------------------
# ส่วนที่โหลดไฟล์ตั้งค่า
# -----------------------------------------------------------------
def get_default_config():
    return {
        "fast_media_index": True,
        "adb_path": "adb",
        "device_id": "AUTO",
        "adb_connection": "USB",
        "app_package": "com.shopee.th",
        "videos_dir": "videos",
        "device_video_dir": "/sdcard/Movies/shopee_uploads",
        "captions_csv": "captions.csv",
        "steps_yaml": "config.yaml",
        "delay_between_posts": 15,  # <--- FIX: เปลี่ยน default จาก 300 เป็น 30
        "num_posts": 90,
        "tap_engine_mode": "u2",  # auto|adb|u2
        "post_push_wait_s": 5,  # เวลารอหลัง push ให้แกลเลอรี่เห็นไฟล์
        "wifi_ip_port": "",
    }


def load_config(cfg_in: dict = None) -> dict:
    cfg = get_default_config()
    if cfg_in:
        for k, v in cfg_in.items():
            if v is not None:
                cfg[k] = v

    # ตรวจสอบว่า local_videos_dir ถูกตั้งค่าหรือไม่ และใช้ videos_dir เป็น fallback
    if 'local_videos_dir' not in cfg or not cfg['local_videos_dir']:
        cfg['local_videos_dir'] = cfg['videos_dir']

    return cfg
#----------------
def load_steps_yaml(cfg: dict) -> dict:
    """
    (แก้ไขใหม่) โหลด Steps จาก .yaml ที่ระบุใน UI เท่านั้น
    โดยไม่ fallback ไปหา config.yaml อีกต่อไป
    """
    try:
        # --- 1. (แก้ไข) พยายามค้นหา Path จาก UI (ลองทั้ง 2 keys) ---
        yaml_path_str = cfg.get('steps_yaml_path')  # ลอง key ที่ 1 (ที่ผมเคยแนะนำ)
        if not yaml_path_str:
            yaml_path_str = cfg.get('steps_yaml')  # ลอง key ที่ 2 (ที่คุณมีในโค้ด)

        # --- 2. (แก้ไข) ตรวจสอบว่า UI ส่งมาจริงหรือไม่ ---
        if not yaml_path_str or not isinstance(yaml_path_str, str) or not yaml_path_str.strip():
            log("CRITICAL", "ไม่ได้ระบุไฟล์ .yaml ใน UI (ไม่พบ 'steps_yaml' หรือ 'steps_yaml_path')")
            log("CRITICAL", "กรุณาตรวจสอบว่าเลือกไฟล์ YAML ใน UI ถูกต้อง")
            return {}

        # --- 3. (แก้ไข) ตรวจสอบว่าไฟล์มีอยู่จริงหรือไม่ (แบบเข้มงวด) ---
        yaml_path = pathlib.Path(yaml_path_str.strip())

        if not yaml_path.exists():
            log("CRITICAL", f"ไม่พบไฟล์ steps_yaml ที่ระบุใน UI: {yaml_path}")
            log("CRITICAL", f"(Path ที่ได้รับจาก UI: {yaml_path_str})")
            # [สำคัญ] ลบการ fallback ไปหา 'config.yaml' ทิ้ง
            return {}

        # --- 4. ถ้าผ่าน 3 ด่านบนมาได้ ค่อยโหลด ---
        with yaml_path.open('r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            # (ปรับปรุงการดึง steps ให้ยืดหยุ่นขึ้น)
            steps = {}
            if isinstance(data, dict):
                steps_data = data.get('steps', {})
                if isinstance(steps_data, list):
                    steps = {str(step.get('id', i)): step for i, step in enumerate(steps_data)}
                else:
                    steps = steps_data  # (ถ้าเป็น dict อยู่แล้ว)
            elif isinstance(data, list):
                steps = {str(step.get('id', i)): step for i, step in enumerate(data)}

            if not steps:
                log("WARN", f"ไฟล์ YAML {yaml_path} ว่างเปล่า หรือไม่มีคีย์ 'steps'")

            log("INFO", f"โหลด Steps จาก {yaml_path} สำเร็จ")
            return steps

    except Exception as e:
        log("ERROR", f"โหลด Steps YAML ล้มเหลว ({cfg.get('steps_yaml_path', 'N/A')}): {e}")
        log("ERROR", traceback.format_exc())  # เพิ่ม traceback
        return {}
#---------------




def load_captions(cfg: dict) -> list[dict]:
    rows = []
    try:
        if 'captions_csv' not in cfg or not cfg['captions_csv']:
            log("CRITICAL", "ไม่พบการตั้งค่า 'captions_csv'")
            return []

        csv_path = pathlib.Path(cfg['captions_csv'])

        if not csv_path.exists():
            log("CRITICAL", f"ไม่พบไฟล์ captions_csv ที่ระบุ: {csv_path}")
            return []

        with csv_path.open('r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)

            fieldnames = reader.fieldnames

            if not fieldnames or 'video_file' not in fieldnames:
                log("CRITICAL", f"CSV ต้องมีคอลลัมน์ 'video_file'. พบหัวคอลลัมน์: {fieldnames}")
                return []

            for row in reader:
                rows.append(row)

        log("INFO", f"โหลด {len(rows)} แถวจาก {csv_path} สำเร็จ")
    except Exception as e:
        log("ERROR", f"โหลด Captions CSV ล้มเหลว: {e}")
        return []
    return rows

#------------------------------------------------
def save_debug_on_fail(d, device_id, label):
    ts = int(time.time())
    folder = Path(f"logs/{date_str}/{device_id}")
    folder.mkdir(parents=True, exist_ok=True)
    try:
        d.screenshot(str(folder / f"dbg_{label}_{ts}.png"))
    except Exception:
        pass
    try:
        xml = d.dump_hierarchy(compressed=False) or ""
        (folder / f"dbg_{label}_{ts}.xml").write_text(xml, encoding="utf-8")
    except Exception:
        pass

# =================================================================
# (วางทับ def _find_ui_element เดิม)
def _find_ui_element(d, selectors: list, timeout: float = 10.0, log_label: str = ""):
    """
    (แก้ไข) พยายามหา UI element จาก list ของ selectors
    (อัปเกรดให้อ่าน 'Format ใหม่' ที่เป็น dict {'text_contains': [...]})
    """
    t0 = time.time()
    last_err = None
    while time.time() - t0 < timeout:
        for sel_item in selectors:
            try:
                ui_obj = None
                sel_str_log = str(sel_item) # (สำหรับ Log)

                # ▼▼▼ (ตรรกะใหม่) ▼▼▼
                if isinstance(sel_item, str):
                    # (รูปแบบเก่า: "textContains=...")
                    sel_str = sel_item
                    if sel_str.startswith("xpath="):
                        ui_obj = d.xpath(sel_str[6:])
                    elif sel_str.startswith("description="):
                        ui_obj = d(description=sel_str[12:])
                    elif sel_str.startswith("resourceId="):
                        ui_obj = d(resourceId=sel_str[11:])
                    elif sel_str.startswith("textContains="):
                        ui_obj = d(textContains=sel_str[13:])
                    else: # (Default คือ textContains)
                        ui_obj = d(textContains=sel_str)
                
                elif isinstance(sel_item, dict):
                    # (รูปแบบใหม่: {'text_contains': [...]})
                    if 'text_contains' in sel_item:
                        # (ลองหาทีละตัวใน List)
                        for text in sel_item['text_contains']:
                            if d(textContains=text).exists:
                                ui_obj = d(textContains=text)
                                sel_str_log = f"textContains='{text}'"
                                break # (เจอแล้ว ออก)
                # ▲▲▲ (จบตรรกะใหม่) ▲▲▲

                if ui_obj and ui_obj.exists:
                    log("INFO", f"{log_label} Found UI element, tapping: {sel_str_log}")
                    return ui_obj, None # (เจอ)

            except Exception as e:
                last_err = e
        
        sleep_s_responsive(0.2) # (รอสักครู่ก่อนลองใหม่)

    # (ถ้าหลุด Loop = Timeout)
    return None, f"Timeout {timeout}s (selectors: {selectors}, last_err: {last_err})"
# =================================================================
class UploadFlowException(Exception):
    """ใช้บอก process_posts ว่าให้ข้ามไฟล์นี้ โดยไม่ต้อง Recovery"""
    pass


#-----------------------------------------------
def wait_for_any(d, selectors, total_timeout=20.0, poll_interval=0.5, device_id=None):
    """
    selectors: list of lambdas or tuples e.g. ("resourceId", "com.shopee...") or text strings use d(textContains=..)
    returns (found_selector, element) or (None, None)
    """
    t0 = time.time()
    last_log = 0.0
    while time.time() - t0 < float(total_timeout):
        for sel in selectors:
            try:
                # prefer passing full selector spec if you have; here we accept textContains strings
                if isinstance(sel, dict):
                    # example: {"resourceId": "..."}
                    key, val = next(iter(sel.items()))
                    if key == "resourceId":
                        if d(resourceId=val).exists(timeout=0.2):
                            return (sel, d(resourceId=val))
                    elif key == "xpath":
                        if d.xpath(val).exists(timeout=0.2):
                            return (sel, d.xpath(val))
                else:
                    # assume textContains string
                    if d(textContains=sel).exists(timeout=0.2):
                        return (sel, d(textContains=sel))
            except Exception:
                pass
        if time.time() - last_log > 5.0:
            last_log = time.time()
            log("DEBUG", f"[wait_for_any] still waiting for selectors {selectors} elapsed {int(time.time()-t0)}s")
        try:
            sleep_s_responsive(poll_interval, device_id=device_id)
        except Exception:
            raise
    return (None, None)

#-----------------------------------------------
def _run_single_video_flow(
    cfg: dict,
    d: u2.Device,
    steps_flow: dict,
    row_data: dict,
    tap_state: TapEngineState
, wait_if_paused=None) -> bool:
    """
    รัน Flow (ทุกขั้นตอน) สำหรับวิดีโอเดียว
    คืนค่า:
        True  = สำเร็จ
        False = ล้มเหลว (ให้ process_posts ไปจัดการ retry/recovery)
        UploadFlowException = ข้ามไฟล์นี้โดยไม่ recovery (ให้ process_posts จัดการ)
    """
    adb_path = cfg['adb_path']
    app_package = cfg['app_package']

    # 1) เตรียมข้อความสำหรับวิดีโอนี้
    caption_text_for_flow = row_data.get('caption', '')
    hashtags_for_flow = row_data.get('hashtags', '')
    links_for_flow = row_data.get('link', '')
    full_caption_for_flow = f"{caption_text_for_flow}\n{hashtags_for_flow}"

    log("INFO", "เริ่มรัน Flow โพสต์")
    upload_verified_in_step = False  # <--- [1. เพิ่มบรรทัดนี้]

    if not steps_flow:
        log("CRITICAL", "steps_flow ว่าง ณ เวลาเริ่มรัน — ยุติวิดีโอนี้")
        return False

    # 2) วนทุก step ตาม steps_flow
    for step_id, step_data in steps_flow.items():
        log_label = step_data.get('label', f"Step {step_id}")

        # ข้าม step ที่ปิดใช้งาน
        if not step_data.get('editable', True):
            log("DEBUG", f"[{log_label}] Step skipped (not editable/enabled).")
            continue

        log("INFO", f"--- Executing Step: [{log_label}] ---")

        action = step_data.get('action', {})
        action_type = action.get('type')
        step_action_taken = False  # ใช้เช็คว่าจะ run auto_input ไหม

        try:
            # ---------- Action: tap_xy ----------
            if action_type == 'tap_xy':
                xy = action.get('xy')
                if xy and isinstance(xy, list) and len(xy) == 2:
                    # 3a: มีพิกัด XY ชัดเจน
                    x, y = xy
                    log("INFO", f"[{log_label}] Tapping explicit XY: {x},{y}")
                    do_tap(d, adb_path, d.serial, int(x), int(y), 0, tap_state)
                    step_action_taken = True
                else:
                    # 3b: ไม่มี XY → หา element จาก expected_ui
                    log("DEBUG", f"[{log_label}] No XY, searching by expected_ui...")
                    expected_ui = step_data.get('expected_ui', [])
                    if not expected_ui:
                        log("WARN",
                            f"[{log_label}] 'tap_xy' action has no 'xy' and no 'expected_ui'. Cannot tap.")
                        continue

                    selectors = []
                    rule_descs = []

                    for rule in expected_ui:
                        if rule.get('text_contains'):
                            for text in rule['text_contains']:
                                selectors.append(d(textContains=text))
                                rule_descs.append(f"textContains='{text}'")
                        if rule.get('content_desc'):
                            for desc in rule['content_desc']:
                                selectors.append(d(description=desc))
                                rule_descs.append(f"description='{desc}'")
                        if rule.get('resource_id'):
                            for rid in rule['resource_id']:
                                selectors.append(d(resourceId=rid))
                                rule_descs.append(f"resourceId='{rid}'")
                        if rule.get('xpath'):
                            for xp in rule['xpath']:
                                selectors.append(d.xpath(xp))
                                rule_descs.append(f"xpath='{xp}'")

                    if not selectors:
                        log("WARN", f"[{log_label}] No valid selectors found in expected_ui.")
                        continue

                    timeout = 10.0
                    t_start = time.time()
                    obj_to_click = None
                    desc_to_log = ""

                    log("DEBUG",
                        f"[{log_label}] Polling for {len(selectors)} selectors: {rule_descs}")

                    while time.time() - t_start < timeout:
                        # กัน popup มากวน
                        if _dismiss_known_popups(d):
                            log("WARN",
                                f"[{log_label}] Dismissed a known popup. Continuing search.")
                            sleep_s_responsive(1.0)
                            continue

                        for i, sel in enumerate(selectors):
                            if sel.exists:
                                obj_to_click = sel
                                desc_to_log = rule_descs[i]
                                break
                        if obj_to_click:
                            break
                        sleep_s_responsive(0.5)

                    if obj_to_click:
                        log("INFO",
                            f"[{log_label}] Found UI element, tapping: {desc_to_log}")
                        obj_to_click.click()
                        step_action_taken = True
                    else:
                        log("WARN",
                            f"[{log_label}] Timeout: Could not find any of {rule_descs} after {timeout}s.")
                        log("CRITICAL",
                            f"[{log_label}] Step failed, UI element not found. Aborting flow.")
                        return False  # flow ล้มเหลว

            # ---------- Action: press_key ----------
            elif action_type == 'press_key':
                key = action.get('key')
                if key:
                    log("INFO", f"[{log_label}] Pressing Key: {key}")
                    d.press(key.replace("KEYCODE_", "").lower())
                    step_action_taken = True
                else:
                    log("WARN", f"[{log_label}] 'press_key' action with no 'key'.")

            else:
                log("INFO",
                    f"[{log_label}] No 'tap_xy' or 'press_key' action found.")

            # ---------- Auto Input ----------
            auto_input_key = step_data.get('auto_input')
            if (step_action_taken or auto_input_key) and auto_input_key:
                sleep_s(1.0, "Wait for keyboard/focus")
                if auto_input_key == 'caption':
                    log("INFO", f"[{log_label}] Auto-inputting caption...")
                    send_text_or_abort(d, full_caption_for_flow, abort_on_fail=True)
                elif auto_input_key == 'link':
                    log("INFO", f"[{log_label}] Auto-inputting link...")
                    send_text_or_abort(d, links_for_flow, abort_on_fail=True)

            # ---------- Delay ----------
            delay = step_data.get('delay_s', 2)
            if delay > 0:
                sleep_s(delay, f"After step: {log_label}")
# ---------- Post-check ----------
                # ---------- Post-check (robust, balanced try/except) ----------
                post_check = step_data.get('post_check')
                if post_check:
                    log("DEBUG", f"[{log_label}] Running post-check...")
                    # flatten expected texts
                    expected_texts = []
                    for rule in post_check:
                        if 'text_contains' in rule:
                            expected_texts.extend(rule['text_contains'])

                    # markers for upload-success
                    upload_success_markers = ["อัปโหลดสำเร็จ", "อัปโหลดสำเร็จ คลิกที่นี่เพื่อดูวิดีโอ", "Upload successful"]
                    found_upload_marker = any(m in expected_texts for m in upload_success_markers)

                    # --- Case A: step itself verifies upload (aggressive XML check) ---
                    if found_upload_marker:
                        try:
                            timeout_sec = int(cfg.get("verify_upload_timeout", 90))
                        except Exception:
                            timeout_sec = 90
                        log("INFO",
                            f"[{log_label}] (Aggressive) Waiting up to {timeout_sec}s for upload-success popup...")
                        t0 = time.time()
                        got_success = False
                        last_log = 0.0

                        while time.time() - t0 < timeout_sec:
                            # respect pause/stop responsiveness
                            try:
                                sleep_s_responsive(0.05, device_id=device_id)
                            except Exception:
                                # stop requested -> bubble up to caller
                                raise

                            # try dump xml
                            xml = ""
                            try:
                                xml = d.dump_hierarchy(compressed=True) or ""
                            except Exception:
                                # transient failure of dump: wait a bit and retry
                                try:
                                    sleep_s_responsive(0.2, device_id=device_id)
                                except Exception:
                                    raise
                                continue

                            # success markers?
                            for marker in upload_success_markers:
                                if marker in xml:
                                    log("INFO", f"[{log_label}] Post-check OK (XML): Found '{marker}'")
                                    got_success = True
                                    break
                            if got_success:
                                break

                            # fail markers?
                            fail_markers = ("อัปโหลดล้มเหลว", "Upload failed", "โพสต์ไม่สำเร็จ")
                            if any(m in xml for m in fail_markers):
                                log("WARN", f"[{log_label}] Post-check FAILED (XML): Found fail marker.")
                                break

                            # periodic debug log
                            if time.time() - last_log > 5.0:
                                last_log = time.time()
                                log("DEBUG",
                                    f"[{log_label}] (Aggressive) Waiting for upload popup... elapsed {int(time.time() - t0)}s")

                        if got_success:
                            upload_verified_in_step = True
                        else:
                            log("WARN",
                                f"[{log_label}] Upload verification TIMEOUT after {timeout_sec}s — skipping file (no recovery).")
                            # raise special exception so caller can handle skip vs recovery
                            raise UploadFlowException(f"Upload verification timeout ({timeout_sec}s)")

                    # --- Case B: normal post-check rules (retry per rule) ---
                    else:
                        all_ok = True
                        for rule in post_check:
                            if 'text_contains' not in rule:
                                continue
                            texts = list(rule['text_contains'])
                            # per-rule timeout (configurable in rule; default 6s)
                            try:
                                rule_timeout = float(rule.get("timeout", 6.0))
                            except Exception:
                                rule_timeout = 6.0

                            found_text = False
                            t_start = time.time()
                            last_log = 0.0

                            while time.time() - t_start < rule_timeout:
                                # try each candidate quickly
                                for txt in texts:
                                    try:
                                        if d(textContains=txt).wait(timeout=1.0):
                                            log("DEBUG", f"[{log_label}] Post-check OK: Found '{txt}'")
                                            found_text = True
                                            break
                                    except Exception:
                                        pass

                                if found_text:
                                    break

                                # respect pause/stop responsiveness
                                try:
                                    sleep_s_responsive(0.1, device_id=device_id)
                                except Exception:
                                    # stop requested -> bubble up
                                    raise

                                # periodic debug log
                                if time.time() - last_log > 3.0:
                                    last_log = time.time()
                                    log("DEBUG",
                                        f"[{log_label}] Post-check: waiting for texts {texts} (elapsed {int(time.time() - t_start)}s)")

                            if not found_text:
                                all_ok = False
                                log("WARN", f"[{log_label}] Post-check FAILED: Text not found {texts}")
                                break

                        if not all_ok:
                            log("CRITICAL", f"[{log_label}] Post-check failed. Aborting flow.")
                            return False
        # ---------- End Post-check ----------

        except Exception as e:
            log("CRITICAL",
                f"[{log_label}] Unhandled exception during step execution: {e}")
            log("CRITICAL", traceback.format_exc())
            return False

    # ====== หลังจากรันครบทุก step (รวมแตะปุ่ม 'โพสต์' แล้ว) ======

    # ใช้ helper รอ popup ตามเงื่อนไขที่ต้องการ
    # --- Verify upload final step (ใช้ helper wait_upload_result) ---
    # ===== after steps finished =====
    try:
        timeout_sec = float(cfg.get("verify_upload_timeout", 90.0))
    except Exception:
        timeout_sec = 90.0

    # Only run upload verification if step explicitly enabled (config) or default True
    if cfg.get("enable_upload_verify", True) and not upload_verified_in_step:
        result = wait_upload_result(d, timeout=timeout_sec)
        if result == "success":
            log("INFO", "ตรวจพบข้อความ 'อัปโหลดสำเร็จ' การทำงานสมบูรณ์")
            # ensure tap_state flag reset (if object)
            try:
                tap_state = normalize_tap_state(tap_state)
                tap_state.use_adb_this_round = False
            except Exception:
                pass
            return True
        elif result == "fail":
            log("CRITICAL", "ผลอัปโหลด: ล้มเหลว (flow ถือว่าผิดพลาด)")
            return False
        elif result in ("timeout", "unknown"):
            # skip this file WITHOUT recovery -> raise UploadFlowException so caller handles it specially
            raise UploadFlowException(f"Upload verification timeout ({timeout_sec}s)")
    else:
        # If verify is disabled OR it was already verified -> assume success
        if upload_verified_in_step:
            log("INFO", "--- อัปโหลดวิดีโอสำเร็จ (Verified in step) ---")
        else:
            log("INFO", "--- อัปโหลดวิดีโอสำเร็จ (skip verify) ---")
        return True


# -----------------------------------------------------------------
# EDITED: Process Posts (Loop หลัก - แก้ไข Tap XY)
# -----------------------------------------------------------------
def process_posts(cfg: dict, d: u2.Device, steps_flow: dict, captions_data: list[dict], retry_policy: dict,
                  recovery_policy: dict, check_func: callable):
    global successful_posts, failed_posts, skipped_retry, skipped_missing
    import shlex
    import pathlib
    import os       # <--- เพิ่ม
    import shutil   # <--- เพิ่ม

    adb_path = cfg['adb_path']
    conn_mode = cfg.get('adb_connection', 'usb')
    app_package = cfg.get('app_package', '')

    try:
        delay_between_posts = float(cfg.get('delay_between_posts', 300))
    except Exception:
        delay_between_posts = 300.0

    # ดึงค่า path จาก config มาสร้างเป็นตัวแปร videos_dir_path
    videos_dir_path = pathlib.Path(cfg.get('local_videos_dir', 'videos'))

    post_push_wait_s = float(cfg.get('post_push_wait_s', 3))
    fast_media_index = bool(cfg.get("fast_media_index", True))
    if fast_media_index and post_push_wait_s > 1:
        post_push_wait_s = 1

    # --- Retry policy (ensure defined) ---
    try:
        max_retries = int(retry_policy.get('max_retries', 3))
    except Exception:
        max_retries = 3

    try:
        retry_interval = float(retry_policy.get('retry_interval', 5.0))
    except Exception:
        retry_interval = 3.0

    # optional per-attempt timeout (if you use it)
    try:
        retry_timeout = float(retry_policy.get('timeout', 15.0))
    except Exception:
        retry_timeout = 15.0
    # ------------------------------------------------

    # <-- IMPORTANT: initialize tap_state as object to avoid dict attribute errors -->
    tap_state = normalize_tap_state(None)  # use default "u2"

    # other setup...

    # [FIX 2: เพิ่มการหน่วงเวลาก่อนเริ่ม Loop หลัก]
    log("INFO", "หน่วงเวลา 2.0s ก่อนเริ่ม Loop โพสต์แต่ละไฟล์ (แก้ปัญหา Skip)")
    sleep_s(2.0, "Wait before starting post loop")

    try:
        for row in captions_data:
            # --- ensure basic row fields exist and normalized early ---
            # --- [จุดแก้ไข 2: เช็กสัญญาณ "ก่อน" เริ่มลูปใหม่] ---
            # (เช็กสัญญาณ "ก่อน" เริ่มทำงานกับวิดีโอตัวถัดไป)
            check_func(device_id)
            filename = row.get('video_file') if isinstance(row, dict) else None
            if not filename:
                log("FAIL", f"ข้าม: แถวนี้ไม่มี 'video_file': {row}")
                # maintain counters (ensure defined above)
                try:
                    skipped_missing += 1
                except Exception:
                    pass
                continue

            # normalize name early so any later logs can use it
            try:
                filename_clean = filename.strip()
            except Exception:
                filename_clean = str(filename)

            log("INFO", f"======= เริ่มโพสต์: {filename_clean} =======")

            # 1. ตรวจสอบไฟล์วิดีโอ (local path)
            try:
                local_src = videos_dir_path / filename_clean
            except Exception:
                local_src = pathlib.Path(str(videos_dir_path)) / filename_clean

            if not local_src.exists():
                try:
                    path_to_log = local_src.resolve()
                except Exception:
                    path_to_log = str(local_src)
                log("FAIL", f"ข้าม: ไม่พบไฟล์ {path_to_log}")
                try:
                    skipped_missing += 1
                except Exception:
                    pass
                continue

            # 2. PUSH ไฟล์ไปยังอุปกรณ์ และ SCAN
            device_video_dir = cfg.get('device_video_dir', '/sdcard/Movies/shopee_uploads')
            # (สร้าง dev_src_path ที่นี่ เพื่อให้ลูป retry และส่วนลบไฟล์มองเห็น)
            dev_src_path = f"{device_video_dir.rstrip('/')}/{filename_clean}"

            try:
                log("INFO", f"กำลัง PUSH: {filename_clean} -> {dev_src_path}")
                d.push(local_src, dev_src_path)
                sleep_s(post_push_wait_s, "หลัง push")
            except Exception as e:
                log("ERROR", f"Push ไฟล์ล้มเหลว: {e}")
                try:
                    failed_posts += 1
                except Exception:
                    pass
                continue  # ข้ามไปไฟล์ถัดไป

            # 3. สแกนไฟล์ให้แกลเลอรี่เห็น
            try:
                ensure_media_indexed_select(
                    adb_path=adb_path,
                    device_id=d.serial,
                    device_video_dir=device_video_dir,
                    filename=filename_clean,
                    fast=fast_media_index
                )
                log("INFO", f"สแกนไฟล์ {filename_clean} สำเร็จ")
            except Exception as e:
                log("WARN", f"สแกน Media ล้มเหลว (แต่จะลองโพสต์ต่อ): {e}")

            # (Optional: Delete local file after push)
            #if cfg.get('delete_after_push', False):
                #try:
                    #local_src.unlink()
                    #log("INFO", f"ลบไฟล์ local {filename_clean} (ตาม Cfg)")
                #except Exception as e:
                    #log("WARN", f"ลบไฟล์ local ล้มเหลว: {e}")

            # 4. Run Flow with retry
            video_success = False
            for attempt in range(1, max_retries + 1):
                skip_no_recovery = False
                log("INFO", f"--- Starting Flow Attempt {attempt}/{max_retries} for {filename_clean} ---")
                try:
                    flow_ok = _run_single_video_flow(
                        cfg=cfg, d=d, steps_flow=steps_flow,
                        row_data=row,
                        tap_state=tap_state
                    )

                except UploadFlowException as e_skip:
                    # Special-case: skip file WITHOUT triggering recovery
                    log("WARN", f"Flow สั่ง 'ข้ามไฟล์นี้' (No Recovery): {e_skip}")
                    skip_no_recovery = True
                    flow_ok = False
                    # break out of retry loop for this file
                    break

                except PostLimitException:
                    raise

                except Exception as e_recover:
                    log("CRITICAL", f"Flow ล้มเหลว (ต้อง Recovery): {e_recover}")
                    log("CRITICAL", traceback.format_exc())
                    flow_ok = False

                if flow_ok:
                    video_success = True
                    break
                # ------------------------------------------------------------------------

                # If we are here and skip_no_recovery -> do NOT do recovery; break retry loop
                if skip_no_recovery:
                    log("INFO", "Skipping file without recovery (as requested).")
                    break

                log("WARN", f"Flow attempt {attempt} failed for {filename_clean}.")

                if attempt < max_retries:
                    # --- [จุดแก้ไข 3: เช็กสัญญาณ "ก่อน" เข้า Recovery] ---
                    log("INFO", "Checking for stop signal before recovery...")
                    check_func(device_id)
                    # perform recovery actions
                    log("INFO", "Triggering recovery policy...")
                    try:
                        if app_package:
                            d.app_stop(app_package)
                            sleep_s(2.0)
                            d.app_start(app_package, use_monkey=True)
                            sleep_s(5.0)
                        else:
                            d.press("home")
                            sleep_s(2.0)
                    except Exception as rec_e:
                        log("ERROR", f"Recovery policy ล้มเหลว: {rec_e}")
                        sleep_s(5.0)
                else:
                    log("CRITICAL", f"All {max_retries} attempts failed for {filename_clean}.")
            # end attempts loop
# ▼▼▼▼▼ [ โค้ดที่แก้ไข Indentation แล้ว ] ▼▼▼▼▼

            # 5. สรุปผลของวิดีโอนี้ (เพิ่ม counter, ลบไฟล์, และหน่วงเวลา)
            if video_success:
                successful_posts += 1
                log("INFO", f"--- โพสต์สำเร็จ ({filename_clean}) ---")
                
                # ▼▼▼ [1. ตะโกนบอก GUI ให้อัปเดต Counter] ▼▼▼
                print(f"REALTIME_UPDATE success=1", flush=True)

                # ▼▼▼ [2. ย้ายไฟล์ PC ไปยังโฟลเดอร์ posted] ▼▼▼
                try:
                    # (ดึง path ที่จะย้ายไปเก็บจาก config, ถ้าไม่มีใช้ default)
                    posted_dir = cfg.get('posted_videos_dir', r'D:\Shopee\videos\posted') 
                    
                    posted_dir_path = pathlib.Path(posted_dir)
                    posted_dir_path.mkdir(parents=True, exist_ok=True) # (สร้างโฟลเดอร์ถ้ายังไม่มี)
                    
                    dest_path = posted_dir_path / local_src.name
                    
                    log("INFO", f"กำลังย้ายไฟล์ PC: {local_src.name} -> {dest_path}")
                    shutil.move(str(local_src), str(dest_path))

                except Exception as e:
                    log("ERROR", f"ย้ายไฟล์ PC ล้มเหลว: {e}")
                
                # ▼▼▼ [3. ลบไฟล์บนมือถือ (เหมือนเดิม)] ▼▼▼
                if cfg.get('delete_device_file_after_post', True):
                    try:
                        adb_shell(adb_path, d.serial, f"rm {shlex.quote(dev_src_path)}")
                        log("INFO", f"ลบไฟล์บนอุปกรณ์ {dev_src_path} (ตาม Cfg)")
                    except Exception as e:
                        log("WARN", f"ลบไฟล์บนอุปกรณ์ล้มเหลว: {e}")

                # ▼▼▼ [4. หน่วงเวลา (เหมือนเดิม)] ▼▼▼
                log("INFO", f"--- หน่วงเวลาระหว่างโพสต์ {delay_between_posts} วินาที ---")
                sleep_s(delay_between_posts, "Delay between posts")

            else:
                # (ส่วน failed... เหมือนเดิม)
                try:
                    if not skip_no_recovery:
                        failed_posts += 1
                        log("WARN", f"--- โพสต์ล้มเหลว ({filename_clean}) ---")
                except Exception:
                    pass            
            #-------------------------------
# ▲▲▲▲▲ [ จบโค้ดที่แก้ไข Indentation แล้ว ] ▲▲▲▲▲

    except PostLimitException as e:
        log("CRITICAL", f"!!! หยุดการทำงานบอททั้งหมด (Post Limit) !!! : {e}")
    except Exception as loop_e:
        log("CRITICAL", f"เกิด Error ร้ายแรงใน Loop หลัก (process_posts): {loop_e}")
        log("CRITICAL", traceback.format_exc())
    finally:
        log("INFO", "ฟังก์ชัน process_posts จบการทำงาน (Main loop finished)")

# ---------- main ----------
def main(cfg_in: dict = None, adb_path_in: str = None):
    log("INFO", "เริ่มต้น Bot")
    device_id = "" # (ประกาศไว้ก่อน)

    # (หุ้ม try...except...finally หลักไว้รอบนอกสุด)
    try:
        # 1) โหลด Config
        cfg = load_config(cfg_in)

        # 2) commit global CFG
        global CFG
        CFG = cfg

        # 3) apply CLI override (ถ้ามี)
        if adb_path_in:
            cfg['adb_path'] = adb_path_in

        # 4) เซ็ต prefix สำหรับ log ตาม device_id
        global _DEV_PREFIX
        try:
            device_id = (cfg.get('device_id') or "").strip() # (กำหนด device_id)
            _DEV_PREFIX = f"[{device_id}] " if device_id else ""
        except Exception:
            _DEV_PREFIX = ""
            
        # --- [จุดแก้ไข 1] ---
        # (เช็กสัญญาณทันทีที่มี device_id)
        check_bot_signals(device_id)

        # 5) ดึงค่าที่ใช้ต่อ
        adb_path    = cfg.get('adb_path', '')
        app_package = cfg.get('app_package', '')
        conn_mode   = (cfg.get('adb_connection') or cfg.get('adb_transport') or 'usb')
        num_posts   = int(cfg.get('num_posts', cfg.get('max_posts', 20)))
        ip_port     = cfg.get('wifi_ip_port', '')

        # (ใช้ adb_path, conn_mode, ฯลฯ ต่อได้ตามโค้ดเดิมคุณ)

        # 2. ตรวจสอบ ADB และเชื่อมต่อ u2
        if device_id == "AUTO":
            fatal("Device ID ต้องถูกระบุ (ไม่รองรับ AUTO ใน bot.py)", device_id)

        log("INFO", f"Checking Device: {device_id} ({conn_mode})")
        # --- ADB path fallback ---
        adb_path = resolve_adb_path(cfg.get("adb_path", ""))
        if not adb_path:
            fatal(r"ไม่พบ adb.exe: โปรดตั้งค่า adb_path ให้ถูกต้อง (เช่น D:\Shopee\usb_driver\adb.exe)", device_id)

        # --- only ensure ADB server/connectivity; do NOT assign to d ---
        ok = ensure_adb_connection(adb_path, device_id, conn_mode, False)
        if not ok:
            fatal("ไม่สามารถเชื่อมต่ออุปกรณ์ได้. โปรดตรวจสอบการเชื่อมต่อ ADB/Wi-Fi", device_id)

        import uiautomator2 as u2
        d = None # (ประกาศ d ไว้ข้างนอก try)
        try:
            d = u2.connect(device_id)
        except Exception as e:
            fatal(f"เชื่อมต่อ uiautomator2 ไม่สำเร็จ: {e}", device_id)
        try:
            d.settings['operation_delay'] = 0.5
            d.implicitly_wait(5.0)
            log("INFO", "ตั้งค่า u2 settings สำเร็จ")

            safe_setup_u2_settings(d)
        except Exception as e:
            fatal(f"กำหนด uiautomator2 settings ล้มเหลว: {e}", device_id)

        
        # 3. โหลด Steps และ Captions
        # *** FIX: โหลด steps, retry_policy, recovery_policy ***
        steps_flow, retry_policy, recovery_policy = _build_steps_flow_from_cfg(cfg, steps_override=None)

        log("INFO", f"รวมสเต็ปหลัง build: {len(steps_flow)} รายการ")
        if not steps_flow:
            fatal("Steps ว่างหรือโหลดไม่สำเร็จ", device_id)
            return

        captions_data = load_captions(cfg)

        if not steps_flow:
            fatal("ไม่พบ Flow Steps ที่ถูกต้องใน YAML หรือ config", device_id)
        if not captions_data:
            fatal("ไม่พบข้อมูล Captions ใน CSV", device_id)

        # 4. เตรียมพร้อม
        log("INFO", f"Step Count: {len(steps_flow)}")
        log("INFO", f"Post Count: {len(captions_data)} (จำกัด: {num_posts})")
        log("INFO", f"Retry Policy: {retry_policy}")
        log("INFO", f"Setting u2 IME...")
        try:
            safe_setup_u2_settings(d)
        except Exception as ime_e:
            log("WARN", f"ตั้งค่า FastInput IME ไม่สำเร็จ: {ime_e}")

        ensure_app_foreground(adb_path, device_id, app_package)
        sleep_s(4, "หลังเปิดแอป")

        # 5. เริ่มทำงาน
        # --- [จุดแก้ไข 2] ---
        # (ส่ง "ฟังก์ชันตัวเช็ก" ลงไปให้ "ลูปทำงาน" ด้วย)
        process_posts(cfg, d, steps_flow, captions_data[:num_posts], 
                      retry_policy, recovery_policy, 
                      check_bot_signals) # <--- [เพิ่ม] ส่งฟังก์ชัน

        # 6. สรุป
        log("INFO", "งานเสร็จสิ้น")
        print(
            f"SUMMARY_RUN success={successful_posts} "
            f"fail={failed_posts} skipped_missing={skipped_missing}",
            flush=True
        )

        # ปิด IME
    except StopRequestedException:
        # --- [จุดแก้ไข 3] ---
        # (นี่คือการ "จบ" แบบถูกต้องตามคำสั่ง UI)
        log("INFO", f"[{device_id}] หยุดการทำงานตามคำสั่ง (Stop Flag)")
        sys.exit(0) # (Exit code 0 = จบปกติ)
        
    except Exception as e:
        # --- [จุดแก้ไข 4] ---
        # (นี่คือ "Error" จริง ที่ทำให้บอทล้มเหลว)
        log("CRITICAL", f"Unhandled error in main(): {e}")
        log("CRITICAL", traceback.format_exc())
        
        # (สำคัญ!) ก่อนเข้า Recovery... เช็ก Flag ก่อน!
        try:
            check_bot_signals(device_id)
        except StopRequestedException:
            log("INFO", f"[{device_id}] หยุดตามคำสั่ง (Stop Flag) - ไม่เข้า Recovery")
            sys.exit(0)
            
        # (ถ้าไม่เจอ flag... ก็เข้า Recovery ตามปกติ)
        log("ERROR", f"[{device_id}] ไม่พบ Stop Flag, กำลังเข้าสู่ Recovery Policy...")
        # (โค้ด recovery policy ของคุณ (จาก steps.yaml) จะทำงานที่นี่)
        
    finally:
        # ปิด IME / เคลียร์ pause flag ให้เรียบร้อย
        try:
            if d: # (d อาจจะยังไม่ถูกสร้าง ถ้าแครชก่อน)
                if hasattr(d, "set_input_ime"):
                    d.set_input_ime(False)
                elif hasattr(d, "set_fastinput_ime"):
                    d.set_fastinput_ime(False)
                log("INFO", "สลับกลับคีย์บอร์ดเดิมสำเร็จ")
        except Exception as e:
            log("ERROR", f"สลับคีย์บอร์ดเดิมไม่สำเร็จ: {e}")
            
        # --- [จุดแก้ไข 5] ---
        # (เราจะใช้ "ตัวเช็ก" เป็นคนลบ flag แทน)
        # _cleanup_pause_flag() # <--- (ลบ หรือ คอมเมนต์บรรทัดนี้ทิ้ง)
        # (ถ้าบอทจบงานเอง ก็ควรเช็ก/ลบ flag ทิ้งตอนจบ)
        try:
            check_bot_signals(device_id)
        except StopRequestedException:
            pass # (จบเพราะสั่งหยุด ก็ไม่เป็นไร)

# ===============================================================
# Entry point ปลอดชน log (เวอร์ชันใหม่)
# ===============================================================
if __name__ == "__main__":
    import json
    import argparse
    import traceback

    parser = argparse.ArgumentParser(description="Shopee Video Bot")
    parser.add_argument("--config_data", help="JSON string of config data")
    parser.add_argument("--adb", help="Path to adb.exe", default=None)
    args, unknown_args = parser.parse_known_args()

    cfg_data = json.loads(args.config_data) if args.config_data else {}

    # รองรับ --package / --captions จาก UI
    unknown_map = {}
    for i in range(0, len(unknown_args), 2):
        key = unknown_args[i].lstrip('-').replace('-', '_')
        if i + 1 < len(unknown_args):
            unknown_map[key] = unknown_args[i + 1]

    if 'package' in unknown_map:
        cfg_data['app_package'] = unknown_map['package']
    if 'captions' in unknown_map:
        cfg_data['captions_csv'] = unknown_map['captions']
        
    # (ดึง device_id มาไว้ใช้เช็ก)
    device_id = cfg_data.get('device_id', '')

    run_mode = cfg_data.get('run_mode', 'NORMAL')

    try:
        # --- [จุดแก้ไข 1] ---
        # (เช็กสัญญาณทันทีที่เริ่ม)
        check_bot_signals(device_id)

        if run_mode.startswith("AUTOBOT"):
            # ถ้ามี autobot.py จริงค่อยใช้
            try:
                import autobot
            except ImportError:
                log("CRITICAL", "ไม่พบไฟล์ autobot.py แต่ run_mode เป็น AUTOBOT")
            else:
                log("INFO", f"▶️ โหมด AUTOBOT ({cfg_data.get('autobot_mode')})")
                
                # --- [จุดแก้ไข 2] ---
                # (ส่ง "ฟังก์ชันตัวเช็ก" ลงไปให้ autobot ด้วย)
                autobot.run_autobot_flow(cfg_data, check_bot_signals)
        else:
            log("INFO", "▶️ ตรวจพบโหมด NORMAL... กำลังเรียก main() (Flow ปกติ)")
            main(cfg_data, args.adb)
            
    except StopRequestedException:
        # --- [จุดแก้ไข 3] ---
        # (ดักจับการ "หยุด" ที่ UI สั่ง)
        log("INFO", f"[{device_id}] หยุดการทำงานตามคำสั่ง (Stop Flag)")
        sys.exit(0) # (จบปกติ)
        
    except SystemExit:
        pass # (ปล่อยผ่าน ถ้า fatal() ถูกเรียก)
        
    except Exception as e:
        # --- [จุดแก้ไข 4] ---
        # (นี่คือ "Error" จริง ที่ทำให้บอทล้มเหลว)
        log("CRITICAL", f"CRITICAL INIT ERROR (นอก main): {e}")
        log("CRITICAL", traceback.format_exc())
        
        # (สำคัญ!) ก่อนจบ... เช็ก Flag ก่อน!
        try:
            check_bot_signals(device_id)
        except StopRequestedException:
            log("INFO", f"[{device_id}] หยุดตามคำสั่ง (Stop Flag) - ไม่เข้า Recovery")
            sys.exit(0)
            
        # (ถ้าไม่เจอ flag... ก็อาจจะเข้า Recovery)
        log("ERROR", f"[{device_id}] ไม่พบ Stop Flag, อาจจะเข้าสู่ Recovery Policy (ถ้ามี)")