import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
import re
from queue import Empty, SimpleQueue
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from urllib.parse import parse_qs, urlsplit

from review import GogError, review, run_gog
from rose_ui import BACKGROUND, RoseButton, RoseCard, configure_theme, dialog


ROOT = Path(__file__).resolve().parent
PRODUCT_CLIENT = "gmail-inbox-review"
SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
PREFERENCES = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "InboxWorkbench" / "accounts.json"


def load_preferences(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_preferences(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False, mode="w", encoding="utf-8") as file:
        temporary = Path(file.name)
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)



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
        self.accounts = []
        self.busy = False
        self.links = SimpleQueue()
        self.active_url = None
        self.auth_address = ""
        self.preferences = load_preferences(PREFERENCES)
        self.dragged = None
        self.selection_hint = tk.StringVar(value="選取信箱後可管理暱稱、排序與授權。")
        self.auth_hint = tk.StringVar(value="授權開始後，可複製原始連結到對應的 Chrome 設定檔。")
        self.status = tk.StringVar()
        window.title("信箱工作台 · Inbox Workbench")
        window.geometry("960x640")
        window.minsize(820, 560)
        configure_theme(window)

        panel = ttk.Frame(window, style="Rose.TFrame", padding=(24, 16))
        panel.pack(fill="both", expand=True)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        header = ttk.Frame(panel, style="Rose.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        ttk.Label(header, text="信箱工作台", style="Title.TLabel").pack(side="left")
        self.buttons = []
        for label, action, style in (
            ("新增 Gmail", self.add, "Accent.TButton"),
            ("測試全部信箱", self.check, "TButton"),
            ("重新整理", self.refresh, "TButton"),
        ):
            button = RoseButton(header, label, action, primary=style == "Accent.TButton", background=BACKGROUND)
            button.pack(side="right", padx=(8, 0))
            self.buttons.append(button)

        card_surface = RoseCard(panel)
        card_surface.grid(row=1, column=0, sticky="nsew")
        card = card_surface.content
        ttk.Label(card, text="已連接的信箱", style="Section.TLabel").pack(anchor="w", pady=(0, 6))
        table = ttk.Frame(card)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table, columns=("nickname", "email", "client", "read", "send"),
                                 show="headings", selectmode="browse", height=4)
        for key, label, width in (("nickname", "暱稱", 115), ("email", "Gmail 帳號", 245),
                                  ("client", "OAuth 用戶端", 140), ("read", "查信狀態", 115),
                                  ("send", "寄信授權紀錄", 120)):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=65, stretch=key in {"nickname", "email"})
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview, style="Rose.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.update_selection)
        self.tree.bind("<ButtonPress-1>", self.start_drag)
        self.tree.bind("<ButtonRelease-1>", self.finish_drag)

        actions = ttk.Frame(card)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Label(actions, textvariable=self.selection_hint, style="Muted.TLabel").pack(side="left")
        self.row_buttons = []
        for label, command in (("重新授權", self.reauthorize), ("上移", lambda: self.move_selected(-1)),
                               ("下移", lambda: self.move_selected(1)), ("編輯暱稱", self.rename)):
            button = RoseButton(actions, label, command)
            button.pack(side="right", padx=(5, 0))
            self.row_buttons.append(button)

        auth_surface = RoseCard(panel)
        auth_surface.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        auth = auth_surface.content
        ttk.Label(auth, text="Google 授權", style="Section.TLabel").pack(anchor="w")
        ttk.Label(auth, textvariable=self.auth_hint, style="Muted.TLabel", wraplength=570).pack(side="left", anchor="w")
        self.copy_link = RoseButton(auth, "複製授權連結", self.copy_authorization_link)
        self.copy_link.pack(side="right")
        self.copy_link.state(["disabled"])

        footer = ttk.Frame(panel, style="Rose.TFrame")
        footer.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(footer, textvariable=self.status, style="RoseStatus.TLabel", wraplength=590).pack(side="left")
        config = RoseButton(footer, "匯入 OAuth 設定", self.choose_config, background=BACKGROUND)
        config.pack(side="right")
        self.buttons.append(config)
        auth_surface.fit()
        self.update_selection()
        window.after(0, self.refresh)

    def update_selection(self, event=None):
        selected = self.tree.selection()
        for button in self.row_buttons:
            button.state(["!disabled"] if selected and not self.busy else ["disabled"])
        self.selection_hint.set(self.tree.set(selected[0], "email") if selected
                                else "選取信箱後可管理暱稱、排序與授權。")

    def save_layout(self):
        try:
            save_preferences(PREFERENCES, self.preferences)
        except OSError:
            self.status.set("無法儲存信箱排序或暱稱，本次視窗仍會顯示變更。")

    def persist_order(self):
        current = list(self.tree.get_children())
        stored = self.preferences.get("order")
        hidden = [key for key in stored if isinstance(key, str) and key not in current] if isinstance(stored, list) else []
        self.preferences["order"] = current + hidden
        self.save_layout()

    def move_selected(self, offset):
        selected = self.tree.selection()
        if self.busy or not selected:
            return
        key = selected[0]
        position = self.tree.index(key) + offset
        if 0 <= position < len(self.tree.get_children()):
            self.tree.move(key, "", position)
            self.tree.see(key)
            self.persist_order()

    def start_drag(self, event):
        self.dragged = self.tree.identify_row(event.y) if not self.busy else None

    def finish_drag(self, event):
        source, self.dragged = self.dragged, None
        target = self.tree.identify_row(event.y)
        if not self.busy and source and target and source != target and self.tree.exists(source):
            self.tree.move(source, "", self.tree.index(target))
            self.tree.selection_set(source)
            self.persist_order()

    def rename(self):
        selected = self.tree.selection()
        if self.busy or not selected:
            return
        key = selected[0]
        nickname = dialog(self.window, "編輯暱稱", "輸入暱稱，留空可清除。", initial=self.tree.set(key, "nickname"))
        if nickname is None:
            return
        nickname = nickname.strip()
        if len(nickname) > 40 or any(ord(char) < 32 for char in nickname):
            self.status.set("暱稱請使用不超過 40 個字的單行文字。")
            return
        names = self.preferences.get("names")
        if not isinstance(names, dict):
            names = {}
            self.preferences["names"] = names
        if nickname:
            names[key] = nickname
        else:
            names.pop(key, None)
        self.tree.set(key, "nickname", nickname)
        self.save_layout()

    def background(self, message, task, done):
        if self.busy:
            return
        self.busy = True
        for button in self.buttons:
            button.state(["disabled"])
        self.update_selection()
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
                self.auth_hint.set(f"正在授權 {self.auth_address}。可複製連結到對應的 Chrome 設定檔。")
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
            self.update_selection()
            if self.auth_address:
                self.auth_hint.set(f"{self.auth_address} 的授權流程已結束，請測試信箱確認權限。")
                self.auth_address = ""
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

    def show_rows(self, accounts, *, tested=False):
        if not tested:
            self.accounts = accounts
            self.results = {}
        else:
            self.results = {(a["account"].lower(), a["oauth_client"]): a for a in accounts}

        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        rows = {}
        names = self.preferences.get("names")
        names = names if isinstance(names, dict) else {}
        for account in self.accounts:
            services = account.get("services") or []
            if services and "gmail" not in services:
                continue
            email = account["email"]
            client = account.get("client") or "default"
            key = json.dumps([email.lower(), client], ensure_ascii=False)
            result = self.results.get((email.lower(), client), {})
            read = {
                "ok": "可查信",
                "reauthorization_required": "需重新授權",
                "permission_denied": "權限不足",
                "rate_limited": "頻率受限",
            }.get(result.get("error") or result.get("status"), "查詢失敗" if result else "尚未測試")
            send = "已記錄" if SEND_SCOPE in (account.get("scopes") or []) else "未記錄"
            rows[key] = (names.get(key, ""), email, client, read, send)

        order = self.preferences.get("order")
        if isinstance(order, list):
            for key in order:
                if isinstance(key, str) and key in rows:
                    self.tree.insert("", "end", iid=key, values=rows.pop(key))
        for key, row in rows.items():
            self.tree.insert("", "end", iid=key, values=row)
        if selected and self.tree.exists(selected[0]):
            self.tree.selection_set(selected[0])
        self.update_selection()

    def refresh(self):
        self.background("讀取帳號清單中…", self.load, self.show_accounts)

    def choose_config(self):
        if self.configured:
            dialog(self.window, "OAuth 設定", "這台電腦已有 OAuth 設定，可以直接新增 Gmail。")
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
        address = dialog(self.window, "新增 Gmail", "輸入要授權的 Gmail 地址。", initial="")
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
        email, client = (self.tree.set(selection[0], key) for key in ("email", "client"))
        if client != PRODUCT_CLIENT:
            self.status.set("此信箱沿用既有 gogcli 設定。要改用本工具的授權，請按「新增 Gmail」。")
            return
        self.connect(email, reauthorize=True)

    def copy_authorization_link(self):
        if self.active_url:
            self.window.clipboard_clear()
            self.window.clipboard_append(self.active_url)
            self.auth_hint.set(f"已複製 {self.auth_address} 的授權連結。請保持工具開啟。")

    def connect(self, address, reauthorize=False):
        if self.busy:
            return
        self.auth_address = address
        self.auth_hint.set(f"正在為 {address} 準備授權連結…")

        def task():
            authorize(self.gog, address, self.links.put, reauthorize)
            return self.load()
        self.background("請在瀏覽器選擇對應帳號並完成 Google 授權…", task, self.show_accounts)

    def check(self):
        def show(report):
            self.show_rows(report["accounts"], tested=True)
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
        configure_theme(window)
        window.withdraw()
        dialog(window, "找不到 gog.exe", "請解壓縮完整的 Windows 套件或安裝 gogcli。")
