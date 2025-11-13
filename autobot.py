# -*- coding: utf-8 -*-
"""
Shopee Video Bot - AUTOBOT Logic
[เวอร์ชันอัปเกรด: เชื่อมต่อกับ UI, Log, และระบบ Pause/Stop]
"""
from __future__ import annotations

import os
import sys
import json
import time
import argparse
import traceback
import signal
from pathlib import Path # (เพิ่ม)
from loguru import logger # (เพิ่ม)
import os, atexit

pidfile = f"autobot_{os.getpid()}.pid"
with open(pidfile, "w") as f:
    f.write(str(os.getpid()))

def _cleanup():
    try:
        os.remove(pidfile)
    except Exception:
        pass

atexit.register(_cleanup)

# และ optional: log pid
import logging, sys
logging.info(f"Autobot PID: {os.getpid()}")


# --- [เพิ่ม] ระบบ Signal/Pause/Stop (ยืมมาจาก bot.py) ---
class StopRequestedException(Exception):
    """Exception ที่จะถูก raise เมื่อ UI สั่งหยุด (ผ่าน .stop flag)"""
    pass

# (เราต้องมี 'log' ก่อน ถึงจะใช้ 'check_bot_signals' ได้)
# (นี่คือ 'log' ตัวจริง ที่จะถูกตั้งค่าโดย setup_logging)
log = logger 

def check_bot_signals(device_id: str):
    """
    (ฟังก์ชันใหม่) ตรวจหา .stop และ .pause flag
    """
    if not device_id: return 
        
    stop_flag = Path("flags") / f"{device_id}.stop"
    pause_flag = Path("flags") / f"{device_id}.pause"

    # 1. เช็ก "หยุดถาวร"
    if stop_flag.exists():
        log.warning(f"[{device_id}] ตรวจพบ .stop flag! ยุติการทำงาน...")
        try: stop_flag.unlink()
        except: pass
        try: pause_flag.unlink()
        except: pass
        raise StopRequestedException(f"UI สั่งหยุด {device_id}")

    # 2. เช็ก "หยุดชั่วคราว"
    if pause_flag.exists():
        log.info(f"[{device_id}] Paused! (พบ .pause flag) กำลังรอ...")
        while pause_flag.exists():
            time.sleep(2)
            if stop_flag.exists(): # (เช็ก stop ซ้ำเผื่อกดหยุดตอน pause)
                log.warning(f"[{device_id}] ตรวจพบ .stop flag (ขณะ Pause)!")
                try: stop_flag.unlink()
                except: pass
                raise StopRequestedException(f"UI สั่งหยุด {device_id}")
        log.info(f"[{device_id}] Resumed! (.pause flag หายไป) ทำงานต่อ...")

# --- [เพิ่ม] ระบบ Logging (ยืมมาจาก bot.py) ---
def setup_logging(cfg: dict, device_id: str):
    """
    ตั้งค่า Loguru: ล้าง handler เก่า, เพิ่ม Console, เพิ่ม File
    """
    global log
    log.remove() # (ล้าง config เริ่มต้น)
    
    # (ตั้งค่า Console - ให้ UI ดักฟังได้)
    log.add(
        sys.stdout,
        level="DEBUG",
        format="{message}", # (ส่งเฉพาะ message ให้ UI)
        colorize=False
    )
    
    # (ตั้งค่า File Log)
    try:
        logs_dir = Path(cfg.get("logs_dir", "logs"))
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        # (สร้างชื่อไฟล์ log สำหรับ Autobot)
        log_filename = f"AUTOBOT_{device_id}_{time.strftime('%Y-%m-%d_%H%M%S')}.log"
        log_path = logs_dir / log_filename
        
        log.add(
            log_path,
            level="DEBUG",
            rotation="10 MB",
            encoding="utf-8",
            format="{time:HH:mm:ss.SSS} | {level:<8} | {message}"
        )
        log.info(f"--- Autobot Log เริ่มต้น (ไฟล์: {log_path}) ---")
    except Exception as e:
        log.error(f"ตั้งค่า File Log ล้มเหลว: {e}")

# --- (โค้ด Orchestrator/State Machine ของคุณ) ---
# (นี่คือฟังก์ชัน "ตัวอย่าง" จำลองการทำงานจาก Log ของคุณ)
def run_state_machine(device_id: str, cfg: dict, check_func: callable):
    """
    นี่คือ "หัวใจ" ของ Autobot ที่ทำงานเป็นลูป
    """
    log.info("--- Executing State: LaunchAppState ---")
    time.sleep(2)
    check_func(device_id) # (เช็กสัญญาณหลังจบ 1 State)
    log.info("แอป Shopee เปิดสำเร็จ")

    log.info("--- Executing State: FindProductState ---")
    time.sleep(3)
    check_func(device_id)
    log.info("ค้นหาสินค้า Affiliate สำเร็จ")

    log.info("--- Executing State: UploadVideoState ---")
    time.sleep(5)
    check_func(device_id)
    log.info("โพสต์วิดีโอสำเร็จ จบการทำงาน 1 รอบ")

    log.info("--- Executing State: UploadCheckStatusState ---")
    time.sleep(2)
    check_func(device_id)
    log.info("อัปโหลดสำเร็จ!")

# --- (ฟังก์ชันหลักที่ UI เรียก) ---
def run_autobot_flow(cfg: dict, check_func: callable):
    """
    (แก้ไข) Main entry point for AUTOBOT mode.
    รับ 'check_func' และ 'autobot_loops' จาก UI
    """
    device_id = cfg.get("device_id", "N/A")
    log.info(f"🤖 AUTOBOT Flow เริ่มทำงาน (Device: {device_id})")
    
    # (ดึง "จำนวน Loop" จาก UI)
    try:
        total_loops = int(cfg.get("autobot_loops", 1))
    except Exception:
        total_loops = 1
    log.info(f"ตั้งค่าจำนวน Loop ทั้งหมด: {total_loops}")

    try:
        # (เชื่อมต่อ u2, โหลด steps.yaml ฯลฯ ที่นี่)
        # ...
        
        # --- [นี่คือ "ลูปหลัก" (Main Loop)] ---
        for i in range(1, total_loops + 1):
            
            # (1. เช็กสัญญาณ "ก่อน" เริ่มลูปใหม่)
            check_func(device_id) 
            
            log.info(f"--- 🌀 เริ่ม AUTOBOT Loop {i}/{total_loops} ---")
            
            # (2. รัน State Machine 1 รอบ)
            run_state_machine(device_id, cfg, check_func)
            
            # (3. สรุปผลลูป)
            log.info(f"--- ✅ Loop {i}/{total_loops} successful ---")
            
            # (4. หน่วงเวลาระหว่างลูป (ถ้าไม่ใช่ลูปสุดท้าย))
            if i < total_loops:
                delay = int(cfg.get("delay_between_posts", 30))
                log.info(f"หน่วงเวลาระหว่างลูป {delay} วินาที...")
                
                # (เราต้องใช้ 'check_func' แทน 'time.sleep' ปกติ)
                start_delay = time.time()
                while (time.time() - start_delay) < delay:
                    check_func(device_id) # (เช็กทุก 1 วิ)
                    time.sleep(1)

    except StopRequestedException:
        log.warning(f"[{device_id}] หยุดการทำงาน AUTOBOT ตามคำสั่ง (Stop Flag)")
        sys.exit(0) # (จบปกติ)
    except Exception as e:
        log.critical(f"❌ เกิดข้อผิดพลาดร้ายแรงใน AUTOBOT: {e}")
        log.critical(traceback.format_exc())
        # (เราควรเช็ก flag อีกครั้ง ก่อนเข้า Recovery (ถ้ามี))
        check_func(device_id)
    finally:
        log.info("🔚 สิ้นสุดการทำงาน AUTOBOT")


# ---- CLI main (แก้ไข: ให้เหมือน bot.py) ----
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shopee Video Bot - AUTOBOT")
    parser.add_argument("--device", help="Device Serial ID")
    parser.add_argument("--config_data", help="JSON string of config data")
    args, unknown_args = parser.parse_known_args()

    cfg_data = json.loads(args.config_data) if args.config_data else {}

    # (ดึง device_id)
    device_id = cfg_data.get('device_id', '')
    if not device_id:
        device_id = args.device
    cfg_data['device_id'] = device_id

    # (สำคัญ!) "เปิดไมค์" (Setup Log) ทันที
    setup_logging(cfg=cfg_data, device_id=device_id)

    try:
        # (รัน flow AUTOBOT)
        run_autobot_flow(cfg_data, check_bot_signals)
        
    except StopRequestedException:
        log.info(f"[{device_id}] หยุดการทำงานตามคำสั่ง (Stop Flag)")
        sys.exit(0) 
    except SystemExit:
        pass
    except Exception as e:
        log.critical(f"CRITICAL INIT ERROR (autobot.py): {e}")
        log.critical(traceback.format_exc())