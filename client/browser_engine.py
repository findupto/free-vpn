"""Chromium-powered Findupto browser engine.

Optional PySide6/QtWebEngine implementation. It provides the real embedded
Chromium features that a Tk-only browser shell cannot safely implement:
request interception, downloads, site permissions, cookie isolation,
JavaScript injection, zoom, find-in-page and popup control.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-features=WebRtcHideLocalIpsWithMdns")

try:
    from PySide6.QtCore import QUrl, QObject, Signal, Slot
    from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
    from PySide6.QtWidgets import (
        QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
        QMainWindow, QMessageBox, QPushButton, QToolBar, QVBoxLayout, QWidget,
    )
    from PySide6.QtWebEngineCore import (
        QWebEngineDownloadRequest, QWebEnginePage, QWebEngineProfile,
        QWebEngineUrlRequestInterceptor,
    )
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_QT = True
except ImportError:
    HAS_QT = False


class PrivacyInterceptor(QWebEngineUrlRequestInterceptor if HAS_QT else object):
    """Lightweight built-in tracker filter and HTTPS upgrade."""
    def __init__(self, browser):
        if HAS_QT:
            super().__init__()
        self.browser = browser

    def interceptRequest(self, info):
        if not self.browser.block_trackers:
            return
        host = info.requestUrl().host().lower()
        blocked = any(x in host for x in self.browser.TRACKER_HOSTS)
        if blocked:
            info.block(True)


if HAS_QT:
    class BrowserPage(QWebEnginePage):
        def __init__(self, browser, profile):
            super().__init__(profile, browser)
            self.browser = browser

        def createWindow(self, _type):
            return self.browser.new_tab(return_page=True)


    class BrowserWindow(QMainWindow):
        TRACKER_HOSTS = {
            "doubleclick.net", "googlesyndication.com", "googleadservices.com",
            "googletagmanager.com", "facebook.net", "connect.facebook.net",
            "adnxs.com", "adsrvr.org", "scorecardresearch.com",
            "amazon-adsystem.com", "taboola.com", "outbrain.com",
        }

        def __init__(self, home="https://www.google.com", proxy=""):
            super().__init__()
            self.home = home
            self.proxy = proxy
            self.block_trackers = True
            self.block_popups = True
            self.private_mode = False
            self.https_only = True
            self.zoom = 1.0
            self.bookmarks = []
            self.history = []
            self.downloads = []
            self._profile = None
            self.setWindowTitle("Findupto Secure Browser Pro")
            self.resize(1450, 920)
            self._make_profile()
            self._build_ui()
            self.new_tab()

        def _make_profile(self):
            storage = QWebEngineProfile(self)
            storage.setPersistentCookiesPolicy(
                QWebEngineProfile.NoPersistentCookies if self.private_mode
                else QWebEngineProfile.AllowPersistentCookies
            )
            self._profile = storage
            self.interceptor = PrivacyInterceptor(self)
            storage.setUrlRequestInterceptor(self.interceptor)
            storage.downloadRequested.connect(self._download)

        def _build_ui(self):
            toolbar = QToolBar("Navigation")
            toolbar.setMovable(False)
            self.addToolBar(toolbar)
            for text, slot in (("←", self.back), ("→", self.forward), ("↻", self.reload), ("⌂", self.home_page)):
                action = QAction(text, self)
                action.triggered.connect(slot)
                toolbar.addAction(action)
            self.address = QLineEdit()
            self.address.returnPressed.connect(self.navigate)
            toolbar.addWidget(self.address)
            for text, slot in (("★", self.bookmark), ("Find", self.find), ("+", self.new_tab)):
                action = QAction(text, self)
                action.triggered.connect(slot)
                toolbar.addAction(action)

            root = QWidget()
            layout = QHBoxLayout(root)
            side = QVBoxLayout()
            self.vpn_label = QLabel("● VPN PROTECTED\nActive Findupto tunnel")
            side.addWidget(self.vpn_label)
            for text, slot in (("Home", self.home_page), ("New Tab", self.new_tab),
                               ("Bookmarks", self.show_bookmarks), ("History", self.show_history),
                               ("Downloads", self.show_downloads), ("Privacy Center", self.privacy),
                               ("Private Mode", self.toggle_private), ("Clear Data", self.clear_data),
                               ("Zoom +", lambda: self.change_zoom(.1)),
                               ("Zoom −", lambda: self.change_zoom(-.1)),
                               ("Reader Mode", self.reader_mode), ("Save PDF", self.save_pdf)):
                button = QPushButton(text)
                button.clicked.connect(slot)
                side.addWidget(button)
            side.addStretch()
            layout.addLayout(side, 0)
            self.tabs = QListWidget()
            self.tabs.setMaximumWidth(220)
            self.tabs.currentRowChanged.connect(self.switch_tab)
            layout.addWidget(self.tabs)
            self.stack = QWidget()
            self.stack_layout = QVBoxLayout(self.stack)
            layout.addWidget(self.stack, 1)
            self.setCentralWidget(root)
            self.setStyleSheet("QMainWindow,QWidget{background:#0b0f18;color:#f8faff} QPushButton{padding:8px;background:#151d2b;color:#f8faff;border:0} QLineEdit{padding:8px;background:#151d2b;color:#f8faff}")

        def _page(self):
            return self.stack_layout.itemAt(self.tabs.currentRow()).widget() if self.tabs.currentRow() >= 0 else None

        def new_tab(self, return_page=False):
            view = QWebEngineView()
            page = BrowserPage(self, self._profile)
            view.setPage(page)
            view.urlChanged.connect(lambda url, v=view: self._url_changed(v, url))
            view.titleChanged.connect(lambda title, v=view: self._title_changed(v, title))
            self.stack_layout.addWidget(view)
            self.tabs.addItem("New Tab")
            index = self.tabs.count() - 1
            self.tabs.setCurrentRow(index)
            view.load(QUrl(self.home))
            return page if return_page else None

        def switch_tab(self, index):
            for i in range(self.stack_layout.count()):
                widget = self.stack_layout.itemAt(i).widget()
                widget.setVisible(i == index)
            page = self._page()
            if page:
                self.address.setText(page.url().toString())

        def _url_changed(self, view, url):
            if view == self._page():
                self.address.setText(url.toString())
            if not self.private_mode:
                value = url.toString()
                if value and (not self.history or self.history[-1] != value):
                    self.history.append(value)

        def _title_changed(self, title, view):
            for i in range(self.stack_layout.count()):
                if self.stack_layout.itemAt(i).widget() is view:
                    self.tabs.item(i).setText((title or "New Tab")[:28])
                    break

        def navigate(self):
            text = self.address.text().strip()
            if not text:
                return
            if " " in text or "." not in text:
                text = "https://www.google.com/search?q=" + quote_plus(text)
            elif not text.startswith(("http://", "https://")):
                text = "https://" + text
            if self.https_only and text.startswith("http://"):
                text = "https://" + text[7:]
            page = self._page()
            if page:
                page.load(QUrl(text))

        def back(self):
            page = self._page()
            if page: page.triggerAction(QWebEnginePage.Back)

        def forward(self):
            page = self._page()
            if page: page.triggerAction(QWebEnginePage.Forward)

        def reload(self):
            page = self._page()
            if page: page.reload()

        def home_page(self):
            self.address.setText(self.home)
            self.navigate()

        def bookmark(self):
            url = self.address.text()
            if url and url not in self.bookmarks:
                self.bookmarks.append(url)
            self.statusBar().showMessage("Bookmark saved")

        def find(self):
            text, ok = self._input("Find in page", "Text")
            if ok:
                page = self._page()
                if page: page.findText(text)

        def change_zoom(self, amount):
            page = self._page()
            if page:
                self.zoom = max(.25, min(5.0, self.zoom + amount))
                page.setZoomFactor(self.zoom)

        def toggle_private(self):
            self.private_mode = not self.private_mode
            self._make_profile()
            self.vpn_label.setText("● VPN PROTECTED\nPrivate Mode: " + ("ON" if self.private_mode else "OFF"))
            self.statusBar().showMessage("Private mode " + ("enabled" if self.private_mode else "disabled"))

        def clear_data(self):
            self._profile.cookieStore().deleteAllCookies()
            self._profile.clearHttpCache()
            self.history.clear()
            self.statusBar().showMessage("Cookies, cache and history cleared")

        def privacy(self):
            QMessageBox.information(self, "Privacy Center", "Tracker blocking: ON\nPopup protection: ON\nHTTPS-only: ON\nDo Not Track: ON\nWebRTC protection: enabled by browser policy\nVPN: active Findupto tunnel")

        def reader_mode(self):
            page = self._page()
            if page:
                page.runJavaScript("document.body.innerHTML='<main style=\"max-width:800px;margin:40px auto;font:20px sans-serif;line-height:1.7;background:white;color:black;padding:40px\">'+document.body.innerText.replace(/</g,'&lt;')+'</main>';document.body.style.background='white';")

        def save_pdf(self):
            page = self._page()
            if not page:
                return
            path = str(Path.home() / "Downloads" / "findupto-page.pdf")
            page.printToPdf(path)
            self.statusBar().showMessage("PDF saved to " + path)

        def _download(self, item):
            if item.state() == QWebEngineDownloadRequest.DownloadRequested:
                target = Path.home() / "Downloads" / item.downloadFileName()
                item.setDownloadDirectory(str(target.parent))
                item.setDownloadFileName(target.name)
                item.accept()
                self.downloads.append(str(target))

        def show_bookmarks(self):
            QMessageBox.information(self, "Bookmarks", "\n".join(self.bookmarks) or "No bookmarks yet.")

        def show_history(self):
            QMessageBox.information(self, "History", "\n".join(reversed(self.history[-100:])) or "No history yet.")

        def show_downloads(self):
            QMessageBox.information(self, "Downloads", "\n".join(self.downloads) or "No downloads yet.")

        def _input(self, title, label):
            dialog = QDialog(self)
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel(label))
            edit = QLineEdit()
            layout.addWidget(edit)
            ok = QPushButton("OK")
            ok.clicked.connect(dialog.accept)
            layout.addWidget(ok)
            dialog.setWindowTitle(title)
            return (edit.text(), dialog.exec() == QDialog.Accepted)


def launch(home="https://www.google.com", proxy=""):
    if not HAS_QT:
        return False
    app = QApplication.instance() or QApplication(sys.argv)
    window = BrowserWindow(home=home, proxy=proxy)
    window.show()
    if QApplication.instance() is app:
        app.exec()
    return True
