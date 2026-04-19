"""
OneSoul License Server
Flask application for managing license activation, validation, and client presence.
"""
import os
import threading
import tkinter as tk
import socket
from datetime import datetime, timezone
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.parse import urlparse

import requests
from flask import Flask, request
from flask_limiter import Limiter
from sqlalchemy import inspect, text

from models import ClientInstallation, db
from presence import ONLINE_WINDOW_SECONDS, RECENT_WINDOW_SECONDS, presence_state_label
from request_meta import extract_client_public_ip
from routes import api


def create_app():
    """Create and configure Flask application."""
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///licenses.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    app.config["JSON_SORT_KEYS"] = False

    db.init_app(app)

    limiter = Limiter(
        app=app,
        key_func=lambda: extract_client_public_ip(request),
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://",
    )
    limiter.limit("10 per minute")(api)

    app.register_blueprint(api, url_prefix="/api")

    with app.app_context():
        db.create_all()
        _ensure_schema()
        print("Database tables created successfully")

    @app.route("/")
    def index():
        return {
            "service": "OneSoul License Server",
            "version": "1.0.0",
            "status": "running",
            "endpoints": {
                "health": "/api/health",
                "activate": "/api/license/activate",
                "validate": "/api/license/validate",
                "deactivate": "/api/license/deactivate",
                "heartbeat": "/api/license/heartbeat",
                "status": "/api/license/status",
                "admin_generate": "/api/admin/generate",
            },
        }

    return app


def _ensure_schema() -> None:
    """Apply tiny compatibility migrations for existing SQLite installs."""
    try:
        inspector = inspect(db.engine)
        if "client_installations" not in inspector.get_table_names():
            return
        columns = {col["name"] for col in inspector.get_columns("client_installations")}
        wanted_columns = {
            "last_lan_ip": "ALTER TABLE client_installations ADD COLUMN last_lan_ip VARCHAR(50)",
            "pending_task": "ALTER TABLE client_installations ADD COLUMN pending_task VARCHAR(64)",
            "pending_task_id": "ALTER TABLE client_installations ADD COLUMN pending_task_id VARCHAR(64)",
            "pending_task_created_at": "ALTER TABLE client_installations ADD COLUMN pending_task_created_at DATETIME",
            "active_task_id": "ALTER TABLE client_installations ADD COLUMN active_task_id VARCHAR(64)",
            "last_tracking_status": "ALTER TABLE client_installations ADD COLUMN last_tracking_status VARCHAR(64)",
            "last_tracking_error": "ALTER TABLE client_installations ADD COLUMN last_tracking_error TEXT",
            "last_links_file": "ALTER TABLE client_installations ADD COLUMN last_links_file VARCHAR(512)",
            "last_links_count": "ALTER TABLE client_installations ADD COLUMN last_links_count INTEGER",
            "last_links_updated_at": "ALTER TABLE client_installations ADD COLUMN last_links_updated_at DATETIME",
        }
        with db.engine.begin() as conn:
            for column_name, ddl in wanted_columns.items():
                if column_name not in columns:
                    conn.execute(text(ddl))
    except Exception as exc:
        print(f"Schema ensure warning: {exc}")


def _presence_state(client: ClientInstallation) -> str:
    return presence_state_label(client.last_seen, bool(client.is_online))


def _format_dt(value) -> str:
    if not value:
        return "-"
    try:
        return value.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(value)


def _format_tracking_status(client: ClientInstallation) -> str:
    if getattr(client, "pending_task", None):
        return "Queued"
    if getattr(client, "active_task_id", None):
        return "Client Fetching"

    raw = str(getattr(client, "last_tracking_status", "") or "").strip().lower()
    if not raw:
        return "Idle"
    if raw == "queued":
        return "Queued"
    if raw == "dispatched":
        return "Sent To Client"
    if raw == "completed":
        return "File Ready"
    if raw == "failed":
        return "Failed"
    return raw.replace("_", " ").title()


def _format_client_event(value) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "-"
    if raw == "startup":
        return "Started"
    if raw == "running":
        return "Running"
    if raw == "shutdown":
        return "Closed"
    return raw.replace("_", " ").title()


def _load_license_endpoints() -> dict:
    candidates = [
        Path(__file__).resolve().parents[1] / "license_endpoints.json",
        Path.cwd() / "license_endpoints.json",
    ]
    for candidate in candidates:
        try:
            if candidate.exists():
                import json

                payload = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return payload
        except Exception:
            continue
    return {}


def _get_primary_license_url() -> str:
    payload = _load_license_endpoints()
    return str(payload.get("primary_url", "") or "").strip()


def _get_local_lan_ip() -> str:
    candidates = []
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 80))
            candidates.append(probe.getsockname()[0])
        finally:
            probe.close()
    except Exception:
        pass

    try:
        hostname = socket.gethostname()
        candidates.extend(socket.gethostbyname_ex(hostname)[2])
    except Exception:
        pass

    for candidate in candidates:
        text = str(candidate or "").strip()
        if text and not text.startswith("127."):
            return text
    return ""


def _build_fixed_url_status(port: int) -> str:
    primary_url = _get_primary_license_url()
    if not primary_url:
        return (
            "Fixed URL status:\n\n"
            "Primary fixed URL configured nahi hai.\n"
            "license_endpoints.json mein primary_url set honi chahiye."
        )

    parsed = urlparse(primary_url)
    host = parsed.hostname or "-"
    fixed_port = parsed.port or (443 if parsed.scheme == "https" else 80)

    resolved_ip = ""
    try:
        resolved_ip = socket.gethostbyname(host)
    except Exception:
        resolved_ip = "DNS resolve failed"

    local_health = "Failed"
    try:
        response = requests.get(f"http://127.0.0.1:{port}/api/health", timeout=2)
        if response.status_code == 200:
            local_health = "OK"
    except Exception:
        pass

    lan_ip = _get_local_lan_ip() or "-"
    return (
        "Fixed URL status:\n\n"
        f"Client fixed URL: {primary_url}\n"
        f"Hostname: {host}\n"
        f"Port: {fixed_port}\n"
        f"DNS resolves to: {resolved_ip}\n"
        f"Local server health: {local_health}\n"
        f"This PC LAN IP: {lan_ip}\n\n"
        "Remote EXEs ke liye 3 cheezen zaroori hain:\n"
        "1. No-IP hostname current public IP par point kare\n"
        "2. Router port 5000 is PC par forward kare\n"
        "3. Windows Firewall port 5000 allow kare\n\n"
        "Agar local health OK hai lekin remote EXE connect nahi kar rahi,\n"
        "to issue networking side par hai, app code side par nahi."
    )


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "False").lower() == "true"
    admin_key = os.getenv("ADMIN_KEY", "ONESOUL_ADMIN_2025")
    host = os.getenv("HOST", "0.0.0.0")

    def run_flask():
        if debug:
            app.run(host=host, port=port, debug=True, use_reloader=False)
            return

        try:
            from waitress import serve

            print("Using Waitress WSGI server", flush=True)
            serve(app, host=host, port=port, threads=8)
        except Exception as exc:
            print(f"Waitress unavailable, falling back to Flask dev server: {exc}", flush=True)
            app.run(host=host, port=port, debug=False, use_reloader=False)

    def open_admin_gui():
        root = tk.Tk()
        root.title("OneSoul License Admin")
        root.geometry("1560x780")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Main.TFrame", background="#0f172a")
        style.configure("TLabel", background="#0f172a", foreground="#e2e8f0")
        style.configure("TEntry", fieldbackground="#1f2937", foreground="#e2e8f0")
        style.configure("Accent.TButton", background="#10b981", foreground="white")
        style.map("Accent.TButton", background=[("active", "#0ea472")])
        style.configure("Secondary.TButton", background="#1f2937", foreground="#e2e8f0")
        style.map("Secondary.TButton", background=[("active", "#111827")])
        style.configure("Treeview", background="#111827", foreground="#e2e8f0", fieldbackground="#111827", rowheight=24)
        style.configure("Treeview.Heading", background="#1f2937", foreground="#e2e8f0")

        root.configure(bg="#0f172a")
        main_frame = ttk.Frame(root, padding=12, style="Main.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True)

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        generate_tab = ttk.Frame(notebook, style="Main.TFrame", padding=12)
        clients_tab = ttk.Frame(notebook, style="Main.TFrame", padding=12)
        notebook.add(generate_tab, text="Generate License")
        notebook.add(clients_tab, text="Client Activity")

        fixed_url_var = tk.StringVar(value=f"Fixed Client URL: {_get_primary_license_url() or '(not configured)'}")

        # Generate tab
        ttk.Label(generate_tab, textvariable=fixed_url_var, foreground="#10b981").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )
        ttk.Label(generate_tab, text="Email").grid(row=1, column=0, sticky="w")
        email_var = tk.StringVar()
        ttk.Entry(generate_tab, textvariable=email_var, width=40).grid(row=1, column=1, sticky="ew")

        ttk.Label(generate_tab, text="User Name").grid(row=2, column=0, sticky="w")
        name_var = tk.StringVar()
        ttk.Entry(generate_tab, textvariable=name_var, width=30).grid(row=2, column=1, sticky="ew")

        ttk.Label(generate_tab, text="Hardware ID").grid(row=3, column=0, sticky="w")
        hw_var = tk.StringVar()
        ttk.Entry(generate_tab, textvariable=hw_var, width=40).grid(row=3, column=1, sticky="ew")

        ttk.Label(generate_tab, text="Plan").grid(row=4, column=0, sticky="w")
        plan_var = tk.StringVar(value="basic")
        ttk.Combobox(generate_tab, textvariable=plan_var, values=["basic", "pro"], state="readonly").grid(
            row=4, column=1, sticky="ew"
        )

        ttk.Label(generate_tab, text="Duration (days)").grid(row=5, column=0, sticky="w")
        duration_var = tk.IntVar(value=30)
        ttk.Entry(generate_tab, textvariable=duration_var, width=10).grid(row=5, column=1, sticky="w")

        ttk.Label(generate_tab, text="Admin Key").grid(row=6, column=0, sticky="w")
        admin_var = tk.StringVar(value=admin_key)
        ttk.Entry(generate_tab, textvariable=admin_var, width=40, show="*").grid(row=6, column=1, sticky="ew")

        ttk.Label(generate_tab, text="License Key (result)").grid(row=7, column=0, sticky="w")
        result_var = tk.StringVar()
        result_entry = ttk.Entry(generate_tab, textvariable=result_var, width=40, state="readonly")
        result_entry.grid(row=7, column=1, sticky="ew")

        def copy_result():
            val = result_var.get().strip()
            if not val:
                messagebox.showwarning("Nothing to copy", "Generate a license first.")
                return
            root.clipboard_clear()
            root.clipboard_append(val)
            messagebox.showinfo("Copied", "License key copied to clipboard.")

        ttk.Button(generate_tab, text="Copy Key", style="Secondary.TButton", command=copy_result).grid(
            row=7, column=2, padx=(6, 0), sticky="ew"
        )

        status_var = tk.StringVar(value="Ready")
        ttk.Label(generate_tab, textvariable=status_var, foreground="#2c3e50").grid(
            row=8, column=0, columnspan=3, sticky="w", pady=(8, 4)
        )

        def generate_key():
            email = email_var.get().strip()
            plan = plan_var.get().strip().lower()
            duration = duration_var.get()
            hw = hw_var.get().strip()
            name = name_var.get().strip()
            adm = admin_var.get().strip()

            if not email or not plan or not adm:
                messagebox.showerror("Missing Data", "Email, plan, and admin key are required.")
                return

            payload = {
                "email": email,
                "user_name": name,
                "hardware_id": hw,
                "plan_type": plan,
                "duration_days": duration,
                "admin_key": adm,
            }

            try:
                resp = requests.post(f"http://localhost:{port}/api/admin/generate", json=payload, timeout=10)
                data = resp.json()
                if resp.status_code == 201 and data.get("success"):
                    result_var.set(data.get("license_key", ""))
                    status_var.set(f"Success. Expires: {data.get('expiry_date', '')}")
                    messagebox.showinfo("License Created", f"License Key:\n{data.get('license_key')}")
                else:
                    status_var.set(data.get("message", f"Failed: {resp.status_code}"))
                    messagebox.showerror("Error", data.get("message", "Failed to generate license"))
            except Exception as exc:
                status_var.set(f"Error: {exc}")
                messagebox.showerror("Error", str(exc))

        ttk.Button(generate_tab, text="Generate License", style="Accent.TButton", command=generate_key).grid(
            row=9, column=0, columnspan=3, pady=10, sticky="ew", ipadx=6, ipady=4
        )

        info_text = (
            "Licensing Security:\n"
            "• Hardware-bound activation\n"
            "• Signed offline leases (7 days)\n"
            "• Heartbeat presence tracking for distributed EXEs"
        )
        ttk.Label(generate_tab, text=info_text, foreground="#10b981").grid(
            row=10, column=0, columnspan=3, sticky="w", pady=(4, 0)
        )

        for i in range(3):
            generate_tab.columnconfigure(i, weight=1)

        # Client activity tab
        summary_var = tk.StringVar(value="Loading client activity...")
        ttk.Label(clients_tab, textvariable=summary_var).pack(anchor="w", pady=(0, 8))
        ttk.Label(clients_tab, textvariable=fixed_url_var, foreground="#10b981").pack(anchor="w", pady=(0, 6))

        controls = ttk.Frame(clients_tab, style="Main.TFrame")
        controls.pack(fill=tk.X, pady=(0, 8))
        auto_refresh_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="Auto Refresh", variable=auto_refresh_var).pack(side=tk.LEFT)

        def show_fixed_url_status():
            messagebox.showinfo("Fixed URL Status", _build_fixed_url_status(port))

        ttk.Button(
            controls,
            text="Fixed URL Status",
            style="Secondary.TButton",
            command=show_fixed_url_status,
        ).pack(side=tk.LEFT, padx=(8, 0))

        columns = (
            "presence",
            "email",
            "plan",
            "device",
            "version",
            "installation",
            "status",
            "tracking",
            "links_count",
            "links_file",
            "last_links_updated",
            "last_seen",
            "lease_expires",
            "public_ip",
            "lan_ip",
        )
        table_frame = ttk.Frame(clients_tab, style="Main.TFrame")
        table_frame.pack(fill=tk.BOTH, expand=True)

        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=22)
        widths = {
            "presence": 90,
            "email": 200,
            "plan": 70,
            "device": 180,
            "version": 80,
            "installation": 180,
            "status": 110,
            "tracking": 120,
            "links_count": 80,
            "links_file": 260,
            "last_links_updated": 150,
            "last_seen": 150,
            "lease_expires": 150,
            "public_ip": 140,
            "lan_ip": 120,
        }
        for col in columns:
            heading = "Last Event" if col == "status" else col.replace("_", " ").title()
            tree.heading(col, text=heading)
            tree.column(col, width=widths[col], anchor="w")

        y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")

        installation_col_index = columns.index("installation")

        def selected_installation_id() -> str:
            selected = tree.selection()
            if not selected:
                return ""
            values = tree.item(selected[0], "values") or ()
            if len(values) <= installation_col_index:
                return ""
            return str(values[installation_col_index]).strip()

        def refresh_clients():
            rows = []
            with app.app_context():
                clients = ClientInstallation.query.order_by(ClientInstallation.last_seen.desc()).all()
                for client in clients:
                    rows.append(
                        (
                            _presence_state(client),
                            getattr(client.license, "email", "-"),
                            getattr(client.license, "plan_type", "-"),
                            client.device_name or "-",
                            client.app_version or "-",
                            client.installation_id,
                            _format_client_event(client.last_status),
                            _format_tracking_status(client),
                            client.last_links_count if client.last_links_count is not None else "-",
                            os.path.basename(client.last_links_file) if client.last_links_file else "-",
                            _format_dt(client.last_links_updated_at),
                            _format_dt(client.last_seen),
                            _format_dt(client.lease_expires_at),
                            client.last_ip or "-",
                            client.last_lan_ip or "-",
                        )
                    )

            for item in tree.get_children():
                tree.delete(item)

            online = 0
            recent = 0
            offline = 0
            for row in rows:
                tree.insert("", tk.END, values=row)
                if row[0] == "Online":
                    online += 1
                elif row[0] == "Recent":
                    recent += 1
                else:
                    offline += 1

            summary_var.set(
                f"Tracked EXEs: {len(rows)}  |  Online: {online}  |  Recent: {recent}  |  Offline: {offline}"
            )

        def manual_refresh():
            refresh_clients()

        ttk.Button(controls, text="Refresh Now", style="Secondary.TButton", command=manual_refresh).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        def request_creator_links():
            installation_id = selected_installation_id()
            if not installation_id:
                messagebox.showwarning("Select Client", "Please select an online client row first.")
                return
            try:
                resp = requests.post(
                    f"http://localhost:{port}/api/admin/request-creator-links",
                    json={"installation_id": installation_id, "admin_key": admin_var.get().strip()},
                    timeout=10,
                )
                data = resp.json()
                if resp.status_code == 200 and data.get("success"):
                    messagebox.showinfo("Tracking Queued", data.get("message", "Tracking request queued."))
                    refresh_clients()
                else:
                    messagebox.showerror("Tracking Error", data.get("message", f"Failed: {resp.status_code}"))
            except Exception as exc:
                messagebox.showerror("Tracking Error", str(exc))

        def open_links_file():
            installation_id = selected_installation_id()
            if not installation_id:
                messagebox.showwarning("Select Client", "Please select a client row first.")
                return
            with app.app_context():
                client = ClientInstallation.query.filter_by(installation_id=installation_id).first()
                file_path = client.last_links_file if client else ""
            if not file_path or not os.path.exists(file_path):
                messagebox.showwarning("No File", "No creator-links file is available for this client yet.")
                return
            os.startfile(file_path)

        ttk.Button(controls, text="Fetch Creator URLs", style="Secondary.TButton", command=request_creator_links).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(controls, text="Open Links File", style="Secondary.TButton", command=open_links_file).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        def auto_refresh():
            if auto_refresh_var.get():
                refresh_clients()
            root.after(15000, auto_refresh)

        refresh_clients()
        root.after(15000, auto_refresh)
        root.mainloop()

    print(
        "------------------------------------------------------------\n"
        f"  OneSoul License Server\n"
        f"  Running on: http://localhost:{port}\n"
        f"  Bind Host: {host}\n"
        f"  Debug Mode: {debug}\n"
        "------------------------------------------------------------"
    )

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    open_admin_gui()
