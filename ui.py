# -*- coding: utf-8 -*-
"""
Shopee Video Bot UI — หน่วยดีเลย์เป็นวินาที (s)
- post_push_wait_s: เวลารอหลัง push ให้แกลเลอรี่เห็นไฟล์
- ปุ่ม 'รัน ▶'(สีแดง) + 'หยุด' + 'เช็คอุปกรณ์' อยู่บรรทัดเดียวกัน
- คอมไพล์คอนเทนต์เป็นคอลัมน์เดียว (มีปุ่ม 'วาง' และสกรอลของตัวเอง)
- ปุ่ม 'โหลด captions.csv' คืนข้อมูลเข้า 4 กล่อง (วิดีโอ/แคปชั่น/แฮชแท็ก/ลิงก์)
- อ่าน/เขียน log แบบ UTF-8 + run.log แบบเรียลไทม์
- ปรับแท็บ AI: แยกช่องแสดงผล แคปชั่น/แฮชแท็ก + ตัวแยกผล JSON แบบไม่แตะเครื่องหมายในเนื้อหา
- ธีมสีส้ม Shopee
"""
import sys, csv, os, shlex, subprocess, threading, random, time

from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from tkinter import filedialog
import yaml
import requests
import pyperclip
import re
import json
from loguru import logger
import re  # สำหรับพาร์สข้อความ/สถานะ
import sys, os, json, threading, subprocess, datetime, queue
import signal
import subprocess, sys, json, threading
import tkinter as tk
import threading
from dotenv import load_dotenv, find_dotenv
try:
    load_dotenv(find_dotenv(filename=".env", usecwd=True) or find_dotenv(filename="env", usecwd=True))
except Exception:
    pass


APP_TITLE = "Shopee Video Bot — บอทโพสต์วิดีโอ"


def normalize_step(s: dict):
    if not isinstance(s, dict):
        return {"enabled": False, "xy": [], "delay_s": 3.0}
    return {
        "enabled": s.get("enabled", False),
        "xy": s.get("xy", []),
        "delay_s": s.get("delay_s", 3.0),
    }

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1024x700")
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.on_app_close)

        self._apply_shopee_theme()
        # ตัวแปรของแท็บ AI (ส่วน section นี้)
        import tkinter as tk  # เผื่อไว้ในกรณี scope
        self.ai_ffprobe_path = getattr(self, "ai_ffprobe_path", None)
        if not self.ai_ffprobe_path:
            self.ai_ffprobe_path = tk.StringVar(value="")

        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.adb_process = None
        self.run_thread = None
        #--autobot--------------------
        # ▼▼▼ [แก้ไข 2 บรรทัดนี้] ▼▼▼
        self.var_autobot_loops = tk.StringVar(value="90") # (1. เพิ่มตัวแปร Loop)
        # ▲▲▲ [จบส่วนแก้ไข] ▲▲▲

        # --- ตัวแปรสถานะโพสต์ & อุปกรณ์ ---
        self.posts_done = 0
        self.device_status_var = tk.StringVar(value="อุปกรณ์: - | Temp: - | CPU: - | RAM: -")
        self._prev_proc_stat = None  # (total_jiffies, idle_jiffies)
        self.device_post_counts = {}  # <--- เพิ่มบรรทัดนี้ (สำหรับนับโพสต์ต่อเครื่อง)
        self.metrics_thread_running = False # <--- เพิ่มบรรทัดนี้ (ตัวล็อค)
        self.create_widgets()
        self.after(3000, self._periodic_status_update) # <--- คงเหลือบรรทัดนี้ไว้ (ต้องมี 1 บรรทัด)
        #--------------------
        # ======= เพิ่มตัวแปรหลักที่แท็บั้นตอน ใช้ =======
        import tkinter as tk
        self.var_adb_path = tk.StringVar(value="D:/Shopee/usb_driver/adb.exe")
        self.var_device_id = tk.StringVar(value="")
        self.var_app_package = tk.StringVar(value="com.shopee.th")
        self.var_local_videos_dir = tk.StringVar(value="D:/Shopee/videos")
        self.var_device_video_dir = tk.StringVar(value="/sdcard/Movies/shopee_uploads")
        self.var_max_posts = tk.StringVar(value="20")
        self.var_delay_between_posts = tk.StringVar(value="40")
        self.var_post_push_wait_s = tk.StringVar(value="7")
        self.var_adb_connection = tk.StringVar(value="USB")
        self.var_wifi_host = tk.StringVar(value="")
        self.var_api_key = tk.StringVar(value="")
        self.var_api_provider = tk.StringVar(value="Gemini")
        # [NEW] เพิ่มตัวแปรโหมด AUTOBOT
        self.var_autobot_mode = tk.StringVar(value="Affiliate Link")  # <--- บรรทัดที่เพิ่ม
        # (ประกาศ "ผู้จัดการ" ที่คอยเก็บสถานะบอท)
        self.device_states = {}
                # --- init: container สำหรับสถานะ/ตัวแปร per-device ---
        self.device_vars = {}      # map: serial -> vars_map (BooleanVar, etc.)
        self.device_states = {}    # map: serial -> state dict (process, status, etc.)
        self.device_buttons = {}   # map: serial -> buttons dict (pause/resume/stop/run)
        self.device_vars = {}

        self.device_log_widgets = {}


        # ▲▲▲ [จบส่วนที่เพิ่ม] ▲▲▲
        # ▼▼▼ [แทนที่บล็อกนี้] ▼▼▼
        # (Auto-clear stop flags ตอนเริ่ม)
        try:
            # (เรียกฟังก์ชันที่เราเพิ่งสร้าง)
            cleared = self._clear_all_stop_flags()
            if cleared > 0:
                print(f"[UI] Auto-cleared {cleared} leftover .stop/.pause flags at startup")
        except Exception as e:
            # (ถ้ามันยังพังอีก อย่างน้อยก็แจ้งให้เรารู้)
            print(f"[UI] CRITICAL: _clear_all_stop_flags ล้มเหลว: {e}")
        # ▲▲▲ [จบส่วนที่แทนที่] ▲▲▲

    # ---------------- Shopee theme ----------------
    def _apply_shopee_theme(self):
        ORANGE = "#EE4D2D"
        LIGHT = "#FFF7F3"
        DARK  = "#352A26"

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        self.configure(bg=LIGHT)
        style.configure(".", background=LIGHT, foreground=DARK)
        style.configure("TFrame", background=LIGHT)
        style.configure("TLabel", background=LIGHT, foreground=DARK)
        style.configure("TLabelframe", background=LIGHT, foreground=DARK)
        style.configure("TLabelframe.Label", foreground=ORANGE)
        style.configure("Shopee.TButton", padding=6, foreground="white", background=ORANGE)
        style.map("Shopee.TButton", background=[("active", "#ff6b49")])

    # ------------------------------------------------
    def _on_closing(self):
        if self.adb_process and self.adb_process.poll() is None:
            self.adb_process.terminate()
        self.destroy()
        
        # =====================================================================
    #   AUTO-INJECTED HELPERS (Stop / Pause / Resume / UI Update)
    # =====================================================================

    # =====================================================================
    # (วางฟังก์ชันนี้ใน class App ของ ui.py)

    def _clear_all_stop_flags(self) -> int:
        """
        (ฟังก์ชันใหม่) ค้นหาและลบ .stop / .pause flag ที่ค้างในระบบ
        คืนค่าจำนวนไฟล์ที่ลบ
        """
        flags_dir = Path("flags")
        count = 0
        if not flags_dir.exists():
            print("[UI] ไม่พบโฟลเดอร์ flags/ (ไม่ต้องเคลียร์)")
            return 0

        try:
            # (ลบ .stop และ .pause ที่ค้าง)
            for f in flags_dir.glob("*.stop"):
                f.unlink()
                count += 1
            for f in flags_dir.glob("*.pause"):
                f.unlink()
                count += 1
        except Exception as e:
            # (ถ้าล้มเหลว ต้องแจ้งให้ผู้ใช้รู้)
            print(f"[UI] Error: ไม่สามารถลบ flag ที่ค้าง: {e}")
            messagebox.showwarning("Warning", f"ไม่สามารถลบ flag ที่ค้าง:\n{e}\n\n"
                                   "กรุณาลบไฟล์ในโฟลเดอร์ 'flags' ด้วยตนเอง")
        return count

    # =====================================================================

    def _stop_all_devices(self):
        """หยุดงานทุกอุปกรณ์ที่กำลังรันอยู่"""
        try:
            if not hasattr(self, "device_procs"):
                return
            for serial, info in list(self.device_procs.items()):
                p = info.get("p")
                if not p:
                    continue
                try:
                    if p.poll() is None:
                        p.terminate()
                except:
                    pass
                try:
                    if p.poll() is None:
                        p.kill()
                except:
                    pass

            if hasattr(self, "device_states"):
                for s in self.device_states:
                    try:
                        self.device_states[s]["status"] = "idle"
                        self.device_states[s]["process"] = None
                    except:
                        pass

            if hasattr(self, "_update_buttons_ui_all"):
                self._update_buttons_ui_all()

        except Exception as e:
            print("ERROR _stop_all_devices:", e)
    
    #---------------------------------
    def _pause_device(self, serial: str):
        """Cooperative pause: สร้าง flags/{serial}.pause และอัปเดตสถานะ (ไม่แตะ .stop)"""
        try:
            from pathlib import Path
            flags_dir = Path("flags")
            flags_dir.mkdir(parents=True, exist_ok=True)
            pause_file = flags_dir / f"{serial}.pause"
            pause_file.write_text("1")
            # update device_states
            if hasattr(self, "device_states") and serial in self.device_states:
                try:
                    self.device_states[serial]["status"] = "paused"
                    # do NOT set process = None; just mark paused
                except Exception:
                    pass
            # update UI on main thread
            try:
                self.after(0, self._update_buttons_ui, serial, "paused")
            except Exception:
                pass
        except Exception as e:
            print("ERROR in _pause_device:", e)

    def _resume_device(self, serial: str):
        """Cooperative resume: ลบ flags/{serial}.pause และอัปเดตสถานะ"""
        try:
            from pathlib import Path
            pause_file = Path("flags") / f"{serial}.pause"
            if pause_file.exists():
                try:
                    pause_file.unlink()
                except Exception:
                    pass
            if hasattr(self, "device_states") and serial in self.device_states:
                try:
                    self.device_states[serial]["status"] = "running"
                except Exception:
                    pass
            try:
                self.after(0, self._update_buttons_ui, serial, "running")
            except Exception:
                pass
        except Exception as e:
            print("ERROR in _resume_device:", e)

    #---------------------------------
    

    def _update_buttons_ui(self, serial: str, status: str):
        """อัปเดต UI ปุ่ม Pause/Resume สำหรับเครื่องเดียว"""
        if not hasattr(self, "device_buttons"):
            return

        btns = self.device_buttons.get(serial, {})
        if not isinstance(btns, dict):
            return

        if "pause" in btns:
            try:
                if status == "paused":
                    btns["pause"].config(text="▶ ทำงานต่อ")
                else:
                    btns["pause"].config(text="⏸ หยุดชั่วคราว")
            except:
                pass

    def _update_buttons_ui_all(self):
        """อัปเดต UI ปุ่มทุกเครื่อง"""
        if not hasattr(self, "device_states"):
            return
        for serial, st in self.device_states.items():
            try:
                self._update_buttons_ui(serial, st.get("status", "idle"))
            except:
                pass

    # =====================================================================


    # =====================================================================


    def create_widgets(self):
        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.nb = ttk.Notebook(self.main_frame)
        self.nb.pack(fill=tk.BOTH, expand=True)

        self.tab_config = ttk.Frame(self.nb)
        #self.tab_flow = ttk.Frame(self.nb)
        # หลัง setup_flow_tab() และ _refresh_flow_profiles() เรียบร้อย
        #self.after(300, self._load_flow_profile)  # จะโหลดโปรไฟล์ที่ถูกเลือกใน combobox ทันที
        self.tab_compile = ttk.Frame(self.nb)
        self.tab_ai = ttk.Frame(self.nb)
        #self.tab_log = ttk.Frame(self.nb)
        # แท็บใหม่: ตั้งค่า (Setup)
        self.tab_setup = ttk.Frame(self.nb)
        # --- เพิ่มแท็บอุปกรณ์ (Dynamic Tabs per Device) ---
        self.tab_devices = ttk.Frame(self.nb)
        self.nb.add(self.tab_devices, text="มือถือ")
        self.setup_devices_tab()


        self.nb.add(self.tab_ai, text="AI🤖Caption")
        #self.nb.add(self.tab_log, text="ล็อก")

        #self.setup_flow_tab()
        self.setup_ai_tab()
        #self.setup_log_tab()
        self.status_bar = ttk.Frame(self.main_frame)
        self.status_bar.pack(fill=tk.X, pady=(5, 0))
        self.status_label = ttk.Label(self.status_bar, text="สถานะ: พร้อมใช้งาน")
        self.status_label.pack(side=tk.LEFT)

        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))


        self.post_status_var = tk.StringVar(value="(โพสต์วันนี้.0 | กำลังโพสต์.0)")
        self.posts_today = 0
        self.posts_in_progress = 0
        self._load_post_counter()
        self._update_post_status()
        self.posts_label = ttk.Label(btn_frame, textvariable=self.post_status_var)
        self.posts_label.pack(side=tk.LEFT, padx=10)

        self.device_status_label = ttk.Label(btn_frame, textvariable=self.device_status_var)
        self.device_status_label.pack(side=tk.LEFT, padx=10)
        # ----------------------------------------------------------------------

    # ================== Dynamic Tabs per Device (STEP 1) ==================
    def setup_devices_tab(self):
        """แท็บ 'อุปกรณ์' : ปุ่มตรวจอุปกรณ์ + Notebook สำหรับแท็บย่อย per-device"""
        root = ttk.Frame(self.tab_devices, padding=10)
        root.pack(fill="both", expand=True)

        # แถวบน
        top = ttk.Frame(root)
        top.pack(fill="x")
        # --- ปุ่ม Resize/Reset Screen (ทุกเครื่อง) ---
        ttk.Button(top, text="📱 Resize all screen", command=self._resize_all_screens).pack(side="left", padx=4)
        ttk.Button(top, text="♻️ Reset all screen", command=self._reset_all_screens).pack(side="left", padx=4)
        ttk.Button(top, text="🪞 Mirror all screens", command=self._mirror_all_screens).pack(side="left", padx=4)
        # ใน def setup_devices_tab(self):

        ttk.Button(top, text="🛑 Close all mirrors", command=self._close_all_mirrors).pack(side="left", padx=4)
        # (บรรทัด 282)
        ttk.Button(top, text="🔄 ตรวจอุปกรณ์ (ADB)", command=self._start_refresh_devices_thread).pack(side="left")

        ttk.Button(top, text="🚀 รันทั้งหมด (Run All)", style="Shopee.TButton",
                   command=self._run_all_devices).pack(side="left", padx=6)
        # [NEW] ปุ่ม AUTOBOT ALL
        ttk.Button(top, text="🤖 AUTOBOT ALL", style="Shopee.TButton",
                   command=self._run_autobot_all_devices).pack(side="left", padx=6)
        # (ปุ่ม Stop All ถ้ายังไม่มีบนแถว top ก็เพิ่ม)
        ttk.Button(top, text="⛔ หยุดทั้งหมด", command=self._stop_all_devices).pack(side="left", padx=6)

        self.lbl_dev_status = ttk.Label(top, text="ยังไม่ได้ตรวจอุปกรณ์")
        self.lbl_dev_status.pack(side="left", padx=10)

        # Notebook สำหรับแท็บย่อย
        self.nb_devices = ttk.Notebook(root)
        self.nb_devices.pack(fill="both", expand=True, pady=(8, 0))

        # โครงสร้างเก็บค่า
        self.device_tabs = {}
        self.device_vars = {}
        self.device_log_widgets = {}  # serial -> Text widget (log เฉพาะเครื่อง)
        self.device_log_queues = {}  # serial -> queue.Queue() สำหรับข้อความจาก thread
        self.device_procs = {}  # serial -> {"p": Popen, "log_path": str, "fh": file_handle}
    #--------ปุ่ม Adb devices---------------------------
    def _find_adb_path(self) -> str:
        """
        หา adb.exe จากค่า per-device ถ้ามี — เอาอันแรกที่ไม่ว่าง
        ถ้าไม่เจอ ให้ fallback เป็น 'adb' (ต้องอยู่ใน PATH)
        """
        try:
            for serial, vars_ in getattr(self, "device_vars", {}).items():
                p = (vars_.get("adb_path").get() or "").strip()
                if p:
                    return p
        except Exception:
            pass
        return "adb"
    #---------------------------------------------------
    # ⬇️⬇️⬇️ เพิ่มฟังก์ชันใหม่นี้ (ก่อน _refresh_devices) ⬇️⬇️⬇️
    def _start_refresh_devices_thread(self):
        """
        [ฟังก์ชันใหม่] เริ่ม Thread สำหรับ _refresh_devices เพื่อป้องกัน UI ค้าง
        """
        self._append_global("[ADB] 🔄 กำลังเริ่มตรวจสอบอุปกรณ์ (ใน Thread)...")
        # (คุณสามารถเพิ่มตัวแปร self.is_refreshing = True เพื่อป้องกันการกดซ้ำได้)
        threading.Thread(target=self._refresh_devices, daemon=True).start()

    # (โค้ด def _refresh_devices(self): เดิมอยู่ต่อจากตรงนี้)

    # (โค้ด def _refresh_devices(self): เดิมอยู่ต่อจากตรงนี้)
    #--------------------------------------------------------
    # ⬇️⬇️⬇️ วางโค้ด 3 ฟังก์ชันนี้ (ตั้งแต่บรรทัด 290 เป็นต้นไป) ⬇️⬇️⬇️

    def _start_refresh_devices_thread(self):
        """
        [ฟังก์ชันใหม่] เริ่ม Thread สำหรับ _refresh_devices เพื่อป้องกัน UI ค้าง
        """
        self._append_global("[ADB] 🔄 กำลังเริ่มตรวจสอบอุปกรณ์ (ใน Thread)...")
        threading.Thread(target=self._refresh_devices, daemon=True).start()

    def _refresh_devices(self):
        """
        ตรวจ/เชื่อมต่อ ADB อัตโนมัติ (รันใน Thread แยก)
        """
        import subprocess, time, os

        # Helper function เพื่อส่งงานกลับไปที่ UI Thread
        def ui_update(callback):
            try:
                self.after(0, callback)
            except Exception as e:
                pass # (ป้องกัน error ตอนปิดโปรแกรม)

        adb = self._find_adb_path()
        ui_update(lambda: self._append_global(f"[ADB] ใช้: {adb}"))

        # 1) ❗️❗️ ฆ่า Server เก่า (ตามที่คุณต้องการ) ❗️❗️
        for cmd in ([adb, "kill-server"], [adb, "start-server"]):
            try:
                out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=10)
                msg = (out.stdout or out.stderr or "").strip()
                if msg:
                    ui_update(lambda m=msg, c=cmd: self._append_global(f"[ADB] {' '.join(c[1:])} -> {m}"))
            except Exception as e:
                ui_update(lambda e=e, c=cmd: self._append_global(f"[ADB] ERROR {' '.join(c[1:])}: {e}"))

        time.sleep(0.2) # รอ Server สักครู่

        # 2) list devices
        try:
            out = subprocess.run([adb, "devices"], capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=10)
            lines = (out.stdout or "").splitlines()
            serials = []
            for ln in lines:
                ln = ln.strip()
                if "\tdevice" in ln:
                    serials.append(ln.split("\t")[0])

            if not serials:
                ui_update(lambda: self._append_global("[ADB] ไม่พบอุปกรณ์ (กรุณาเชื่อมต่อ USB และอนุญาตในมือถือ)"))
                ui_update(lambda: self.lbl_dev_status.config(text="ไม่พบอุปกรณ์"))
                # (แสดง Popup เตือน - ทำงานใน UI Thread)
                ui_update(lambda: messagebox.showwarning("ไม่พบอุปกรณ์", "ไม่พบอุปกรณ์ที่เชื่อมต่อ (สถานะ: device)\nกรุณาตรวจสอบสาย USB และการอนุญาต (RSA) บนหน้าจอมือถือ"))
                return

            ui_update(lambda: self._append_global(f"[ADB] พบอุปกรณ์ {len(serials)} เครื่อง: {', '.join(serials)}"))
            ui_update(lambda: self.lbl_dev_status.config(text=f"พบอุปกรณ์ {len(serials)} เครื่อง"))

            # 3) สร้าง/อัปเดตแท็บอุปกรณ์ (ต้องทำใน UI Thread)
            for s in serials:
                ui_update(lambda s=s: self._create_or_update_device_tab_ui(s))

        except Exception as e:
            ui_update(lambda e=e: self._append_global(f"[ADB] ERROR devices: {e}"))
            ui_update(lambda: self.lbl_dev_status.config(text="ADB Error (devices)"))


    # ⬆️⬆️⬆️ สิ้นสุดโค้ด 3 ฟังก์ชันที่นำมาวางแทนที่ ⬆️⬆️⬆️
    def get_checked_devices(self) -> list:
        """
        คืน list ของ serial ที่ Checkbox 'selected' ถูกติ๊ก
        """
        serials = []
        for serial, vars_map in self.device_vars.items():
            try:
                sel_var = vars_map.get("selected")
                if sel_var and getattr(sel_var, "get", None) and sel_var.get():
                    serials.append(serial)
            except Exception as e:
                print(f"Error ใน get_checked_devices (serial={serial}): {e}")
        return serials
    #--------------------------------------------------
    # ----------------- START: Autobot subprocess helpers -----------------
    import subprocess, threading, json, os, sys, signal, time

    def _build_device_cfg(self, serial: str) -> dict:
        """
        สร้าง dict config จาก self.device_vars[serial]
        เรียกก่อนส่งเป็น --config_data ให้ autobot.py
        """
        vars_map = self.device_vars.get(serial)
        if not vars_map:
            return {}
        # สร้าง dict จาก vars_map (ดึงค่า .get() ของ tk.Variables)
        cfg = {}
        for k, v in vars_map.items():
            try:
                # ถ้าว่าเป็น tk.Variable ให้ .get() แล้วใช้ value
                if hasattr(v, "get"):
                    cfg[k] = v.get()
                else:
                    cfg[k] = v
            except Exception:
                cfg[k] = v
        # ยืนยัน device_id เป็น serial ที่สะอาด
        cfg["device_id"] = cfg.get("device_id", serial).strip()
        return cfg

    def _start_autobot_subprocess(self, serial: str):
        """
        เริ่ม subprocess ของ autobot (python -u) และอ่าน stdout มาที่ UI
        บันทึก proc ลง self.device_states[serial]['process']
        """
        # ถ้ามี process เดิมอยู่ ให้แจ้ง/ข้าม
        state = self.device_states.get(serial, {})
        proc = state.get("process")
        if proc and getattr(proc, "poll", None) is None:
            # ยังรันอยู่
            self._append_to_device_log(serial,
                                       f"[UI] พบ Autobot process เดิม (pid={getattr(proc, 'pid', '?')}), จะไม่ start ใหม่\n")
            return

        # สร้าง cfg และ command
        cfg = self._build_device_cfg(serial)
        config_str = json.dumps(cfg, ensure_ascii=False)
        python_exe = sys.executable or "python"
        cmd = [python_exe, "-u", "autobot.py", "--config_data", config_str]

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        try:
            newproc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True,
                env=env,
                creationflags=0  # windows: could add CREATE_NEW_PROCESS_GROUP if needed
            )
        except Exception as e:
            self._append_to_device_log(serial, f"[UI ERROR] ไม่สามารถเริ่ม Autobot: {e}\n")
            return

        # เก็บ proc ใน state
        state["process"] = newproc
        self.device_states[serial] = state

        # log และ start reader thread
        self._append_to_device_log(serial, f"[UI] เริ่ม Autobot (pid={newproc.pid})\n")
        t = threading.Thread(target=self._read_process_stdout_thread, args=(serial, newproc), daemon=True)
        t.start()

    def _read_process_stdout_thread(self, serial: str, proc: subprocess.Popen):
        """
        อ่าน stdout ของ subprocess และ append เข้า UI Text (ใช้ .after)
        """
        try:
            for line in proc.stdout:
                if line is None:
                    continue
                # ส่งขึ้น UI thread
                try:
                    self.after(0, lambda ln=line: self._append_to_device_log(serial, ln))
                except Exception:
                    # fallback: print
                    print(f"[{serial}] {line}", end="")
        except Exception as e:
            self.after(0, lambda: self._append_to_device_log(serial, f"[UI read error] {e}\n"))
        finally:
            try:
                proc.stdout.close()
            except Exception:
                pass
            rc = proc.poll()
            # อัพเดต state หลัง process จบ
            s = self.device_states.get(serial, {})
            s["process"] = None
            self.device_states[serial] = s
            self.after(0,
                       lambda: self._append_to_device_log(serial, f"[UI] Autobot process exited (returncode={rc})\n"))

    def _append_to_device_log(self, serial: str, text: str):
        """
        แทรกข้อความเข้า Text widget ของ device (thread-safe ผ่าน .after)
        """
        try:
            txt = self.device_log_widgets.get(serial)
            if not txt:
                # ถ้าไม่มี widget สำหรับ device ให้ fallback พิมพ์ console
                print(f"[{serial}] {text}", end="")
                return
            # ใช้ .after() เพื่อ thread-safe
            self.after(0, txt.insert, "end", text)
            self.after(0, txt.see, "end")
        except Exception as e:
            print(f"[append_to_device_log error] {e}")

    def _stop_device_process(self, serial: str, force_kill_after: int = 3):
        """
        หยุด Autobot ของ device:
        1) สร้าง flags/{serial}.stop เพื่อให้ Autobot ที่ตรวจ flag ออกอย่างสุภาพ
        2) ถ้าหลังเวลาหน่วงยังไม่หยุด ให้ terminate/kill process ที่ UI spawn
        """
        # (1) สร้าง flag
        try:
            flags_dir = Path("flags")
            flags_dir.mkdir(parents=True, exist_ok=True)
            stop_flag = flags_dir / f"{serial}.stop"
            stop_flag.write_text("stop")
            self._append_to_device_log(serial, f"[UI] เขียน flags/{serial}.stop เพื่อสั่ง Autobot ให้หยุด\n")
        except Exception as e:
            self._append_to_device_log(serial, f"[UI ERROR] ไม่สามารถเขียน stop flag: {e}\n")

        # (2) ถ้ามี process ที่ spawn โดย UI ให้พยายาม terminate
        state = self.device_states.get(serial, {})
        proc = state.get("process")
        if proc:
            try:
                if proc.poll() is None:
                    self._append_to_device_log(serial, f"[UI] พยายาม terminate pid={proc.pid} ...\n")
                    # พยายามส่ง gentle terminate
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    # รอคร่าว ๆ
                    t0 = time.time()
                    while proc.poll() is None and (time.time() - t0) < force_kill_after:
                        time.sleep(0.2)
                    if proc.poll() is None:
                        self._append_to_device_log(serial, f"[UI] terminate ไม่สำเร็จ กำลัง kill pid={proc.pid}\n")
                        try:
                            proc.kill()
                        except Exception:
                            pass
                    self._append_to_device_log(serial, f"[UI] process pid={proc.pid} now exit code={proc.poll()}\n")
            except Exception as e:
                self._append_to_device_log(serial, f"[UI ERROR] ขณะหยุด process: {e}\n")
        else:
            self._append_to_device_log(serial,
                                       "[UI] ไม่พบ process ที่ spawn โดย UI (อาจเป็น process แยกที่ start ก่อนหน้านี้)\n")

    # ----------------- END: Autobot subprocess helpers -----------------

    #------------------------------------------
    def _create_or_update_device_tab_ui(self, serial: str):
        """
        [ฟังก์ชันใหม่] (UI Thread) สร้างแท็บอุปกรณ์ถ้ายังไม่มี หรืออัปเดตถ้ามีแล้ว
        """
        try:
            if serial not in self.device_tabs:
                self._create_device_tab(serial) # สร้าง UI

            # เติมค่า device_id ถ้าว่าง (Safe to do again)
            v = self.device_vars[serial]["device_id"]
            if not (v.get() or "").strip():
                v.set(serial)

            # แจ้งใน log ของเครื่อง
            if serial in self.device_log_widgets:
                self.device_log_widgets[serial].insert("end", f"[ADB] Connected (Refreshed): {serial}\n")
                self.device_log_widgets[serial].see("end")
        except Exception as e:
            # (ป้องกัน Error หาก UI ปิดไปแล้ว)
            print(f"[UI Thread] Error creating tab for {serial}: {e}")

    # (ฟังก์ชัน _append_global เดิมอยู่ต่อจากตรงนี้)
    #--helper เขียน ล๊อก--------------------------------------------------------------
    def _append_global(self, text: str):
        if hasattr(self, "global_log_text"):
            self.global_log_text.insert("end", text + "\n")
            self.global_log_text.see("end")

    # ================== STEP 2: Run Buttons & Parallel Runner ==================
    
    #----------------------------------------------------------------------
    def _create_device_tab(self, serial: str):
        """
        สร้างแท็บย่อยสำหรับอุปกรณ์หนึ่งเครื่อง และผูกตัวแปร UI
        เวอร์ชันนี้ปลอดภัย: ใช้ local buttons, สร้าง device_buttons ก่อน device_states,
        และตรวจ/สร้าง dict container ถ้ายังไม่มี
        """
        # ปลอดภัย: trim serial
        serial = (serial or "").strip()

        # ตรวจ/สร้าง containers ถ้ายังไม่มี (safety)
        if not hasattr(self, "device_vars") or self.device_vars is None:
            self.device_vars = {}
        if not hasattr(self, "device_buttons") or self.device_buttons is None:
            self.device_buttons = {}
        if not hasattr(self, "device_states") or self.device_states is None:
            self.device_states = {}
        if not hasattr(self, "device_log_widgets") or self.device_log_widgets is None:
            self.device_log_widgets = {}

        # --- สร้าง tab ---
        tab = ttk.Frame(self.nb_devices, padding=10)
        self.nb_devices.add(tab, text=serial)
        self.device_tabs[serial] = tab

        # ---- ประกาศ vars_map per-device ----
        def _get(varname, default=""):
            # หากคุณยังอยากใช้ getattr(self, varname) จาก GUI หลัก ให้คืนค่า; ถ้าไม่มีก็ default
            val = getattr(self, varname).get().strip() if hasattr(self, varname) else default
            return val

        vars_map = {
            "device_id": tk.StringVar(value=serial),
            "adb_path": tk.StringVar(value="D:/Shopee/usb_driver/adb.exe"),
            "app_package": tk.StringVar(value="com.shopee.th"),
            "local_videos_dir": tk.StringVar(value="D:/Shopee/videos/somjane"),
            "device_video_dir": tk.StringVar(value="/sdcard/Movies/shopee_uploads"),
            "max_posts": tk.IntVar(value=20),
            "delay_between_posts": tk.DoubleVar(value=40.0),
            "post_push_wait_s": tk.DoubleVar(value=7.0),
            "captions_csv": tk.StringVar(value="captions.csv"),
            "autobot_loops": tk.StringVar(value="90"),
            "steps_yaml": tk.StringVar(value="steps.yaml"),
            "autobot_mode": tk.StringVar(value="Affiliate Link"),
            "adb_connection": tk.StringVar(value="usb"),
            "autobot_steps_yaml": tk.StringVar(value="autobot_steps.yaml"),
            "status_var": tk.StringVar(value="Temp: - | CPU: - | RAM: -"),
            "post_count_var": tk.StringVar(value="โพสต์วันนี้: 0"),
            "template_folder": tk.StringVar(value="D:/Shopee/templates"),
            "fast_media_index": tk.BooleanVar(value=True),
            "selected": tk.BooleanVar(value=False),
        }

        # เก็บ vars_map
        self.device_vars[serial] = vars_map

        # ---- Layout widgets (ตามของเดิม โดยย่อ/รักษา layout) ----
        row = 0
        ttk.Label(tab, text="Device ID:").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        ttk.Entry(tab, textvariable=vars_map["device_id"], state="readonly").grid(row=row, column=1, sticky="ew",
                                                                                  padx=5, pady=5)

        # Checkbox สำหรับ Run All / Autobot All
        chk = ttk.Checkbutton(tab, text="เลือก", variable=vars_map["selected"])
        chk.grid(row=0, column=4, sticky="w", padx=5)

        ttk.Label(tab, text="ADB Path:").grid(row=row, column=2, sticky="e", padx=5, pady=5)
        ttk.Entry(tab, textvariable=vars_map["adb_path"]).grid(row=row, column=3, sticky="ew", padx=5, pady=5)

        row += 1
        ttk.Label(tab, text="App Package:").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        ttk.Entry(tab, textvariable=vars_map["app_package"]).grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        ttk.Label(tab, text="Device Video Dir:").grid(row=row, column=2, sticky="e", padx=5, pady=5)
        ttk.Entry(tab, textvariable=vars_map["device_video_dir"]).grid(row=row, column=3, sticky="ew", padx=5, pady=5)

        # AUTOBOT frame (ตามของคุณ)
        row += 1
        autobot_frame = ttk.LabelFrame(tab, text="สำหรับตั้งค่า🤖 โหมด AUTOBOT เท่านั้น")
        autobot_frame.grid(row=row, column=0, columnspan=4, sticky="ew", padx=5, pady=(5, 10))
        autobot_frame.columnconfigure(1, weight=1)

        ttk.Label(autobot_frame, text="โหมด/กลยุทธ์:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        mode_options = ["Affiliate Link", "Cart Link", "Random Product"]
        ttk.Combobox(autobot_frame, textvariable=vars_map["autobot_mode"],
                     values=mode_options, state="readonly").grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        ttk.Label(autobot_frame, text="จำนวนโพสต์สูงสุด:").grid(row=0, column=2, sticky="e", padx=(10, 5), pady=5)
        ttk.Spinbox(autobot_frame, from_=1, to=90, textvariable=vars_map["autobot_loops"], width=8).grid(
            row=0, column=3, sticky="w", padx=5, pady=5)

        # Local videos and captions
        row += 1
        ttk.Label(tab, text="Local Videos Dir:").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        ttk.Entry(tab, textvariable=vars_map["local_videos_dir"]).grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(tab, text="เลือกโฟลเดอร์วิดีโอ (PC)",
                   command=lambda s=serial: self._browse_dir_for_device(s, "local_videos_dir")).grid(
            row=row, column=1, sticky="e", padx=5, pady=5
        )
        ttk.Entry(tab, textvariable=vars_map["captions_csv"]).grid(row=row, column=3, sticky="ew", padx=5, pady=5)
        ttk.Button(tab, text="เลือก captions.csv",
                   command=lambda s=serial: self._browse_file_for_device(s, "captions_csv",
                                                                         [("CSV files", "*.csv"), ("All files", "*.*")])
                   ).grid(row=row, column=3, sticky="e", padx=5, pady=5)
        ttk.Label(tab, text="Captions CSV:").grid(row=row, column=2, sticky="e", padx=5, pady=5)

        row += 1
        ttk.Label(tab, text="โฟลเดอร์เทมเพลต (PC):").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        ttk.Entry(tab, textvariable=vars_map["template_folder"]).grid(row=row, column=1, sticky="ew", padx=5, pady=5,
                                                                      columnspan=3)
        ttk.Button(tab, text="เลือก...",
                   command=lambda s=serial: self._browse_dir_for_device(s, "template_folder")).grid(row=row, column=3,
                                                                                                    sticky="e", padx=5)

        row += 1
        ttk.Label(tab, text="Steps YAML:").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        ttk.Entry(tab, textvariable=vars_map["steps_yaml"]).grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(tab, text="เลือก steps.yaml",
                   command=lambda s=serial: self._browse_file_for_device(s, "steps_yaml",
                                                                         [("YAML files", "*.yaml *.yml"),
                                                                          ("All files", "*.*")])
                   ).grid(row=row, column=1, sticky="e", padx=5, pady=5)

        ttk.Label(tab, text="Steps YAML (AUTOBOT):").grid(row=row, column=2, sticky="e", padx=5, pady=5)
        ttk.Entry(tab, textvariable=vars_map["autobot_steps_yaml"]).grid(row=row, column=3, sticky="ew", padx=5, pady=5)
        ttk.Button(tab, text="เลือก...", command=lambda s=serial: self._browse_file_for_device(s, "autobot_steps_yaml",
                                                                                               [("YAML",
                                                                                                 "*.yaml *.yml")])
                   ).grid(row=row, column=3, sticky="e", padx=5)

        row += 1
        ttk.Label(tab, text="จำนวนโพสต์สูงสุด:").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        ttk.Spinbox(tab, from_=1, to=300, textvariable=vars_map["max_posts"], width=8).grid(row=row, column=1,
                                                                                            sticky="w", padx=5, pady=5)
        ttk.Label(tab, text="ดีเลย์ระหว่างโพสต์ (s):").grid(row=row, column=2, sticky="e", padx=5, pady=5)
        ttk.Spinbox(tab, from_=0, to=99, increment=0.5, textvariable=vars_map["delay_between_posts"], width=8).grid(
            row=row, column=3, sticky="w", padx=5, pady=5)

        row += 1
        ttk.Label(tab, text="ดีเลย์หลัง Push (s):").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        ttk.Spinbox(tab, from_=0, to=99, increment=0.5, textvariable=vars_map["post_push_wait_s"], width=8).grid(
            row=row, column=1, sticky="w", padx=5, pady=5)

        ttk.Checkbutton(tab, text="โหมดเร็ว (Index)", variable=vars_map["fast_media_index"]).grid(
            row=row, column=1, sticky="e", padx=(0, 10), pady=5)

        ttk.Label(tab, text="สถานะเครื่อง:").grid(row=row, column=2, sticky="e", padx=5, pady=5)
        ttk.Label(tab, textvariable=vars_map["status_var"], foreground="#007BFF", width=25).grid(
            row=row, column=3, sticky="w", padx=5, pady=5)

        row += 1
        ttk.Label(tab, text="สถานะโพสต์ (เครื่องนี้):").grid(row=row, column=0, sticky="e", padx=5, pady=5)
        ttk.Label(tab, textvariable=vars_map["post_count_var"], foreground="green").grid(
            row=row, column=1, sticky="w", padx=5, pady=5)

        # Separator + run buttons
        run_row = row + 1
        ttk.Separator(tab, orient="horizontal").grid(row=run_row, column=0, columnspan=4, sticky="ew", pady=10)
        run_buttons_row = run_row + 1

        # ปุ่ม AUTOBOT (per-device) และ Run Single (per-device)
        btn_autobot = ttk.Button(tab, text=f"🤖 AUTOBOT ({serial})",
                                 style="Shopee.TButton",
                                 command=lambda s=serial: self._run_autobot_single_device(s))
        btn_autobot.grid(row=run_buttons_row, column=0, columnspan=2, sticky="ew", padx=(5, 2), pady=(0, 5))

        btn_run_single = ttk.Button(tab, text=f"▶ รันเฉพาะเครื่องนี้ ({serial})",
                                    command=lambda s=serial: self._run_single_device(s))
        btn_run_single.grid(row=run_buttons_row, column=2, columnspan=2, sticky="ew", padx=(2, 5), pady=(0, 5))

        # control buttons frame (local)
        control_row = run_buttons_row + 1
        control_frame = ttk.Frame(tab)
        control_frame.grid(row=control_row, column=0, columnspan=4, sticky="ew", padx=0, pady=0)
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)
        control_frame.columnconfigure(2, weight=1)

        # สร้างปุ่มเป็น local variables (ไม่ใช้ self.btn_*)
        pause_btn = ttk.Button(control_frame, text="⏸ หยุดชั่วคราว", command=lambda s=serial: self._pause_device(s))
        pause_btn.grid(row=0, column=0, sticky="ew", padx=(5, 2), pady=(0, 5))

        resume_btn = ttk.Button(control_frame, text="▶ ทำงานต่อ", command=lambda s=serial: self._resume_device(s))
        resume_btn.grid(row=0, column=1, sticky="ew", padx=2, pady=(0, 5))

        stop_btn = ttk.Button(control_frame, text="⛔ หยุดเครื่องนี้", command=lambda s=serial: self._stop_device(s))
        stop_btn.grid(row=0, column=2, sticky="ew", padx=(2, 5), pady=(0, 5))

        # Log area
        log_row = control_row + 1
        lf = ttk.LabelFrame(tab, text=f"Log ของเครื่อง {serial} (Realtime)")
        lf.grid(row=log_row, column=0, columnspan=4, sticky="nsew", padx=0, pady=(0, 5))
        tab.rowconfigure(log_row, weight=1)
        frm_log = ttk.Frame(lf)
        frm_log.pack(fill="both", expand=True)
        txt = tk.Text(frm_log, height=12, wrap="none")
        scroll_y = ttk.Scrollbar(frm_log, orient="vertical", command=txt.yview)
        scroll_x = ttk.Scrollbar(frm_log, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        txt.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")

        # เก็บ widget ไว้ใช้งาน
        self.device_log_widgets[serial] = txt

        for c in (1, 3):
            tab.columnconfigure(c, weight=1)

        # เก็บ mapping ปุ่ม (ต้องมาก่อนสร้าง device_states)
        self.device_buttons[serial] = {
            "pause": pause_btn,
            "resume": resume_btn,
            "stop": stop_btn,
            "run_auto": btn_autobot,
            "run_single": btn_run_single
        }

        # สร้าง device_states (อ้าง vars_map และ device_buttons ที่มีแล้ว)
        self.device_states[serial] = {
            'process': None,
            'status': 'idle',
            'buttons': self.device_buttons[serial],
            'vars': vars_map,
            'log_widget': txt
        }

    #-------------------END---------------------
    def on_app_close(self):
        """
        เรียกก่อนปิด UI: เขียน stop flag ให้ทุก device และพยายาม kill proc ที่ spawn
        """
        for serial in list(self.device_states.keys()):
            try:
                self._append_to_device_log(serial, "[UI] การปิด UI: สั่ง STOP ให้ Autobot\n")
                # สร้าง flag และ kill proc ถ้ามี
                self._stop_device_process(serial, force_kill_after=2)
            except Exception as e:
                print(f"Error stopping {serial}: {e}")
        # หลัง cleanup ให้ปิดหน้าต่างจริง ๆ
        try:
            self.destroy()
        except Exception:
            pass

    # โค้ดที่เพิ่ม (แทรกก่อน def _run_single_device(self, serial: str):)
    def _run_autobot_single_device(self, serial):
        """(แก้ไข) รัน Autobot เดี่ยว: รวบรวม cfg และส่งต่อ"""
        print(f"[{serial}] User clicked 'Autobot Single'")
        
        # (1. เคลียร์ Flag)
        try:
            flag_stop = self._get_flag_path(serial, "stop"); flag_pause = self._get_flag_path(serial, "pause")
            if flag_stop.exists(): flag_stop.unlink(); print(f"[{serial}] เคลียร์ .stop flag เก่า")
            if flag_pause.exists(): flag_pause.unlink(); print(f"[{serial}] เคลียร์ .pause flag เก่า")
        except Exception as e:
            messagebox.showerror("Error", f"[{serial}] ไม่สามารถลบ flag: {e}"); return

        # (2. [ใหม่] รวบรวม Config)
        cfg = self._collect_device_config(serial)
        if not cfg: return
        cfg['run_mode'] = 'AUTOBOT' # (ตั้งโหมด)
        
        # (3. [ใหม่] ส่ง 'cfg' ไปให้ Wrapper)
        self._run_bot_wrapper(serial, "AUTOBOT", cfg)
        self._append_to_device_log(serial, "[UI] เรียก Autobot (subprocess) ...\n")
        self._start_autobot_subprocess(serial)
#------------------------------------------------
    def _run_autobot_all_devices(self):
        """(แก้ไข) รัน Autobot All: วนลูป รวบรวม cfg และส่งต่อ"""
        serials = self.get_checked_devices() 
        if not serials:
            messagebox.showwarning("ไม่ได้เลือก", "กรุณาเลือกอุปกรณ์ที่ต้องการรัน")
            return
            
        for serial in serials:
            # (1. เคลียร์ Flag)
            try:
                flag_stop = self._get_flag_path(serial, "stop"); flag_pause = self._get_flag_path(serial, "pause")
                if flag_stop.exists(): flag_stop.unlink(); print(f"[{serial}] เคลียร์ .stop flag เก่า")
                if flag_pause.exists(): flag_pause.unlink(); print(f"[{serial}] เคลียร์ .pause flag เก่า")
            except Exception as e:
                messagebox.showerror("Error", f"[{serial}] ไม่สามารถลบ flag: {e}"); continue
            
            # (2. [ใหม่] รวบรวม Config)
            cfg = self._collect_device_config(serial)
            if not cfg: continue
            cfg['run_mode'] = 'AUTOBOT'

            # (3. [ใหม่] ส่ง 'cfg' ไปให้ Wrapper)
            print(f"[{serial}] Autobot All starting...")
            self._run_bot_wrapper(serial, "AUTOBOT", cfg)

    #--เพิ่มต่อท้ายคลาส------------------------------
    def _run_single_device(self, serial):
        """(แก้ไข) รันเดี่ยว: รวบรวม cfg และส่งต่อ"""
        print(f"[{serial}] User clicked 'Run Single'")
        
        # (1. เคลียร์ Flag - โค้ดเดิมของคุณ)
        try:
            flag_stop = self._get_flag_path(serial, "stop"); flag_pause = self._get_flag_path(serial, "pause")
            if flag_stop.exists(): flag_stop.unlink(); print(f"[{serial}] เคลียร์ .stop flag เก่า")
            if flag_pause.exists(): flag_pause.unlink(); print(f"[{serial}] เคลียร์ .pause flag เก่า")
        except Exception as e:
            messagebox.showerror("Error", f"[{serial}] ไม่สามารถลบ flag: {e}"); return

        # (2. [ใหม่] รวบรวม Config)
        cfg = self._collect_device_config(serial)
        if not cfg: return # (ถ้าเก็บ Config ล้มเหลว)
        cfg['run_mode'] = 'NORMAL' # (ตั้งโหมด)

        # (3. [ใหม่] ส่ง 'cfg' ไปให้ Wrapper)
        self._run_bot_wrapper(serial, "NORMAL", cfg)
#------------------------------------
    def _run_all_devices(self):
        """(แก้ไข) รัน All: วนลูป รวบรวม cfg และส่งต่อ"""
        serials = self.get_checked_devices() 
        if not serials:
            messagebox.showwarning("ไม่ได้เลือก", "กรุณาเลือกอุปกรณ์ที่ต้องการรัน")
            return

        for serial in serials:
            # (1. เคลียร์ Flag)
            try:
                flag_stop = self._get_flag_path(serial, "stop"); flag_pause = self._get_flag_path(serial, "pause")
                if flag_stop.exists(): flag_stop.unlink(); print(f"[{serial}] เคลียร์ .stop flag เก่า")
                if flag_pause.exists(): flag_pause.unlink(); print(f"[{serial}] เคลียร์ .pause flag เก่า")
            except Exception as e:
                messagebox.showerror("Error", f"[{serial}] ไม่สามารถลบ flag: {e}"); continue
            
            # (2. [ใหม่] รวบรวม Config)
            cfg = self._collect_device_config(serial)
            if not cfg: continue # (ข้ามเครื่องนี้)
            cfg['run_mode'] = 'NORMAL'

            # (3. [ใหม่] ส่ง 'cfg' ไปให้ Wrapper)
            print(f"[{serial}] Run All starting...")
            self._run_bot_wrapper(serial, "NORMAL", cfg)
    #-----------------------------------
    # (วางใน class App)
    def _get_flag_path(self, device_id: str, flag_type: str = "stop") -> Path:
        """
        (ฟังก์ชันใหม่) สร้างและคืน path ของ flag
        เช่น ./flags/R52N619SH8J.stop หรือ .pause
        """
        flags_dir = Path("flags") # (สร้างโฟลเดอร์ flags/ ในโปรเจกต์)
        try:
            flags_dir.mkdir(exist_ok=True)
        except Exception as e:
            print(f"ไม่สามารถสร้างโฟลเดอร์ flags: {e}")
        return flags_dir / f"{device_id}.{flag_type}"
    
    #-----------------------------------
    def _start_bot_process(self, device_id: str, run_mode: str, cfg: dict):
        """
        (2) ตัวรันจริง: [รันใน Thread]
        (เวอร์ชันแก้ไข: "เลือก" สคริปต์ที่จะรันตาม run_mode + realtime log capture)
        """
        state = self.device_states[device_id]
        process = None
        import datetime
        
        try:
            # (1. สร้าง Config JSON)
            config_data = json.dumps(cfg, ensure_ascii=False)
            
        except Exception as e:
            msg = f"[{device_id}] สร้าง JSON config ล้มเหลว: {e}"
            print(msg)
            self._append_to_device_log(device_id, msg + "\n")
            self.after(0, self._update_buttons_ui, device_id, 'idle') 
            return

        # (เลือก script ตามโหมด)
        if run_mode == "AUTOBOT":
            script_to_run = "autobot.py"
        else:
            script_to_run = "bot.py"

        # (สร้าง command args)
        cmd_args = [
            sys.executable,  
            script_to_run,
            "--device", device_id,
            "--config_data", config_data 
        ]

        # (สร้าง log file)
        try:
            day = datetime.datetime.now().strftime("%Y-%m-%d")
            logs_dir = os.path.join(os.getcwd(), "logs", day)
            os.makedirs(logs_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%H%M%S")
            log_path = os.path.join(logs_dir, f"{device_id}_{run_mode}_{ts}.log")
        except Exception:
            log_path = None

        try:
            # (รันบอทกับการ capture realtime)
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            process = subprocess.Popen(
                cmd_args,
                creationflags=creation_flags, 
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # (รวม stderr เข้า stdout)
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                env=env
            )

            # (ลงทะเบียน process)
            state['process'] = process
            start_msg = f"[{device_id}] เริ่มบอท (PID: {process.pid}, Mode: {run_mode}, Script: {script_to_run})"
            print(start_msg)
            self._append_to_device_log(device_id, start_msg + "\n")
            
            # (ล็อก file ถ้ามี)
            if log_path:
                self._append_to_device_log(device_id, f"📝 เขียนล็อก: {log_path}\n")

            # (อ่าน stdout แบบ realtime + บันทึก log)
            log_file = None
            if log_path:
                try:
                    log_file = open(log_path, "w", encoding="utf-8", newline="")
                except Exception:
                    log_file = None

            while True:
                line = process.stdout.readline()
                if not line:
                    break
                
                # (บันทึกลง log file)
                if log_file:
                    try:
                        log_file.write(line)
                        log_file.flush()
                    except Exception:
                        pass
                
                # (แสดงใน UI widget)
                self._append_to_device_log(device_id, line)
                
                # (แสดงใน global log)
                try:
                    if hasattr(self, "global_log_text") and self.global_log_text:
                        self.after(0, self.global_log_text.insert, "end", f"[{device_id}] {line}")
                        self.after(0, self.global_log_text.see, "end")
                except Exception:
                    pass

            # (ปิด log file และรอ process จบ)
            if log_file:
                try:
                    log_file.close()
                except Exception:
                    pass
            
            return_code = process.wait() if process else -1
            end_msg = f"[{device_id}] โปรเซสจบการทำงาน (Code: {return_code}, Mode: {run_mode})"
            print(end_msg)
            self._append_to_device_log(device_id, end_msg + "\n")
            
            if return_code != 0:
                error_msg = f"⚠️ Bot จบด้วยสถานะผิดพลาด (exit code: {return_code})"
                self._append_to_device_log(device_id, error_msg + "\n")
                self.after(0, messagebox.showwarning, "Bot Exit", 
                          f"[{device_id}] จบการทำงาน (Code: {return_code})\n"
                          f"ตรวจสอบล็อกสำหรับรายละเอียด")

        except Exception as e:
            error_msg = f"[{device_id}] รันบอทล้มเหลว: {e}"
            print(error_msg)
            self._append_to_device_log(device_id, error_msg + "\n")
            self.after(0, messagebox.showerror, "รันล้มเหลว", f"{error_msg}")
            
        finally:
            # (รีเซ็ต state)
            state['process'] = None
            state['status'] = 'idle'
            self.after(0, self._update_buttons_ui, device_id, 'idle')
    
    #----------------------------------
    def _run_bot_wrapper(self, device_id: str, run_mode: str, cfg: dict):
        """
        (1) ตัวหุ้ม: [แก้ไข] รับ 'cfg' และส่งต่อให้ Thread
        """
        # (ส่วนเคลียร์ Flag ถูกย้ายไปที่ "ฟังก์ชันที่เรียก" แล้ว)

        # (2. ตรวจสอบสถานะ)
        state = self.device_states.get(device_id)
        if not state:
            print(f"[{device_id}] ไม่พบ state ใน device_states (ตอน spawn)")
            return
            
        if state['process'] is not None or state['status'] != 'idle':
            messagebox.showwarning("กำลังทำงาน", f"[{device_id}] กำลังทำงานอยู่ ไม่สามารถรันซ้ำ")
            return

        # (3. อัปเดต UI และเริ่มบอท)
        self._update_buttons_ui(device_id, 'running')
        state['status'] = 'running'

        threading.Thread(
            target=self._start_bot_process, 
            # ▼▼▼ [นี่คือจุดแก้ไข] ▼▼▼
            # (ส่ง 'cfg' ที่รับมา ไปให้ Thread)
            args=(device_id, run_mode, cfg), 
            # ▲▲▲ [จบจุดแก้ไข] ▲▲▲
            daemon=True
        ).start()
    #------------helper stop------------
    def _stop_device(self, serial: str, kill_process: bool = True):
        self._append_to_device_log(serial, f"[UI] User requested STOP for {serial}\n")
        self._stop_device_process(serial)
        """
        Cooperative stop for a single device:
        - create flags/{serial}.stop so bot's check_bot_signals() will raise StopRequestedException
        - optionally terminate the subprocess (Popen) to make stop immediate
        - update device_states and UI
        """
        try:
            from pathlib import Path
            flags_dir = Path("flags");
            flags_dir.mkdir(parents=True, exist_ok=True)
            stop_file = flags_dir / f"{serial}.stop"
            stop_file.write_text("1")
            print(f"[UI] stop flag created for {serial} by user action at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            # ... (rest of code)
            # Update state
            if hasattr(self, "device_states") and serial in self.device_states:
                try:
                    self.device_states[serial]["status"] = "stopped"
                except Exception:
                    pass

            # Try graceful terminate the process (if available)
            try:
                if hasattr(self, "device_procs") and serial in self.device_procs:
                    p = self.device_procs[serial].get("p")
                    if p:
                        try:
                            p.terminate()
                            time.sleep(0.4)
                        except Exception:
                            pass
                        if p.poll() is None and kill_process:
                            try:
                                p.kill()
                            except Exception:
                                pass
            except Exception:
                pass

            # UI update
            try:
                self.after(0, self._update_buttons_ui, serial, "stopped")
            except Exception:
                pass

            # Optionally call global updater
            try:
                if hasattr(self, "_update_buttons_ui_all"):
                    self._update_buttons_ui_all()
            except Exception:
                pass

            return True
        except Exception as e:
            print("ERROR in _stop_device:", e)
            return False


    def _clear_stop(self, serial: str):
        """
        Remove flags/{serial}.stop so device can be restarted without leftover stop flag.
        Useful for debugging / retrying.
        """
        try:
            from pathlib import Path
            stop_file = Path("flags") / f"{serial}.stop"
            if stop_file.exists():
                try:
                    stop_file.unlink()
                except Exception:
                    pass
            # if device_states exists, set to idle
            if hasattr(self, "device_states") and serial in self.device_states:
                try:
                    self.device_states[serial]["status"] = "idle"
                except Exception:
                    pass
            try:
                self.after(0, self._update_buttons_ui, serial, "idle")
            except Exception:
                pass
            return True
        except Exception as e:
            print("ERROR in _clear_stop:", e)
            return False

    #--------- หยุด----------------------
    #--------browse ปุ่ม--------
    def _browse_file_for_device(self, serial: str, key: str, filetypes):
        """เปิด file dialog แล้ว set ค่าเข้าสู่ self.device_vars[serial][key]"""
        try:
            path = filedialog.askopenfilename(title="เลือกไฟล์", filetypes=filetypes)
            if path:
                var = self.device_vars.get(serial, {}).get(key)
                if var:
                    var.set(path)
        except Exception as e:
            self._append_global(f"[Browse] ERROR: {e}")

    def _browse_dir_for_device(self, serial: str, key: str):
        """เปิด directory dialog แล้ว set ค่าเข้าสู่ self.device_vars[serial][key]"""
        try:
            path = filedialog.askdirectory(title="เลือกโฟลเดอร์")
            if path:
                var = self.device_vars.get(serial, {}).get(key)
                if var:
                    var.set(path)
        except Exception as e:
            self._append_global(f"[Browse] ERROR: {e}")

    # --- ใส่ในคลาส App (ใกล้ๆ _collect_device_config) ---
    def _build_steps_from_ui(self):
        steps = {}
        # steps คงที่จากตารางหลัก
        for key, (v_en, v_xy, v_dl) in getattr(self, "step_vars", {}).items():
            xy_str = (v_xy.get() or "").strip()
            xy = [int(p) for p in xy_str.split(",")] if xy_str else []
            delay = float(v_dl.get() or 0)
            steps[key] = {"enabled": bool(v_en.get()), "xy": xy, "delay_s": delay}
        # steps ที่ผู้ใช้เพิ่ม
        for row in getattr(self, "user_flow_rows", []):
            key = row["key"]
            xy_str = (row["xy_var"].get() or "").strip()
            xy = [int(p) for p in xy_str.split(",")] if xy_str else []
            delay = float(row["delay_var"].get() or 0)
            steps[key] = {"enabled": bool(row["enabled_var"].get()), "xy": xy, "delay_s": delay}

        # ลำดับที่ชัดเจน (กัน key order เพี้ยน)
        step_sequence = [
                            "tap_shopee_icon", "tap_live_video_menu", "tap_create_video", "tap_open_gallery",
                            "tap_pick_video", "tap_next1", "tap_next2", "tap_focus_caption", "tap_back_after_caption",
                            "tap_add_product_btn", "tap_add_link_btn", "tap_focus_link", "tap_back_after_link",
                            "tap_post_btn"
                        ] + [k for k in steps.keys() if k.startswith("user_step_")]
        return steps, step_sequence

    #------------------------------------------------------------------
    def _collect_device_config(self, serial: str) -> dict:
        """(แก้ไข) อ่านค่า config และแก้ Bug "steps_yaml" """
        vars_ = self.device_vars.get(serial)
        if not vars_:
            return {}

        # อ่านค่าจากตัวแปรในแท็บอุปกรณ์
        get = lambda key: (vars_.get(key).get() or "").strip() if vars_.get(key) else ""

        # (อ่านค่าอื่นๆ)
        device_id = get("device_id")
        adb_path = get("adb_path")
        app_package = get("app_package")
        local_videos_dir = get("local_videos_dir")
        device_video_dir = get("device_video_dir")
        captions_csv = get("captions_csv")
        adb_connection = (get("adb_connection") or "USB").upper()
        wifi_ip_port = get("wifi_ip_port")

        # ▼▼▼ (นี่คือการแก้ไข Bug ที่สำคัญที่สุด) ▼▼▼
        # (1) แก้ key จาก "steps.yaml" เป็น "steps_yaml" (ไม่มีจุด)
        # (2) ลบ fallback "config.yaml" ทิ้ง ให้เป็น "" (ว่าง)
        steps_yaml_val = (get("steps_yaml") or "")
        # ▲▲▲ (จบการแก้ไข) ▲▲▲

        cfg = {
            "serial": serial,
            "device_id": device_id,
            "adb_path": adb_path,
            "app_package": app_package,
            "local_videos_dir": local_videos_dir,
            "device_video_dir": device_video_dir,
            "captions_csv": captions_csv,
            "adb_connection": adb_connection,
            "wifi_ip_port": wifi_ip_port,

            "steps_yaml": steps_yaml_val,  # (ใช้ค่าที่แก้แล้ว)

            "autobot_steps_yaml": (get("autobot_steps_yaml") or "autobot_steps.yaml"),
            "autobot_mode": get("autobot_mode"),
            "template_folder": get("template_folder"),
            "run_mode": get("run_mode")
        }
        # (ดึงค่า Autobot)
        cfg['autobot_mode'] = self.var_autobot_mode.get()
            
        # ▼▼▼ [เพิ่มบรรทัดนี้] ▼▼▼
        cfg['autobot_loops'] = self.var_autobot_loops.get() # (โหมด Autobot ใช้ตัวนี้)
        # ▲▲▲ [จบส่วนที่เพิ่ม] ▲▲▲

        try:
            cfg['fast_media_index'] = vars_.get('fast_media_index').get()
        except Exception:
            cfg['fast_media_index'] = True

        # เคลียร์ path ให้เป็น absolute (กันไปหยิบไฟล์กลาง)
        import os
        if captions_csv:
            cfg["captions_csv"] = os.path.abspath(captions_csv)
        if local_videos_dir:
            cfg["local_videos_dir"] = os.path.abspath(local_videos_dir)

        # (แก้ไข: ทำให้ path ของ YAML เป็น absolute path เสมอ (ถ้ามันไม่ว่าง))
        if cfg.get("steps_yaml"):  # (ถ้ามีค่า และไม่ว่าง)
            cfg["steps_yaml"] = os.path.abspath(cfg["steps_yaml"])
        if cfg.get("autobot_steps_yaml"):
            cfg["autobot_steps_yaml"] = os.path.abspath(cfg["autobot_steps_yaml"])

        return cfg
    #-------------------------------------------
    def _spawn_bot_process(self, config: dict):
        """
        เปิด bot.py เป็น process ใหม่ (ต่อเครื่อง) + pipe logs เข้ากล่องของแท็บนั้น
        """
        import datetime, os, sys, json, subprocess, threading, queue, signal

        # 1) เตรียม log file
        day = datetime.datetime.now().strftime("%Y-%m-%d")
        logs_dir = os.path.join(os.getcwd(), "logs", day)
        os.makedirs(logs_dir, exist_ok=True)

        serial = (config.get("device_id") or config.get("serial") or "unknown").replace(":", "_")
        ts = datetime.datetime.now().strftime("%H%M%S")
        log_path = os.path.join(logs_dir, f"{serial}_{ts}.log")
        fh = open(log_path, "w", encoding="utf-8", newline="")

        # 2) path เต็ม + unbuffered
        bot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.py")
        config_json = json.dumps(config, ensure_ascii=False)
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        args = [sys.executable, "-u", bot_path, "--config_data", config_json]
        adb_arg = (config.get("adb_path") or "").strip()
        pkg_arg = (config.get("app_package") or "").strip()
        cap_arg = (config.get("captions_csv") or "").strip()
        if adb_arg:
            args += ["--adb", adb_arg]
        if pkg_arg:
            args += ["--package", pkg_arg]
        if cap_arg:
            args += ["--captions", cap_arg]
        from tkinter import ttk
        frame_top = ttk.Frame(self.main_frame)
        frame_top.pack(fill="x", pady=6)

        # 3) สร้าง process (หยุดได้จริง)
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        preexec_fn = None if os.name == "nt" else os.setsid
        p = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
            encoding='utf-8',
            errors='replace',
            creationflags=creationflags,
            preexec_fn=preexec_fn,
            close_fds=False,
            env=env,
        )
        # check leftover stop flag for this serial before spawning process
        try:
            from pathlib import Path
            stop_flag = Path("flags") / f"{serial}.stop"
            if stop_flag.exists():
                # Do not spawn process: device is marked stopped by UI
                if not hasattr(self, "device_states"):
                    self.device_states = {}
                self.device_states[serial] = {
                    "process": None,
                    "status": "stopped",
                    "log_path": log_path,
                }
                try:
                    self.after(0, self._update_buttons_ui, serial, "stopped")
                except Exception:
                    pass
                # skip spawning: return early from _spawn_bot_process
                return
        except Exception:
            pass

        # 4) เก็บ state พื้นฐาน (แก้: สร้าง dict ถ้ายังไม่มี เพื่อป้องกัน AttributeError)
        if not hasattr(self, "device_procs"): 
            self.device_procs = {}
        if not hasattr(self, "device_log_queues"):
            self.device_log_queues = {}
        if not hasattr(self, "proc_by_serial"):
            self.proc_by_serial = {}

        self.device_procs[serial] = {"p": p, "log_path": log_path, "fh": fh}
        self.proc_by_serial[serial] = p
        if serial not in self.device_log_queues:
            self.device_log_queues[serial] = queue.Queue()

        # === NEW: ลงทะเบียน device_states เพื่อใช้ Pause/Resume ได้ ===
        if not hasattr(self, "device_states"):
            self.device_states = {}

        try:
            self.device_states[serial] = {
                "process": p,                # subprocess.Popen object
                "status": "running",         # running | paused | idle
                "log_path": log_path,
                "started_at": time.time() if 'time' in globals() else None,
            }
        except Exception:
            # fallback minimal info
            self.device_states[serial] = {"process": p, "status": "running"}

        # อัปเดตปุ่มบน UI (เรียกบน main thread หากมี)
        try:
            if hasattr(self, "_update_buttons_ui"):
                self.after(0, self._update_buttons_ui, serial, "running")
        except Exception:
            pass
        # =============================================================

        # =============================================================

        # 5) อ่าน stdout -> queue
        threading.Thread(target=self._reader_thread, args=(serial,), daemon=True).start()
        self._schedule_drain(serial)

        # 6) แจ้งเริ่มรัน
        now = datetime.datetime.now().strftime('%H:%M:%S')
        if hasattr(self, "global_log_text"):
            self.global_log_text.insert("end", f"[{now}] START {serial} → {log_path}\n")
            self.global_log_text.see("end")
        if hasattr(self, "device_log_widgets") and serial in self.device_log_widgets:
            self.device_log_widgets[serial].insert("end", f"เริ่มรัน • เขียนล็อกที่: {log_path}\n")
            self.device_log_widgets[serial].see("end")
        # when process ends:
        self.device_states[serial]["process"] = None
        self.device_states[serial]["status"] = "idle"
        self.after(0, self._update_buttons_ui, serial, 'idle')
    def _reader_thread(self, serial: str):
        """อ่าน stdout ของโปรเซส → เขียนลงไฟล์ + โยนเข้า queue สำหรับอัปเดต UI"""
        entry = self.device_procs.get(serial)
        if not entry:
            return
        p, fh = entry["p"], entry["fh"]
        try:
            for line in iter(p.stdout.readline, ''):
                if not line:
                    break
                # เขียนไฟล์และส่งเข้าคิว
                try:
                    fh.write(line);
                    fh.flush()
                except Exception:
                    pass
                q = self.device_log_queues.get(serial)
                if q:
                    q.put(line)
        except Exception:
            pass
        finally:
            try:
                p.stdout.close()
            except Exception:
                pass
            try:
                fh.close()
            except Exception:
                pass
            # บอก UI ว่าจบแล้ว
            q = self.device_log_queues.get(serial)
            if q:
                q.put(f"[{serial}] END\n")

    def _schedule_drain(self, serial: str, interval_ms: int = 120):
        """ดึงข้อความจาก queue มาแปะลง Text ทั้ง per-device และแท็บรวม"""
        q = self.device_log_queues.get(serial)
        if not q:
            return
        try:
            while True:
                line = q.get_nowait()
                # ต่ออุปกรณ์
                if hasattr(self, "device_log_widgets") and serial in self.device_log_widgets:
                    self.device_log_widgets[serial].insert("end", line)
                    self.device_log_widgets[serial].see("end")
                # รวม
                if hasattr(self, "global_log_text"):
                    self.global_log_text.insert("end", f"[{serial}] {line}")
                    self.global_log_text.see("end")
        except Exception:
            pass
        # วนใหม่
        self.after(interval_ms, lambda: self._schedule_drain(serial, interval_ms))

    def _remove_user_flow_row(self, frame_to_remove, key_to_remove):
        frame_to_remove.destroy()
        self.user_flow_rows = [row for row in self.user_flow_rows if row["key"] != key_to_remove]
        self._on_canvas_resize(None)

    def _on_canvas_resize(self, event):
        self.flow_canvas.itemconfig(self.flow_canvas.find_withtag("all")[0], width=self.flow_canvas.winfo_width())
    #------------helper-------------------
    def _parse_xy(self, xy_str: str):
        """คืนค่า (x, y) จากสตริง XY ที่อาจมีสเปซ/อักขระหลงมา รองรับทั้ง , และ ，"""
        import re
        if not xy_str:
            raise ValueError("empty")
        s = xy_str.strip().replace("，", ",")  # เผื่อคอมม่าจีน
        m = re.match(r"^\s*(\d+)\s*,\s*(\d+)\s*$", s)
        if not m:
            raise ValueError("format")
        return int(m.group(1)), int(m.group(2))

    #--------tab ขั้นตอน  XY---------------------
    # ===== PATCH: test tap robust =====
    def _test_tap_coords(self, step_name=None):
        """ทดสอบแตะพิกัด: ถ้ามี step_name → แตะเฉพาะแถวนั้น; ถ้าไม่มี → แตะเฉพาะแถวที่ติ๊ก ✔️"""
        from tkinter import messagebox
        import subprocess, shlex, time

        adb_path = self._find_adb_path() if hasattr(self, "_find_adb_path") else None
        if not adb_path:
            messagebox.showerror("ข้อผิดพลาด", "ไม่พบ adb.exe กลาง")
            return
        if not hasattr(self, "device_vars") or not self.device_vars:
            messagebox.showwarning("คำเตือน", "ยังไม่มีอุปกรณ์ที่เชื่อมต่อ")
            return
        if not hasattr(self, "step_vars") or not isinstance(self.step_vars, dict):
            messagebox.showwarning("คำเตือน", "ยังไม่มีตารางขั้นตอน (step_vars)")
            return

        # รวบรวม target
        targets = []
        if step_name and step_name in self.step_vars:
            targets = [step_name]
        else:
            # ปุ่มรวม → เฉพาะ step ที่ติ๊กและมี XY
            for sname, vars_tuple in self.step_vars.items():
                try:
                    v_en, v_xy, _ = vars_tuple
                    if v_en.get() and (v_xy.get() or "").strip():
                        targets.append(sname)
                except Exception:
                    continue

        if not targets:
            messagebox.showwarning("ไม่มีการแตะ", "ไม่มีขั้นตอนที่ถูกติ๊กหรือไม่มีค่า XY")
            return

        total_ok = 0
        for sname in targets:
            try:
                v_en, v_xy, _ = self.step_vars[sname]
                x, y = self._parse_xy(v_xy.get())
            except Exception:
                messagebox.showerror("ข้อผิดพลาด", f"พิกัดของ '{sname}' ไม่ถูกต้อง (ควรเป็น 123,456)")
                continue

            for serial in list(self.device_vars.keys()):
                try:
                    cmd = f'"{adb_path}" -s {serial} shell input tap {x} {y}'
                    subprocess.run(shlex.split(cmd), check=True)
                    try:
                        self._append_global(f"[ADB] แตะ {x},{y} ({sname}) ที่ {serial}")
                    except Exception:
                        pass
                    time.sleep(0.2)
                    total_ok += 1
                except Exception as e:
                    try:
                        self._append_global(f"[ADB] แตะ {sname} ล้มเหลว {serial}: {e}")
                    except Exception:
                        pass

        messagebox.showinfo("สำเร็จ",
                            f"ทดสอบแตะ {len(targets)} ขั้นตอน บนอุปกรณ์ {len(self.device_vars)} เครื่อง (tap ทั้งหมด {total_ok} ครั้ง)")

    # ===== PATCH END =====

    #----------------------------------------
    def _get_current_coords(self):
        selected_coords = []
        for key, (v_en, v_xy, v_dl) in self.step_vars.items():
            if v_en.get() and v_xy.get():
                try:
                    selected_coords.append([int(p) for p in v_xy.get().strip().split(",")])
                except ValueError:
                    continue
        for row in self.user_flow_rows:
            if row["enabled_var"].get() and row["xy_var"].get():
                try:
                    selected_coords.append([int(p) for p in row["xy_var"].get().strip().split(",")])
                except ValueError:
                    continue
        return selected_coords[0] if selected_coords else None

    # ---------------- ล็อก ----------------
    #def setup_log_tab(self):
        self.log_text = tk.Text(self.tab_log, state=tk.DISABLED, wrap="word")
        self.log_text.pack(fill=tk.BOTH, expand=True)
        # (เผื่อโค้ดเดิมที่ใช้ global_log_text)
        self.global_log_text = self.log_text

    def log_to_ui(self, message):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # ---------------- คอมไพล์ ----------------
    def setup_compile_tab(self):
        self.compile_frame = ttk.Frame(self.tab_compile, padding="10")
        self.compile_frame.pack(fill=tk.BOTH, expand=True)

        # --- ช่องรายชื่อวิดีโอ -> AUTO + Spinbox จำนวน ---
        frame_auto = ttk.Frame(self.compile_frame)
        frame_auto.grid(row=0, column=0, sticky=tk.N, padx=5, pady=5)

        ttk.Label(frame_auto, text="รายชื่อวิดีโอ (AUTO)").pack()
        self.video_auto_entry = ttk.Entry(frame_auto, width=20, state="disabled")
        self.video_auto_entry.pack(fill=tk.BOTH, expand=True)
        self.video_auto_entry.configure(state="normal")
        self.video_auto_entry.delete(0, "end")
        self.video_auto_entry.insert(0, "AUTO")
        self.video_auto_entry.configure(state="disabled")

        cnt_frame = ttk.Frame(frame_auto)
        cnt_frame.pack(fill=tk.X, pady=5)
        ttk.Label(cnt_frame, text="จำนวนวิดีโอ:").pack(side=tk.LEFT)
        self.auto_video_count_var = tk.StringVar(value="10")
        self.auto_video_count = ttk.Spinbox(cnt_frame, from_=1, to=9999, width=6, textvariable=self.auto_video_count_var)
        self.auto_video_count.pack(side=tk.LEFT, padx=(6,0))

        # ช่องอื่น ๆ
        self.caption_text = self._create_text_area(self.compile_frame, "แคปชั่น", 1)
        self.hashtag_text = self._create_text_area(self.compile_frame, "แฮชแท็ก", 2)
        self.link_text = self._create_text_area(self.compile_frame, "ลิงก์สินค้า", 3)

        btn_frame = ttk.Frame(self.compile_frame)
        btn_frame.grid(row=4, column=0, columnspan=4, pady=10)

        self.var_hashtag_pick = tk.StringVar(value="3")
        hashtag_frame = ttk.Frame(btn_frame); hashtag_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(hashtag_frame, text="จำนวนแฮชแท็ก:").pack(side=tk.LEFT)
        self.hashtag_dropdown = ttk.Combobox(hashtag_frame, textvariable=self.var_hashtag_pick, state="readonly", width=3)
        self.hashtag_dropdown['values'] = tuple(range(3, 8))
        self.hashtag_dropdown.pack(side=tk.LEFT)

        # จำนวนลิงก์/โพสต์ (เหมือนแฮชแท็ก)
        self.var_link_pick = tk.StringVar(value="1")
        linkpick_frame = ttk.Frame(btn_frame); linkpick_frame.pack(side=tk.LEFT, padx=5)
        ttk.Label(linkpick_frame, text="จำนวนลิงก์/โพสต์:").pack(side=tk.LEFT)
        self.link_dropdown = ttk.Combobox(linkpick_frame, textvariable=self.var_link_pick, state="readonly", width=3)
        self.link_dropdown['values'] = tuple(range(1, 6))
        self.link_dropdown.pack(side=tk.LEFT)

        ttk.Button(btn_frame, text="สร้าง captions.csv", command=self._make_csv).pack(side=tk.LEFT, padx=5)
        # dropdown รายชื่อ captions.csv + ปุ่มโหลด
        self.captions_combo = ttk.Combobox(btn_frame, state="readonly", width=28)
        self.captions_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="โหลด", command=self._load_captions_from_selected).pack(side=tk.LEFT, padx=5)
        self._refresh_captions_list()

    def _create_text_area(self, parent_frame, label_text, col):
        frame = ttk.Frame(parent_frame)
        frame.grid(row=0, column=col, sticky=tk.N, padx=5, pady=5)
        ttk.Label(frame, text=label_text).pack()
        text_widget = tk.Text(frame, height=15, width=20, wrap="word")
        text_widget.pack(fill=tk.BOTH, expand=True)
        ttk.Button(frame, text="วาง", command=lambda: self._paste_content(text_widget)).pack(fill=tk.X)
        return text_widget

    def _paste_content(self, text_widget):
        try:
            content = pyperclip.paste()
            text_widget.insert(tk.END, content)
        except pyperclip.PyperclipException:
            messagebox.showerror("ข้อผิดพลาด", "ไม่สามารถเข้าถึงคลิปบอร์ดได้")

    def _make_csv(self):
        """
        โหมด AUTO:
        - อ่าน Local Videos Dir
        - เลือกไฟล์วิดีโอตามจำนวน (Spinbox)
        - เปลี่ยนชื่อไฟล์จริงในโฟลเดอร์เป็นลำดับ vdo (1).ext ... vdo (N).ext
        - สร้าง captions.csv จากรายชื่อใหม่
        """
        caps = [ln.strip() for ln in self.caption_text.get("1.0", "end").splitlines() if ln.strip()]
        tags_pool = [ln.strip() for ln in self.hashtag_text.get("1.0", "end").splitlines() if ln.strip()]
        links_pool = [ln.strip() for ln in self.link_text.get("1.0", "end").splitlines() if ln.strip()]
        try:
            pick_n = int(self.var_hashtag_pick.get())
        except Exception:
            pick_n = 3
        try:
            link_n = int(self.var_link_pick.get())
        except Exception:
            link_n = 1
        link_n = max(0, link_n)

        base_dir = (self.var_local_videos_dir.get() or "").strip()
        if not base_dir or not os.path.isdir(base_dir):
            messagebox.showerror("ข้อผิดพลาด", "Local Videos Dir ไม่ถูกต้อง หรือโฟลเดอร์ไม่มีอยู่จริง")
            return
        try:
            wanted = int(self.auto_video_count_var.get())
            if wanted < 1:
                raise ValueError
        except Exception:
            messagebox.showerror("ข้อผิดพลาด", "กรุณาระบุจำนวนวิดีโอเป็นตัวเลขตั้งแต่ 1 ขึ้นไป")
            return

        exts = {".mp4",".mov",".mkv",".avi",".m4v",".webm",".3gp"}
        all_files = sorted([p for p in Path(base_dir).iterdir() if p.is_file() and p.suffix.lower() in exts], key=lambda x: x.name.lower())
        if not all_files:
            messagebox.showerror("ข้อผิดพลาด", "ไม่พบไฟล์วิดีโอในโฟลเดอร์ที่ระบุ")
            return

        picks = all_files[:min(len(all_files), wanted)]
        if len(picks) < wanted:
            messagebox.showwarning("คำเตือน", f"พบไฟล์วิดีโอ {len(picks)} ไฟล์ (น้อยกว่าที่ตั้งไว้ {wanted}) — จะใช้เท่าที่มี")

        used_names = set()
        renamed_names = []
        for idx, path in enumerate(picks, start=1):
            new_name = f"vdo ({idx}){path.suffix.lower()}"
            target = Path(base_dir) / new_name

            if target.exists() and target.resolve() != path.resolve():
                if path.name.lower() != new_name.lower():
                    j = 2
                    while True:
                        alt = Path(base_dir) / f"vdo ({idx})_{j}{path.suffix.lower()}"
                        if not alt.exists():
                            target = alt
                            break
                        j += 1

            try:
                if path.resolve() != target.resolve():
                    path.rename(target)
            except Exception as e:
                messagebox.showerror("ข้อผิดพลาด", f"เปลี่ยนชื่อไฟล์ล้มเหลว:\n{path.name} -> {target.name}\n{e}")
                return

            used_names.add(target.name)
            renamed_names.append(target.name)

        rows = []
        for i, vid_filename in enumerate(renamed_names, start=1):
            caption = random.choice(caps) if caps else ""
            if tags_pool:
                chosen = random.sample(tags_pool, min(len(tags_pool), pick_n))
                hashtags = " ".join(t if t.startswith("#") else f"#{t}" for t in chosen)
            else:
                hashtags = ""
            chosen_links = []
            if links_pool and link_n > 0:
                if len(links_pool) >= link_n:
                    chosen_links = random.sample(links_pool, link_n)
                else:
                    chosen_links = [random.choice(links_pool) for _ in range(link_n)]
            link_field = " ".join(chosen_links).strip()
            rows.append({"video_filename": vid_filename, "caption": caption, "hashtags": hashtags, "link": link_field})

        try:
            with open("captions.csv", "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["video_filename", "caption", "hashtags", "link"])
                w.writeheader(); w.writerows(rows)
            messagebox.showinfo("สำเร็จ", f"สร้าง captions.csv แล้ว ({len(rows)} แถว)\nไฟล์วิดีโอถูกจัดเรียงชื่อเป็น vdo (1..N).ext เรียบร้อย")
        except Exception as e:
            messagebox.showerror("ข้อผิดพลาด", f"ไม่สามารถสร้างไฟล์: {e}")

    def _refresh_captions_list(self):
        try:
            files = []
            for p in Path(".").glob("*.csv"):
                if "caption" in p.name.lower():
                    files.append(p.name)
            files = sorted(set(files))
            self.captions_combo["values"] = files
            if files:
                self.captions_combo.set(files[0])
        except Exception:
            self.captions_combo["values"] = []

    def _load_captions_from_selected(self):
        name = (self.captions_combo.get() or "").strip()
        if not name:
            messagebox.showerror("ข้อผิดพลาด", "กรุณาเลือกไฟล์ captions.csv จากรายการ")
            return
        self._load_captions(path=name)

    def _load_captions(self, path="captions.csv"):
        """
        ปรับปรุง: แตก hashtags เป็น 'แท็กละ 1 บรรทัด' + ลบซ้ำ + บังคับขึ้นต้นด้วย #
        ไม่แตะการโหลดแคปชั่น/ลิงก์ส่วนอื่น
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            if not rows:
                messagebox.showinfo("ข้อมูลว่าง", "ไฟล์ captions.csv ไม่มีข้อมูล"); return

            # --- เติมแคปชั่น (คงเดิม) ---
            self.caption_text.delete("1.0", tk.END)
            self.caption_text.insert(tk.END, "\n".join(row.get("caption","") for row in rows))

            # --- เติมลิงก์ (คงเดิม) ---
            self.link_text.delete("1.0", tk.END)
            self.link_text.insert(tk.END, "\n".join(row.get("link","") for row in rows))

            # --- เติมแฮชแท็ก: แตกเป็นแท็กละ 1 บรรทัด + ลบซ้ำ (คงลำดับ) ---
            tags_all = []
            seen = set()
            for row in rows:
                raw = row.get("hashtags", "") or ""
                parts = re.split(r"[,\s]+", raw.strip())
                for p in parts:
                    if not p:
                        continue
                    tag = p.strip()
                    if not tag.startswith("#"):
                        tag = "#" + tag
                    tag = "#" + tag.lstrip("#")
                    if tag == "#":
                        continue
                    if tag not in seen:
                        seen.add(tag)
                        tags_all.append(tag)

            self.hashtag_text.delete("1.0", tk.END)
            self.hashtag_text.insert(tk.END, "\n".join(tags_all))

            messagebox.showinfo("สำเร็จ", "โหลดข้อมูลจาก captions.csv แล้ว\n(แฮชแท็กถูกแยกเป็นบรรทัดละ 1 แท็ก และลบแท็กซ้ำ)")
        except FileNotFoundError:
            messagebox.showerror("ข้อผิดพลาด", f"ไม่พบไฟล์: {path}")
        except Exception as e:
            messagebox.showerror("ข้อผิดพลาด", f"ไม่สามารถโหลดไฟล์: {e}")

    # ---------------- แท็บ AI ----------------
    def setup_ai_tab(self):
        #===== Scrollable area (แนวตั้งเท่านั้น ไม่ล้นด้านข้าง) =====
        container = ttk.Frame(self.tab_ai)
        container.pack(fill="both", expand=True)
        canvas = tk.Canvas(container, highlightthickness=0)
        vscroll = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        # ให้ Canvas แสดง Scroll แนวตั้ง แต่ล็อกความกว้างเท่าหน้าต่าง
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all"),
                width=canvas.winfo_width()
            )
        )
        # ป้องกัน Canvas ขยายแนวนอน
        canvas.bind("<Configure>", lambda e: canvas.itemconfig("frame", width=e.width))

        frame_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", tags="frame")

        canvas.configure(yscrollcommand=vscroll.set)

        canvas.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        frm = scrollable_frame  # ใช้ frm เป็น parent ของ UI ต่อไป
#---------------------------------------------------------
        # API row
        ttk.Label(frm, text="API Key:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.api_key_entry = ttk.Entry(frm, width=50)
        self.api_key_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(frm, text="วาง", command=lambda: self._paste_to_entry(self.api_key_entry)).grid(row=0, column=2,
                                                                                                   padx=4)
        ttk.Button(frm, text="บันทึกคีย์", command=self._save_api_key, style="Shopee.TButton").grid(row=0, column=3,
                                                                                                    padx=4)

        ttk.Label(frm, text="API Provider:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.ai_provider_combo = ttk.Combobox(frm, values=["Gemini", "OpenAI"], width=47, state="readonly")
        self.ai_provider_combo.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        self.ai_provider_combo.set("Gemini")

        # Prompt row
        ttk.Label(frm, text="ชื่อสินค้า/คำสั่ง (Prompt):").grid(row=2, column=0, sticky=tk.NW, padx=5, pady=5)
        self.ai_prompt_text = tk.Text(frm, height=4, width=50, wrap="word")
        self.ai_prompt_text.grid(row=2, column=1, columnspan=3, sticky="nsew", padx=5, pady=5)

        # Generation amounts (for AI call)
        ttk.Label(frm, text="จำนวนแคปชั่น:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.ai_caps_spin = ttk.Spinbox(frm, from_=1, to=100, width=6)
        self.ai_caps_spin.delete(0, "end");
        self.ai_caps_spin.insert(0, "5")
        self.ai_caps_spin.grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)

        ttk.Label(frm, text="จำนวนแฮชแท็ก/แคปชั่น:").grid(row=3, column=2, sticky=tk.E, padx=5, pady=5)
        self.ai_tags_spin = ttk.Spinbox(frm, from_=1, to=20, width=6)
        self.ai_tags_spin.delete(0, "end");
        self.ai_tags_spin.insert(0, "5")
        self.ai_tags_spin.grid(row=3, column=3, sticky=tk.W, padx=5, pady=5)

        # Top buttons
        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=4, sticky="w", padx=5, pady=5)
        ttk.Button(btns, text="ทดสอบ API", command=self._test_api_once).pack(side=tk.LEFT, padx=3)
        ttk.Button(btns, text="สร้างแคปชั่น", command=self._start_generate_caption_thread, style="Shopee.TButton").pack(side=tk.LEFT,
                                                                                                           padx=3)
        ttk.Button(btns, text="คัดลอกแคปชั่น", command=lambda: self._copy_from_text(self.ai_caps_output)).pack(
            side=tk.LEFT, padx=3)
        ttk.Button(btns, text="คัดลอกแฮชแท็ก", command=lambda: self._copy_from_text(self.ai_tags_output)).pack(
            side=tk.LEFT, padx=3)
        ttk.Button(btns, text="สร้าง captions.csv", command=self._make_csv_from_ai).pack(side=tk.LEFT, padx=3)

        # Limits (used when building CSV)
        limit_row = ttk.Frame(frm)
        limit_row.grid(row=5, column=0, columnspan=4, sticky="w", padx=5, pady=(0, 6))

        if not hasattr(self, "var_hashtag_pick"):
            self.var_hashtag_pick = tk.StringVar(value="5")
        ttk.Label(limit_row, text="จำนวนแฮชแท็ก/โพสต์:").pack(side=tk.LEFT)
        self.hashtag_dropdown = ttk.Combobox(limit_row, textvariable=self.var_hashtag_pick, state="readonly", width=3)
        self.hashtag_dropdown['values'] = tuple(range(1, 21))
        self.hashtag_dropdown.pack(side=tk.LEFT, padx=(2, 10))

        if not hasattr(self, "var_link_pick"):
            self.var_link_pick = tk.StringVar(value="1")
        ttk.Label(limit_row, text="จำนวนลิงก์/โพสต์:").pack(side=tk.LEFT)
        self.link_dropdown = ttk.Combobox(limit_row, textvariable=self.var_link_pick, state="readonly", width=3)
        self.link_dropdown['values'] = tuple(range(1, 11))
        self.link_dropdown.pack(side=tk.LEFT, padx=(2, 10))

        # Outputs area (3 columns)
        box = ttk.LabelFrame(frm, text="ผลลัพธ์จาก AI", padding=8)
        box.grid(row=6, column=0, columnspan=4, sticky="nsew", padx=5, pady=5)

        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(6, weight=1)
        for c in (0, 1, 2):
            box.columnconfigure(c, weight=1)
        box.rowconfigure(0, weight=1)

        # Left: captions
        left = ttk.Frame(box);
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ttk.Label(left, text="แคปชั่น").pack(anchor="w")
        lf = ttk.Frame(left);
        lf.pack(fill="both", expand=True)
        self.ai_caps_output = tk.Text(lf, height=12, wrap="word")
        lscroll = ttk.Scrollbar(lf, orient="vertical", command=self.ai_caps_output.yview)
        self.ai_caps_output.configure(yscrollcommand=lscroll.set)
        self.ai_caps_output.pack(side="left", fill="both", expand=True);
        lscroll.pack(side="right", fill="y")

        # Middle: hashtags
        mid = ttk.Frame(box);
        mid.grid(row=0, column=1, sticky="nsew", padx=(6, 6))
        ttk.Label(mid, text="แฮชแท็ก").pack(anchor="w")
        mf = ttk.Frame(mid);
        mf.pack(fill="both", expand=True)
        self.ai_tags_output = tk.Text(mf, height=12, wrap="word")
        mscroll = ttk.Scrollbar(mf, orient="vertical", command=self.ai_tags_output.yview)
        self.ai_tags_output.configure(yscrollcommand=mscroll.set)
        self.ai_tags_output.pack(side="left", fill="both", expand=True);
        mscroll.pack(side="right", fill="y")

        # Right: product links
        right = ttk.Frame(box);
        right.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        ttk.Label(right, text="ลิงก์สินค้า").pack(anchor="w")
        rf = ttk.Frame(right);
        rf.pack(fill="both", expand=True)
        self.ai_links_output = tk.Text(rf, height=12, wrap="word")
        rscroll = ttk.Scrollbar(rf, orient="vertical", command=self.ai_links_output.yview)
        self.ai_links_output.configure(yscrollcommand=rscroll.set)
        self.ai_links_output.pack(side="left", fill="both", expand=True);
        rscroll.pack(side="right", fill="y")
    #---------บังคับไฟล์วิดีโอ---------------------------
        # ====== เพิ่มส่วนเตรียมไฟล์วิดีโอสำหรับ captions.csv ======
        section = ttk.LabelFrame(frm, text="เตรียมวิดีโอ → รีเนม + สร้าง caption.csv", padding=8)
        section.grid(row=7, column=0, columnspan=4, sticky="nsew", padx=5, pady=6)
        # ตัวแปรเฉพาะแท็บ AI (สำหรับส่วนนี้)
        import datetime, os
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.ai_video_dir = getattr(self, "ai_video_dir", tk.StringVar(value=""))
        self.ai_count = getattr(self, "ai_count", tk.IntVar(value=20))
        self.ai_shuffle = getattr(self, "ai_shuffle", tk.BooleanVar(value=True))
        self.ai_order_mode = getattr(self, "ai_order_mode",
                                     tk.StringVar(value="modified_desc"))  # modified_desc | name_asc
        self.ai_pattern = getattr(self, "ai_pattern", tk.StringVar(value="spv_{date:YYYYMMDD}_{index:03d}"))
        self.ai_csv_path = getattr(self, "ai_csv_path", tk.StringVar(value=os.path.join("caption", f"{now}.csv")))
        self.ai_use_relative = getattr(self, "ai_use_relative", tk.BooleanVar(value=True))
        self.ai_lowres_delete = getattr(self, "ai_lowres_delete",
                                        tk.BooleanVar(value=False))  # ถ้าติ๊ก=ลบถาวร, ไม่ติ๊ก=ย้ายไป __trash_lowres
        self.ai_lowres_cutoff = getattr(self, "ai_lowres_cutoff", tk.IntVar(value=480))  # short-side >= 480




        # แถว: โฟลเดอร์วิดีโอ
        r = 0
        # ...ใน layout, ใต้แถวเลือกโฟลเดอร์วิดีโอ ให้เพิ่มแถวนี้...
        ttk.Label(section, text="ffprobe.exe (ถ้ามี):").grid(row=r, column=0, sticky="e")
        ttk.Entry(section, textvariable=self.ai_ffprobe_path, width=60).grid(row=r, column=1, sticky="we", padx=6)
        ttk.Button(section, text="เลือก ffprobe…", command=lambda: self._ai_pick_ffprobe()).grid(row=r, column=2,
                                                                                                 padx=4)
        r += 1
        ttk.Label(section, text="โฟลเดอร์วิดีโอ:").grid(row=r, column=0, sticky="e")
        ttk.Entry(section, textvariable=self.ai_video_dir, width=60).grid(row=r, column=1, sticky="we", padx=6)
        ttk.Button(section, text="เลือกโฟลเดอร์…", command=self._ai_browse_video_dir).grid(row=r, column=2, padx=4)
        r += 1

        # แถว: จำนวนไฟล์ + ลำดับ
        ttk.Label(section, text="จำนวนไฟล์ที่จะบันทึก:").grid(row=r, column=0, sticky="e")
        ttk.Spinbox(section, from_=1, to=100000, textvariable=self.ai_count, width=10).grid(row=r, column=1, sticky="w")
        ttk.Checkbutton(section, text="สุ่มลำดับไฟล์", variable=self.ai_shuffle).grid(row=r, column=1, sticky="e",
                                                                                      padx=6)
        r += 1

        ttk.Label(section, text="โหมดเรียงไฟล์:").grid(row=r, column=0, sticky="e")
        ord_box = ttk.Frame(section);
        ord_box.grid(row=r, column=1, sticky="w", pady=2)
        ttk.Radiobutton(ord_box, text="แก้ไขล่าสุด (ใหม่→เก่า)", value="modified_desc",
                        variable=self.ai_order_mode).pack(side="left")
        ttk.Radiobutton(ord_box, text="ตามชื่อ (A→Z)", value="name_asc", variable=self.ai_order_mode).pack(side="left",
                                                                                                           padx=10)
        r += 1

        # แถว: กรองความละเอียด
        lr_box = ttk.Frame(section);
        lr_box.grid(row=r, column=0, columnspan=3, sticky="w", pady=(2, 6))
        ttk.Label(lr_box, text="คัดทิ้งต่ำกว่า (short-side):").pack(side="left")
        ttk.Entry(lr_box, textvariable=self.ai_lowres_cutoff, width=6).pack(side="left", padx=(4, 6))
        ttk.Label(lr_box, text="พิกเซล  (480 = 480p)").pack(side="left")
        ttk.Checkbutton(lr_box, text="ลบถาวร (ไม่ย้ายไปถัง)", variable=self.ai_lowres_delete).pack(side="left", padx=12)
        r += 1
        # แถว: รูปแบบชื่อไฟล์ใหม่
        ttk.Label(section, text="รูปแบบชื่อไฟล์ใหม่:").grid(row=r, column=0, sticky="e")
        ttk.Entry(section, textvariable=self.ai_pattern, width=60).grid(row=r, column=1, sticky="we", padx=6)
        ttk.Button(section, text="ตัวอย่าง", command=self._ai_preview).grid(row=r, column=2, padx=4)
        r += 1

        ttk.Label(section, text="โทเคน: {index[:fmt]} {date[:fmt]} {time[:fmt]} {random4} {stem}").grid(
            row=r, column=1, sticky="w", pady=(0, 6)
        )
        r += 1

        # แถว: ไฟล์ CSV ปลายทาง
        # ตัวแปร
        self.ai_default_caption = getattr(self, "ai_default_caption", tk.StringVar(value=""))
        self.ai_default_tags = getattr(self, "ai_default_tags", tk.StringVar(value=""))
        self.ai_default_link = getattr(self, "ai_default_link", tk.StringVar(value=""))

        # UI แคปชัน + แท็ก
        ttk.Label(section, text="Caption (ใส่เหมือนกันทุกไฟล์):").grid(row=r, column=0, sticky="e")
        ttk.Entry(section, textvariable=self.ai_default_caption, width=60).grid(row=r, column=1, sticky="we", padx=6)
        r += 1
        ttk.Label(section, text="แฮชแท็ก (คั่นด้วยคอมมา):").grid(row=r, column=0, sticky="e")
        ttk.Entry(section, textvariable=self.ai_default_tags, width=60).grid(row=r, column=1, sticky="we", padx=6)
        r += 1
        ttk.Label(section, text="ลิงก์ (ค่าเริ่มต้นทุกไฟล์):").grid(row=r, column=0, sticky="e")
        ttk.Entry(section, textvariable=self.ai_default_link, width=60).grid(row=r, column=1, sticky="we", padx=6)
        r += 1

        #-------------------------------------
        ttk.Label(section, text="บันทึกเป็นไฟล์ CSV:").grid(row=r, column=0, sticky="e")
        ttk.Entry(section, textvariable=self.ai_csv_path, width=60).grid(row=r, column=1, sticky="we", padx=6)
        ttk.Button(section, text="เลือกที่บันทึก…", command=self._ai_browse_csv_path).grid(row=r, column=2, padx=4)
        r += 1
        ttk.Checkbutton(section, text="ใช้พาธสัมพัทธ์ (relative) ต่อโฟลเดอร์วิดีโอ", variable=self.ai_use_relative) \
            .grid(row=r, column=1, sticky="w", pady=(0, 8))
        r += 1

        # ปุ่มทำงาน
        bar = ttk.Frame(section);
        bar.grid(row=r, column=0, columnspan=3, sticky="we", pady=(0, 8))
        ttk.Button(bar, text="🔍 แสดงตัวอย่าง", command=self._ai_preview).pack(side="left")
        ttk.Button(bar, text="📝 สร้าง caption", command=self._ai_create_caption).pack(side="left", padx=8)
        r += 1

        # Log/สถานะเฉพาะส่วนนี้
        self.ai_log = getattr(self, "ai_log", None)
        if self.ai_log is None:
            self.ai_log = tk.Text(section, height=8, wrap="word")
        self.ai_log.grid(row=r, column=0, columnspan=3, sticky="nsew")
        section.columnconfigure(1, weight=1)
        section.rowconfigure(r, weight=1)


    #-------------------------------------------------
    def _ai_pick_ffprobe(self):
        path = filedialog.askopenfilename(
            title="เลือก ffprobe.exe",
            filetypes=[("ffprobe", "ffprobe.exe"), ("All files", "*.*")]
        )
        if path:
            self.ai_ffprobe_path.set(path)
            self._ai_log_line(f"[AI] ffprobe: {path}")
    #-----------------------------------------------------
    def _ai_try_get_ai_value(self, candidates: list[str]) -> str:
        """
        พยายามดึงค่าจาก widget/ตัวแปรของ 'ผลลัพธ์ AI' ตามรายชื่อ candidates (ชื่อแอตทริบิวต์)
        รองรับทั้ง StringVar, Entry, Text; คืนสตริงแรกที่ 'ไม่ว่าง' ถ้าไม่พบ คืน "".
        """

        import tkinter as tk
        from tkinter import Entry, Text
        for name in candidates:
            if not hasattr(self, name):
                continue
            obj = getattr(self, name)

            # StringVar
            if isinstance(obj, tk.StringVar):
                try:
                    val = (obj.get() or "").strip()
                    if val:
                        return val
                except Exception:
                    pass
                continue

            # Entry
            if hasattr(obj, "get") and hasattr(obj, "winfo_exists"):
                try:
                    if obj.winfo_exists() and isinstance(obj, Entry):
                        val = (obj.get() or "").strip()
                        if val:
                            return val
                        continue
                except Exception:
                    pass

            # Text
            try:
                if isinstance(obj, Text) and obj.winfo_exists():
                    val = (obj.get("1.0", "end") or "").strip()
                    if val:
                        return val
            except Exception:
                pass


        return ""

    #-------------------------------------------------
    def _validate_before_run(self, cfg: dict) -> bool:
        must = ["adb_path", "device_id", "app_package", "local_videos_dir", "device_video_dir"]
        missing = [k for k in must if not (cfg.get(k) or "").strip()]
        if missing:
            messagebox.showerror("ตั้งค่าไม่ครบ",
                                 "ค่าบังคับว่างอยู่:\n- " + "\n- ".join(missing) +
                                 "\n\nกรุณากรอกให้ครบก่อนเริ่มรัน")
            return False

        cap = (cfg.get("captions_csv") or "").strip()
        if cap and not os.path.isfile(cap):
            messagebox.showerror("ไม่พบ captions.csv", f"ไฟล์ไม่พบ:\n{cap}\n\nโปรดเลือกไฟล์ของเครื่องนี้")
            return False

        return True
    #-------------------เพิ่ม Handlers-------------------
    def _ai_log_line(self, msg: str):
        if hasattr(self, "ai_log") and self.ai_log:
            self.ai_log.insert("end", msg + "\n")
            self.ai_log.see("end")

    def _ai_browse_video_dir(self):
        path = filedialog.askdirectory(title="เลือกโฟลเดอร์วิดีโอ")
        if path:
            self.ai_video_dir.set(path)
            self._ai_log_line(f"[AI] โฟลเดอร์วิดีโอ: {path}")

    def _ai_browse_csv_path(self):
        path = filedialog.asksaveasfilename(
            title="บันทึกเป็น CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if path:
            self.ai_csv_path.set(path)
            self._ai_log_line(f"[AI] จะบันทึก CSV: {path}")

    def _ai_preview(self):
        """
        สแกนไฟล์วิดีโอ -> อ่านความละเอียด -> กรอง < cutoff -> จัดลำดับ/สุ่ม -> จำกัดจำนวน
        -> จำลองชื่อใหม่ตามแพทเทิร์น -> แสดงสรุป + ตัวอย่าง (ยังไม่แตะไฟล์จริง)
        """
        import os, datetime, random

        video_dir = (self.ai_video_dir.get() or "").strip()
        if not video_dir or not os.path.isdir(video_dir):
            self._ai_log_line("[AI] กรุณาเลือกโฟลเดอร์วิดีโอที่ถูกต้องก่อน")
            return

        try:
            cutoff = int(self.ai_lowres_cutoff.get())
        except Exception:
            cutoff = 480

        count = int(self.ai_count.get() or 1)
        order = (self.ai_order_mode.get() or "modified_desc").strip().lower()
        do_shuffle = bool(self.ai_shuffle.get())
        pattern = (self.ai_pattern.get() or "spv_{date:YYYYMMDD}_{index:03d}").strip()
        use_rel = bool(self.ai_use_relative.get())

        self._ai_log_line(f"[AI] สแกนโฟลเดอร์: {video_dir}")
        files = self._ai_scan_videos(video_dir)
        if not files:
            self._ai_log_line("[AI] ไม่พบไฟล์วิดีโอที่รองรับ (.mp4 .mov .mkv .avi .wmv)")
            return
        self._ai_log_line(f"[AI] พบไฟล์ทั้งหมด: {len(files)}")

        # อ่านความละเอียดและกรอง low-res
        ok, low = [], []
        if cutoff <= 0:
            # ปิดการกรองความละเอียด
            for p in files:
                ok.append((p, None, None))  # ไม่ต้องอ่านขนาด
            self._ai_log_line("[AI] ปิดการกรองความละเอียด (cutoff=0) — จะใช้ไฟล์ทั้งหมด")
        else:
            self._ai_log_line("[AI] ตรวจความละเอียดวิดีโอ (short-side ≥ %d) ..." % cutoff)
            for p in files:
                wh = self._ai_get_video_resolution(p)
                if not wh:
                    low.append((p, None))
                    continue
                w, h = wh
                short_side = min(w, h)
                if short_side >= cutoff:
                    ok.append((p, w, h))
                else:
                    low.append((p, (w, h)))

        self._ai_log_line(f"[AI] ผ่านเกณฑ์: {len(ok)} • ต่ำกว่าเกณฑ์: {len(low)} (จะถูกลบทิ้ง/ย้ายทิ้งตอนสร้างจริง)")
        if not ok:
            self._ai_log_line("[AI] ไม่มีไฟล์ที่ผ่านเกณฑ์พอทำงานต่อ")
            return

        # จัดลำดับ
        if order == "name_asc":
            ok.sort(key=lambda t: os.path.basename(t[0]).lower())
        else:
            # modified_desc: ใหม่ -> เก่า
            ok.sort(key=lambda t: os.path.getmtime(t[0]), reverse=True)

        # สุ่มลำดับ (optional)
        if do_shuffle:
            random.shuffle(ok)

        # จำกัดจำนวน
        ok = ok[:count]

        # จำลองชื่อใหม่
        now = datetime.datetime.now()
        preview_rows = []
        for i, (p, w, h) in enumerate(ok, start=1):
            stem = os.path.splitext(os.path.basename(p))[0]
            ext = os.path.splitext(p)[1].lower()
            new_stem = self._ai_render_name(pattern, index=i, stem=stem, now=now)
            new_name = new_stem + ext
            preview_rows.append((p, new_name, (w, h)))

        # แสดงตัวอย่าง (สูงสุด 20 แถว)
        self._ai_log_line("— ตัวอย่างชื่อใหม่ (สูงสุด 20 แถว) —")
        for row in preview_rows[:20]:
            src, dst, wh = row
            wh_text = f"{wh[0]}x{wh[1]}" if wh else "N/A"
            base_src = os.path.basename(src)
            self._ai_log_line(f"  {base_src} [{wh_text}]  ->  {dst}")

        # สรุปปลายทาง CSV
        csv_path = (self.ai_csv_path.get() or "").strip()
        if not csv_path:
            import os
            csv_path = os.path.join("caption", now.strftime("%Y%m%d_%H%M%S") + ".csv")
            self.ai_csv_path.set(csv_path)
        self._ai_log_line(f"[AI] จะเขียน CSV ไปที่: {csv_path} (ตอนกด 'สร้าง caption')")

        # สรุปตัวเลข
        self._ai_log_line(
            f"[AI] สรุป: จะรีเนมและเขียน CSV จำนวน {len(preview_rows)} ไฟล์ • คัดทิ้งต่ำกว่าเกณฑ์ {len(low)} ไฟล์")
    #----------------------------------------------
    def _start_generate_caption_thread(self):
        """ฟังก์ชันเริ่มต้น Thread สำหรับการสร้างแคปชั่น"""

        # (1) แสดงสถานะ 'กำลังดำเนินการ' ทันที
        if hasattr(self, 'ai_caps_output'):  # <--- แก้ไข (1): เช็กกล่องที่ถูกต้อง

            # เคลียร์ทั้งสองกล่องเพื่อเตรียมรับข้อมูลใหม่
            self.ai_caps_output.delete("1.0", "end")  # <--- แก้ไข (2): เคลียร์กล่องแคปชั่น

            # (แนะนำ) เคลียร์กล่องแท็กด้วย
            if hasattr(self, 'ai_tags_output'):
                self.ai_tags_output.delete("1.0", "end")

            # แสดงสถานะ "กำลังโหลด" ในกล่องแคปชั่น
            self.ai_caps_output.insert("1.0",
                                       "กำลังเรียก AI... กรุณารอสักครู่ (ไม่ควรเกิน 20 วินาที)")  # <--- แก้ไข (3)

        # (2) รัน _generate_caption ใน Thread แยก
        threading.Thread(target=self._generate_caption, daemon=True).start()
#--------------------------------------------------------------
    def _ai_scan_videos(self, video_dir: str):
        """คืนลิสต์พาธไฟล์วิดีโอที่รองรับ (ไม่ลงไดเรกทอรีย่อย)"""
        import os
        exts = {".mp4", ".mov", ".mkv", ".avi", ".wmv"}
        items = []
        for name in os.listdir(video_dir):
            p = os.path.join(video_dir, name)
            if os.path.isfile(p) and os.path.splitext(name)[1].lower() in exts:
                items.append(p)
        return items

    def _ai_get_video_resolution(self, path: str):
        """
        คืน (width, height) หากอ่านได้, ไม่งั้นคืน None
        ลำดับ: ffprobe (จากช่อง UI/ค่าเดิม) -> which("ffprobe") -> OpenCV -> MoviePy
        พร้อม log หนึ่งครั้งถ้าไม่มีเอนจินให้ใช้
        """
        import shutil, subprocess, os

        # 0) candidate list for ffprobe
        candidates = []
        ui_ffprobe = (getattr(self, "ai_ffprobe_path", tk.StringVar(value="")).get() or "").strip()
        if ui_ffprobe and os.path.isfile(ui_ffprobe):
            candidates.append(ui_ffprobe)
        # common location (ปรับได้ตามที่คุณใช้งาน)
        common = os.path.join("D:\\Shopee", "ffmpeg", "bin", "ffprobe.exe")
        if os.path.isfile(common):
            candidates.append(common)
        which_probe = shutil.which("ffprobe")
        if which_probe:
            candidates.append(which_probe)

        # 1) ffprobe
        for ffprobe in candidates:
            try:
                cmd = [ffprobe, "-v", "error", "-select_streams", "v:0",
                       "-show_entries", "stream=width,height", "-of", "csv=p=0", path]
                cp = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=10)
                if cp.returncode == 0:
                    out = (cp.stdout or "").strip()
                    if out and "," in out:
                        w, h = out.split(",", 1)
                        return int(float(w)), int(float(h))
            except Exception:
                pass

        # 2) OpenCV
        try:
            import cv2  # type: ignore
            cap = cv2.VideoCapture(path)
            if cap.isOpened():
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                if w > 0 and h > 0:
                    return w, h
        except Exception:
            pass

        # 3) MoviePy
        try:
            from moviepy.editor import VideoFileClip  # type: ignore
            with VideoFileClip(path) as clip:
                w, h = clip.size
                if w and h:
                    return int(w), int(h)
        except Exception:
            pass

        # แจ้งหนึ่งครั้งว่าไม่มีเอนจิน (ป้องกัน log ล้น)
        if not getattr(self, "_ai_warn_no_probe", False):
            self._ai_log_line(
                "[AI] ⚠️ ไม่มี ffprobe / OpenCV / MoviePy ให้ใช้ → อ่านความละเอียดไม่ได้ (ไฟล์จะถูกนับเป็นต่ำกว่าเกณฑ์)")
            self._ai_warn_no_probe = True
        return None

    #-----------------------------------------
    def _ai_render_name(self, pattern: str, *, index: int, stem: str, now):
        """เรนเดอร์แพทเทิร์น เช่น spv_{date:YYYYMMDD}_{index:03d}"""
        import random, string

        def fmt_datetime(tag: str):
            # tag: 'date:YYYYMMDD' | 'time:HHmmss'
            if ":" in tag:
                head, fmt = tag.split(":", 1)
            else:
                head, fmt = tag, None
            if head == "date":
                return now.strftime(fmt or "%Y%m%d")
            if head == "time":
                return now.strftime(fmt or "%H%M%S")
            return ""

        out = ""
        i = 0
        while i < len(pattern):
            ch = pattern[i]
            if ch == "{" and "}" in pattern[i + 1:]:
                j = pattern.find("}", i + 1)
                token = pattern[i + 1:j]
                # index with format e.g. index:03d
                if token.startswith("index"):
                    if ":" in token:
                        _, fmt = token.split(":", 1)
                        try:
                            out += format(index, fmt)
                        except Exception:
                            out += str(index)
                    else:
                        out += str(index)
                elif token.startswith("date") or token.startswith("time"):
                    out += fmt_datetime(token)
                elif token == "random4":
                    out += "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
                elif token == "stem":
                    out += stem
                else:
                    out += "{" + token + "}"
                i = j + 1
            else:
                out += ch
                i += 1

        # sanitize เบื้องต้น (กันอักขระต้องห้ามบน Windows)
        forbidden = '<>:"/\\|?*'
        out = "".join("_" if c in forbidden else c for c in out).strip().rstrip(".")
        # จำกัดความยาวโหด ๆ กันยาวเกินไป
        if len(out) > 120:
            out = out[:116] + "_x"
        return out

    #-----------------AI CAPTION-----------------------------------------
    # ----------------------------------------------------------
    def _ai_create_caption(self):
        """
        ทำจริง: สแกน -> คัด <cutoffp (ลบ/ย้ายตามตัวเลือก) -> รีเนมไฟล์ที่ผ่าน -> เขียน caption.csv (atomic)
        CSV schema: video_file, caption, hashtags, link
        - ดึง caption/hashtags/link จาก 'ผลลัพธ์ AI' ก่อน
        - ถ้า AI ว่าง → fallback ไปช่อง default (caption/tags/link)
        - ถ้าจำนวนบรรทัด AI/Default น้อยกว่าจำนวนไฟล์ → วนซ้ำให้ครบอัตโนมัติ
        """
        import os, datetime, random, time, csv, shutil

        # --------- อ่านค่าจาก UI หลัก ---------
        video_dir = (self.ai_video_dir.get() or "").strip()
        if not video_dir or not os.path.isdir(video_dir):
            self._ai_log_line("[AI] กรุณาเลือกโฟลเดอร์วิดีโอที่ถูกต้องก่อน")
            return

        try:
            cutoff = int(self.ai_lowres_cutoff.get())
        except Exception:
            cutoff = 480

        try:
            count = int(self.ai_count.get() or 1)
        except Exception:
            count = 1

        order = (self.ai_order_mode.get() or "modified_desc").strip().lower()
        do_shuffle = bool(self.ai_shuffle.get())
        pattern = (self.ai_pattern.get() or "spv_{date:YYYYMMDD}_{index:03d}").strip()
        use_rel = bool(self.ai_use_relative.get())
        hard_delete_lowres = bool(self.ai_lowres_delete.get())

        # เตรียม CSV path (และโฟลเดอร์ caption)
        csv_path = (self.ai_csv_path.get() or "").strip()
        if not csv_path:
            now = datetime.datetime.now()
            csv_path = os.path.join("caption", now.strftime("%Y%m%d_%H%M%S") + ".csv")
            self.ai_csv_path.set(csv_path)
        os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)

        # --------- สแกนไฟล์วิดีโอ ----------
        self._ai_log_line(f"[AI] เริ่มทำงานจริงที่: {video_dir}")
        files = self._ai_scan_videos(video_dir)
        if not files:
            self._ai_log_line("[AI] ไม่พบไฟล์วิดีโอที่รองรับ (.mp4 .mov .mkv .avi .wmv)")
            return
        self._ai_log_line(f"[AI] พบไฟล์ทั้งหมด: {len(files)}")

        # --------- กรองความละเอียด ----------
        ok, low = [], []
        if cutoff <= 0:
            for p in files:
                ok.append((p, None, None))
            self._ai_log_line("[AI] ปิดการกรองความละเอียด (cutoff=0) — จะไม่ลบ/ย้ายไฟล์ใด ๆ จากขนาด")
        else:
            self._ai_log_line(f"[AI] ตรวจความละเอียด (short-side ≥ {cutoff}) …")
            for p in files:
                wh = self._ai_get_video_resolution(p)
                if not wh:
                    # อ่านไม่ได้ → ถือว่าต่ำกว่าเกณฑ์
                    low.append((p, None))
                    continue
                w, h = wh
                if min(w, h) >= cutoff:
                    ok.append((p, w, h))
                else:
                    low.append((p, (w, h)))

        self._ai_log_line(f"[AI] ผ่านเกณฑ์: {len(ok)} • ต่ำกว่าเกณฑ์: {len(low)}")

        # --------- จัดการไฟล์ต่ำกว่าเกณฑ์ ----------
        if cutoff > 0 and low:
            if hard_delete_lowres:
                removed = 0
                for p, _ in low:
                    if self._ai_try_remove(p):
                        removed += 1
                self._ai_log_line(f"[AI] ลบถาวรไฟล์ต่ำกว่าเกณฑ์แล้ว {removed}/{len(low)}")
            else:
                trash = os.path.join(video_dir, "__trash_lowres")
                os.makedirs(trash, exist_ok=True)
                moved = 0
                for p, _ in low:
                    try:
                        base = os.path.basename(p)
                        dst = self._ai_unique_name_in_dir(trash, base)
                        shutil.move(p, dst)
                        moved += 1
                    except Exception:
                        pass
                self._ai_log_line(f"[AI] ย้ายไฟล์ต่ำกว่าเกณฑ์ไป {trash} จำนวน {moved}/{len(low)}")

        if not ok:
            self._ai_log_line("[AI] ไม่มีไฟล์ที่ผ่านเกณฑ์พอทำงานต่อ")
            return

        # --------- จัดลำดับ / สุ่ม / จำกัดจำนวน ----------
        if order == "name_asc":
            ok.sort(key=lambda t: os.path.basename(t[0]).lower())
        else:
            ok.sort(key=lambda t: os.path.getmtime(t[0]), reverse=True)

        if do_shuffle:
            random.shuffle(ok)

        ok = ok[:max(1, count)]
        self._ai_log_line(f"[AI] จะทำการรีเนมและบันทึก {len(ok)} ไฟล์")

        # --------- รีเนม ----------
        now = datetime.datetime.now()
        renamed_map = []  # [(old_path, new_path)]
        try:
            for i, (old_p, w, h) in enumerate(ok, start=1):
                stem = os.path.splitext(os.path.basename(old_p))[0]
                ext = os.path.splitext(old_p)[1].lower()
                new_stem = self._ai_render_name(pattern, index=i, stem=stem, now=now)
                safe_name = new_stem + ext
                target = self._ai_unique_name_in_dir(video_dir, safe_name)
                self._ai_try_rename(old_p, target)
                renamed_map.append((old_p, target))
                self._ai_log_line(f"[AI] รีเนม: {os.path.basename(old_p)} -> {os.path.basename(target)}")
        except Exception as e:
            # Rollback ถ้ามีปัญหา
            self._ai_log_line(f"[AI] Error ระหว่างรีเนม: {e} → กำลังย้อนกลับชื่อเดิม…")
            for old_p, new_p in reversed(renamed_map):
                try:
                    if os.path.exists(new_p) and (not os.path.exists(old_p)):
                        os.replace(new_p, old_p)
                except Exception:
                    pass
            self._ai_log_line("[AI] ย้อนกลับเสร็จสิ้น")
            return

        # --------- ดึงผลลัพธ์ AI + fallback default ----------
        # Candidates ของกล่องผลลัพธ์ AI (Text/StringVar/Entry)
        def _get_ai_value(cands):
            if hasattr(self, "_ai_try_get_ai_value"):
                return self._ai_try_get_ai_value(cands)
            return ""

        cap_ai_text = _get_ai_value([
            "ai_caps_output",  # Text ที่ใช้จริง
            "ai_output_caption_text", "ai_caption_text", "ai_caption_var",
            "txt_ai_caption", "entry_ai_caption", "ai_caption_entry",
        ])
        tags_ai_text = _get_ai_value([
            "ai_tags_output",  # Text ที่ใช้จริง
            "ai_output_tags_text", "ai_hashtags_text", "ai_tags_var",
            "txt_ai_hashtags", "entry_ai_tags", "ai_hashtags_entry",
        ])
        link_ai_text = _get_ai_value([
            "ai_links_output",  # Text ที่ใช้จริง
            "ai_output_link_text", "ai_product_url_text", "ai_product_url_var",
            "txt_ai_link", "entry_ai_link", "ai_affiliate_link",
        ])

        cap_default = (self.ai_default_caption.get() if hasattr(self, "ai_default_caption") else "") or ""
        tags_default = (self.ai_default_tags.get() if hasattr(self, "ai_default_tags") else "") or ""
        link_default = (self.ai_default_link.get() if hasattr(self, "ai_default_link") else "") or ""

        def _split_lines(s: str):
            return [ln.strip() for ln in (s or "").replace("\r", "").split("\n") if ln.strip()]

        caps_list = _split_lines(cap_ai_text) or ([cap_default] if cap_default else [])
        tags_list = _split_lines(tags_ai_text) or ([tags_default] if tags_default else [])
        links_list = _split_lines(link_ai_text) or ([link_default] if link_default else [])

        # ทำความยาวให้พอดีกับจำนวนไฟล์ (วนซ้ำ)
        n = len(renamed_map)

        def _pad_or_cycle(lst: list[str], n: int, fill: str = "") -> list[str]:
            if not lst:
                return [fill] * n
            if len(lst) >= n:
                return lst[:n]
            times = (n + len(lst) - 1) // len(lst)
            return (lst * times)[:n]

        caps_n = _pad_or_cycle(caps_list, n, cap_default)
        tags_n = _pad_or_cycle(tags_list, n, tags_default)
        links_n = _pad_or_cycle(links_list, n, link_default)


        # --------- สร้าง rows_for_csv (รองรับจำนวนแท็ก/ลิงก์ต่อโพสต์) ----------
        try:
            tag_n = max(0, int(self.var_hashtag_pick.get()))
        except Exception:
            tag_n = 5
        try:
            link_n = max(0, int(self.var_link_pick.get()))
        except Exception:
            link_n = 1

        import re
        def _split_lines_strict(s: str):
            return [ln.strip() for ln in (s or "").replace("\r", "").split("\n") if ln.strip()]

        # เตรียม pool: แท็ก = token เดี่ยว, ใส่ # และ unique ตามลำดับ
        raw_tags_join = "\n".join(_split_lines_strict(tags_ai_text))
        tokens = [t.strip() for t in re.split(r"[,\s]+", raw_tags_join) if t.strip()]
        tags_pool, _seen = [], set()
        for t in tokens:
            if not t.startswith("#"):
                t = "#" + t.lstrip("#")
            if t != "#" and t not in _seen:
                _seen.add(t)
                tags_pool.append(t)

        # ลิงก์เป็นบรรทัด ๆ
        links_pool = _split_lines_strict(link_ai_text)

        # แคปชั่นหนึ่งบรรทัด/แถว (ใช้ caps_n ที่คำนวณวนไว้แล้ว)
        def _take_window(pool: list[str], start_idx: int, k: int) -> list[str]:
            if k <= 0 or not pool:
                return []
            m = len(pool)
            return [pool[(start_idx + j) % m] for j in range(k)]

        rows_for_csv = []
        for i, (_, new_p) in enumerate(renamed_map):
            new_name = os.path.basename(new_p)
            video_file = new_name if use_rel else new_p

            caption_val = caps_n[i] if caps_n else ""

            # เลือก tag_n ตัว เลื่อนไปเรื่อย ๆ ต่อโพสต์
            if tags_pool:
                chosen_tags = _take_window(tags_pool, start_idx=i * max(tag_n, 1), k=tag_n)
            else:
                # fallback: ใช้ค่าจาก tags_n (วน) ถ้าผู้ใช้กรอกแถวละ 1 บรรทัด
                chosen_tags = [ (tags_n[i % len(tags_n)]) ] if tags_n else []
            hashtags_val = " ".join([t for t in chosen_tags if t]).strip()

            # เลือก link_n ตัว เลื่อนไปเรื่อย ๆ ต่อโพสต์
            if links_pool:
                chosen_links = _take_window(links_pool, start_idx=i * max(link_n, 1), k=link_n)
            else:
                chosen_links = [ (links_n[i % len(links_n)]) ] if links_n else []
            link_val = " ".join([u for u in chosen_links if u]).strip()

            rows_for_csv.append({
                "video_file": video_file,
                "caption":    caption_val,
                "hashtags":   hashtags_val,
                "link":       link_val,
            })

        # --------- เขียน CSV แบบ atomic ----------
        try:
            if not rows_for_csv:
                self._ai_log_line("[AI] ⚠️ ไม่มีข้อมูลใน rows_for_csv — ไม่เขียนไฟล์ CSV")
                return

            tmp = csv_path + ".part"
            with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["video_file", "caption", "hashtags", "link"])
                w.writeheader()
                w.writerows(rows_for_csv)
            os.replace(tmp, csv_path)

            self._ai_log_line(f"[AI] ✅ เขียน CSV สำเร็จ → {csv_path}")
            self._ai_log_line(f"[AI] รวมทั้งหมด {len(rows_for_csv)} แถว เขียนเสร็จสิ้น")
        except Exception as e:
            self._ai_log_line(f"[AI] ❌ ERROR เขียน CSV: {e}")
            import traceback; traceback.print_exc()

    #-------------------------------------------------------
    def _ai_unique_name_in_dir(self, directory: str, filename: str) -> str:
        """คืนพาธที่ไม่ชนในโฟลเดอร์นั้น ๆ: name.ext → name-1.ext …"""
        import os
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(directory, filename)
        k = 1
        while os.path.exists(candidate):
            candidate = os.path.join(directory, f"{base}-{k}{ext}")
            k += 1
        return candidate

    def _ai_try_rename(self, src: str, dst: str, retries: int = 6, delay: float = 0.4):
        """rename ด้วย retry ป้องกัน PermissionError/AV จับไฟล์ชั่วคราว"""
        import os, time, shutil
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        for _ in range(retries):
            try:
                os.replace(src, dst)  # atomic บนไดรฟ์เดียวกัน
                return
            except PermissionError:
                time.sleep(delay)
            except Exception:
                time.sleep(delay)
        # ครั้งสุดท้ายลอง copy+remove (กันบางเคส)
        try:
            shutil.copy2(src, dst)
            os.remove(src)
        except Exception as e:
            raise e

    def _ai_write_csv_atomic(self, csv_path: str, rows: list[dict]):
        """เขียน CSV แบบ atomic: .part -> .csv"""
        import os, csv, tempfile
        os.makedirs(os.path.dirname(os.path.abspath(csv_path)), exist_ok=True)
        tmp_path = csv_path + ".part"
        with open(tmp_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["video_file", "title", "caption", "tags", "product_url", "status",
                                              "created_at"])
            w.writeheader()
            for row in rows:
                w.writerow(row)
        os.replace(tmp_path, csv_path)

    def _ai_try_remove(self, path: str, retries: int = 4, delay: float = 0.3) -> bool:
        """ลบไฟล์ด้วย retry; คืน True ถ้าสำเร็จ"""
        import os, time
        for _ in range(retries):
            try:
                os.remove(path)
                return True
            except PermissionError:
                time.sleep(delay)
            except Exception:
                time.sleep(delay)
        return False
#------------------------------------------------------
    # ⬇️⬇️⬇️ คัดลอกโค้ด 3 ฟังก์ชันนี้ไปวางในคลาส App ⬇️⬇️⬇️

    def _periodic_status_update(self):
        """
        [ฟังก์ชันใหม่] อัปเดต Log, สถานะโพสต์ และเรียก Thread ตรวจสอบ CPU/RAM
        """

        # 1. อัปเดต Log Realtime และนับโพสต์
        for serial, q in self.device_log_queues.items():
            txt_widget = self.device_log_widgets.get(serial)
            if txt_widget:
                while not q.empty():
                    try:
                        line = q.get_nowait()
                        txt_widget.insert("end", line)
                        txt_widget.see("end")
                        self.global_log_text.insert("end", f"[{serial}] {line}")
                        self.global_log_text.see("end")

                        # Logic ตรวจจับการโพสต์สำเร็จ (ต้องตรงกับ Log จาก bot.py)
                        if "โพสต์สำเร็จ" in line or "POST SUCCESS" in line:
                            self.device_post_counts[serial] = self.device_post_counts.get(serial, 0) + 1
                            count_var = self.device_vars.get(serial, {}).get("post_count_var")
                            if count_var:
                                count_var.set(f"โพสต์วันนี้: {self.device_post_counts[serial]}")

                    except queue.Empty:
                        break
                    except Exception:
                        pass # (ป้องกัน Error ตอนปิดโปรแกรม)

        # 2. Schedule next run (3 วินาที)
        self.after(3000, self._periodic_status_update)
         # ใน def _periodic_status_update(self):
# ...
        # 3. Update per-device status metrics (CPU, RAM, Temp) in a separate thread
        if self.device_vars and not self.metrics_thread_running:
            # ล็อคก่อนเริ่ม
            self.metrics_thread_running = True
            threading.Thread(target=self._update_all_device_metrics_thread, daemon=True).start()


    def _get_device_metrics(self, serial: str, adb_path: str) -> dict:
        """
        [ฟังก์ชันใหม่] ดึง CPU, RAM, Temp ผ่าน ADB shell สำหรับ serial นี้
        """
        import subprocess, re
        metrics = {}

        # 1. CPU & RAM (using top)
        try:
            cmd = [adb_path, "-s", serial, "shell", "top", "-n", "1", "-b"]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=5)
            output = proc.stdout or ""

            cpu_match = re.search(r"(\d+)%cpu", output)
            if not cpu_match:
                    cpu_match = re.search(r"Cpu\s+usages?\s*:\s*([\d\.]+)%", output, re.IGNORECASE)

            metrics['cpu_perc'] = f"{float(cpu_match.group(1)):.1f}%" if cpu_match else '-'

            mem_match = re.search(r"Mem:\s*(\d+)\s*total,\s*(\d+)\s*free,\s*(\d+)\s*used", output, re.IGNORECASE)
            if mem_match:
                used_kb = int(mem_match.group(3))
                metrics['ram_used'] = f"{used_kb/1024/1024:.2f}G" # KB to GB
            else:
                mem_match = re.search(r"Mem:\s*(\d+)K\s*total,\s*(\d+)K\s*free", output, re.IGNORECASE)
                if mem_match:
                    total_kb = int(mem_match.group(1))
                    free_kb = int(mem_match.group(2))
                    used_kb = total_kb - free_kb
                    metrics['ram_used'] = f"{used_kb/1024/1024:.2f}G" # KB to GB
                else:
                    metrics['ram_used'] = '-'

        except Exception:
            metrics['cpu_perc'] = 'Err'
            metrics['ram_used'] = 'Err'


        # 2. Temperature
        try:
            temp = '-'
            cmd = [adb_path, "-s", serial, "shell", "cat", "/sys/class/thermal/thermal_zone*/temp"]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=3)
            output = proc.stdout or ""

            temps = [int(t.strip()) for t in output.splitlines() if t.strip().isdigit()]

            if temps:
                max_temp = max(temps)
                if max_temp > 1000: # 40000 -> 40.0
                    temp = f"{max_temp/1000:.1f}"
                elif max_temp > 100: # 405 -> 40.5
                    temp = f"{max_temp/10:.1f}"
                else: # 40 -> 40
                    temp = f"{max_temp}"
            else:
                cmd = [adb_path, "-s", serial, "shell", "dumpsys", "battery"]
                proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=3)
                output = proc.stdout or ""
                temp_match = re.search(r"temperature:\s*(\d+)", output, re.IGNORECASE)
                if temp_match:
                    temp_val = int(temp_match.group(1))
                    temp = f"{temp_val/10:.1f}" # 400 -> 40.0

            metrics['temp'] = temp

        except Exception:
            metrics['temp'] = 'Err'

        return metrics

    # ⬆️⬆️⬆️ สิ้นสุดโค้ด 3 ฟังก์ชันที่ต้องเพิ่ม ⬆️⬆️⬆️
    # ---------------- รัน/หยุด/เช็คอุปกรณ์ ----------------
    def _start_run_bot(self):
        if self.run_thread and self.run_thread.is_alive():
            messagebox.showwarning("กำลังทำงาน", "บอทกำลังทำงานอยู่ กรุณารอสิ้นสุดหรือกด 'หยุด' ก่อน")
            return
        config = self._collect_config()
        if not config:
            return

        # ตรวจ config ก่อน
        if not self._validate_before_run(config):
            return

        # ตรวจลิมิต 99/วัน และคาดการณ์จากจำนวนที่จะโพสต์
        try:
            max_per_day = 99
            will_do = int(config.get("max_posts") or 0)
            today = self._today_key()
            already = int(self._post_counter.get(today, 0))
            if already + will_do > max_per_day:
                ans = messagebox.askyesno("เตือนเกินโควตา",
                                          f"โพสต์วันนี้ {already} รายการแล้ว + จะรันอีก {will_do} = {already+will_do} (> {max_per_day})\nต้องการรันต่อหรือไม่?")
                if not ans:
                    return
        except Exception:
            pass

        # reset นับ “กำลังโพสต์”
        self.posts_in_progress = 0
        self._update_post_status()

        self.btn_run.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.status_label.config(text="สถานะ: กำลังรัน...")
        self.run_thread = threading.Thread(target=self._run_bot_thread, args=(config,), daemon=True)
        self.run_thread.start()

    def _run_bot_thread(self, config):
        try:
            self.log_to_ui("เริ่มต้นการทำงานของบอท.")
            # ใช้ path เต็มของ bot.py ป้องกันหาไฟล์ไม่เจอเวลา cwd เปลี่ยน
            bot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.py")
            # บังคับ unbuffered ทั้งระดับ interpreter และ env
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            cmd = [sys.executable, "-u", "-u", "-u", bot_path, "--config_data", json.dumps(config, ensure_ascii=False)]

            self.adb_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                env=env
            )
            for line in iter(proc.stdout.readline, ""):
                line = (line or "").rstrip("\n")
                if not line:
                    continue
                self.log_to_ui(line)
                # ▼▼▼ [โค้ดใหม่: ดึง Device ID] ▼▼▼
                dev_id_match = re.search(r'\[(.*?)\]', line)
                if dev_id_match:
                    dev_id = dev_id_match.group(1)
                else:
                    dev_id = None 
                # ▲▲▲ [จบโค้ดใหม่] ▲▲▲
                
                if line.startswith("กำลังโพสต์วิดีโอ:"):
                    self.posts_in_progress += 1
                    self.after(0, self._update_post_status)
                # ▼▼▼ [โค้ดที่ขาดหายไป: สำหรับนับยอดโพสต์สำเร็จ Real-time] ▼▼▼
                if "โพสต์สำเร็จ" in line:   
                    if self.posts_in_progress > 0:
                        self.posts_in_progress -= 1
                    self._inc_today_counter() # ฟังก์ชันนี้จะอัปเดตยอดนับ 'โพสต์วันนี้'
                    self.after(0, self._update_post_status)
                    # ▲▲▲ [จบส่วนที่เพิ่ม] ▲▲▲
        

            self.adb_process.wait()
            self.log_to_ui("บอททำงานเสร็จสิ้น")
        except Exception as e:
            self.log_to_ui(f"เกิดข้อผิดพลาด: {e}")
        finally:
            self.btn_run.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)
            self.status_label.config(text="สถานะ: พร้อมใช้งาน")
            self.adb_process = None

    def _stop_run_bot(self):
        if self.adb_process and self.adb_process.poll() is None:
            self.adb_process.terminate()
            self.log_to_ui("สั่งหยุดการทำงานของบอทแล้ว")

    def _check_device(self):
        adb_path = self.var_adb_path.get()
        device_id = self.var_device_id.get()
        conn = (self.var_adb_connection.get() or "USB").strip()
        if not adb_path or not device_id:
            messagebox.showerror("Error", "กรุณาระบุ ADB Path และ Device ID"); return
        try:
            if conn == "WiFi":
                # ลอง disconnect ก่อน แล้ว connect
                try:
                    subprocess.run(shlex.split(f'"{adb_path}" disconnect {device_id}'), capture_output=True, text=True, encoding='utf-8')
                except Exception:
                    pass
                c = subprocess.run(shlex.split(f'"{adb_path}" connect {device_id}'), capture_output=True, text=True, encoding='utf-8')
                self.log_to_ui((c.stdout or "").strip())

            # ตรวจรายการอุปกรณ์
            result = subprocess.run(shlex.split(f'"{adb_path}" devices'), capture_output=True, text=True, encoding='utf-8', check=True)
            found = False
            for ln in (result.stdout or "").splitlines():
                if ln.strip().startswith(device_id) and "device" in ln:
                    found = True; break
            if found:
                messagebox.showinfo("Success", f"[{conn}] เชื่อมต่ออุปกรณ์ {device_id} สำเร็จ")
            else:
                messagebox.showerror("Error", f"[{conn}] ไม่พบอุปกรณ์ {device_id}\n\n{result.stdout}")
        except FileNotFoundError:
            messagebox.showerror("Error", "ไม่พบไฟล์ adb.exe กรุณาตรวจสอบเส้นทาง")
        except Exception as e:
            messagebox.showerror("Error", f"เกิดข้อผิดพลาด: {e}")

    #---------ส่วน config--------------------------------------
    def load_config_if_exists(self):
        """
        โหลดค่า default จากไฟล์ config.json (ถ้ามี) แล้วกระจายลง per-device (ถ้ามีแท็บอุปกรณ์แล้ว)
        ไม่แตะตัวแปรเก่าจากแท็บตั้งค่า (var_adb_path / var_device_id / ฯลฯ)
        """
        import os, json

        cfg_path = os.path.join(os.getcwd(), "config.json")
        if not os.path.isfile(cfg_path):
            return

        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            return

        # เก็บไว้เป็น default กลาง (ใช้ตอนสร้างแท็บอุปกรณ์ใหม่)
        self._global_defaults = {
            "adb_path": cfg.get("adb_path", ""),
            "app_package": cfg.get("app_package", ""),
            "local_videos_dir": cfg.get("local_videos_dir", ""),
            "device_video_dir": cfg.get("device_video_dir", ""),
            "captions_csv": cfg.get("captions_csv", ""),
        }

        # ถ้ามีแท็บอุปกรณ์อยู่แล้ว ให้เติมค่าให้เฉพาะช่องที่ยังว่าง
        if hasattr(self, "device_vars"):
            for serial, vars_ in self.device_vars.items():
                def set_if_empty(key, value):
                    var = vars_.get(key)
                    if var and not (var.get() or "").strip():
                        var.set(value)

                set_if_empty("adb_path", self._global_defaults["adb_path"])
                set_if_empty("app_package", self._global_defaults["app_package"])
                set_if_empty("local_videos_dir", self._global_defaults["local_videos_dir"])
                set_if_empty("device_video_dir", self._global_defaults["device_video_dir"])
                # captions.csv ต้องเป็นของแต่ละเครื่องจริง ๆ — ใส่เฉพาะถ้าคุณอยากมีค่าเริ่มต้น
                # set_if_empty("captions_csv", self._global_defaults["captions_csv"])

    # ========================== ส่วน: โควตา/โพสต์ประจำวัน ==========================
    def _today_key(self):
        # นับวันแบบ 00:01-23:59 ของวันที่เครื่อง
        import datetime as _dt
        now = _dt.datetime.now()
        return now.strftime("%Y-%m-%d")

    def _counter_path(self):
        return Path("post_counter.json")

    def _load_post_counter(self):
        self._post_counter = {}
        try:
            if self._counter_path().exists():
                self._post_counter = json.load(open(self._counter_path(), "r", encoding="utf-8"))
        except Exception:
            self._post_counter = {}
        # sync ค่า UI
        self.posts_today = int(self._post_counter.get(self._today_key(), 0))

    def _save_post_counter(self):
        try:
            json.dump(self._post_counter, open(self._counter_path(), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _inc_today_counter(self, step=1):
        key = self._today_key()
        self._post_counter[key] = int(self._post_counter.get(key, 0)) + int(step)
        self.posts_today = int(self._post_counter.get(key, 0))
        self._save_post_counter()

    def _update_post_status(self):
        self.post_status_var.set(f"(โพสต์วันนี้.{self.posts_today} | กำลังโพสต์.{self.posts_in_progress})")

    def _list_posted_videos(self):
        """
        คืนรายชื่อไฟล์ใน Shopee/posted (เพื่อให้บอทข้ามชื่อเดิม)
        """
        try:
            root = Path(self.var_local_videos_dir.get() or "D:/Shopee/videos")
            posted = Path(root).parent / "posted"
            if posted.exists():
                return sorted([p.name for p in posted.iterdir() if p.is_file()])
        except Exception:
            pass
        return []

    # ========================== ส่วนแสดงผลสถานะ/อุปกรณ์ ==========================
    def _update_posts_label(self):
        # คง method เดิมไว้เพื่อความเข้ากันได้ แต่ไปอัปเดตตัวแปรใหม่แทน
        self._update_post_status()

    def _run_shell(self, cmd_list):
        try:
            r = subprocess.run(cmd_list, capture_output=True, text=True, encoding='utf-8', timeout=5)
            return r.stdout or ""
        except Exception:
            return ""

    def _get_device_status(self):
        """
        คืนสตริงสถานะอุปกรณ์: Temp, CPU%, RAM
        - CPU% พยายามพาร์สจาก dumpsys cpuinfo ถ้าไม่มี -> คำนวณจาก /proc/stat (delta)
        """
        adb_path = self._find_adb_path()   # ใช้ helper หาค่า ADB จาก per-device; ถ้าไม่เจอ คืน 'adb'
        device_id = (self.var_device_id.get() or "").strip()
        if not adb_path or not device_id:
            return "อุปกรณ์: - | Temp: - | CPU: - | RAM: -"

        # ---------- Temperature ----------
        temp_c = "-"
        out_batt = self._run_shell(shlex.split(f'"{adb_path}" -s {device_id} shell dumpsys battery'))
        m = re.search(r'temperature:\s*(\d+)', out_batt)
        if m:
            try:
                temp_c = f"{int(m.group(1))/10:.1f}°C"
            except Exception:
                temp_c = "-"

        # ---------- CPU (try dumpsys cpuinfo) ----------
        cpu_pct = None
        out_cpu = self._run_shell(shlex.split(f'"{adb_path}" -s {device_id} shell dumpsys cpuinfo'))
        m2 = re.search(r'Total CPU usage:\s*([\d\.]+)%', out_cpu)
        if m2:
            cpu_pct = f"{m2.group(1)}%"

        # ---------- CPU fallback: /proc/stat delta ----------
        if cpu_pct is None:
            out_stat = self._run_shell(shlex.split(f'"{adb_path}" -s {device_id} shell cat /proc/stat | head -n 1'))
            parts = out_stat.strip().split()
            if parts and parts[0] == "cpu" and len(parts) >= 5:
                try:
                    nums = [float(x) for x in parts[1:8]]  # user nice system idle iowait irq softirq
                    idle = nums[3] + (nums[4] if len(nums) > 4 else 0.0)  # idle + iowait
                    total = sum(nums)
                    if self._prev_proc_stat is not None:
                        prev_total, prev_idle = self._prev_proc_stat
                        dt_total = max(1.0, total - prev_total)
                        dt_idle = max(0.0, idle - prev_idle)
                        usage = (1.0 - (dt_idle / dt_total)) * 100.0
                        usage = max(0.0, min(100.0, usage))
                        cpu_pct = f"{usage:.0f}%"
                    self._prev_proc_stat = (total, idle)
                except Exception:
                    cpu_pct = None
            if cpu_pct is None:
                cpu_pct = "-"

        # ---------- RAM ----------
        ram_text = "-"
        out_mem = self._run_shell(shlex.split(f'"{adb_path}" -s {device_id} shell cat /proc/meminfo'))
        try:
            mt = re.search(r'MemTotal:\s+(\d+)\s+kB', out_mem)
            ma = re.search(r'MemAvailable:\s+(\d+)\s+kB', out_mem)
            if mt and ma:
                total_kb = int(mt.group(1)); avail_kb = int(ma.group(1))
                total_gb = total_kb / (1024*1024)
                avail_gb = avail_kb / (1024*1024)
                ram_text = f"{avail_gb:.1f}/{total_gb:.1f} GB free"
        except Exception:
            pass

        return f"อุปกรณ์: {device_id or '-'} | Temp: {temp_c} | CPU: {cpu_pct} | RAM: {ram_text}"

    def _update_device_status_label(self):
        try:
            self.device_status_var.set(self._get_device_status())
        except Exception:
            self.device_status_var.set("อุปกรณ์: - | Temp: - | CPU: - | RAM: -")

    # ========================== แสดงAdb ==========================
    # --- NEW: Thread Runner for all metrics ---
    def _update_all_device_metrics_thread(self):
        """
        [ฟังก์ชันใหม่] รันใน thread แยก เพื่อดึง metric ทุกเครื่องพร้อมกัน
        """
        import subprocess, re

        try: # <--- เพิ่ม try ที่นี่
            for serial in list(self.device_vars.keys()):
                try:
                    adb = self.device_vars[serial]["adb_path"].get()
                    if not adb or not adb.strip():
                        adb = "adb"

                    metrics = self._get_device_metrics(serial, adb)

                    if metrics and serial in self.device_vars:
                        status_text = f"Temp: {metrics.get('temp', '-')}°C | CPU: {metrics.get('cpu_perc', '-')} | RAM: {metrics.get('ram_used', '-')}"
                        self.after(0, lambda s=serial, t=status_text: self.device_vars[s]["status_var"].set(t))
                except Exception:
                    pass
        finally: # <--- เพิ่ม finally ที่นี่
            # ปลดล็อคเสมอ เมื่อทำงานเสร็จ (ไม่ว่าจะสำเร็จหรือล้มเหลว)
            self.metrics_thread_running = False

    # --- NEW: Core ADB Metrics Fetcher ---
    def _get_device_metrics(self, serial: str, adb_path: str) -> dict:
        """ดึง CPU, RAM, Temp ผ่าน ADB shell สำหรับ serial นี้"""
        import subprocess, re
        metrics = {}

        # 1. CPU & RAM (using top)
        try:
            # ใช้ -n 1 (1 iteration) และ -b (batch mode)
            cmd = [adb_path, "-s", serial, "shell", "top", "-n", "1", "-b"]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=5)
            output = proc.stdout or ""

            # CPU (Global usage) - (Parsing 'top' output is very unreliable across Android versions)
            # ลองหาบรรทัดสรุป CPU
            cpu_match = re.search(r"(\d+)%cpu", output) # แบบง่าย
            if not cpu_match:
                    cpu_match = re.search(r"Cpu\s+usages?\s*:\s*([\d\.]+)%", output, re.IGNORECASE) # แบบละเอียด

            metrics['cpu_perc'] = f"{float(cpu_match.group(1)):.1f}%" if cpu_match else '-'

            # RAM (Used/Free from Mem line)
            mem_match = re.search(r"Mem:\s*(\d+)\s*total,\s*(\d+)\s*free,\s*(\d+)\s*used", output, re.IGNORECASE)
            if mem_match:
                used_kb = int(mem_match.group(3))
                metrics['ram_used'] = f"{used_kb/1024/1024:.2f}G" # Convert KB to GB
            else:
                # หาก parsing Mem: ล้มเหลว (บางเครื่อง Android)
                mem_match = re.search(r"Mem:\s*(\d+)K\s*total,\s*(\d+)K\s*free", output, re.IGNORECASE)
                if mem_match:
                    total_kb = int(mem_match.group(1))
                    free_kb = int(mem_match.group(2))
                    used_kb = total_kb - free_kb
                    metrics['ram_used'] = f"{used_kb/1024/1024:.2f}G" # Convert KB to GB
                else:
                    metrics['ram_used'] = '-'

        except Exception:
            metrics['cpu_perc'] = 'Err'
            metrics['ram_used'] = 'Err'


        # 2. Temperature (using thermal zone or dumpsys battery)
        try:
            temp = '-'
            # Try thermal zone (usually more accurate CPU/SoC temp)
            cmd = [adb_path, "-s", serial, "shell", "cat", "/sys/class/thermal/thermal_zone*/temp"]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=3)
            output = proc.stdout or ""

            temps = [int(t.strip()) for t in output.splitlines() if t.strip().isdigit()]

            if temps:
                max_temp = max(temps)
                if max_temp > 1000: # Assume milli-celsius (e.g., 40000)
                    temp = f"{max_temp/1000:.1f}"
                elif max_temp > 100: # Assume 3-digit celsius (e.g. 405 = 40.5C)
                    temp = f"{max_temp/10:.1f}"
                else: # Assume celsius (e.g., 40)
                    temp = f"{max_temp}"
            else:
                # Fallback to dumpsys battery (usually battery temp)
                cmd = [adb_path, "-s", serial, "shell", "dumpsys", "battery"]
                proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=3)
                output = proc.stdout or ""
                temp_match = re.search(r"temperature:\s*(\d+)", output, re.IGNORECASE)
                if temp_match:
                    temp_val = int(temp_match.group(1))
                    temp = f"{temp_val/10:.1f}" # Tenths of a degree Celsius (e.g., 400 = 40.0C)

            metrics['temp'] = temp

        except Exception:
            metrics['temp'] = 'Err'

        return metrics
    # --- New Helper for general status ---
    def _update_device_count(self):
        """อัปเดตสถานะจำนวนอุปกรณ์ใน status bar หลัก"""
        count = len(self.device_vars)
        if count > 0:
            self.device_status_var.set(f"อุปกรณ์: {count} เครื่องพร้อมใช้งาน")
        else:
            self.device_status_var.set("อุปกรณ์: ไม่พบ")


    # --- Core ADB Metrics Fetcher ---
    def _get_device_metrics(self, serial: str, adb_path: str) -> dict:
        """ดึง CPU, RAM, Temp ผ่าน ADB shell สำหรับ serial นี้"""
        import subprocess, re
        metrics = {}

        # 1. CPU & RAM (using top) - Simplified approach for quick global status
        try:
            cmd = [adb_path, "-s", serial, "shell", "top", "-n", "1", "-o", "PID,CPU,VSIZE,RSS,NAME", "-b"]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=5)
            output = proc.stdout or ""

            # CPU (Global usage)
            cpu_match = re.search(r"Cpu\s+usages?\s*:\s*([\d\.]+)%", output, re.IGNORECASE)
            metrics['cpu_perc'] = f"{float(cpu_match.group(1)):.1f}%" if cpu_match else '-'

            # RAM (Used/Free from Mem line)
            mem_match = re.search(r"Mem:\s*(\d+)K\s*total,\s*(\d+)K\s*free,\s*(\d+)K\s*used", output, re.IGNORECASE)
            if mem_match:
                used_kb = int(mem_match.group(3))
                metrics['ram_used'] = f"{used_kb/1024/1024:.2f}G" # Convert KB to GB
            else:
                metrics['ram_used'] = '-'

        except Exception:
            metrics['cpu_perc'] = 'Err'
            metrics['ram_used'] = 'Err'


        # 2. Temperature (using thermal zone or dumpsys battery)
        try:
            temp = '-'
            # Try thermal zone (usually more accurate CPU/SoC temp)
            cmd = [adb_path, "-s", serial, "shell", "cat", "/sys/class/thermal/thermal_zone*/temp"]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=3)
            output = proc.stdout or ""

            temps = [int(t.strip()) for t in output.splitlines() if t.strip().isdigit()]

            if temps:
                max_temp = max(temps)
                if max_temp > 1000: # Assume milli-celsius (e.g., 40000)
                    temp = f"{max_temp/1000:.1f}"
                else: # Assume celsius (e.g., 40)
                    temp = f"{max_temp}"
            else:
                # Fallback to dumpsys battery (usually battery temp)
                cmd = [adb_path, "-s", serial, "shell", "dumpsys", "battery"]
                proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=3)
                output = proc.stdout or ""
                temp_match = re.search(r"temperature:\s*(\d+)", output, re.IGNORECASE)
                if temp_match:
                    temp_val = int(temp_match.group(1))
                    temp = f"{temp_val/10:.1f}" # Tenths of a degree Celsius (e.g., 400 = 40.0C)

            metrics['temp'] = temp

        except Exception:
            metrics['temp'] = 'Err'

        return metrics
    # ---------------- Dashboard (Shopee Affiliate GraphQL) ----------------

    # ========================== แท็บ: AutoBot (แยกจากระบบ step เดิม) ==========================
    def setup_autobot_tab(self):
        frm = ttk.Frame(self.tab_autobot, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(frm); top.pack(fill=tk.X, pady=(0,8))
        ttk.Label(top, text="AutoBot — โพสต์อัตโนมัติจากตะกร้า/เทมเพลตในแอป Shopee (ไม่ใช้ไฟล์/step เดิม)").pack(side=tk.LEFT)

        ctl = ttk.Frame(frm); ctl.pack(fill=tk.X, pady=(0,8))
        ttk.Button(ctl, text="รีเฟรชอุปกรณ์ (ADB)", command=self._autobot_refresh_devices).pack(side=tk.LEFT, padx=4)
        ttk.Button(ctl, text="เชื่อมต่อ USB อัตโนมัติ", command=self._autobot_connect_usb_auto).pack(side=tk.LEFT, padx=4)
        ttk.Button(ctl, text="เริ่ม AutoBot ▶", command=self._autobot_start, style="Shopee.TButton").pack(side=tk.LEFT, padx=8)
        ttk.Button(ctl, text="หยุด AutoBot", command=self._autobot_stop).pack(side=tk.LEFT, padx=4)

        box = ttk.LabelFrame(frm, text="อุปกรณ์ที่เชื่อมต่อ", padding=8)
        box.pack(fill=tk.BOTH, expand=True)

        cols = ("serial","status","transport")
        self.autobot_tree = ttk.Treeview(box, columns=cols, show="headings", height=6)
        for c in cols:
            self.autobot_tree.heading(c, text=c.capitalize())
            self.autobot_tree.column(c, width=160 if c!="status" else 120, anchor="w")
        self.autobot_tree.pack(fill=tk.BOTH, expand=True)

        opt = ttk.LabelFrame(frm, text="โหมด/กลยุทธ์", padding=8)
        opt.pack(fill=tk.X, pady=(8,0))
        self.autobot_strategy = tk.StringVar(value="CART_TO_VIDEO")
        ttk.Radiobutton(opt, text="หยิบสินค้าจากตะกร้า → ทำวิดีโอ (ในแอป)", value="CART_TO_VIDEO", variable=self.autobot_strategy).pack(side=tk.LEFT, padx=6)
        ttk.Radiobutton(opt, text="หยิบสินค้าจาก Affiliate → ทำวิดีโอ (ในแอป)", value="AFF_TO_VIDEO", variable=self.autobot_strategy).pack(side=tk.LEFT, padx=6)

        note = ttk.Label(frm, text="* แท็บนี้ไม่ยุ่งกับขั้นตอน/ไฟล์วิดีโอ/แคปชั่นจากระบบเดิม และจะควบคุมผ่าน UI ของแอป Shopee โดยตรง", foreground="#555")
        note.pack(anchor="w", pady=(6,0))


    #-------------------------------------------------
    def _autobot_run_cmd(self, cmd: str, check=False):
        try:
            r = subprocess.run(shlex.split(cmd), capture_output=True, text=True, encoding="utf-8", check=check)
            out = (r.stdout or "").strip()
            err = (r.stderr or "").strip()
            if out: self.log_to_ui(out)
            if err: self.log_to_ui(err)
            return r
        except Exception as e:
            self.log_to_ui(f"[AutoBot] ERROR: {e}")
            raise

    def _autobot_refresh_devices(self):
        adb_path = self._find_adb_path()   # ใช้ helper หาค่า ADB จาก per-device; ถ้าไม่เจอ คืน 'adb'
        if not adb_path:
            messagebox.showerror("Error", "กรุณาระบุ ADB Path ในแท็บตั้งค่า"); return
        try:
            r = self._autobot_run_cmd(f'"{adb_path}" devices', check=True)
            rows = []
            for ln in (r.stdout or "").splitlines():
                ln = ln.strip()
                if not ln or ln.startswith("List of devices"):
                    continue
                parts = ln.split()
                serial = parts[0]
                status = parts[1] if len(parts)>1 else "-"
                transport = "wifi" if ":" in serial else "usb"
                rows.append((serial, status, transport))

            for iid in self.autobot_tree.get_children():
                self.autobot_tree.delete(iid)
            for t in rows:
                self.autobot_tree.insert("", "end", values=t)
            if not rows:
                self.log_to_ui("[AutoBot] ไม่พบอุปกรณ์ — เสียบสาย USB และอนุญาตการดีบัก")
        except FileNotFoundError:
            messagebox.showerror("Error", "ไม่พบ adb.exe")
        except Exception as e:
            messagebox.showerror("Error", f"เกิดข้อผิดพลาด: {e}")

    def _autobot_connect_usb_auto(self):
        adb_path = self._find_adb_path()   # ใช้ helper หาค่า ADB จาก per-device; ถ้าไม่เจอ คืน 'adb'
        if not adb_path:
            messagebox.showerror("Error", "กรุณาระบุ ADB Path"); return
        try:
            self._autobot_run_cmd(f'"{adb_path}" kill-server')
            self._autobot_run_cmd(f'"{adb_path}" start-server', check=True)
            self._autobot_refresh_devices()
            messagebox.showinfo("AutoBot", "รีสตาร์ท ADB และรีเฟรชอุปกรณ์แล้ว")
        except Exception as e:
            messagebox.showerror("Error", f"เชื่อมต่อ USB อัตโนมัติไม่สำเร็จ: {e}")

    def _autobot_start(self):
        if getattr(self, "_autobot_thread", None) and self._autobot_thread.is_alive():
            messagebox.showwarning("AutoBot", "AutoBot กำลังทำงานอยู่"); return
        self._autobot_stop_flag = False
        self._autobot_thread = threading.Thread(target=self._autobot_worker, daemon=True)
        self._autobot_thread.start()
        self.log_to_ui("[AutoBot] เริ่มทำงาน...")

    def _autobot_stop(self):
        self._autobot_stop_flag = True
        self.log_to_ui("[AutoBot] ขอหยุดทำงาน...")

    def _autobot_worker(self):
        adb_path = self._find_adb_path()   # ใช้ helper หาค่า ADB จาก per-device; ถ้าไม่เจอ คืน 'adb'
        if not adb_path:
            self.log_to_ui("[AutoBot] ไม่พบ ADB Path"); return
        try:
            r = self._autobot_run_cmd(f'"{adb_path}" devices', check=True)
            devices = []
            for ln in (r.stdout or "").splitlines():
                ln = ln.strip()
                if not ln or ln.startswith("List of devices"):
                    continue
                parts = ln.split()
                if len(parts)>=2 and parts[1]=="device":
                    devices.append(parts[0])
            if not devices:
                self.log_to_ui("[AutoBot] ไม่มีอุปกรณ์สถานะ device")
                return

            for serial in devices:
                if self._autobot_stop_flag: break
                self.log_to_ui(f"[AutoBot] เตรียมทำงานบนอุปกรณ์: {serial}")
                try:
                    pkg = (self.var_app_package.get() or "com.shopee.th").strip()
                    self._autobot_run_cmd(f'"{adb_path}" -s {serial} shell monkey -p {pkg} -c android.intent.category.LAUNCHER 1')
                    self.log_to_ui(f"[AutoBot] เปิดแอป {pkg} บน {serial} แล้ว")
                except Exception as e:
                    self.log_to_ui(f"[AutoBot] เปิดแอปล้มเหลวบน {serial}: {e}")
        except Exception as e:
            self.log_to_ui(f"[AutoBot] ผิดพลาด: {e}")
    #--------ปุ่มรีเซ็ทจอ---------------------------------------------
    # ==============================
    # 📱 Resize / Reset All Screen
    # ==============================
    import json

    def _adb_get_screen_info(self, adb_path, serial):
        """อ่าน wm size และ density จากอุปกรณ์"""
        import subprocess, re, shlex
        info = {"size": None, "density": None}
        try:
            out_size = subprocess.run(
                shlex.split(f'"{adb_path}" -s {serial} shell wm size'),
                capture_output=True, text=True, encoding="utf-8", timeout=6
            )
            m = re.search(r'Physical size:\s*([\dx]+)', out_size.stdout)
            if m: info["size"] = m.group(1).strip()

            out_den = subprocess.run(
                shlex.split(f'"{adb_path}" -s {serial} shell wm density'),
                capture_output=True, text=True, encoding="utf-8", timeout=6
            )
            m2 = re.search(r'Physical density:\s*(\d+)', out_den.stdout)
            if m2: info["density"] = m2.group(1).strip()
        except Exception as e:
            self._append_global(f"[ADB] อ่านขนาดจอ {serial} ไม่สำเร็จ: {e}")
        return info

    def _adb_set_screen(self, adb_path, serial, size=None, density=None):
        """ตั้ง wm size/density"""
        import subprocess, shlex
        try:
            if size:
                subprocess.run(shlex.split(f'"{adb_path}" -s {serial} shell wm size {size}'),
                               capture_output=True, text=True, encoding="utf-8", timeout=6)
                self._append_global(f"[{serial}] ตั้งขนาดจอ → {size}")
            if density:
                subprocess.run(shlex.split(f'"{adb_path}" -s {serial} shell wm density {density}'),
                               capture_output=True, text=True, encoding="utf-8", timeout=6)
                self._append_global(f"[{serial}] ตั้ง DPI → {density}")
        except Exception as e:
            self._append_global(f"[ADB] ตั้งค่าจอ {serial} ล้มเหลว: {e}")

    def _load_backup_json(self):
        import os
        path = os.path.join(os.getcwd(), "screen_backup.json")
        if os.path.isfile(path):
            try:
                return json.load(open(path, "r", encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_backup_json(self, data):
        import os
        path = os.path.join(os.getcwd(), "screen_backup.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._append_global(f"[ADB] เขียน screen_backup.json ไม่สำเร็จ: {e}")

    def _resize_all_screens(self):
        """ปรับขนาดจอทุกเครื่องเป็น 720x1600/320 DPI"""
        import time
        adb = self._find_adb_path()
        if not adb:
            messagebox.showerror("Error", "ไม่พบ adb.exe กลาง");
            return
        if not getattr(self, "device_vars", {}):
            messagebox.showwarning("คำเตือน", "ยังไม่มีอุปกรณ์ในรายการ");
            return

        data = self._load_backup_json()
        for serial in self.device_vars.keys():
            info = self._adb_get_screen_info(adb, serial)
            if info["size"] and info["density"]:
                data[serial] = info
            self._adb_set_screen(adb, serial, "720x1600", "320")
            self._append_global(f"[ADB] Resize {serial} → 720x1600 / 320dpi")
            time.sleep(0.5)
        self._save_backup_json(data)
        messagebox.showinfo("สำเร็จ", "ปรับขนาดจอทั้งหมดสำเร็จ (720x1600 / 320 DPI)")

    def _reset_all_screens(self):
        """คืนค่าจอทั้งหมดจาก screen_backup.json"""
        import time
        adb = self._find_adb_path()
        if not adb:
            messagebox.showerror("Error", "ไม่พบ adb.exe กลาง");
            return
        if not getattr(self, "device_vars", {}):
            messagebox.showwarning("คำเตือน", "ยังไม่มีอุปกรณ์ในรายการ");
            return

        data = self._load_backup_json()
        if not data:
            messagebox.showwarning("คำเตือน", "ยังไม่มีไฟล์ screen_backup.json หรือไม่มีข้อมูลเดิม");
            return

        for serial in self.device_vars.keys():
            old = data.get(serial)
            if old:
                self._adb_set_screen(adb, serial, old.get("size"), old.get("density"))
                self._append_global(f"[ADB] Reset {serial} → {old}")
            else:
                self._append_global(f"[ADB] ไม่มีข้อมูลจอเดิมของ {serial} — ข้าม")
            time.sleep(0.5)
        messagebox.showinfo("สำเร็จ", "คืนค่าจอทั้งหมดสำเร็จ")
    #-------------------ปุ่ม mirror-------------------------
    def _mirror_all_screens(self):
        """เปิด scrcpy ให้ครบทุกเครื่อง: รออุปกรณ์ + เปิดรอบปกติ + fallback force-adb-forward + renderer สำรอง"""
        import os, shlex, subprocess, time
        from tkinter import messagebox

        scrcpy_path = r"D:\Shopee\usb_driver\scrcpy.exe"  # ตำแหน่ง scrcpy.exe กลางของคุณ
        if not os.path.isfile(scrcpy_path):
            messagebox.showerror("Error", f"ไม่พบไฟล์ scrcpy.exe ที่ {scrcpy_path}")
            return

        adb_path = self._find_adb_path() if hasattr(self, "_find_adb_path") else None
        if not adb_path or not os.path.isfile(adb_path):
            messagebox.showerror("Error", "ไม่พบ adb.exe กลาง")
            return
        adb_dir = os.path.dirname(adb_path)

        if not getattr(self, "device_vars", {}):
            messagebox.showwarning("คำเตือน", "ยังไม่มีอุปกรณ์ในรายการ")
            return

        if not hasattr(self, "scrcpy_procs"):
            self.scrcpy_procs = {}

        # เตรียม env ที่เอาโฟลเดอร์ ADB ไปไว้หน้าสุดของ PATH
        env = os.environ.copy()
        env["PATH"] = adb_dir + os.pathsep + env.get("PATH", "")

        def _wait_for(serial, timeout=12):
            try:
                subprocess.run([adb_path, "-s", serial, "wait-for-device"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout, check=False)
                return True
            except Exception:
                return False

        def _start(serial, pass_no=1, render=None):
            """คืนค่า Popen หรือ None (ถ้าเปิดไม่สำเร็จ)"""
            base = [
                scrcpy_path,
                "-s", serial,
                "--max-size", "1024",
                "--no-audio",
                "--turn-screen-off",
                "--stay-awake",
                "--window-title", f"Device: {serial}",
            ]
            if pass_no == 2:
                base.append("--force-adb-forward")
            if render:
                base += ["--render-driver", render]

            try:
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            except Exception:
                creationflags = 0

            try:
                p = subprocess.Popen(base, creationflags=creationflags, env=env)
                time.sleep(0.8)
                if p.poll() is not None and p.returncode not in (None, 0):
                    return None
                return p
            except Exception as e:
                try:
                    self._append_global(
                        f"[SCRCPY] start fail {serial} (pass{pass_no}{' ' + render if render else ''}): {e}")
                except Exception:
                    pass
                return None

        launched = 0
        for serial in list(self.device_vars.keys()):
            _wait_for(serial)

            # PASS 1: โหมดปกติ
            p = _start(serial, pass_no=1, render=None)

            # PASS 2: บังคับ adb forward (บางเครื่องบล็อก reverse)
            if p is None:
                p = _start(serial, pass_no=2, render=None)

            # PASS 3: Windows renderer สำรอง
            if p is None and os.name == "nt":
                p = _start(serial, pass_no=2, render="direct3d")

            if p is not None:
                self.scrcpy_procs[serial] = p
                launched += 1
                try:
                    tag = "pass=1"
                    if "--force-adb-forward" in p.args:
                        tag = "pass=2"
                    if "--render-driver" in p.args:
                        tag += ", renderer=direct3d"
                    self._append_global(f"[SCRCPY] เปิดจอ {serial} ({tag})")
                except Exception:
                    pass
            else:
                try:
                    self._append_global(f"[SCRCPY] เปิดไม่สำเร็จ: {serial}")
                except Exception:
                    pass

            time.sleep(0.3)

        messagebox.showinfo("Mirror",
                            f"เปิดจอแล้ว {launched}/{len(self.device_vars)} เครื่อง\n(รอบปกติ + fallback ครบ)")

    #-----------------------------------------------------
    def _close_all_mirrors(self):
        """ปิดทุกหน้าจอ scrcpy ที่เปิดอยู่ (รองรับ Windows)"""
        import os, signal, time
        from tkinter import messagebox

        if not hasattr(self, "scrcpy_procs") or not self.scrcpy_procs:
            messagebox.showinfo("Mirror", "ไม่มีหน้าจอที่เปิดอยู่")
            return

        closed = 0
        for serial, p in list(self.scrcpy_procs.items()):
            try:
                if os.name == "nt":
                    # ส่ง CTRL_BREAK แล้ว terminate
                    try:
                        p.send_signal(signal.CTRL_BREAK_EVENT)
                        time.sleep(0.2)
                    except Exception:
                        pass
                    p.terminate()
                else:
                    os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                closed += 1
            except Exception as e:
                try:
                    self._append_global(f"[SCRCPY] ปิดไม่สำเร็จ {serial}: {e}")
                except Exception:
                    pass

        self.scrcpy_procs.clear()
        messagebox.showinfo("Mirror", f"ปิดจอทั้งหมดแล้ว ({closed} เครื่อง)")
    #---------------------------------
   # ---------- Utils for AI ----------
    # ---------- Utils for AI ----------
    # (ฟังก์ชันเดิม - ไม่แก้ไข)
    def _write_env_kv(self, key: str, value: str):
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        found = False;
        new_lines = []
        for ln in lines:
            if ln.startswith(f"{key}="):
                new_lines.append(f"{key}={value}");
                found = True
            else:
                new_lines.append(ln)
        if not found: new_lines.append(f"{key}={value}")
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")
        return env_path

    # (ฟังก์ชันเดิม - ไม่แก้ไข)
    def _paste_to_entry(self, entry_widget):
        try:
            text = self.clipboard_get()
        except Exception:
            text = ""
        entry_widget.delete(0, "end")
        entry_widget.insert(0, text.strip())

    # (ฟังก์ชันเดิม - ไม่แก้ไข)
    def _copy_from_text(self, text_widget):
        try:
            data = text_widget.get("1.0", "end").strip()
            self.clipboard_clear();
            self.clipboard_append(data)
            messagebox.showinfo("คัดลอกแล้ว", "คัดลอกผลลัพธ์ไปยังคลิปบอร์ดแล้ว")
        except Exception as e:
            messagebox.showerror("ข้อผิดพลาด", f"คัดลอกไม่สำเร็จ: {e}")

    # (ฟังก์ชันเดิม - ไม่แก้ไข)
    def _save_api_key(self):
        provider = (self.ai_provider_combo.get() or "Gemini").strip()
        key = (self.api_key_entry.get() or "").strip()
        if not key:
            messagebox.showerror("ข้อผิดพลาด", "กรุณาใส่ API Key ก่อน");
            return
        env_key = "GEMINI_API_KEY" if provider.lower().startswith("gemini") else "OPENAI_API_KEY"
        path = self._write_env_kv(env_key, key)
        messagebox.showinfo("สำเร็จ", f"บันทึก {env_key} ลงไฟล์:\n{path}")

    # (ฟังก์ชันเดิม - ที่เราเพิ่มครั้งที่แล้ว)
    def _manually_read_env(self, key_to_find):
        """(แผนสำรอง) พยายามเปิดไฟล์ .env หรือ env เพื่ออ่านค่า Key"""
        env_path = Path(".env") # (หา .env ในโฟลเดอร์เดียวกับ ui2.py)
        if not env_path.exists():
            env_path = Path("env") # (ลองหาไฟล์ชื่อ env ด้วย)

        if env_path.exists():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        clean_line = line.split('#', 1)[0].strip()
                        if clean_line.startswith(f"{key_to_find}="):
                            return clean_line.split("=", 1)[1].strip().strip('"').strip("'")
            except Exception as e:
                try:
                    self._append_global(f"[AI] Error reading .env manually: {e}")
                except AttributeError:
                    print(f"[AI] Error reading .env manually: {e}")
        return None

    # ▼▼▼ (แก้ไข) ฟังก์ชันนี้จะ "ช่างฟ้อง" มากขึ้น ▼▼▼
    def _get_provider_and_key(self):
        """(แก้ไข) เพิ่มการ Log ว่าหา Key เจอหรือไม่"""
        provider = (self.ai_provider_combo.get() or "Gemini").strip()
        env_key = ""
        key = ""

        # 1. พยายามดึงจาก "ช่องกรอก" (UI) ก่อน
        key_from_box = (self.api_key_entry.get() or "").strip()

        if key_from_box:
            key = key_from_box
            env_key = "(จากช่องกรอก UI)"
            self._append_global("[AI] ใช้ Key จากช่องกรอก UI")
        else:
            # 2. (ถ้าช่อง UI ว่าง) ค่อยไปหาใน .env
            self._append_global("[AI] ช่องกรอก UI ว่าง, กำลังค้นหาใน .env ...")
            if provider.lower().startswith("gemini"):
                env_key = "GEMINI_API_KEY"
                key = os.getenv(env_key) or os.getenv("GOOGLE_API_KEY")
                if not key:
                    self._append_global(f"[AI] os.getenv('{env_key}') ล้มเหลว, กำลังอ่าน .env เอง...")
                    key = self._manually_read_env(env_key) or self._manually_read_env("GOOGLE_API_KEY")
            else: # (OpenAI)
                env_key = "OPENAI_API_KEY"
                key = os.getenv(env_key)
                if not key:
                    self._append_global(f"[AI] os.getenv('{env_key}') ล้มเหลว, กำลังอ่าน .env เอง...")
                    key = self._manually_read_env(env_key)

        # 3. (Debug Log) สรุปว่าเจอ Key หรือไม่
        if not key or not key.strip():
            self._append_global("[AI ERROR] หา Key ไม่เจอ! (ทั้งใน UI และ .env)")
        else:
            # (แสดง Key 4 ตัวท้ายเพื่อยืนยัน)
            self._append_global(f"[AI] พบ Key ...{key[-4:]} สำหรับ {env_key}")

        return provider, (key or "").strip(), env_key

    # ▼▼▼ (แก้ไข) ฟังก์ชันนี้จะ "แสดง Error จริง" ▼▼▼
    def _gemini_client(self, api_key: str):
        """(แก้ไข) เปลี่ยนชื่อ Model เป็น 'gemini-2.5-flash' (ตามที่ถูกต้อง)"""
        try:
            import google.generativeai as genai

            if not api_key:
                raise ValueError("API Key เป็นค่าว่าง (EMPTY)")

            genai.configure(api_key=api_key)

            # ▼▼▼ (แก้ไขที่บรรทัดนี้) ▼▼▼
            model = genai.GenerativeModel('gemini-2.5-flash') # (ใช้ชื่อที่ถูกต้องตามที่คุณแจ้ง)
            # ▲▲▲ (จบส่วนแก้ไข) ▲▲▲

            return model

        except Exception as e:
            real_error_msg = (
                f"ไม่สามารถสร้าง Gemini client:\n\n"
                f"[ประเภท Error]: {type(e).__name__}\n"
                f"[รายละเอียด]: {e}\n\n"
                f"(ถ้า 'ValueError: API Key เป็นค่าว่าง' -> แปลว่าหา Key ไม่เจอ)\n"
                f"(ถ้า 'PermissionDenied' หรือ '403' -> แปลว่า Key ผิด หรือ API ไม่ได้เปิดใช้งาน)\n"
                f"(ถ้า '404 Not Found' -> แปลว่าชื่อ Model ที่ระบุ ('gemini-2.5-flash') ยังผิด)"
            )
            self._append_global(f"[AI ERROR] {real_error_msg}")
            messagebox.showerror("ข้อผิดพลาด (Debug Mode)", real_error_msg)
            return None

    # (ฟังก์ชันเดิม - ไม่แก้ไข)
    def _openai_client(self, api_key: str):
        try:
            from openai import OpenAI
            return OpenAI(api_key=api_key)
        except ImportError:
            messagebox.showerror("ข้อผิดพลาด", f"ไม่สามารถสร้าง OpenAI client:\nไม่พบ Library 'openai'\nติดตั้ง: python -m pip install openai")
            return None
        except Exception as e:
            messagebox.showerror("ข้อผิดพลาด", f"ไม่สามารถสร้าง OpenAI client:\n{e}\n(ตรวจสอบว่าติดตั้ง 'openai' แล้ว)")
            return None

    # (ฟังก์ชันเดิม - ไม่แก้ไข)
    def _test_api_once(self):
        provider, key, env_key = self._get_provider_and_key()
        if not key:
            messagebox.showerror("ข้อผิดพลาด", f"ไม่พบ API Key (ตรวจ {env_key} หรือใส่ในช่อง)");
            return
        try:
            if provider.lower().startswith("gemini"):
                c = self._gemini_client(key)
                if not c: return
                r = c.generate_content("ตอบคำว่า 'พร้อมทำงานคะ เลือกสินค้ามาได้เลย' สั้นๆ ภาษาไทย+อิโมจิสวยๆ")
                messagebox.showinfo("ผลทดสอบ", (r.text or "").strip())
            else:
                c = self._openai_client(key)
                if not c: return
                r = c.chat.completions.create(model="gpt-4o-mini", messages=[
                    {"role": "user", "content": "ตอบคำว่า 'พร้อมทำงานคะ เลือกสินค้ามาได้เลย' สั้นๆ ภาษาไทย+อิโมจิสวยๆ"}])
                messagebox.showinfo("ผลทดสอบ", (r.choices[0].message.content or "").strip())
        except Exception as e:
            messagebox.showerror("ข้อผิดพลาด", f"เรียก API ไม่สำเร็จ:\n{e}")

    # (ฟังก์ชันเดิม - ไม่แก้ไข)
    def _generate_caption(self):
        """
        [ฟังก์ชันที่รันใน Thread]
        1. ดึงค่าจาก UI
        2. สร้าง Prompt ที่ "เข้มงวด"
        3. เรียก AI
        4. ส่งผลลัพธ์ (raw) กลับไปที่ UI Thread หลัก
        """
        provider, key, env_key = self._get_provider_and_key()
        if not key:
            # (ส่ง Error กลับไปที่ UI Thread)
            self.after(0, messagebox.showerror, "ข้อผิดพลาด", f"ไม่พบ API Key (ตรวจ {env_key} หรือใส่ในช่อง)")
            return

        # --- 1. ดึงค่าจาก UI ---
        try:
            product = (self.ai_prompt_text.get("1.0", "end-1c") or "").strip() or "สินค้าโปรโมชั่น"
            n_caps = int(self.ai_caps_spin.get())
            n_tags = int(self.ai_tags_spin.get())
        except ValueError:
            self.after(0, messagebox.showerror, "ผิดพลาด", "กรุณาใส่ 'จำนวน' เป็นตัวเลข")
            return
        except Exception as e:
            self.after(0, messagebox.showerror, "ผิดพลาด", f"อ่านค่า UI ล้มเหลว: {e}")
            return

        # --- 2. สร้าง Prompt ที่ "เข้มงวด" (แก้ไขจุดนี้) ---
        # (เราเปลี่ยน "10 อักขระ" เป็น "1-2 บรรทัด" และแก้ตัวอย่าง JSON ให้ถูกต้อง)
        instr = f"""
คุณคือผู้เชี่ยวชาญด้านการตลาด Shopee Affiliate งานของคุณคือสร้างแคปชั่นและแฮชแท็ก

**สินค้า:**
"{product}"

**ข้อบังคับ (สำคัญมาก):**
1.  **จำนวนแคปชั่น:** {n_caps} แคปชั่น
2.  **จำนวนแฮชแท็ก:** {n_tags} แฮชแท็ก (ต่อ 1 แคปชั่น)
3.  **สไตล์:** สั้น กระชับ (ไม่เกิน 1-2 บรรทัด) เน้นปิดการขาย และใส่อิโมจิ 1-3 ตัว
4.  **ห้าม:** ห้ามใช้ข้อมูลเกินจริง หรือผิดกฏหมาย
5.  **รูปแบบผลลัพธ์:** ต้องเป็น JSON Array ที่สมบูรณ์เท่านั้น ห้ามมีคำอธิบายอื่นนอก JSON

**ตัวอย่าง JSON ที่ถูกต้อง:**
[
  {{
    "caption": "แคปชั่นที่ 1...",
    "hashtags": ["#แท็ก1", "#แท็ก2"]
  }},
  {{
    "caption": "แคปชั่นที่ 2...",
    "hashtags": ["#แท็ก1", "#แท็ก2"]
  }}
]

**สร้างผลลัพธ์:**
"""

        # --- 3. เรียก AI ---
        raw = ""
        try:
            if provider.lower().startswith("gemini"):
                c = self._gemini_client(key)
                if not c: return
                r = c.generate_content(contents=instr)
                raw = r.text or ""
            else:
                c = self._openai_client(key)
                if not c: return
                r = c.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": instr}],
                    temperature=0.9
                )
                raw = r.choices[0].message.content or ""

        except Exception as e:
            # (ส่ง Error กลับไปที่ UI Thread)
            self.after(0, messagebox.showerror, "ข้อผิดพลาด", f"เรียก AI ไม่สำเร็จ:\n{e}")
            return # (จบการทำงานของ Thread นี้ทันที)

        # --- 4. (สำคัญมาก!) ส่งผลลัพธ์กลับไปที่ UI Thread หลัก ---
        # (นี่คือส่วนที่ขาดหายไปจากโค้ดเดิมของคุณ)
        if raw:
            self.after(0, self._process_and_display_ai_result, raw)
        else:
            self.after(0, messagebox.showwarning, "ผลลัพธ์ว่างเปล่า", "AI ตอบกลับมา แต่ไม่มีข้อความ")

        # (คุณอาจต้องเพิ่มโค้ดเพื่อเปิดปุ่ม Generate อีกครั้งที่นี่)
        # self.after(0, lambda: self.ai_generate_btn.config(state=tk.NORMAL))
            # ▼▼▼ [สำคัญมาก: ส่งผลลัพธ์กลับไปที่ UI Thread] ▼▼▼
        self.after(0, self._process_and_display_ai_result, raw)

    # (เปิดปุ่ม Generate อีกครั้งหากคุณทำการปิดไว้ในฟังก์ชัน _start_generate_caption_thread)
    # self.after(0, lambda: self.ai_generate_btn.config(state=tk.NORMAL))
    # ----------------------------------------------------
    # เพิ่มฟังก์ชันแสดงผลลัพธ์นี้เข้าไปใน class App
    # ----------------------------------------------------
    def _process_and_display_ai_result(self, raw_json_text: str):
        """
        จัดการการแสดงผลลัพธ์ JSON ที่ได้รับจาก AI (เวอร์ชันแก้ไขสมบูรณ์)
        1. Parse JSON ที่ได้จาก AI (ซึ่งอาจจะเป็น list[dict] หรือ list[str])
        2. แยก "caption" และ "hashtags"
        3. แสดงผลในกล่องที่ถูกต้อง
        4. แสดง Popup "สำเร็จ" (หลังจากเสร็จสิ้นทุกอย่าง)
        """

        items = []  # นี่คือที่เก็บผลลัพธ์สุดท้ายในรูปแบบ [{caption:..., hashtags:[...]}, ...]

        # --- 1. พยายาม Parse ผลลัพธ์จาก AI ---
        try:
            # (1.1) เรียกฟังก์ชัน helper ที่เราสร้างขึ้น (ได้ผลลัพธ์เป็น list)
            cleaned_data = self._extract_json_array(raw_json_text)

            # (1.2) ตรวจสอบว่า AI ส่งมาแบบไหน
            if (isinstance(cleaned_data, list) and
                    len(cleaned_data) > 0 and
                    isinstance(cleaned_data[0], dict)):

                # >> กรณีที่ 1: AI ส่งมาแบบสมบูรณ์ [ {caption:..., hashtags:...}, ... ]
                # (เราแค่คัดกรองข้อมูลขยะออก)
                for it in cleaned_data:
                    cap = it.get("caption")
                    tags = it.get("hashtags") or []
                    if isinstance(cap, str) and cap.strip():
                        tags = [t for t in tags if isinstance(t, str) and t.strip()]
                        items.append({"caption": cap, "hashtags": tags})

            elif isinstance(cleaned_data, list):
                # >> กรณีที่ 2: AI ส่งมาเป็น List ของข้อความธรรมดา ["cap1", "cap2"]
                for ln in cleaned_data:
                    if isinstance(ln, str) and ln.strip():
                        items.append({"caption": ln, "hashtags": []})
            else:
                # >> กรณีที่ 3: (ไม่ควรเกิด) ถ้า _extract_json_array คืนค่าแปลกๆ
                raise Exception("Fallback to raw text splitting")

        except Exception:
            # >> กรณีฉุกเฉิน: ถ้า JSON พัง หรือเกิดข้อผิดพลาด
            # ให้ถือว่า AI ส่งมาเป็นข้อความธรรมดา และแยกด้วยบรรทัด
            items = [{"caption": ln, "hashtags": []} for ln in raw_json_text.splitlines() if ln.strip()]

        # --- 2. เตรียมข้อความสำหรับแสดงผล ---

        caps_lines = []
        tags_lines = []  # นี่คือ List ที่จะเก็บ "กลุ่ม" ของแฮชแท็ก

        for it in items:
            # (2.1) เพิ่มแคปชั่น (ถ้ามี)
            caps_lines.append(it.get("caption", ""))

            # (2.2) เพิ่ม "กลุ่ม" ของแฮชแท็ก
            # (รวม List แฮชแท็กของโพสต์นี้ ให้เป็น "บรรทัดเดียว" คั่นด้วยเว้นวรรค)
            tags = it.get("hashtags", [])
            tags_lines.append(" ".join(tags))  # <--- นี่คือจุดสำคัญที่แก้ปัญหาการแสดงผล

        # --- 3. แสดงผลลัพธ์ (ล้างของเก่าก่อน) ---

        self.ai_caps_output.delete("1.0", "end")
        self.ai_caps_output.insert("end", "\n\n".join(caps_lines))  # แคปชั่น: คั่นด้วย 2 บรรทัด

        self.ai_tags_output.delete("1.0", "end")
        self.ai_tags_output.insert("end", "\n".join(tags_lines))  # แฮชแท็ก: คั่นด้วย 1 บรรทัด

        self._last_ai_items = items

        # --- 4. แสดง Popup "สำเร็จ" (ย้ายมาไว้ "ท้ายสุด") ---
        messagebox.showinfo("สำเร็จ", "สร้างแคปชั่นเสร็จสมบูรณ์")
#---------------------------------
    # (วางโค้ดนี้ไว้ในคลาส App ของ ui.py)
    def _extract_json_array(self, raw_text: str) -> list[str]:
        """
        พยายามดึงข้อมูล JSON array (list of strings) ที่ซ่อนอยู่ใน raw text จาก AI
        เช่น '```json\n["a", "b"]\n```' หรือ '... ["a", "b"] ...'
        """
        import re
        import json

        # 1. ค้นหา block '```json ... ```' (ที่ Gemini ชอบส่งมา)
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", raw_text)
        if json_match:
            text_to_parse = json_match.group(1)
        else:
            # 2. ถ้าไม่เจอ ให้ค้นหา array [ ... ] ที่ครอบคลุมที่สุด
            bracket_match = re.search(r"\[[\s\S]*\]", raw_text)
            if bracket_match:
                text_to_parse = bracket_match.group(0)
            else:
                # 3. ถ้าไม่เจออะไรเลย ให้ใช้ raw text (เผื่อ AI ตอบมาแค่ array เพียวๆ)
                text_to_parse = raw_text

        try:
            # 4. พยายาม parse
            data = json.loads(text_to_parse)
            if isinstance(data, list):
                # 5. คืนค่า list (แปลงทุกอย่างเป็น str)
                return data
        except json.JSONDecodeError:
            # 6. ถ้า parse ล้มเหลว (เช่น text_to_parse เป็นแค่ "ok")
            pass

        # 7. ถ้าล้มเหลวทั้งหมด (parse ไม่ได้, ไม่ใช่ list)
        # ให้สันนิษฐานว่า AI ตอบมาเป็นข้อความธรรมดา
        # เราก็แค่แยกบรรทัด
        if json_match:
            # ถ้ามี ```json แต่ parse ไม่ได้ ให้ใช้เนื้อหาใน ``` แยกบรรทัด
            return [line.strip() for line in text_to_parse.split('\n') if line.strip()]

        # ถ้าไม่มี ``` และ parse [ ] ไม่ได้ ให้ใช้ raw_text แยกบรรทัด
        return [line.strip() for line in raw_text.split('\n') if line.strip()]

    def _make_csv_from_ai(self):
        """
        สร้างไฟล์ captions.csv จากฟิลด์ในแท็บ AI:
        - 3 คอลัมน์: caption, hashtags, link
        - สุ่มจำนวนแฮชแท็ก/ลิงก์ต่อโพสต์ ตามค่าที่ผู้ใช้เลือก
        - ให้ตั้งชื่อไฟล์เองผ่าน dialog
        """
        import re, random, csv

        # Read fields
        caps = [ln.strip() for ln in self.ai_caps_output.get("1.0", "end").splitlines() if ln.strip()]
        tags_raw = [ln.strip() for ln in self.ai_tags_output.get("1.0", "end").splitlines() if ln.strip()]
        links = [ln.strip() for ln in self.ai_links_output.get("1.0", "end").splitlines() if ln.strip()]

        if not caps:
            messagebox.showwarning("คำเตือน", "ยังไม่มีแคปชั่นในช่องผลลัพธ์ AI");
            return

        # Limits
        try:
            pick_n = max(0, int(self.var_hashtag_pick.get()))
        except:
            pick_n = 5
        try:
            link_n = max(0, int(self.var_link_pick.get()))
        except:
            link_n = 1

        # Build hashtag pool (#normalize + unique)
        seen, tags_pool = set(), []
        for raw in tags_raw:
            for p in re.split(r"[,\s]+", raw):
                t = (p or "").strip()
                if not t: continue
                if not t.startswith("#"): t = "#" + t.lstrip("#")
                if t == "#": continue
                if t not in seen:
                    seen.add(t);
                    tags_pool.append(t)

        rows = []
        n_caps, n_links = len(caps), len(links)

        for i in range(n_caps):
            caption = caps[i]

            # random hashtags (no-dup inside a row)
            if pick_n > 0 and tags_pool:
                chosen_tags = random.sample(tags_pool, min(pick_n, len(tags_pool)))
                hashtags = " ".join(chosen_tags)
            else:
                hashtags = ""

            # random links (allow repeat if pool < need)
            if link_n > 0 and links:
                if len(links) >= link_n:
                    chosen_links = random.sample(links, link_n)
                else:
                    chosen_links = [random.choice(links) for _ in range(link_n)]
                link_field = " ".join(chosen_links).strip()
            else:
                link_field = ""

            rows.append({"caption": caption, "hashtags": hashtags, "link": link_field})

        # Save dialog
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="captions.csv",
            title="บันทึกเป็น captions.csv"
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["caption", "hashtags", "link"])
                w.writeheader();
                w.writerows(rows)
            messagebox.showinfo("สำเร็จ", f"บันทึกไฟล์แล้ว:\n{path}\nรวม {len(rows)} แถว")
        except Exception as e:
            messagebox.showerror("ข้อผิดพลาด", f"ไม่สามารถสร้างไฟล์:\n{e}")
    #-----------------------------------
    # (วางไว้ใน class App, ใกล้ๆ _write_env_kv)
    def _manually_read_env(self, key_to_find):
        """
        (แผนสำรอง) พยายามเปิดไฟล์ .env หรือ env เพื่ออ่านค่า Key
        หาก os.getenv() ล้มเหลว
        """
        env_path = Path(".env") # (หา .env ในโฟลเดอร์เดียวกับ ui2.py)
        if not env_path.exists():
            env_path = Path("env") # (ลองหาไฟล์ชื่อ env ด้วย)

        if env_path.exists():
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        # (ล้าง comment และช่องว่าง)
                        clean_line = line.split('#', 1)[0].strip()
                        if clean_line.startswith(f"{key_to_find}="):
                            # (เจอแล้ว! คืนค่า Key)
                            return clean_line.split("=", 1)[1].strip().strip('"').strip("'")
            except Exception as e:
                # (ใช้ self._append_global ถ้ามี หรือ print)
                print(f"[AI] Error reading .env manually: {e}")
        return None

# ---- main ----
if __name__ == "__main__":
    app = App()
    app.mainloop()