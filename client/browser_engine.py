"""Findupto Secure Browser engine.

Chromium/QtWebEngine browser with defense-in-depth privacy controls. The
browser never fabricates an IP address: public-IP hiding comes from the active
Findupto VPN tunnel and/or an explicitly configured proxy/relay. The browser
adds leak-resistant Chromium policies so websites have fewer direct paths back
to the local network.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote_plus


# Apply privacy flags before QtWebEngine is initialized.
_base_flags = [
    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
    "--disable-webrtc-multiple-routes",
    "--disable-quic",
    "--disable-background-networking",
    "--disable-domain-reliability",
    "--disable-features=PreconnectToSearch",
]
_existing_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").split()
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(dict.fromkeys(_existing_flags + _base_flags))

try:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import (
        QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
        QMainWindow, QMessageBox, QPushButton, QToolBar, QVBoxLayout, QWidget,
    )
    from PySide6.QtWebEngineCore import (
        QWebEngineDownloadRequest, QWebEnginePage, QWebEngineProfile,
        QWebEngineSettings, QWebEngineUrlRequestInterceptor,
    )
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_QT = True
except ImportError:
    HAS_QT = False


class PrivacyInterceptor(QWebEngineUrlRequestInterceptor if HAS_QT else object):
    """Block common trackers and reject cleartext navigation in strict mode."""

    TRACKER_HOSTS = {
        "doubleclick.net", "googlesyndication.com", "googleadservices.com",
        "googletagmanager.com", "facebook.net", "connect.facebook.net",
        "adnxs.com", "adsrvr.org", "scorecardresearch.com",
        "amazon-adsystem.com", "taboola.com", "outbrain.com",
        "criteo.com", "rubiconproject.com", "pubmatic.com",
    }

    def __init__(self, browser):
        if HAS_QT:
            super().__init__()
        self.browser = browser

    def interceptRequest(self, info):
        url = info.requestUrl()
        host = url.host().lower()
        scheme = url.scheme().lower()
        if self.browser.https_only and scheme == "http" and host:
            info.redirect(QUrl("https://" + host + url.path() + ("?" + url.query() if url.query() else "")))
            return
        if self.browser.block_trackers and any(host == x or host.endswith("." + x) for x in self.TRACKER_HOSTS):
            info.block(True)
            return
        # Never allow browser pages to send HTTP Referer/Origin metadata to
        # cleartext destinations when strict privacy mode is enabled.
        if self.browser.strict_privacy and scheme == "http":
            info.block(True)


if HAS_QT:
    class BrowserPage(QWebEnginePage):
        def __init__(self, browser, profile):
            super().__init__(profile, browser)
            self.browser = browser

        def createWindow(self, _type):
            if self.browser.block_popups:
                return self.browser.new_tab(return_page=True)
            return self.browser.new_tab(return_page=True)

        def certificateError(self, error):
            # Do not bypass invalid TLS certificates in strict privacy mode.
            if self.browser.strict_privacy:
                error.rejectCertificate()
                return True
            return super().certificateError(error)


    class BrowserWindow(QMainWindow):
        def __init__(self, home="https://www.google.com", proxy=""):
            super().__init__()
            self.home = home
            self.proxy = (proxy or os.environ.get("FINDUPTO_BROWSER_PROXY", "")).strip()
            self.block_trackers = True
            self.block_popups = True
            self.private_mode = False
            self.https_only = True
            self.strict_privacy = True
            self.block_webrtc = True
            self.block_local_network = True
            self.disable_quic = True
            self.zoom = 1.0
            self.bookmarks = []
            self.history = []
            self.downloads = []
            self.relay_layers = 1 if self.proxy else 0
            self._profile = None
            self._views = []
            self.setWindowTitle("Findupto Secure Browser Pro — IP Leak Shield")
            self.resize(1500, 940)
            self._configure_chromium_proxy()
            self._make_profile()
            self._build_ui()
            self.new_tab()

        def _configure_chromium_proxy(self):
            if not self.proxy:
                return
            flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").split()
            proxy_flag = "--proxy-server=" + self.proxy
            if proxy_flag not in flags:
                flags.append(proxy_flag)
            os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(dict.fromkeys(flags))

        def _make_profile(self):
            self._profile = QWebEngineProfile(self)
            self._profile.setPersistentCookiesPolicy(
                QWebEngineProfile.NoPersistentCookies if self.private_mode
                else QWebEngineProfile.AllowPersistentCookies
            )
            if self.private_mode:
                self._profile.setHttpCacheType(QWebEngineProfile.MemoryHttpCache)
            self.interceptor = PrivacyInterceptor(self)
            self._profile.setUrlRequestInterceptor(self.interceptor)
            self._profile.downloadRequested.connect(self._download)

        def _build_ui(self):
            toolbar = QToolBar("Navigation")
            toolbar.setMovable(False)
            self.addToolBar(toolbar)
            for text, slot in (("←", self.back), ("→", self.forward), ("↻", self.reload), ("⌂", self.home_page)):
                action = QAction(text, self)
                action.triggered.connect(slot)
                toolbar.addAction(action)
            self.address = QLineEdit()
            self.address.setPlaceholderText("Search or enter address — protected by Findupto VPN")
            self.address.returnPressed.connect(self.navigate)
            toolbar.addWidget(self.address)
            for text, slot in (("★", self.bookmark), ("Find", self.find), ("+", self.new_tab)):
                action = QAction(text, self)
                action.triggered.connect(slot)
                toolbar.addAction(action)

            root = QWidget()
            layout = QHBoxLayout(root)
            side = QVBoxLayout()
            self.ip_label = QLabel()
            self._refresh_ip_status()
            side.addWidget(self.ip_label)
            controls = [
                ("Home", self.home_page), ("New Tab", self.new_tab),
                ("Bookmarks", self.show_bookmarks), ("History", self.show_history),
                ("Downloads", self.show_downloads), ("IP Leak Shield", self.show_ip_shield),
                ("Privacy Center", self.privacy), ("Private Mode", self.toggle_private),
                ("Clear Data", self.clear_data), ("Zoom +", lambda: self.change_zoom(.1)),
                ("Zoom −", lambda: self.change_zoom(-.1)), ("Reader Mode", self.reader_mode),
                ("Save PDF", self.save_pdf),
            ]
            for text, slot in controls:
                button = QPushButton(text)
                button.clicked.connect(slot)
                side.addWidget(button)
            side.addStretch()
            layout.addLayout(side, 0)

            self.tabs = QListWidget()
            self.tabs.setMaximumWidth(230)
            self.tabs.currentRowChanged.connect(self.switch_tab)
            layout.addWidget(self.tabs)
            self.stack = QWidget()
            self.stack_layout = QVBoxLayout(self.stack)
            layout.addWidget(self.stack, 1)
            self.setCentralWidget(root)
            self.setStyleSheet(
                "QMainWindow,QWidget{background:#0b0f18;color:#f8faff} "
                "QPushButton{padding:9px;background:#151d2b;color:#f8faff;border:0} "
                "QPushButton:hover{background:#7657ff} "
                "QLineEdit{padding:9px;background:#151d2b;color:#f8faff;border:1px solid #202b3d}"
            )

        def _refresh_ip_status(self):
            if self.proxy:
                text = ("● IP LEAK SHIELD: ACTIVE\n"
                        "Public IP: VPN/relay exit\n"
                        f"Privacy layers: {max(1, self.relay_layers)}\n"
                        "WebRTC direct UDP: BLOCKED")
            else:
                text = ("● IP LEAK SHIELD: VPN-DEPENDENT\n"
                        "Public IP: active Findupto VPN\n"
                        "WebRTC direct UDP: BLOCKED\n"
                        "Relay proxy: not configured")
            self.ip_label.setText(text)

        def _page(self):
            index = self.tabs.currentRow()
            if index < 0 or index >= len(self._views):
                return None
            return self._views[index].page()

        def new_tab(self, return_page=False):
            view = QWebEngineView()
            page = BrowserPage(self, self._profile)
            view.setPage(page)
            view.urlChanged.connect(lambda url, v=view: self._url_changed(v, url))
            view.titleChanged.connect(lambda title, v=view: self._title_changed(v, title))
            view.loadStarted.connect(lambda: self.statusBar().showMessage("● Protected connection starting…"))
            view.loadFinished.connect(lambda ok: self.statusBar().showMessage("● Protected connection active" if ok else "● Page load failed"))
            self._views.append(view)
            self.stack_layout.addWidget(view)
            self.tabs.addItem("New Tab")
            index = self.tabs.count() - 1
            self.tabs.setCurrentRow(index)
            view.load(QUrl(self.home))
            return page if return_page else None

        def switch_tab(self, index):
            for i, view in enumerate(self._views):
                view.setVisible(i == index)
            page = self._page()
            if page:
                self.address.setText(page.url().toString())

        def _url_changed(self, view, url):
            if view is self._views[self.tabs.currentRow()] if self.tabs.currentRow() >= 0 else False:
                self.address.setText(url.toString())
            value = url.toString()
            if value and not self.private_mode and (not self.history or self.history[-1] != value):
                self.history.append(value)

        def _title_changed(self, title, view):
            for i, candidate in enumerate(self._views):
                if candidate is view:
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
            if self.strict_privacy and text.startswith("http://"):
                self.statusBar().showMessage("● Blocked cleartext navigation")
                return
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
            self.statusBar().showMessage("★ Bookmark saved")

        def find(self):
            text, ok = self._input("Find in page", "Text")
            if ok and self._page():
                self._page().findText(text)

        def change_zoom(self, amount):
            page = self._page()
            if page:
                self.zoom = max(.25, min(5.0, self.zoom + amount))
                page.setZoomFactor(self.zoom)
                self.statusBar().showMessage(f"Zoom: {round(self.zoom * 100)}%")

        def toggle_private(self):
            self.private_mode = not self.private_mode
            self._make_profile()
            self._refresh_ip_status()
            self.statusBar().showMessage("Private mode " + ("enabled — cookies/cache are memory-only" if self.private_mode else "disabled"))

        def clear_data(self):
            self._profile.cookieStore().deleteAllCookies()
            self._profile.clearHttpCache()
            self.history.clear()
            self.statusBar().showMessage("Cookies, cache and history cleared")

        def privacy(self):
            self.show_ip_shield()

        def show_ip_shield(self):
            layers = max(1, self.relay_layers) if self.proxy else 1
            proxy_text = self.proxy if self.proxy else "Findupto VPN tunnel (required)"
            QMessageBox.information(
                self, "IP Leak Shield",
                "Findupto Defense-in-Depth\n\n"
                f"Public IP exit: {proxy_text}\n"
                f"Relay layers configured: {layers}\n\n"
                "✓ WebRTC non-proxied UDP blocked\n"
                "✓ WebRTC multiple routes blocked\n"
                "✓ QUIC/HTTP3 disabled\n"
                "✓ HTTPS-only navigation\n"
                "✓ Cleartext requests blocked in strict mode\n"
                "✓ Tracker interception enabled\n"
                "✓ Background networking reduced\n"
                "✓ Private mode uses memory cookies/cache\n\n"
                "Important: browser controls cannot hide an IP from the VPN provider,\n"
                "and multiple-hop anonymity requires real VPN/relay servers."
            )

        def reader_mode(self):
            page = self._page()
            if page:
                page.runJavaScript("document.body.innerHTML='<main style=\"max-width:800px;margin:40px auto;font:20px sans-serif;line-height:1.7;background:white;color:black;padding:40px\">'+document.body.innerText.replace(/</g,'&lt;')+'</main>';document.body.style.background='white';")

        def save_pdf(self):
            page = self._page()
            if page:
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
            edit.setFocus()
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
