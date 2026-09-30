import os
import queue
import threading
import webbrowser

import certifi

os.environ.setdefault("SSL_CERT_FILE", certifi.where())

import yt_dlp
from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.lang import Builder
from kivy.properties import NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.utils import platform

KV = """
#:import dp kivy.metrics.dp

<ResultRow>:
    orientation: 'vertical'
    size_hint_y: None
    height: dp(150)
    padding: dp(6)
    spacing: dp(4)
    canvas.before:
        Color:
            rgba: .16, .16, .16, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(8)]
    BoxLayout:
        spacing: dp(8)
        AsyncImage:
            source: root.thumb
            size_hint_x: None
            width: dp(130)
            fit_mode: 'contain'
        BoxLayout:
            orientation: 'vertical'
            Label:
                text: root.title
                text_size: self.width, None
                size_hint_y: .7
                halign: 'left'
                valign: 'top'
                shorten: True
                max_lines: 3
                text_size: self.size
            Label:
                text: root.meta
                color: .6, .6, .6, 1
                size_hint_y: .3
                halign: 'left'
                valign: 'middle'
                text_size: self.size
    BoxLayout:
        size_hint_y: None
        height: dp(42)
        spacing: dp(6)
        Button:
            text: 'Preview'
            on_release: app.preview(root.url)
        Button:
            text: 'Download'
            background_color: .2, .7, .3, 1
            on_release: app.queue_download(root.url, root.title)

<DownloadRow>:
    orientation: 'vertical'
    size_hint_y: None
    height: dp(120)
    padding: dp(6)
    spacing: dp(3)
    canvas.before:
        Color:
            rgba: .16, .16, .16, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(8)]
    Label:
        text: root.title
        shorten: True
        halign: 'left'
        text_size: self.size
        size_hint_y: None
        height: dp(24)
    ProgressBar:
        max: 100
        value: root.progress
        size_hint_y: None
        height: dp(12)
    Label:
        text: root.details
        halign: 'left'
        valign: 'top'
        text_size: self.size

BoxLayout:
    orientation: 'vertical'
    TabbedPanel:
        do_default_tab: False
        tab_width: self.width / 2
        TabbedPanelItem:
            text: 'Search'
            BoxLayout:
                orientation: 'vertical'
                padding: dp(6)
                spacing: dp(6)
                BoxLayout:
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(6)
                    TextInput:
                        id: search_entry
                        hint_text: 'Search YouTube'
                        multiline: False
                        on_text_validate: app.search()
                    Button:
                        text: 'Search'
                        size_hint_x: None
                        width: dp(80)
                        on_release: app.search()
                    Button:
                        text: 'Trending'
                        size_hint_x: None
                        width: dp(90)
                        on_release: app.trending()
                Label:
                    id: status
                    text: ''
                    size_hint_y: None
                    height: dp(20)
                    color: 1, .6, .4, 1
                ScrollView:
                    GridLayout:
                        id: results
                        cols: 1
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: dp(6)
        TabbedPanelItem:
            text: 'Downloads'
            BoxLayout:
                orientation: 'vertical'
                padding: dp(6)
                spacing: dp(6)
                TextInput:
                    id: url_entry
                    hint_text: 'Paste YouTube URL'
                    multiline: False
                    size_hint_y: None
                    height: dp(44)
                BoxLayout:
                    size_hint_y: None
                    height: dp(44)
                    spacing: dp(6)
                    Button:
                        text: 'Paste'
                        on_release: app.paste_url()
                    Button:
                        text: 'Copy'
                        on_release: app.copy_url()
                    Button:
                        text: 'Download URL'
                        background_color: .2, .7, .3, 1
                        on_release: app.download_url()
                ScrollView:
                    GridLayout:
                        id: manager
                        cols: 1
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: dp(6)
"""


# -----------------------------
# Helpers
# -----------------------------
def format_duration(seconds):
    if not seconds:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def format_bytes(n):
    if not n:
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


# -----------------------------
# Widgets
# -----------------------------
class ResultRow(BoxLayout):
    title = StringProperty("")
    url = StringProperty("")
    thumb = StringProperty("")
    meta = StringProperty("")


class DownloadRow(BoxLayout):
    title = StringProperty("")
    progress = NumericProperty(0)
    details = StringProperty("Waiting...")


# -----------------------------
# App
# -----------------------------
class YTApp(App):
    title = "YouTube Downloader"

    def build(self):
        self.download_queue = queue.Queue()
        for _ in range(2):  # fewer workers on mobile
            threading.Thread(target=self.download_worker, daemon=True).start()

        if platform == "android":
            from android.permissions import Permission, request_permissions

            request_permissions([Permission.INTERNET])

        return Builder.load_string(KV)

    # ---------- utils ----------
    def ui(self, fn):
        """Run fn on the Kivy main thread."""
        Clock.schedule_once(lambda dt: fn(), 0)

    def set_status(self, text):
        self.ui(lambda: setattr(self.root.ids.status, "text", text))

    def downloads_dir(self):
        if platform == "android":
            from android import mActivity

            base = mActivity.getExternalFilesDir(None).getAbsolutePath()
            path = os.path.join(base, "downloads")
        else:
            path = "downloads"
        os.makedirs(path, exist_ok=True)
        return path

    # ---------- clipboard ----------
    def paste_url(self):
        try:
            self.root.ids.url_entry.text = Clipboard.paste() or ""
        except Exception:
            pass

    def copy_url(self):
        text = self.root.ids.url_entry.text
        if text:
            Clipboard.copy(text)

    # ---------- search ----------
    def search(self):
        q = self.root.ids.search_entry.text.strip()
        if q:
            threading.Thread(target=self.search_thread, args=(q,), daemon=True).start()

    def trending(self):
        threading.Thread(
            target=self.search_thread, args=("trending videos",), daemon=True
        ).start()

    def search_thread(self, query):
        self.ui(self.root.ids.results.clear_widgets)
        self.set_status("Searching...")
        try:
            opts = {"quiet": True, "extract_flat": True, "skip_download": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch15:{query}", download=False)
        except Exception as e:
            self.set_status(f"Search failed: {str(e)[:80]}")
            return

        self.set_status("")
        for v in info.get("entries") or []:
            if not v:
                continue
            vid = v.get("id")
            row = ResultRow(
                title=v.get("title") or "",
                url=v.get("url") or f"https://www.youtube.com/watch?v={vid}",
                thumb=f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
                meta=f"{v.get('channel') or ''} • {format_duration(v.get('duration'))}",
            )
            self.ui(lambda r=row: self.root.ids.results.add_widget(r))

    # ---------- preview (opens system video player) ----------
    def preview(self, url):
        threading.Thread(target=self.preview_thread, args=(url,), daemon=True).start()

    def preview_thread(self, url):
        self.set_status("Loading preview...")
        try:
            opts = {"quiet": True, "format": "best[ext=mp4]/best", "noplaylist": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            stream = info.get("url")
        except Exception as e:
            self.set_status(f"Preview failed: {str(e)[:80]}")
            return
        self.set_status("")
        if stream:
            self.ui(lambda: self.open_external(stream))

    def open_external(self, stream_url):
        if platform == "android":
            from android import mActivity
            from jnius import autoclass

            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")
            intent = Intent(Intent.ACTION_VIEW)
            intent.setDataAndType(Uri.parse(stream_url), "video/*")
            mActivity.startActivity(Intent.createChooser(intent, "Play with"))
        else:
            webbrowser.open(stream_url)

    # ---------- download queue ----------
    def queue_download(self, url, title):
        row = DownloadRow(title=title)
        self.root.ids.manager.add_widget(row)
        self.download_queue.put((url, row))
        self.set_status("Added to Downloads tab")

    def download_url(self):
        url = self.root.ids.url_entry.text.strip()
        if url:
            self.queue_download(url, url)

    def download_worker(self):
        while True:
            url, row = self.download_queue.get()
            try:
                self.download_video(url, row)
            except Exception as e:
                msg = f"Error: {str(e)[:120]}"
                self.ui(lambda m=msg: setattr(row, "details", m))
            finally:
                self.download_queue.task_done()

    def progress_hook(self, d, row):
        status = d.get("status")
        if status == "downloading":
            done = d.get("downloaded_bytes") or 0
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            pct = (done / total * 100) if total else 0
            text = (
                f"Progress: {pct:.1f}%\n"
                f"Speed: {format_bytes(d.get('speed'))}/s\n"
                f"ETA: {d.get('eta') if d.get('eta') is not None else '?'}s\n"
                f"Downloaded: {format_bytes(done)} / {format_bytes(total)}"
            )
            self.ui(lambda: (setattr(row, "progress", pct), setattr(row, "details", text)))
        elif status == "finished":
            self.ui(lambda: setattr(row, "details", "Finishing..."))

    def download_video(self, url, row):
        out_dir = self.downloads_dir()
        opts = {
            # single progressive file: no ffmpeg needed on Android
            "format": "best[ext=mp4][vcodec!=none][acodec!=none]/best[ext=mp4]/best",
            "outtmpl": os.path.join(out_dir, "%(title)s.%(ext)s"),
            "progress_hooks": [lambda d: self.progress_hook(d, row)],
            "noplaylist": True,
            "continuedl": True,
            "cachedir": False,
            "quiet": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        self.ui(
            lambda: (
                setattr(row, "progress", 100),
                setattr(row, "details", f"Done. Saved in:\n{out_dir}"),
            )
        )


if __name__ == "__main__":
    YTApp().run()
