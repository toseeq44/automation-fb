"""
Standalone Firestore admin GUI for the OneSoul Firebase MVP.

This version focuses on a cleaner dashboard-style admin surface:
- quick license creation/update
- readable license dashboard
- client activity view
- direct creator snapshot viewer from the activity tab
"""
from __future__ import annotations

import json
import random
import string
import tkinter as tk
from datetime import datetime, timezone
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional

from modules.license.firebase_license_manager import FirestoreLicenseManager


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


class FirebaseAdminService:
    def __init__(self) -> None:
        self.manager = FirestoreLicenseManager(app_version="1.0.0")
        self.manager._ensure_authenticated()

    def project_id(self) -> str:
        return _safe_text(self.manager._firebase_config.get("project_id"))

    def iso_now(self) -> str:
        return self.manager._iso_now()

    def normalize_expiry(self, value: str) -> str:
        raw = _safe_text(value)
        if not raw:
            raise ValueError("Expiry is required.")

        if "T" in raw:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            parsed = datetime.fromisoformat(f"{raw}T00:00:00+00:00")

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.astimezone(timezone.utc)
        return parsed.isoformat()

    def generate_license_key(self, prefix: str = "ONESOUL") -> str:
        alphabet = string.ascii_uppercase + string.digits
        suffix = "".join(random.choice(alphabet) for _ in range(8))
        return f"{prefix}-{suffix}"

    def create_or_update_license(
        self,
        *,
        license_key: str,
        customer_email: str,
        customer_name: str,
        hardware_id: str,
        plan: str,
        expiry: str,
        notes: str,
        active: bool,
    ) -> Dict[str, Any]:
        key = _safe_text(license_key)
        if not key:
            raise ValueError("License key is required.")

        existing = self.get_license(key) or {}
        payload = {
            "active": bool(active),
            "plan": _safe_text(plan or "basic").lower(),
            "expiryAt": self.normalize_expiry(expiry),
            "boundHardwareId": _safe_text(hardware_id) or _safe_text(existing.get("boundHardwareId")),
            "boundDeviceName": _safe_text(existing.get("boundDeviceName")),
            "lastSeenAt": _safe_text(existing.get("lastSeenAt")),
            "lastInstallationId": _safe_text(existing.get("lastInstallationId")),
            "notes": _safe_text(notes),
            "customerEmail": _safe_text(customer_email),
            "customerName": _safe_text(customer_name),
            "createdAt": _safe_text(existing.get("createdAt")) or self.iso_now(),
            "updatedAt": self.iso_now(),
        }
        self.manager._patch_document("licenses", key, payload)
        return payload

    def get_license(self, license_key: str) -> Optional[Dict[str, Any]]:
        return self.manager._get_document("licenses", _safe_text(license_key))

    def unbind_license(self, license_key: str) -> Dict[str, Any]:
        key = _safe_text(license_key)
        if not key:
            raise ValueError("License key is required.")
        payload = {
            "boundHardwareId": "",
            "boundDeviceName": "",
            "lastInstallationId": "",
            "lastSeenAt": self.iso_now(),
            "updatedAt": self.iso_now(),
        }
        self.manager._patch_document("licenses", key, payload)
        return payload

    def _list_collection(self, collection: str) -> List[Dict[str, Any]]:
        payload = self.manager._firestore_request(
            "GET",
            self.manager._collection_path(collection),
            allow_not_found=True,
        ) or {}
        documents = payload.get("documents", []) or []
        return [self.manager._document_to_python(item) for item in documents]

    def list_installations(self) -> List[Dict[str, Any]]:
        docs = self._list_collection("installations")
        docs.sort(key=lambda item: _safe_text(item.get("lastSeenAt")), reverse=True)
        return docs

    def list_licenses(self) -> List[Dict[str, Any]]:
        docs = self._list_collection("licenses")
        docs.sort(key=lambda item: _safe_text(item.get("_document_name")), reverse=False)
        return docs

    def get_dashboard_stats(self) -> Dict[str, int]:
        docs = self.list_licenses()
        now = datetime.now(timezone.utc)
        total = len(docs)
        active = 0
        pending = 0
        alerts = 0
        for doc in docs:
            is_active = bool(doc.get("active", False))
            expiry = self.manager._parse_iso_datetime(doc.get("expiryAt"))
            is_expired = (expiry is None) or (expiry <= now)
            is_bound = bool(_safe_text(doc.get("boundHardwareId")))
            if is_active and not is_expired and is_bound:
                active += 1
            if is_active and not is_expired and not is_bound:
                pending += 1
            if (not is_active) or is_expired:
                alerts += 1
        return {
            "total_users": total,
            "active_licenses": active,
            "pending": pending,
            "alerts": alerts,
        }

    def license_status_label(self, license_doc: Dict[str, Any]) -> str:
        is_active = bool(license_doc.get("active", False))
        expiry = self.manager._parse_iso_datetime(license_doc.get("expiryAt"))
        if not is_active:
            return "SUSPENDED"
        if expiry is None or expiry <= datetime.now(timezone.utc):
            return "EXPIRED"
        if _safe_text(license_doc.get("boundHardwareId")):
            return "ACTIVE"
        return "PENDING"

    def queue_creator_fetch(self, installation_id: str) -> None:
        installation_id = _safe_text(installation_id)
        if not installation_id:
            raise ValueError("Installation ID is required.")
        self.manager._patch_document(
            "installations",
            installation_id,
            {
                "pendingTask": "collect_creator_urls",
                "lastTrackingStatus": "queued",
                "lastTrackingError": "",
                "lastSeenAt": self.iso_now(),
            },
        )

    def get_creator_snapshot(self, license_key: str, installation_id: str) -> Optional[Dict[str, Any]]:
        preferred_id = self.manager._creator_snapshot_doc_id(_safe_text(license_key), _safe_text(installation_id))
        preferred = self.manager._get_document("creator_snapshots", preferred_id)
        if preferred:
            return preferred
        fallback = self.manager._get_document("creator_snapshots", _safe_text(installation_id))
        if fallback:
            return fallback
        return None


class FirebaseAdminGUI:
    BG = "#eef2f7"
    CARD = "#ffffff"
    PANEL = "#f7f9fc"
    INK = "#172033"
    MUTED = "#6d778c"
    ACCENT = "#1aa3ff"
    ACCENT_SOFT = "#e8f4ff"
    BORDER = "#d8e0ec"
    SUCCESS = "#34a853"
    WARNING = "#f4b400"
    DANGER = "#ea4335"
    DARK_PANEL = "#1b2130"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("OneSoul Firebase Admin")
        self.root.geometry("1560x900")
        self.root.minsize(1320, 760)
        self.root.configure(bg=self.BG)

        self.service = FirebaseAdminService()
        self.status_var = tk.StringVar(value="Ready")
        self.activity_status_var = tk.StringVar(value="Ready")

        self.total_users_var = tk.StringVar(value="0")
        self.active_licenses_var = tk.StringVar(value="0")
        self.pending_var = tk.StringVar(value="0")
        self.alerts_var = tk.StringVar(value="0")

        self._build_styles()
        self._build_ui()
        self.refresh_all()

    def _build_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("App.TFrame", background=self.BG)
        style.configure("Card.TFrame", background=self.CARD)
        style.configure("Panel.TFrame", background=self.PANEL)
        style.configure("TLabel", background=self.BG, foreground=self.INK, font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=self.CARD, foreground=self.INK, font=("Segoe UI", 10))
        style.configure("Muted.Card.TLabel", background=self.CARD, foreground=self.MUTED, font=("Segoe UI", 9))
        style.configure("Panel.TLabel", background=self.PANEL, foreground=self.INK, font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=self.BG, foreground=self.INK, font=("Segoe UI", 20, "bold"))
        style.configure("SubHeader.TLabel", background=self.BG, foreground=self.ACCENT, font=("Segoe UI", 10, "bold"))
        style.configure("MetricValue.TLabel", background=self.CARD, foreground=self.INK, font=("Segoe UI", 18, "bold"))
        style.configure("MetricLabel.TLabel", background=self.CARD, foreground=self.MUTED, font=("Segoe UI", 9, "bold"))

        style.configure(
            "TNotebook",
            background=self.BG,
            borderwidth=0,
            tabmargins=(0, 0, 0, 0),
        )
        style.configure(
            "TNotebook.Tab",
            background="#dfe5ef",
            foreground=self.INK,
            padding=(18, 10),
            font=("Segoe UI", 10, "bold"),
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", self.ACCENT_SOFT)],
            foreground=[("selected", self.ACCENT)],
        )

        style.configure(
            "TEntry",
            fieldbackground=self.CARD,
            foreground=self.INK,
            insertcolor=self.INK,
            bordercolor=self.BORDER,
            lightcolor=self.BORDER,
            darkcolor=self.BORDER,
            padding=8,
        )
        style.configure(
            "TCombobox",
            fieldbackground=self.CARD,
            foreground=self.INK,
            bordercolor=self.BORDER,
            lightcolor=self.BORDER,
            darkcolor=self.BORDER,
            padding=6,
        )

        style.configure(
            "Accent.TButton",
            background=self.ACCENT,
            foreground="white",
            borderwidth=0,
            focusthickness=0,
            padding=(16, 9),
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Accent.TButton", background=[("active", "#078ae0")])

        style.configure(
            "Soft.TButton",
            background=self.ACCENT_SOFT,
            foreground=self.ACCENT,
            borderwidth=0,
            focusthickness=0,
            padding=(14, 9),
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Soft.TButton", background=[("active", "#d8ecff")])

        style.configure(
            "Ghost.TButton",
            background=self.CARD,
            foreground=self.INK,
            bordercolor=self.BORDER,
            lightcolor=self.BORDER,
            darkcolor=self.BORDER,
            padding=(14, 9),
            font=("Segoe UI", 10),
        )
        style.map("Ghost.TButton", background=[("active", "#f2f5fa")])

        style.configure(
            "Treeview",
            background=self.CARD,
            foreground=self.INK,
            fieldbackground=self.CARD,
            bordercolor=self.BORDER,
            rowheight=34,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background="#f3f6fb",
            foreground=self.INK,
            bordercolor=self.BORDER,
            font=("Segoe UI", 9, "bold"),
            padding=8,
        )

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, style="App.TFrame", padding=22)
        main.pack(fill=tk.BOTH, expand=True)

        self._build_header(main)
        self._build_metrics(main)

        notebook = ttk.Notebook(main)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(14, 0))

        self.licenses_tab = ttk.Frame(notebook, style="App.TFrame", padding=2)
        self.activity_tab = ttk.Frame(notebook, style="App.TFrame", padding=2)
        notebook.add(self.licenses_tab, text="Create / Update License")
        notebook.add(self.activity_tab, text="Client Activity")

        self._build_licenses_tab()
        self._build_activity_tab()

    def _build_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, style="App.TFrame")
        header.pack(fill=tk.X)

        left = ttk.Frame(header, style="App.TFrame")
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(left, text="OneSoul", style="Header.TLabel").pack(side=tk.LEFT)
        accent = ttk.Label(left, text="Admin", style="Header.TLabel", foreground=self.ACCENT)
        accent.pack(side=tk.LEFT)

        project_badge = tk.Label(
            header,
            text=f"Firebase Connected  •  {self.service.project_id()}",
            bg=self.ACCENT_SOFT,
            fg=self.ACCENT,
            font=("Segoe UI", 9, "bold"),
            padx=14,
            pady=6,
        )
        project_badge.pack(side=tk.RIGHT)

    def _build_metrics(self, parent: ttk.Frame) -> None:
        wrap = ttk.Frame(parent, style="App.TFrame")
        wrap.pack(fill=tk.X, pady=(18, 0))

        cards = [
            ("TOTAL USERS", self.total_users_var),
            ("ACTIVE LICENSES", self.active_licenses_var),
            ("PENDING", self.pending_var),
            ("ALERTS", self.alerts_var),
        ]
        for index, (label, var) in enumerate(cards):
            card = ttk.Frame(wrap, style="Card.TFrame", padding=14)
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 10, 0))
            ttk.Label(card, text=label, style="MetricLabel.TLabel").pack(anchor="w")
            ttk.Label(card, textvariable=var, style="MetricValue.TLabel").pack(anchor="w", pady=(8, 0))
            wrap.columnconfigure(index, weight=1)

    def _build_licenses_tab(self) -> None:
        grid = ttk.Frame(self.licenses_tab, style="App.TFrame")
        grid.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(grid, style="Card.TFrame", padding=18)
        right = ttk.Frame(grid, style="Card.TFrame", padding=18)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right.grid(row=0, column=1, sticky="nsew")
        grid.columnconfigure(0, weight=3)
        grid.columnconfigure(1, weight=5)
        grid.rowconfigure(0, weight=1)

        self._build_form_panel(left)
        self._build_license_table(right)

    def _build_form_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="License Editor", style="Card.TLabel", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(parent, text="Create a new client or update an existing one.", style="Muted.Card.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(2, 18)
        )

        self.license_key_var = tk.StringVar(value=self.service.generate_license_key())
        self.customer_email_var = tk.StringVar()
        self.customer_name_var = tk.StringVar()
        self.hardware_id_var = tk.StringVar()
        self.plan_var = tk.StringVar(value="basic")
        self.expiry_var = tk.StringVar(value="2026-12-31")
        self.notes_var = tk.StringVar()
        self.active_var = tk.BooleanVar(value=True)

        self._field(parent, "LICENSE KEY", self.license_key_var, 2, hint="Leave blank for auto-generate, or click Auto Generate.")
        ttk.Button(parent, text="Auto Generate", style="Soft.TButton", command=self._generate_license_key).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=(0, 14)
        )

        self._field(parent, "CUSTOMER GMAIL", self.customer_email_var, 5)
        self._field(parent, "CUSTOMER NAME", self.customer_name_var, 8)
        self._field(parent, "HARDWARE ID", self.hardware_id_var, 11, hint="Blank = auto-bind on first activation.")

        ttk.Label(parent, text="PLAN", style="Muted.Card.TLabel").grid(row=14, column=0, sticky="w", pady=(2, 6))
        plan_combo = ttk.Combobox(parent, textvariable=self.plan_var, values=["basic", "pro"], state="readonly")
        plan_combo.grid(row=15, column=0, columnspan=2, sticky="ew", pady=(0, 14))

        self._field(parent, "EXPIRY DATE", self.expiry_var, 16)
        self._field(parent, "NOTES", self.notes_var, 19, hint="Optional internal notes.")

        active_row = ttk.Frame(parent, style="Card.TFrame")
        active_row.grid(row=22, column=0, columnspan=2, sticky="w", pady=(4, 18))
        ttk.Checkbutton(active_row, text="Active License", variable=self.active_var).pack(side=tk.LEFT)

        actions = ttk.Frame(parent, style="Card.TFrame")
        actions.grid(row=23, column=0, columnspan=2, sticky="ew")
        ttk.Button(actions, text="Create / Update", style="Accent.TButton", command=self._save_license).pack(side=tk.LEFT)
        ttk.Button(actions, text="Load Existing", style="Ghost.TButton", command=self._load_license).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Unbind Device", style="Ghost.TButton", command=self._unbind_license).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Copy Key", style="Ghost.TButton", command=self._copy_key).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Clear Form", style="Ghost.TButton", command=self._clear_form).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(parent, textvariable=self.status_var, style="SubHeader.TLabel").grid(
            row=24, column=0, columnspan=2, sticky="w", pady=(18, 8)
        )
        ttk.Label(
            parent,
            text=(
                "Tips:\n"
                "• Hardware ID blank chhor do to first activation par auto-bind ho jayega.\n"
                "• Hardware ID fill karo to pehle se us device ke liye reserve ho jayegi.\n"
                "• Gmail + Name Firestore mein admin tracking ke liye save hote hain."
            ),
            style="Muted.Card.TLabel",
            justify="left",
        ).grid(row=25, column=0, columnspan=2, sticky="w", pady=(0, 4))

        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)

    def _field(self, parent: ttk.Frame, label: str, variable: tk.StringVar, row: int, hint: str = "") -> None:
        ttk.Label(parent, text=label, style="Muted.Card.TLabel").grid(row=row, column=0, columnspan=2, sticky="w", pady=(2, 6))
        ttk.Entry(parent, textvariable=variable).grid(row=row + 1, column=0, columnspan=2, sticky="ew")
        if hint:
            ttk.Label(parent, text=hint, style="Muted.Card.TLabel").grid(row=row + 2, column=0, columnspan=2, sticky="w", pady=(6, 12))
        else:
            parent.grid_rowconfigure(row + 2, minsize=10)

    def _build_license_table(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent, style="Card.TFrame")
        top.pack(fill=tk.X)
        ttk.Label(parent, text="License Dashboard", style="Card.TLabel", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(parent, text="Readable license list for quick admin actions.", style="Muted.Card.TLabel").pack(anchor="w", pady=(2, 12))

        actions = ttk.Frame(parent, style="Card.TFrame")
        actions.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(actions, text="Refresh Data", style="Soft.TButton", command=self.refresh_all).pack(side=tk.RIGHT)
        ttk.Button(actions, text="Load Selected", style="Ghost.TButton", command=self._load_selected_license_row).pack(side=tk.LEFT)
        ttk.Button(actions, text="Copy Selected Key", style="Ghost.TButton", command=self._copy_selected_license_key).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Unbind Selected", style="Ghost.TButton", command=self._unbind_selected_license_row).pack(side=tk.LEFT, padx=(8, 0))

        columns = ("licenseKey", "holder", "hwid", "status", "plan", "expiry")
        self.licenses_tree = ttk.Treeview(parent, columns=columns, show="headings", height=20)
        widths = {
            "licenseKey": 180,
            "holder": 190,
            "hwid": 270,
            "status": 100,
            "plan": 70,
            "expiry": 180,
        }
        for column in columns:
            title = {
                "licenseKey": "LICENSE KEY",
                "holder": "HOLDER",
                "hwid": "HWID / SYSTEM",
                "status": "STATUS",
                "plan": "PLAN",
                "expiry": "EXPIRY",
            }[column]
            self.licenses_tree.heading(column, text=title)
            self.licenses_tree.column(column, width=widths[column], anchor="w")

        self.licenses_tree.tag_configure("ACTIVE", background="#edf8ef")
        self.licenses_tree.tag_configure("PENDING", background="#fff8e8")
        self.licenses_tree.tag_configure("EXPIRED", background="#fff0ef")
        self.licenses_tree.tag_configure("SUSPENDED", background="#fff0ef")

        y_scroll = ttk.Scrollbar(parent, orient="vertical", command=self.licenses_tree.yview)
        self.licenses_tree.configure(yscrollcommand=y_scroll.set)
        self.licenses_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_activity_tab(self) -> None:
        shell = ttk.Frame(self.activity_tab, style="Card.TFrame", padding=18)
        shell.pack(fill=tk.BOTH, expand=True)

        ttk.Label(shell, text="Client Activity", style="Card.TLabel", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(shell, text="Queue tasks, inspect live clients, and view fetched creator URLs.", style="Muted.Card.TLabel").pack(anchor="w", pady=(2, 12))

        controls = ttk.Frame(shell, style="Card.TFrame")
        controls.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(controls, text="Refresh Now", style="Ghost.TButton", command=self.refresh_installations).pack(side=tk.LEFT)
        ttk.Button(controls, text="Queue Creator Fetch", style="Soft.TButton", command=self._queue_creator_fetch).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(controls, text="View Snapshot", style="Ghost.TButton", command=self._view_selected_snapshot).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(controls, text="Load License", style="Ghost.TButton", command=self._load_selected_installation_license).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(controls, textvariable=self.activity_status_var, style="SubHeader.TLabel").pack(side=tk.LEFT, padx=(14, 0))

        columns = (
            "installationId",
            "licenseKey",
            "holder",
            "deviceName",
            "status",
            "lastSeenAt",
            "lastTrackingStatus",
            "pendingTask",
            "snapshotId",
        )
        self.installations_tree = ttk.Treeview(shell, columns=columns, show="headings", height=24)
        widths = {
            "installationId": 250,
            "licenseKey": 160,
            "holder": 160,
            "deviceName": 220,
            "status": 95,
            "lastSeenAt": 190,
            "lastTrackingStatus": 140,
            "pendingTask": 170,
            "snapshotId": 170,
        }
        headings = {
            "installationId": "INSTALLATION ID",
            "licenseKey": "LICENSE KEY",
            "holder": "HOLDER",
            "deviceName": "DEVICE",
            "status": "STATUS",
            "lastSeenAt": "LAST SEEN",
            "lastTrackingStatus": "TRACKING",
            "pendingTask": "PENDING TASK",
            "snapshotId": "SNAPSHOT DOC",
        }
        for column in columns:
            self.installations_tree.heading(column, text=headings[column])
            self.installations_tree.column(column, width=widths[column], anchor="w")

        self.installations_tree.tag_configure("running", background="#edf8ef")
        self.installations_tree.tag_configure("startup", background="#eef5ff")
        self.installations_tree.tag_configure("shutdown", background="#f8f1f1")

        y_scroll = ttk.Scrollbar(shell, orient="vertical", command=self.installations_tree.yview)
        x_scroll = ttk.Scrollbar(shell, orient="horizontal", command=self.installations_tree.xview)
        self.installations_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self.installations_tree.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

    def refresh_all(self) -> None:
        self.refresh_dashboard_metrics()
        self.refresh_license_table()
        self.refresh_installations()

    def refresh_dashboard_metrics(self) -> None:
        stats = self.service.get_dashboard_stats()
        self.total_users_var.set(str(stats["total_users"]))
        self.active_licenses_var.set(str(stats["active_licenses"]))
        self.pending_var.set(str(stats["pending"]))
        self.alerts_var.set(str(stats["alerts"]))

    def refresh_license_table(self) -> None:
        docs = self.service.list_licenses()
        for item in self.licenses_tree.get_children():
            self.licenses_tree.delete(item)

        for doc in docs:
            document_name = _safe_text(doc.get("_document_name"))
            license_key = document_name.rsplit("/", 1)[-1] if document_name else ""
            holder = _safe_text(doc.get("customerName")) or _safe_text(doc.get("customerEmail")) or "-"
            hwid = _safe_text(doc.get("boundHardwareId")) or "Auto-bind on first activation"
            status = self.service.license_status_label(doc)
            values = (
                license_key,
                holder,
                hwid,
                status,
                _safe_text(doc.get("plan")),
                _safe_text(doc.get("expiryAt")),
            )
            self.licenses_tree.insert("", tk.END, values=values, tags=(status,))

    def refresh_installations(self) -> None:
        license_map = {}
        for license_doc in self.service.list_licenses():
            name = _safe_text(license_doc.get("_document_name"))
            key = name.rsplit("/", 1)[-1] if name else ""
            if key:
                license_map[key] = license_doc

        docs = self.service.list_installations()
        for item in self.installations_tree.get_children():
            self.installations_tree.delete(item)

        for doc in docs:
            document_name = _safe_text(doc.get("_document_name"))
            installation_id = document_name.rsplit("/", 1)[-1] if document_name else ""
            license_key = _safe_text(doc.get("licenseKey"))
            license_doc = license_map.get(license_key, {})
            holder = _safe_text(license_doc.get("customerName")) or _safe_text(license_doc.get("customerEmail")) or "-"
            snapshot_id = _safe_text(doc.get("creatorSnapshotId")) or self.service.manager._creator_snapshot_doc_id(license_key, installation_id)
            status = _safe_text(doc.get("status")).lower() or "running"
            values = (
                installation_id,
                license_key,
                holder,
                _safe_text(doc.get("deviceName")),
                _safe_text(doc.get("status")),
                _safe_text(doc.get("lastSeenAt")),
                _safe_text(doc.get("lastTrackingStatus")),
                _safe_text(doc.get("pendingTask")),
                snapshot_id,
            )
            self.installations_tree.insert("", tk.END, values=values, tags=(status,))

        self.activity_status_var.set(f"Installations loaded: {len(docs)}")

    def _selected_license_key(self) -> str:
        selected = self.licenses_tree.selection()
        if not selected:
            return ""
        values = self.licenses_tree.item(selected[0], "values") or ()
        return _safe_text(values[0] if values else "")

    def _selected_installation_payload(self) -> Dict[str, str]:
        selected = self.installations_tree.selection()
        if not selected:
            return {}
        values = self.installations_tree.item(selected[0], "values") or ()
        if not values:
            return {}
        return {
            "installation_id": _safe_text(values[0]),
            "license_key": _safe_text(values[1]),
            "holder": _safe_text(values[2]),
            "device_name": _safe_text(values[3]),
            "snapshot_id": _safe_text(values[8]) if len(values) > 8 else "",
        }

    def _generate_license_key(self) -> None:
        self.license_key_var.set(self.service.generate_license_key())
        self.status_var.set("Generated a fresh license key.")

    def _copy_key(self) -> None:
        value = _safe_text(self.license_key_var.get())
        if not value:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.status_var.set("License key copied to clipboard.")

    def _clear_form(self) -> None:
        self.license_key_var.set(self.service.generate_license_key())
        self.customer_email_var.set("")
        self.customer_name_var.set("")
        self.hardware_id_var.set("")
        self.plan_var.set("basic")
        self.expiry_var.set("2026-12-31")
        self.notes_var.set("")
        self.active_var.set(True)
        self.status_var.set("Form cleared.")

    def _save_license(self) -> None:
        try:
            self.service.create_or_update_license(
                license_key=self.license_key_var.get(),
                customer_email=self.customer_email_var.get(),
                customer_name=self.customer_name_var.get(),
                hardware_id=self.hardware_id_var.get(),
                plan=self.plan_var.get(),
                expiry=self.expiry_var.get(),
                notes=self.notes_var.get(),
                active=self.active_var.get(),
            )
            key = _safe_text(self.license_key_var.get())
            self.status_var.set(f"Saved license: {key}")
            self.refresh_all()
        except Exception as exc:
            self.status_var.set(f"Error: {exc}")
            messagebox.showerror("Save Error", str(exc))

    def _load_license(self, key_override: Optional[str] = None) -> None:
        try:
            key = _safe_text(key_override or self.license_key_var.get())
            if not key:
                raise ValueError("License key is required.")
            payload = self.service.get_license(key)
            if not payload:
                raise ValueError("License not found.")

            self.license_key_var.set(key)
            self.customer_email_var.set(_safe_text(payload.get("customerEmail")))
            self.customer_name_var.set(_safe_text(payload.get("customerName")))
            self.hardware_id_var.set(_safe_text(payload.get("boundHardwareId")))
            self.plan_var.set(_safe_text(payload.get("plan") or "basic"))
            self.expiry_var.set(_safe_text(payload.get("expiryAt")))
            self.notes_var.set(_safe_text(payload.get("notes")))
            self.active_var.set(bool(payload.get("active", False)))
            self.status_var.set(f"Loaded license: {key}")
        except Exception as exc:
            self.status_var.set(f"Error: {exc}")
            messagebox.showerror("Load Error", str(exc))

    def _unbind_license(self, key_override: Optional[str] = None) -> None:
        try:
            key = _safe_text(key_override or self.license_key_var.get())
            if not key:
                raise ValueError("License key is required.")
            self.service.unbind_license(key)
            self.hardware_id_var.set("")
            self.status_var.set(f"Unbound license: {key}")
            self.refresh_all()
        except Exception as exc:
            self.status_var.set(f"Error: {exc}")
            messagebox.showerror("Unbind Error", str(exc))

    def _load_selected_license_row(self) -> None:
        key = self._selected_license_key()
        if not key:
            messagebox.showwarning("Select License", "Please select a license row first.")
            return
        self._load_license(key)

    def _copy_selected_license_key(self) -> None:
        key = self._selected_license_key()
        if not key:
            messagebox.showwarning("Select License", "Please select a license row first.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(key)
        self.status_var.set(f"Copied selected key: {key}")

    def _unbind_selected_license_row(self) -> None:
        key = self._selected_license_key()
        if not key:
            messagebox.showwarning("Select License", "Please select a license row first.")
            return
        self._unbind_license(key)

    def _queue_creator_fetch(self) -> None:
        try:
            selected = self._selected_installation_payload()
            installation_id = _safe_text(selected.get("installation_id"))
            if not installation_id:
                raise ValueError("Select an installation row first.")
            self.service.queue_creator_fetch(installation_id)
            self.activity_status_var.set(f"Creator fetch queued for {installation_id}")
            self.refresh_installations()
        except Exception as exc:
            self.activity_status_var.set(f"Queue failed: {exc}")
            messagebox.showerror("Queue Error", str(exc))

    def _load_selected_installation_license(self) -> None:
        selected = self._selected_installation_payload()
        key = _safe_text(selected.get("license_key"))
        if not key:
            messagebox.showwarning("Select Client", "Please select an installation row first.")
            return
        self._load_license(key)

    def _view_selected_snapshot(self) -> None:
        selected = self._selected_installation_payload()
        installation_id = _safe_text(selected.get("installation_id"))
        license_key = _safe_text(selected.get("license_key"))
        if not installation_id or not license_key:
            messagebox.showwarning("Select Client", "Please select an installation row first.")
            return

        snapshot = self.service.get_creator_snapshot(license_key, installation_id)
        if not snapshot:
            messagebox.showwarning("No Snapshot", "No creator snapshot exists yet for this client.")
            return

        viewer = tk.Toplevel(self.root)
        viewer.title(f"Creator Snapshot • {license_key}")
        viewer.geometry("1100x720")
        viewer.configure(bg=self.BG)

        outer = ttk.Frame(viewer, style="App.TFrame", padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, text=f"Creator Snapshot • {license_key}", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text=f"Installation: {installation_id}   •   Snapshot Doc: {_safe_text(snapshot.get('snapshotId')) or license_key}",
            style="SubHeader.TLabel",
        ).pack(anchor="w", pady=(4, 10))

        top = ttk.Frame(outer, style="Card.TFrame", padding=12)
        top.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(top, text=f"Generated At: {_safe_text(snapshot.get('generatedAt'))}", style="Card.TLabel").pack(anchor="w")
        ttk.Label(top, text=f"Creator Count: {_safe_text(snapshot.get('creatorCount'))}", style="Muted.Card.TLabel").pack(anchor="w", pady=(4, 0))

        payload = snapshot.get("payload", {}) or {}
        creators = payload.get("creators", []) or []

        columns = ("folder", "platform", "url", "target", "videos")
        tree = ttk.Treeview(outer, columns=columns, show="headings", height=16)
        widths = {
            "folder": 220,
            "platform": 110,
            "url": 480,
            "target": 90,
            "videos": 90,
        }
        headers = {
            "folder": "FOLDER",
            "platform": "PLATFORM",
            "url": "CREATOR URL",
            "target": "TARGET",
            "videos": "N_VIDEOS",
        }
        for col in columns:
            tree.heading(col, text=headers[col])
            tree.column(col, width=widths[col], anchor="w")

        for creator in creators:
            tree.insert(
                "",
                tk.END,
                values=(
                    _safe_text(creator.get("folder_name")),
                    _safe_text(creator.get("platform")),
                    _safe_text(creator.get("creator_url")),
                    _safe_text(creator.get("uploading_target")),
                    _safe_text(creator.get("n_videos")),
                ),
            )

        tree.pack(fill=tk.BOTH, expand=True)

        raw_box = tk.Text(
            outer,
            height=10,
            wrap="none",
            bg="#0f172a",
            fg="#dbe6ff",
            insertbackground="#dbe6ff",
            relief="flat",
            font=("Consolas", 10),
        )
        raw_box.insert("1.0", json.dumps(snapshot, indent=2, ensure_ascii=False))
        raw_box.configure(state="disabled")
        raw_box.pack(fill=tk.BOTH, expand=True, pady=(10, 0))


def main() -> None:
    root = tk.Tk()
    FirebaseAdminGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
