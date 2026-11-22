"""Preview a Codex-composed message and send only from the local confirmation UI."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk

from account_manager import PRODUCT_CLIENT, ROOT, SEND_SCOPE
from review import GogError, run_gog
from rose_ui import BACKGROUND, FONT, INK, SURFACE, RoseButton, RoseCard, configure_theme


def address(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z0-9-]+", value)


def load_message(path):
    message = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(message, dict) or set(message) != {"from", "to", "subject", "body"}:
        raise ValueError("Required JSON fields: from, to, subject, body")
    sender, recipients, subject, body = (message[key] for key in ("from", "to", "subject", "body"))
    if not address(sender) or not isinstance(recipients, list) or not recipients or not all(map(address, recipients)):
        raise ValueError("Use a full sender address and a list of full recipient addresses")
    if not isinstance(subject, str) or not subject.strip() or any(ord(char) < 32 for char in subject):
        raise ValueError("Subject must be a nonempty single line")
    if not isinstance(body, str) or not body.strip() or "\x00" in body:
        raise ValueError("Body must be nonempty plain text")
    return sender, tuple(recipients), subject, body


def send(gog, message, env):
    sender, recipients, subject, body = message
    arguments = [gog, "--json", "--no-input", "--enable-commands-exact=gmail.send",
                 f"--account={sender}", f"--client={PRODUCT_CLIENT}", "gmail", "send",
                 f"--to={','.join(recipients)}", f"--subject={subject}", "--body-file=-"]
    return subprocess.run(arguments, input=body.encode("utf-8"), env=env, capture_output=True,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=60)


def main():
    parser = argparse.ArgumentParser(description="Open an interactive Gmail send preview.")
    parser.add_argument("message", type=Path, help="UTF-8 JSON message file")
    args = parser.parse_args()
    bundled = ROOT / "bin" / "gog.exe"
    gog = str(bundled) if bundled.is_file() else shutil.which("gog.exe")
    if not gog:
        parser.error("gog.exe not found")
    blocked = {"GOG_ACCESS_TOKEN", "GOOGLE_APPLICATION_CREDENTIALS", "GOG_ACCOUNT", "GOG_CLIENT", "GOG_AUTH_MODE"}
    env = {key: value for key, value in os.environ.items() if key.upper() not in blocked}
    try:
        message = load_message(args.message)
        sender, recipients, subject, body = message
        accounts = run_gog(gog, ["auth", "list"], env).get("accounts") or []
        if not any(a.get("email", "").casefold() == sender.casefold() and a.get("client") == PRODUCT_CLIENT
                   and SEND_SCOPE in (a.get("scopes") or []) for a in accounts):
            raise ValueError("Choose the sender in Gmail Manager and reauthorize with read and send permissions")
    except (OSError, ValueError, GogError) as error:
        parser.error(str(error))

    window = tk.Tk()
    window.title("確認 Gmail 寄送")
    window.geometry("740x540")
    window.minsize(520, 360)
    configure_theme(window)
    outer = ttk.Frame(window, style="Rose.TFrame", padding=16)
    outer.pack(fill="both", expand=True)
    ttk.Label(outer, text="確認寄出郵件", style="Title.TLabel").pack(anchor="w", pady=(0, 12))
    card = RoseCard(outer)
    card.pack(fill="both", expand=True)
    panel = card.content
    preview = tk.Text(panel, wrap="word", bg=SURFACE, fg=INK, font=(FONT, 11), borderwidth=0, highlightthickness=0)
    scrollbar = ttk.Scrollbar(panel, orient="vertical", style="Rose.Vertical.TScrollbar", command=preview.yview)
    scrollbar.pack(side="right", fill="y")
    preview.configure(yscrollcommand=scrollbar.set)
    preview.pack(side="left", fill="both", expand=True)
    preview.insert("1.0", f"寄件人：{sender}\n收件人：{', '.join(recipients)}\n主旨：{subject}\n\n{body}")
    preview.configure(state="disabled")
    controls = ttk.Frame(outer, style="Rose.TFrame")
    controls.pack(fill="x", pady=(12, 0))
    status = "cancelled"

    def confirm():
        nonlocal status
        confirm_button.state(["disabled"])
        cancel_button.state(["disabled"])
        window.protocol("WM_DELETE_WINDOW", lambda: None)
        try:
            result = send(gog, message, env)
            status = "sent" if result.returncode == 0 else "send_unconfirmed"
        except (OSError, subprocess.TimeoutExpired):
            status = "send_unconfirmed"
        window.destroy()

    confirm_button = RoseButton(controls, "確認寄出", confirm, primary=True, background=BACKGROUND)
    confirm_button.pack(side="right")
    cancel_button = RoseButton(controls, "取消", window.destroy, background=BACKGROUND)
    cancel_button.pack(side="right", padx=8)
    cancel_button.focus_set()
    window.mainloop()
    print(json.dumps({"status": status}))
    return 1 if status == "send_unconfirmed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
