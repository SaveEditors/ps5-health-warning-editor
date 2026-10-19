"""Tkinter user interface.

The UI is intentionally boring: enter the console address, connect, edit the
body, apply.  All file and FTP logic lives in ``service`` / ``rco``.
"""

from __future__ import annotations

import logging
import os
import queue
import re
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from . import __version__
from .constants import (
    APP_DESCRIPTION,
    APP_NAME,
    DEFAULT_PORT,
    SYMBOLS,
    TESTED_FIRMWARE,
    TESTED_JAILBREAK,
)
from .paths import (
    get_backup_dir,
    get_log_path,
    get_settings_path,
    resource_path,
)
from .rco import serialized_len
from .service import ApplyResult, Session, apply_text, create_session
from .settings import Settings, load_settings, save_settings

logger = logging.getLogger(__name__)

GREEN = "#0a7d32"
RED = "#b00020"
GRAY = "#666666"
AMBER = "#9a6700"

_GEOMETRY_RE = re.compile(r"\d+x\d+\+-?\d+\+-?\d+")


class EditorApp:
    def __init__(
        self,
        root: tk.Tk,
        *,
        settings_path: Path | None = None,
        backup_dir: Path | None = None,
    ) -> None:
        self.root = root
        self.settings_path = settings_path or get_settings_path()
        self.backup_dir = backup_dir or get_backup_dir()
        self.messages: queue.Queue = queue.Queue()
        self.session: Session | None = None
        self.connected_host = ""
        self.connected_port = ""
        self.connected_status = ""
        self.loaded_body = ""
        self.busy = False
        self._last_body: str | None = None
        self._last_service_message = ""

        settings = load_settings(self.settings_path)
        self.host_var = tk.StringVar(value=settings.host)
        self.port_var = tk.StringVar(value=str(settings.port))

        self.root.title(f"{APP_NAME} {__version__}")
        self.root.minsize(900, 660)
        if settings.geometry and _GEOMETRY_RE.fullmatch(settings.geometry):
            try:
                self.root.geometry(settings.geometry)
            except tk.TclError:
                self.root.geometry("980x720")
        else:
            self.root.geometry("980x720")

        self._set_window_icon()
        self._build_menu()
        self._build_ui()

        self.host_var.trace_add("write", lambda *_args: self._address_changed())
        self.port_var.trace_add("write", lambda *_args: self._address_changed())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._poll_messages)
        self.root.after(250, self._tick)

        self._log(f"{APP_NAME} {__version__}", "ok")
        self._log(f"Local backups: {self.backup_dir}", "dim")
        self._log(
            f"Tested on PS5 firmware {TESTED_FIRMWARE} with "
            f"{TESTED_JAILBREAK}. Unofficial tool.",
            "dim",
        )
        self._log(
            "Connect to load the current warning text. The original is "
            "backed up locally and on the console before editing is enabled.",
            "dim",
        )
        self._update_now()

    # -- window -------------------------------------------------------------

    def _set_window_icon(self) -> None:
        icon = resource_path("assets/icon.ico")
        if not icon.exists():
            return
        try:
            self.root.iconbitmap(default=str(icon))
        except tk.TclError:
            logger.debug("Could not set the window icon", exc_info=True)

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(
            label="Open backups folder", command=self._open_backups
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menu.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(
            label="How it works", command=self._show_how_it_works
        )
        help_menu.add_command(
            label="Restore stock warning...", command=self._show_restore_help
        )
        help_menu.add_separator()
        help_menu.add_command(label="Open log file", command=self._open_log)
        help_menu.add_command(label="About", command=self._show_about)
        menu.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menu)

    # -- UI -----------------------------------------------------------------

    def _build_ui(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Hint.TLabel", foreground=GRAY)

        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=0)
        main.rowconfigure(1, weight=3)
        main.rowconfigure(3, weight=1)

        # Console -----------------------------------------------------------
        conn = ttk.LabelFrame(main, text="Console", padding=(10, 8))
        conn.grid(row=0, column=0, columnspan=2, sticky="ew")
        conn.columnconfigure(4, weight=1)

        ttk.Label(conn, text="Host").grid(row=0, column=0, sticky="w")
        self.host_entry = ttk.Entry(conn, textvariable=self.host_var, width=18)
        self.host_entry.grid(row=0, column=1, padx=(6, 14))
        ttk.Label(conn, text="FTP port").grid(row=0, column=2, sticky="w")
        self.port_entry = ttk.Entry(conn, textvariable=self.port_var, width=7)
        self.port_entry.grid(row=0, column=3, padx=(6, 14))
        self.connect_btn = ttk.Button(
            conn, text="Connect", command=self._connect_clicked
        )
        self.connect_btn.grid(row=0, column=4, sticky="w")

        self.conn_status = ttk.Label(
            conn,
            text=(
                "Not connected. Connect to load the current text and back "
                "up the original."
            ),
            style="Hint.TLabel",
            wraplength=900,
            justify="left",
        )
        self.conn_status.grid(
            row=1, column=0, columnspan=5, sticky="w", pady=(6, 0)
        )

        self.backup_status = ttk.Label(
            conn,
            text=(
                f"Local backups: {self.backup_dir}\n"
                f"Tested on PS5 firmware {TESTED_FIRMWARE} with "
                f"{TESTED_JAILBREAK}."
            ),
            style="Hint.TLabel",
            wraplength=900,
            justify="left",
        )
        self.backup_status.grid(
            row=2, column=0, columnspan=5, sticky="w", pady=(2, 0)
        )

        # Text --------------------------------------------------------------
        text_frame = ttk.LabelFrame(
            main, text="Warning text (English)", padding=(10, 8)
        )
        text_frame.grid(
            row=1, column=0, sticky="nsew", pady=(10, 0), padx=(0, 10)
        )
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(1, weight=1)

        body_wrap = ttk.Frame(text_frame)
        body_wrap.grid(row=1, column=0, sticky="nsew")
        body_wrap.columnconfigure(0, weight=1)
        body_wrap.rowconfigure(0, weight=1)
        self.body_text = tk.Text(
            body_wrap,
            height=8,
            wrap="word",
            undo=True,
            state="disabled",
            font=("Segoe UI", 11),
            padx=8,
            pady=6,
            relief="solid",
            borderwidth=1,
            highlightthickness=0,
        )
        self.body_text.grid(row=0, column=0, sticky="nsew")
        body_scroll = ttk.Scrollbar(
            body_wrap, orient="vertical", command=self.body_text.yview
        )
        body_scroll.grid(row=0, column=1, sticky="ns")
        self.body_text.configure(yscrollcommand=body_scroll.set)

        symbol_row = ttk.Frame(text_frame)
        symbol_row.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(symbol_row, text="Insert:").pack(side="left", padx=(0, 5))
        self.symbol_buttons: list[ttk.Button] = []
        for symbol in SYMBOLS:
            button = ttk.Button(
                symbol_row,
                text=symbol,
                width=3,
                state="disabled",
                command=lambda value=symbol: self._insert_symbol(value),
            )
            button.pack(side="left", padx=1)
            self.symbol_buttons.append(button)
        self.clear_btn = ttk.Button(
            symbol_row,
            text="Clear",
            state="disabled",
            command=self._clear_body,
        )
        self.clear_btn.pack(side="right")

        ttk.Label(
            text_frame,
            text=(
                "Click a symbol to insert it at the cursor. \u25b3 \u25cb \u00d7 \u25a1 and \u2b50 "
                "are confirmed on firmware 12.60. The cross is the "
                "multiplication sign (U+00D7); the \u2715 glyph (U+2715) is "
                "missing from the console font."
            ),
            style="Hint.TLabel",
            wraplength=600,
            justify="left",
        ).grid(row=3, column=0, sticky="w", pady=(5, 0))

        counts = ttk.Frame(text_frame)
        counts.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self.count_label = ttk.Label(
            counts, text="", font=("Segoe UI", 10, "bold")
        )
        self.count_label.pack(anchor="w")
        self.limit_label = ttk.Label(counts, text="", style="Hint.TLabel")
        self.limit_label.pack(anchor="w")
        self.limit_status = ttk.Label(
            counts, text="", font=("Segoe UI", 10, "bold")
        )
        self.limit_status.pack(anchor="w", pady=(2, 0))

        ttk.Label(
            text_frame,
            text=(
                "No character limit in the box. Apply is disabled when the "
                "encoded text exceeds the catalog's byte limit. The title "
                'stays "Health Warning"; all English region variants get '
                "this body."
            ),
            style="Hint.TLabel",
            wraplength=600,
            justify="left",
        ).grid(row=5, column=0, sticky="w", pady=(5, 0))

        # Preview -----------------------------------------------------------
        preview_frame = ttk.LabelFrame(
            main, text="Preview (approximate)", padding=(8, 8)
        )
        preview_frame.grid(row=1, column=1, sticky="nsew", pady=(10, 0))
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        self.preview = tk.Text(
            preview_frame,
            width=34,
            height=12,
            wrap="word",
            bg="#0a0a0c",
            fg="#f2f2f2",
            insertwidth=0,
            relief="flat",
            padx=14,
            pady=14,
            font=("Segoe UI", 11),
        )
        self.preview.grid(row=0, column=0, sticky="nsew")
        self.preview.tag_configure(
            "title", font=("Segoe UI", 15, "bold"), spacing3=12
        )
        self.preview.tag_configure(
            "body", font=("Segoe UI", 11), spacing1=2
        )
        self.preview.tag_configure(
            "empty", font=("Segoe UI", 10), foreground="#888888"
        )
        self.preview.configure(state="disabled")

        # Actions -----------------------------------------------------------
        actions = ttk.Frame(main)
        actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        actions.columnconfigure(0, weight=1)
        left = ttk.Frame(actions)
        left.grid(row=0, column=0, sticky="w")
        self.apply_btn = ttk.Button(
            left,
            text="Apply to console",
            state="disabled",
            command=self._apply_clicked,
        )
        self.apply_btn.pack(side="left")
        self.backups_btn = ttk.Button(
            left, text="Open backups folder", command=self._open_backups
        )
        self.backups_btn.pack(side="left", padx=(8, 0))

        right = ttk.Frame(actions)
        right.grid(row=0, column=1, sticky="e")
        self.progress_label = ttk.Label(right, text="", width=6)
        self.progress_label.pack(side="right")
        self.progress = ttk.Progressbar(
            right, mode="indeterminate", length=210, maximum=100
        )
        self.progress.pack(side="right", padx=(0, 8))

        ttk.Label(
            actions,
            text=(
                "Changes take effect after a full restart of the console "
                "(not Rest Mode). The upload replaces the live file only "
                "after SHA-256 verification."
            ),
            style="Hint.TLabel",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # Log ---------------------------------------------------------------
        log_frame = ttk.LabelFrame(main, text="Log", padding=(8, 8))
        log_frame.grid(
            row=3, column=0, columnspan=2, sticky="nsew", pady=(10, 0)
        )
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log = tk.Text(
            log_frame,
            height=7,
            wrap="word",
            state="disabled",
            font=("Consolas", 9),
            padx=6,
            pady=4,
            relief="solid",
            borderwidth=1,
        )
        self.log.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(
            log_frame, orient="vertical", command=self.log.yview
        )
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=log_scroll.set)
        self.log.tag_configure("info", foreground="#222222")
        self.log.tag_configure("ok", foreground=GREEN)
        self.log.tag_configure("warn", foreground=AMBER)
        self.log.tag_configure("error", foreground=RED)
        self.log.tag_configure("dim", foreground=GRAY)

    # -- text helpers -------------------------------------------------------

    def _body(self) -> str:
        return self.body_text.get("1.0", "end-1c")

    def _insert_symbol(self, symbol: str) -> None:
        self.body_text.insert("insert", symbol)
        self.body_text.focus_set()
        self._update_now()

    def _clear_body(self) -> None:
        self.body_text.delete("1.0", "end")
        self.body_text.focus_set()
        self._update_now()

    def _fits(self, body: str) -> bool:
        if self.session is None:
            return False
        if not body.strip():
            return False
        try:
            return serialized_len(body) <= self.session.rco.max_body
        except UnicodeEncodeError:
            return False

    def _update_now(self) -> None:
        self._last_body = None
        self._update_counts()
        self._update_preview()
        self._refresh_buttons()

    def _tick(self) -> None:
        try:
            body = self._body()
            if body != self._last_body:
                self._last_body = body
                self._update_counts()
                self._update_preview()
                self._refresh_buttons()
        except tk.TclError:
            return
        try:
            self.root.after(250, self._tick)
        except tk.TclError:
            pass

    def _update_counts(self) -> None:
        try:
            body = self._body()
        except tk.TclError:
            return

        if self.session is None:
            self.count_label.configure(
                text="Connect to calculate the byte limit."
            )
            self.limit_label.configure(text="")
            self.limit_status.configure(text="", foreground=GRAY)
            return

        try:
            utf8_len = len(body.encode("utf-8"))
            json_len = serialized_len(body)
        except UnicodeEncodeError:
            self.count_label.configure(text="Invalid Unicode in the text.")
            self.limit_label.configure(text="")
            self.limit_status.configure(
                text="Fix the invalid character before applying.",
                foreground=RED,
            )
            return

        extra = f" · {json_len} B serialized" if json_len != utf8_len else ""
        self.count_label.configure(
            text=f"Body: {len(body)} chars · {utf8_len} B UTF-8{extra}"
        )
        limit = self.session.rco.max_body
        headroom = limit - json_len
        self.limit_label.configure(text=f"Limit: {limit} bytes")
        if not body.strip():
            self.limit_status.configure(
                text="Enter some text to enable Apply.", foreground=GRAY
            )
        elif headroom >= 0:
            self.limit_status.configure(
                text=f"Fits — {headroom} B left", foreground=GREEN
            )
        else:
            self.limit_status.configure(
                text=f"Over limit by {-headroom} B — shorten the text.",
                foreground=RED,
            )

    def _update_preview(self) -> None:
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        if self.session is None:
            self.preview.insert("end", "Connect to preview", "empty")
        else:
            body = self._body()
            title = self.session.rco.title
            title_text = title if len(title) <= 500 else title[:500] + "…"
            body_text = body if len(body) <= 2500 else body[:2500] + "\n…"
            self.preview.insert("end", title_text, "title")
            self.preview.insert("end", "\n\n")
            self.preview.insert("end", body_text or "(no body)", "body")
        self.preview.configure(state="disabled")

    def _refresh_buttons(self) -> None:
        if self.busy:
            return
        connected = self.session is not None
        address_matches = connected and (
            self.host_var.get().strip(),
            self.port_var.get().strip(),
        ) == (self.connected_host, self.connected_port)
        fits = connected and self._fits(self._body())

        self.apply_btn.configure(
            state="normal" if address_matches and fits else "disabled"
        )
        self.connect_btn.configure(
            state="normal", text="Reconnect" if connected else "Connect"
        )
        self.body_text.configure(state="normal" if connected else "disabled")
        for button in self.symbol_buttons:
            button.configure(state="normal" if connected else "disabled")
        self.clear_btn.configure(
            state="normal" if connected else "disabled"
        )

    def _address_changed(self) -> None:
        if self.busy:
            return
        if self.session is not None:
            if (
                self.host_var.get().strip(),
                self.port_var.get().strip(),
            ) != (self.connected_host, self.connected_port):
                self.conn_status.configure(
                    text="Console address changed — click Reconnect to use it.",
                    foreground=AMBER,
                )
            elif self.connected_status:
                self.conn_status.configure(
                    text=self.connected_status, foreground=GREEN
                )
        self._refresh_buttons()

    # -- log / queue --------------------------------------------------------

    def _log(self, text: str, tag: str = "info") -> None:
        try:
            self.log.configure(state="normal")
            self.log.insert(
                "end", f"[{time.strftime('%H:%M:%S')}] {text}\n", tag
            )
            self.log.see("end")
            self.log.configure(state="disabled")
        except tk.TclError:
            pass

    def _service_event(self, message: str, percent: int | None) -> None:
        if message != self._last_service_message:
            self._last_service_message = message
            self.messages.put(("log", message, "info"))
        if percent is not None:
            self.messages.put(("progress", percent))

    def _poll_messages(self) -> None:
        try:
            while True:
                message = self.messages.get_nowait()
                kind = message[0]
                if kind == "log":
                    self._log(
                        message[1], message[2] if len(message) > 2 else "info"
                    )
                elif kind == "progress":
                    self._show_progress(int(message[1]))
                elif kind == "connected":
                    self._on_connected(message[1])
                elif kind == "connect_error":
                    self._on_connect_error(message[1], message[2], message[3])
                elif kind == "applied":
                    self._on_applied(message[1], message[2])
                elif kind == "error":
                    self._log(message[1], "error")
                    messagebox.showerror(APP_NAME, message[1])
                elif kind == "done":
                    self._set_busy(False)
        except queue.Empty:
            pass
        try:
            self.root.after(100, self._poll_messages)
        except tk.TclError:
            pass

    def _show_progress(self, percent: int) -> None:
        if str(self.progress.cget("mode")) != "determinate":
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)
        self.progress.configure(value=percent)
        self.progress_label.configure(text=f"{percent}%")

    def _on_connected(self, session: Session) -> None:
        self.session = session
        self.connected_host = session.host
        self.connected_port = str(session.port)
        self.loaded_body = session.rco.current_body
        self.connected_status = (
            "Connected — original backed up locally and on the console."
        )
        self.conn_status.configure(
            text=self.connected_status, foreground=GREEN
        )
        self.backup_status.configure(
            text=(
                f"Local backup: {session.backup.local_path}\n"
                f"Console backup: {session.backup.remote_path}"
            )
        )

        self.body_text.configure(state="normal")
        self.body_text.delete("1.0", "end")
        self.body_text.insert("1.0", self.loaded_body)
        self.body_text.configure(state="disabled")
        self._log(
            f"Connected. {len(session.rco.catalogs)} English catalog(s), "
            f"body limit {session.rco.max_body} B.",
            "ok",
        )
        logger.info(
            "Connected to %s:%s; local backup=%s; console backup=%s",
            session.host,
            session.port,
            session.backup.local_path,
            session.backup.remote_path,
        )
        self._update_now()

    def _on_connect_error(self, detail: str, host: str, port: str) -> None:
        self.conn_status.configure(
            text="Connection failed — " + detail.splitlines()[0],
            foreground=RED,
        )
        self._log(f"Connection failed: {detail}", "error")
        logger.error("Connection failed: %s", detail)
        messagebox.showerror(
            APP_NAME,
            f"Could not prepare the console:\n\n{detail}\n\n"
            f"Check that the console is on and its FTP server is running "
            f"on {host}:{port}.",
        )

    def _on_applied(self, result: ApplyResult, body: str) -> None:
        self.loaded_body = body
        self.connected_status = "Applied — restart the console to see changes."
        self.conn_status.configure(
            text=self.connected_status, foreground=GREEN
        )
        self._log(
            f"Applied successfully. {result.size:,} B, "
            f"sha256 {result.sha256[:16]}...",
            "ok",
        )
        logger.info(
            "Applied successfully: size=%s sha256=%s", result.size, result.sha256
        )
        messagebox.showinfo(APP_NAME, "Restart console to see changes!")

    # -- busy state ---------------------------------------------------------

    def _set_busy(self, busy: bool, label: str = "") -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        for widget in (
            self.host_entry,
            self.port_entry,
            self.connect_btn,
            self.backups_btn,
            self.body_text,
            self.clear_btn,
        ):
            widget.configure(state=state)
        for button in self.symbol_buttons:
            button.configure(state=state)

        if busy:
            self.apply_btn.configure(state="disabled")
            self.progress.stop()
            self.progress.configure(mode="indeterminate", value=0)
            self.progress.start(12)
            self.progress_label.configure(text=label or "Working...")
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)
            self.progress_label.configure(text="")
            self._refresh_buttons()

    # -- connect ------------------------------------------------------------

    def _connect_clicked(self) -> None:
        if self.busy:
            return
        host = self.host_var.get().strip()
        port_text = self.port_var.get().strip()
        if not host or not port_text:
            messagebox.showerror(
                APP_NAME, "Enter the console host and FTP port."
            )
            return
        try:
            port = int(port_text)
        except ValueError:
            messagebox.showerror(
                APP_NAME, "The FTP port must be a number."
            )
            return
        if not 1 <= port <= 65535:
            messagebox.showerror(
                APP_NAME, "The FTP port must be between 1 and 65535."
            )
            return
        if self.session is not None and self._body() != self.loaded_body:
            if not messagebox.askyesno(
                APP_NAME,
                "Reconnect and reload the console's current text?\n\n"
                "Unsaved text changes will be lost.",
            ):
                return

        self._set_busy(True, "Connecting...")
        self.conn_status.configure(
            text=f"Connecting to {host}:{port} ...", foreground=GRAY
        )
        self._last_service_message = ""
        logger.info("Connecting to %s:%s", host, port)

        def worker() -> None:
            try:
                session = create_session(
                    host, port, self.backup_dir, self._service_event
                )
                self.messages.put(("connected", session))
            except Exception as exc:
                self.messages.put(("connect_error", str(exc), host, str(port)))
            finally:
                self.messages.put(("done",))

        threading.Thread(target=worker, daemon=True).start()

    # -- apply --------------------------------------------------------------

    def _apply_clicked(self) -> None:
        if self.busy or self.session is None:
            return
        body = self._body()
        if not self._fits(body):
            return
        host = self.host_var.get().strip()
        port = self.port_var.get().strip()
        if (host, port) != (self.connected_host, self.connected_port):
            messagebox.showerror(
                APP_NAME,
                "The console address changed. Click Reconnect before applying.",
            )
            return

        session = self.session
        self._set_busy(True, "Applying...")
        self._last_service_message = ""
        logger.info(
            "Applying text: host=%s port=%s body_bytes=%s",
            session.host,
            session.port,
            serialized_len(body),
        )

        def worker() -> None:
            try:
                result = apply_text(session, body, self._service_event)
                self.messages.put(("applied", result, body))
            except Exception as exc:
                self.messages.put(
                    (
                        "error",
                        f"Apply failed: {exc}\n\n"
                        f"Check that the console is reachable and its FTP "
                        f"server is running on {session.host}:{session.port}.",
                    )
                )
            finally:
                self.messages.put(("done",))

        threading.Thread(target=worker, daemon=True).start()

    # -- menus / misc -------------------------------------------------------

    def _open_backups(self) -> None:
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            os.startfile(str(self.backup_dir))  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror(
                APP_NAME, f"Could not open the backups folder:\n{exc}"
            )

    def _open_log(self) -> None:
        path = get_log_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text(
                    "The log is empty. Start the editor and connect once.\n",
                    encoding="utf-8",
                )
            os.startfile(str(path))  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror(
                APP_NAME, f"Could not open the log file:\n{exc}"
            )

    def _show_how_it_works(self) -> None:
        messagebox.showinfo(
            "How it works",
            "Connect downloads the console's current "
            "Sce.PlayStation.PUI_UI3.rco and saves two backups:\n"
            "  - one in your Documents\\PS5 Health Warning Editor\\backups "
            "folder\n"
            "  - one on the console as "
            "/system_ex/vsh_asset/PUI_UI3_BACKUP_*.rco.bak\n\n"
            "The editor loads the current English warning body. Type a new "
            "one, or insert symbols. The byte limit is calculated from the "
            "catalogs in the live file.\n\n"
            "Apply rebuilds the RCO at exactly the same size, uploads it to "
            "a temporary name, downloads it back to verify SHA-256, and only "
            "then replaces the live file.\n\n"
            "Changes appear on the next full power-on, not Rest Mode. Only "
            'the English catalogs are changed; the title stays "Health '
            'Warning".',
        )

    def _show_restore_help(self) -> None:
        text = (
            "To restore the stock warning:\n\n"
            "1. Open File > Open backups folder.\n"
            "2. With an FTP client, upload a PUI_UI3_original_*.rco file "
            "over:\n"
            "   /system_ex/vsh_asset/Sce.PlayStation.PUI_UI3.rco\n\n"
            "   You can also use the console backup named "
            "PUI_UI3_BACKUP_*.rco.bak in the same folder. Rename it to "
            "Sce.PlayStation.PUI_UI3.rco when uploading.\n\n"
            "3. Fully power the console off and on.\n\n"
            "Open the backups folder now?"
        )
        if messagebox.askyesno("Restore stock warning", text):
            self._open_backups()

    def _show_about(self) -> None:
        messagebox.showinfo(
            f"About {APP_NAME}",
            f"{APP_NAME} {__version__}\n"
            f"{APP_DESCRIPTION}\n\n"
            f"Tested on PS5 firmware {TESTED_FIRMWARE} with "
            f"{TESTED_JAILBREAK}.\n\n"
            "Unofficial tool. Not affiliated with Sony Interactive "
            "Entertainment.\n\n"
            f"Backups folder:\n{self.backup_dir}\n\n"
            f"Log file:\n{get_log_path()}",
        )

    def _on_close(self) -> None:
        if self.busy:
            if not messagebox.askyesno(
                APP_NAME,
                "An operation is still running. Close anyway?\n\n"
                "An interrupted upload never replaces the live file, but a "
                "temporary file may be left on the console.",
            ):
                return
        if (
            self.session is not None
            and self._body() != self.loaded_body
            and not messagebox.askyesno(
                APP_NAME, "You have unsaved text changes. Close anyway?"
            )
        ):
            return

        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            port = DEFAULT_PORT
        geometry = None
        try:
            if self.root.state() == "normal":
                geometry = self.root.geometry()
        except tk.TclError:
            pass
        save_settings(
            Settings(
                host=self.host_var.get().strip(),
                port=port,
                geometry=geometry,
            ),
            self.settings_path,
        )
        self.root.destroy()
