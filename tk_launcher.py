# day_trading_bot/tk_launcher.py
# GUI with login persistence, dark mode, and SAFE shutdown:
# - If the window is closed OR user logs out, the bot process is stopped automatically.

import os, sys, json, subprocess, signal
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Local imports
from day_trading_bot import auth
from day_trading_bot.config import (
    TRADING_SYMBOLS, TIMEFRAMES, RISK_PERCENT,
    AUTO_MODE
)
from day_trading_bot.utils.logger import print_debug

APP_NAME = "Angela"

PKG_DIR = Path(__file__).resolve().parent            # .../day_trading_bot
PROJECT_ROOT = PKG_DIR.parent                        # repo root
IS_FROZEN = getattr(sys, "frozen", False)

STOP_FLAG = PKG_DIR / "BOT_STOP.flag"

# ---- Settings persisted (username, dark mode, tokens, UI prefs) ----
SETTINGS_DIR = Path(os.getenv("APPDATA") or Path.home()) / "ForexBot"
SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "dark_mode": False,
    "remember_user": True,
    "last_user": "",
    "keep_signed_in": False,
    "session_token": "",
    "last_symbols": ",".join(TRADING_SYMBOLS),
    "last_timeframe": "M15",
    "last_risk": str(RISK_PERCENT),
    "auto_mode": AUTO_MODE,
}

def load_settings():
    if not SETTINGS_FILE.exists():
        return DEFAULT_SETTINGS.copy()
    try:
        with SETTINGS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        merged = DEFAULT_SETTINGS.copy()
        merged.update(data or {})
        return merged
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_settings(s: dict):
    tmp = SETTINGS_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
    tmp.replace(SETTINGS_FILE)

# ---- Theming ----
def apply_theme(root: tk.Tk, dark: bool):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    if dark:
        bg = "#111418"; panel = "#1b1f24"; fg = "#E6E6E6"; fg_muted = "#B8C0CC"
        root.configure(bg=bg)
        style.configure(".", background=panel, foreground=fg, fieldbackground=panel)
        style.configure("TLabel", background=panel, foreground=fg)
        style.configure("TFrame", background=panel)
        style.configure("TCheckbutton", background=panel, foreground=fg)
        style.configure("TRadiobutton", background=panel, foreground=fg)
        style.configure("TEntry", fieldbackground="#0f1216", foreground=fg)
        style.configure("TCombobox", fieldbackground="#0f1216", foreground=fg)
        style.configure("Accent.TButton", padding=8)
        style.configure("Danger.TButton", padding=8)
    else:
        bg = "#F3F5F7"; panel = "#FFFFFF"; fg = "#1E2329"
        root.configure(bg=bg)
        style.configure(".", background=panel, foreground=fg, fieldbackground=panel)
        style.configure("TLabel", background=panel, foreground=fg)
        style.configure("TFrame", background=panel)
        style.configure("TCheckbutton", background=panel, foreground=fg)
        style.configure("TRadiobutton", background=panel, foreground=fg)
        style.configure("TEntry", fieldbackground="#ffffff", foreground=fg)
        style.configure("TCombobox", fieldbackground="#ffffff", foreground=fg)
        style.configure("Accent.TButton", padding=8)
        style.configure("Danger.TButton", padding=8)

# ---- Process helpers ----
def _write_stop_flag():
    try:
        STOP_FLAG.write_text("1", encoding="utf-8")
    except Exception:
        pass

def start_bot_process(symbols: str, timeframe: str, risk: float, auto_mode: bool):
    """
    Launch main bot in a separate process with PROJECT_ROOT as cwd:
        python -m day_trading_bot.main SYMBOLS TF RISK AUTO
    Returns the subprocess.Popen handle (or None on failure).
    """
    auto_flag = "1" if auto_mode else "0"
    cmd = [sys.executable, "-m", "day_trading_bot.main", symbols, timeframe, str(risk), auto_flag]
    creationflags = 0
    if os.name == "nt":
        # Create a new process group so we can terminate the whole group on exit
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    print_debug(f"[LAUNCH] cwd={PROJECT_ROOT} cmd={' '.join(cmd)}")
    try:
        return subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), creationflags=creationflags)
    except Exception as e:
        # Fallback: run direct script path (works even if packaging is odd)
        script = PKG_DIR / "main.py"
        fallback = [sys.executable, str(script), symbols, timeframe, str(risk), auto_flag]
        print_debug(f"[LAUNCH-FALLBACK] {e} → {' '.join(fallback)}")
        try:
            return subprocess.Popen(fallback, cwd=str(PROJECT_ROOT), creationflags=creationflags)
        except Exception as e2:
            messagebox.showerror("Launch error", f"Could not start bot:\n{e2}")
            return None

def stop_bot_process(proc: subprocess.Popen | None):
    # Signal the bot via STOP_FLAG (main.py watches it every second)
    _write_stop_flag()
    # Also try to terminate the child we launched (best-effort)
    if proc and proc.poll() is None:
        try:
            if os.name == "nt":
                # On Windows, terminate() is OK (hard kill). Try CTRL_BREAK first if in new process group.
                try:
                    os.kill(proc.pid, signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
                except Exception:
                    pass
            proc.terminate()
        except Exception:
            pass

# ---- GUI ----
class AngelaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("420x560")
        self.minsize(420, 520)
        self.resizable(False, False)

        self.settings = load_settings()
        apply_theme(self, self.settings["dark_mode"])

        # shared variables
        self.dark_var = tk.BooleanVar(value=self.settings["dark_mode"])
        self.username_var = tk.StringVar(value=self.settings.get("last_user", ""))
        self.password_var = tk.StringVar(value="")
        self.remember_var = tk.BooleanVar(value=self.settings.get("remember_user", True))
        self.keep_signed_var = tk.BooleanVar(value=self.settings.get("keep_signed_in", False))

        # main controls vars
        self.symbols_all_var = tk.BooleanVar(value=True)
        self.timeframe_var = tk.StringVar(value=self.settings.get("last_timeframe", "M15"))
        self.risk_var = tk.StringVar(value=self.settings.get("last_risk", "1.0"))
        self.auto_mode_var = tk.BooleanVar(value=self.settings.get("auto_mode", False))
        self.selected_symbols = set(TRADING_SYMBOLS)

        # track launched process
        self.bot_proc: subprocess.Popen | None = None

        # frames
        self.header = ttk.Frame(self, padding=14); self.header.pack(side="top", fill="x")
        self.content = ttk.Frame(self, padding=14); self.content.pack(side="top", fill="both", expand=True)

        self._build_header()
        self.login_frame = None
        self.main_frame = None

        # ensure we stop the bot if user closes the window
        self.protocol("WM_DELETE_WINDOW", self._on_app_close)

        # auto-login if session valid
        token = self.settings.get("session_token", "")
        user = auth.validate_session(token) if token else None
        if self.keep_signed_var.get() and user:
            self._render_main(user)
        else:
            self._render_login()

    # ---------- UI building ----------
    def _build_header(self):
        left = ttk.Frame(self.header); left.pack(side="left", fill="x", expand=True)
        ttk.Label(left, text="Angela", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(left, text="Smart day trading controller", foreground="#7e8794").pack(anchor="w")
        right = ttk.Frame(self.header); right.pack(side="right")
        ttk.Checkbutton(right, text="Dark Mode", variable=self.dark_var, command=self._toggle_dark).pack()

    def _clear_content(self):
        for w in self.content.winfo_children():
            w.destroy()

    def _render_login(self):
        self._clear_content()
        f = ttk.Frame(self.content); f.pack(fill="both", expand=True)
        ttk.Label(f, text="Sign in", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        ttk.Label(f, text="Username").grid(row=1, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.username_var, width=28).grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(f, text="Password").grid(row=2, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.password_var, show="•", width=28).grid(row=2, column=1, sticky="ew", pady=4)

        ttk.Checkbutton(f, text="Remember username", variable=self.remember_var).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Checkbutton(f, text="Keep me signed in (7 days)", variable=self.keep_signed_var).grid(row=4, column=0, columnspan=2, sticky="w")

        btns = ttk.Frame(f); btns.grid(row=5, column=0, columnspan=2, pady=12, sticky="ew")
        ttk.Button(btns, text="Sign in", style="Accent.TButton", command=self._on_login).pack(side="left", expand=True, fill="x")
        ttk.Button(btns, text="Create admin", command=self._on_create_admin).pack(side="left", padx=8, expand=True, fill="x")

        for i in range(2):
            f.columnconfigure(i, weight=1)

    def _render_main(self, username: str):
        self._clear_content()
        m = ttk.Frame(self.content); m.pack(fill="both", expand=True)

        top = ttk.Frame(m); top.pack(fill="x")
        ttk.Label(top, text=f"Signed in as: {username}", font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Button(top, text="Logout", command=self._logout).pack(side="right")

        # Symbols
        box = ttk.LabelFrame(m, text="Symbols", padding=10); box.pack(fill="x", pady=(10, 6))
        ttk.Checkbutton(box, text="Select All Symbols", variable=self.symbols_all_var, command=self._on_toggle_all).pack(anchor="w")
        sym_row = ttk.Frame(box); sym_row.pack(fill="x", pady=6)
        self.symbol_menu_btn = ttk.Menubutton(sym_row, text="Select Symbols  ▼")
        self.symbol_menu = tk.Menu(self.symbol_menu_btn, tearoff=0)
        for s in TRADING_SYMBOLS:
            self.symbol_menu.add_checkbutton(label=s, onvalue=True, offvalue=False,
                                             command=lambda sym=s: self._toggle_symbol(sym))
        self.symbol_menu_btn["menu"] = self.symbol_menu
        self.symbol_menu_btn.pack(anchor="w")

        # Timeframe & risk
        grid = ttk.LabelFrame(m, text="Parameters", padding=10); grid.pack(fill="x", pady=(6, 6))
        ttk.Label(grid, text="Timeframe:").grid(row=0, column=0, sticky="w")
        cb = ttk.Combobox(grid, values=list(TIMEFRAMES.keys()), textvariable=self.timeframe_var, width=8, state="readonly")
        cb.grid(row=0, column=1, sticky="w", padx=(6, 0))

        ttk.Label(grid, text="Risk %:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(grid, textvariable=self.risk_var, width=10).grid(row=1, column=1, sticky="w", padx=(6, 0), pady=(6, 0))

        ttk.Checkbutton(grid, text="Enable Auto Mode", variable=self.auto_mode_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        # Controls
        btns = ttk.Frame(m); btns.pack(fill="x", pady=10)
        ttk.Button(btns, text="Start Bot", style="Accent.TButton", command=self._start_bot).pack(side="left", expand=True, fill="x")
        ttk.Button(btns, text="Stop Bot", style="Danger.TButton", command=self._stop_bot).pack(side="left", padx=8, expand=True, fill="x")

        # License
        lic = ttk.LabelFrame(m, text="License", padding=10); lic.pack(fill="x", pady=(0, 8))
        ttk.Button(lic, text="Load License Key", command=self._load_license).pack(side="left")
        self.access_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(lic, text="Access Granted", variable=self.access_var, state="disabled").pack(side="left", padx=(10, 0))

        # footer
        ttk.Label(m, text="Tip: Close this window or logout to stop the bot automatically.", foreground="#7e8794").pack(anchor="w", pady=(6, 0))

    # ---------- Actions ----------
    def _toggle_dark(self):
        self.settings["dark_mode"] = bool(self.dark_var.get())
        save_settings(self.settings)
        apply_theme(self, self.settings["dark_mode"])

    def _on_create_admin(self):
        u = self.username_var.get().strip().lower()
        p = self.password_var.get()
        if not u or not p:
            messagebox.showwarning("Create admin", "Enter a username and password first.")
            return
        try:
            auth.create_user(u, p)
            messagebox.showinfo("Create admin", "Admin user created.")
        except Exception as e:
            messagebox.showerror("Create admin", str(e))

    def _on_login(self):
        u = self.username_var.get().strip().lower()
        p = self.password_var.get()
        if not u or not p:
            messagebox.showwarning("Sign in", "Please enter username and password.")
            return
        if not auth.verify_credentials(u, p):
            messagebox.showerror("Sign in", "Invalid username or password.")
            return

        self.settings["last_user"] = u if self.remember_var.get() else ""
        self.settings["remember_user"] = bool(self.remember_var.get())
        self.settings["keep_signed_in"] = bool(self.keep_signed_var.get())

        if self.keep_signed_var.get():
            token = auth.issue_session(u)
            self.settings["session_token"] = token
        else:
            self.settings["session_token"] = ""

        save_settings(self.settings)
        self._render_main(u)

    def _logout(self):
        # stop bot on logout
        stop_bot_process(self.bot_proc)
        token = self.settings.get("session_token", "")
        if token:
            auth.revoke_session(token)
        self.settings["session_token"] = ""
        save_settings(self.settings)
        self.password_var.set("")
        self._render_login()

    def _on_toggle_all(self):
        if self.symbols_all_var.get():
            self.selected_symbols = set(TRADING_SYMBOLS)
        else:
            self.selected_symbols = set()
        for i, s in enumerate(TRADING_SYMBOLS):
            state = (s in self.selected_symbols)
            self.symbol_menu.entryconfigure(i, label=f"{s}{' ✓' if state else ''}")

    def _toggle_symbol(self, sym: str):
        if sym in self.selected_symbols:
            self.selected_symbols.remove(sym)
        else:
            self.selected_symbols.add(sym)
        self.symbols_all_var.set(len(self.selected_symbols) == len(TRADING_SYMBOLS))
        for i, s in enumerate(TRADING_SYMBOLS):
            state = (s in self.selected_symbols)
            self.symbol_menu.entryconfigure(i, label=f"{s}{' ✓' if state else ''}")

    def _start_bot(self):
        symbols = ",".join(sorted(self.selected_symbols)) if not self.symbols_all_var.get() else ",".join(TRADING_SYMBOLS)
        tf = self.timeframe_var.get()
        try:
            risk = float(self.risk_var.get())
        except Exception:
            messagebox.showwarning("Start Bot", "Risk must be a number.")
            return

        self.settings["last_symbols"] = symbols
        self.settings["last_timeframe"] = tf
        self.settings["last_risk"] = str(risk)
        self.settings["auto_mode"] = bool(self.auto_mode_var.get())
        save_settings(self.settings)

        # If a bot is already running, stop it before starting a new one
        if self.bot_proc and self.bot_proc.poll() is None:
            stop_bot_process(self.bot_proc)

        self.bot_proc = start_bot_process(symbols, tf, risk, self.auto_mode_var.get())
        if self.bot_proc:
            messagebox.showinfo("Bot", "Bot started.")

    def _stop_bot(self):
        stop_bot_process(self.bot_proc)
        messagebox.showinfo("Bot", "Stop signal sent.")

    def _load_license(self):
        path = filedialog.askopenfilename(
            title="Select license_token.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
         return
        try:
            dest = PKG_DIR / "license_token.json"
            os.makedirs(dest.parent, exist_ok=True)
            with open(path, "r", encoding="utf-8") as fsrc, open(dest, "w", encoding="utf-8") as fdst:
                fdst.write(fsrc.read())
            self.access_var.set(True)
            messagebox.showinfo("License", "License key loaded.")
        except Exception as e:
            messagebox.showerror("License", f"Failed to load license: {e}")

    def _on_app_close(self):
        # Stop the bot automatically on window close.
        stop_bot_process(self.bot_proc)
        self.destroy()

# ---- Entrypoint ----
def main():
    app = AngelaApp()
    app.mainloop()

if __name__ == "__main__":
    main()
