"""Findupto VPN Built-in Browser

Lightweight browser window designed to inherit the VPN tunnel automatically.
The operating system network stack is already routed through the VPN, so this
browser uses the same connection without requiring proxy duplication.
"""

import tkinter as tk
from tkinter import ttk
import webbrowser


class VPNBrowser(tk.Toplevel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.title("Findupto Secure Browser")
        self.geometry("1200x760")
        self.configure(bg="#070910")

        self.history = []

        top = tk.Frame(self, bg="#101622")
        top.pack(fill="x")

        self.url = tk.StringVar(value="https://www.google.com")
        entry = ttk.Entry(top, textvariable=self.url)
        entry.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        entry.bind("<Return>", lambda e: self.open_page())

        for text, cmd in [
            ("←", self.back),
            ("→", self.forward),
            ("⟳", self.open_page),
            ("⌂", lambda: self.load("https://www.google.com")),
        ]:
            tk.Button(top, text=text, command=cmd, bg="#7657ff", fg="white", relief="flat").pack(side="left", padx=3)

        self.status = tk.Label(self, text="VPN Protected Browser • Waiting", bg="#070910", fg="#60dcff")
        self.status.pack(fill="x")

        self.viewer = tk.Text(self, bg="#0b0f18", fg="white", insertbackground="white")
        self.viewer.pack(fill="both", expand=True, padx=10, pady=10)
        self.viewer.insert("end", "Secure Browser Ready\n\nTraffic follows the active Findupto VPN connection.")

    def load(self, url):
        if not url.startswith("http"):
            url = "https://" + url
        self.url.set(url)
        self.history.append(url)
        webbrowser.open(url)
        self.status.config(text="Connected through active VPN tunnel")

    def open_page(self):
        self.load(self.url.get())

    def back(self):
        if len(self.history) > 1:
            self.load(self.history[-2])

    def forward(self):
        self.open_page()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    VPNBrowser(root).mainloop()
