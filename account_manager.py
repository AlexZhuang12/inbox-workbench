import json
import os
from pathlib import Path
import re
from queue import Empty, SimpleQueue
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from urllib.parse import parse_qs, urlsplit

from review import GogError, review, run_gog


ROOT = Path(__file__).resolve().parent
PRODUCT_CLIENT = "gmail-inbox-review"
SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


def import_client(gog, path):
    try:
        installed = json.loads(path.read_text(encoding="utf-8-sig"))["installed"]
        if not all(isinstance(installed[key], str) and installed[key].strip()
                   for key in ("client_id", "client_secret")):
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        raise GogError("invalid_desktop_oauth_file") from None
    run_gog(gog, [f"--client={PRODUCT_CLIENT}", "auth", "credentials", "set", str(path)], os.environ)


def authorization_url(line):
    url = line.strip()
    if not url.startswith("https://accounts.google.com/"):
        return None
    parts = urlsplit(url)
    params = parse_qs(parts.query)
    paths = {"/o/oauth2/auth", "/o/oauth2/v2/auth"}
    if parts.path in paths and {"client_id", "state", "code_challenge"} <= params.keys():
        return url
    return None


def authorize(gog, email, publish_link, reauthorize=False):
    arguments = [gog, f"--client={PRODUCT_CLIENT}", "auth", "add", email,
                 "--services=gmail", "--gmail-scope=read-send"]
    if reauthorize:
        arguments.append("--force-consent")
    with subprocess.Popen(
        arguments, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE, encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    ) as process:
        timed_out = threading.Event()

        def stop():
            timed_out.set()
            process.kill()

        timer = threading.Timer(360, stop)
        timer.daemon = True
        timer.start()
        try:
            for line in process.stderr:
                url = authorization_url(line)
                if url:
                    publish_link(url)
            result = process.wait()
        finally:
            timer.cancel()
    if timed_out.is_set():
        raise GogError("authorization_timed_out")
    if result:
        raise GogError("authorization_failed")


class App:
    def __init__(self, window, gog):
        self.window = window
        self.gog = gog
        self.configured = False
        self.busy = False
        self.links = SimpleQueue()
        self.active_url = None
        window.title("Gmail 信箱管理")
        window.geometry("760x500")
        window.minsize(660, 420)
        panel = ttk.Frame(window, padding=20)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="Gmail 信箱管理", font=("Microsoft JhengHei UI", 19, "bold")).pack(anchor="w")
        ttk.Label(panel, text="一次授權 Gmail 讀取與寄信，寄出前由你確認。").pack(anchor="w", pady=(4, 14))
        self.tree = ttk.Treeview(panel, columns=("email", "client", "status"), show="headings", selectmode="browse")
        for key, label, width in (("email", "Gmail 帳號", 270), ("client", "OAuth 用戶端", 160), ("status", "查詢狀態", 170)):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width)
        self.tree.pack(fill="both", expand=True)
        controls = ttk.Frame(panel)
        controls.pack(fill="x", pady=12)
        self.buttons = []
        for label, action in (("新增 Gmail", self.add), ("重新授權", self.reauthorize),
                              ("測試全部信箱", self.check), ("重新整理", self.refresh),
                              ("匯入 OAuth 設定", self.choose_config)):
            button = ttk.Button(controls, text=label, command=action)
            button.pack(side="left", padx=(0, 5))
            self.buttons.append(button)
        self.copy_link = ttk.Button(panel, text="複製授權連結", command=self.copy_authorization_link)
        self.copy_link.pack(anchor="w", pady=(0, 8))
        self.copy_link.state(["disabled"])
        self.status = tk.StringVar()
        ttk.Label(panel, textvariable=self.status, wraplength=520).pack(anchor="w")
        window.after(0, self.refresh)

    def background(self, message, task, done):
        if self.busy:
            return
        self.busy = True
        for button in self.buttons:
            button.state(["disabled"])
        self.status.set(message)
        outcome = []

        def run():
            try:
                outcome.append((True, task()))
            except (GogError, OSError) as error:
                code = str(error) if isinstance(error, GogError) else "local_command_failed"
                outcome.append((False, code))

        worker = threading.Thread(target=run, daemon=True)
        worker.start()

        def poll():
            try:
                self.active_url = self.links.get_nowait()
                self.copy_link.state(["!disabled"])
                self.status.set("請在 Google 頁面完成授權，或複製連結到正確的 Chrome 設定檔。")
            except Empty:
                pass
            if worker.is_alive():
                self.window.after(100, poll)
                return
            self.busy = False
            self.active_url = None
            self.copy_link.state(["disabled"])
            for button in self.buttons:
                button.state(["!disabled"])
            if outcome and outcome[0][0]:
                done(outcome[0][1])
            else:
                code = outcome[0][1] if outcome else "local_command_failed"
                self.status.set(f"操作未完成（{code}）。")

        self.window.after(100, poll)

    def load(self):
        clients = run_gog(self.gog, ["auth", "credentials", "list"], os.environ)["clients"]
        configured = any(entry["client"] == PRODUCT_CLIENT for entry in clients)
        accounts = run_gog(self.gog, ["auth", "list"], os.environ)["accounts"]
        return configured, accounts or []

    def show_accounts(self, state):
        self.configured, accounts = state
        self.show_rows(accounts)
        if self.configured:
            self.status.set("可新增 Gmail。請在 Google 同意讀取與寄信權限。")
        else:
            self.status.set("請匯入你自己的 Google 桌面 OAuth 設定。")

    def show_rows(self, accounts):
        self.tree.delete(*self.tree.get_children())
        for account in accounts:
            services = account.get("services") or []
            if services and "gmail" not in services:
                continue
            status = {
                "ok": "可查詢",
                "reauthorization_required": "需要重新授權",
                "permission_denied": "權限不足",
                "rate_limited": "暫時受到頻率限制",
            }.get(account.get("error") or account.get("status"), account.get("error") or "尚未測試")
            self.tree.insert("", "end", values=(account.get("email") or account["account"],
                             account.get("client") or account.get("oauth_client") or "default", status))

    def refresh(self):
        self.background("讀取帳號清單中…", self.load, self.show_accounts)

    def choose_config(self):
        if self.configured:
            messagebox.showinfo("OAuth 設定", "這台電腦已有 OAuth 設定，可以直接新增 Gmail。")
            return
        path = filedialog.askopenfilename(title="匯入桌面版 OAuth 設定", filetypes=[("JSON", "*.json")])
        if path:
            def setup():
                import_client(self.gog, Path(path))
                return self.load()
            self.background("匯入 OAuth 設定中…", setup, self.show_accounts)

    def add(self):
        if not self.configured:
            self.choose_config()
            return
        address = simpledialog.askstring("新增 Gmail", "輸入要授權的 Gmail 地址", parent=self.window)
        if address is None:
            return
        address = address.strip().lower()
        if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+", address):
            self.status.set("請輸入有效的 Gmail 或 Google Workspace 電子郵件地址。")
            return
        self.connect(address)

    def reauthorize(self):
        selection = self.tree.selection()
        if not selection:
            self.status.set("請先選擇要重新授權的信箱。")
            return
        email, client, _ = self.tree.item(selection[0], "values")
        if client != PRODUCT_CLIENT:
            self.status.set("此信箱沿用既有 gogcli 設定。要改用本工具的授權，請按「新增 Gmail」。")
            return
        self.connect(email, reauthorize=True)

    def copy_authorization_link(self):
        if self.active_url:
            self.window.clipboard_clear()
            self.window.clipboard_append(self.active_url)
            self.status.set("已複製。請貼到正確的 Chrome 設定檔，並保持此視窗開啟。")

    def connect(self, address, reauthorize=False):
        def task():
            authorize(self.gog, address, self.links.put, reauthorize)
            return self.load()
        self.background("請在瀏覽器選擇對應帳號並完成 Google 授權…", task, self.show_accounts)

    def check(self):
        def show(report):
            self.show_rows(report["accounts"])
            checked = report["accounts"]
            succeeded = sum(account["status"] == "ok" for account in checked)
            self.status.set(f"測試完成。成功 {succeeded} 個，失敗 {len(checked) - succeeded} 個。")
        self.background("正在對每個信箱執行唯讀查詢…",
                        lambda: review(self.gog, "newer_than:7d", 1), show)


if __name__ == "__main__":
    window = tk.Tk()
    bundled = ROOT / "bin" / "gog.exe"
    gog = str(bundled) if bundled.is_file() else shutil.which("gog.exe")
    if gog:
        App(window, gog)
        window.mainloop()
    else:
        window.withdraw()
        messagebox.showerror("Gmail 信箱管理", "找不到 gog.exe。請解壓縮完整的 Windows 套件。")
