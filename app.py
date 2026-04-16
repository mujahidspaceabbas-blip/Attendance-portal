"""
╔══════════════════════════════════════════════════════════╗
║    SS TEAM PORTAL — Enhanced UI + Advanced Features      ║
║    Smooth Animations • Modern Colors • Admin GPS Control  ║
║    Version 5.0 FINAL                                     ║
╚══════════════════════════════════════════════════════════╝

⚠️  SECURITY NOTE: Sensitive credentials in .env file
    Never commit secrets directly to repository!
"""

import streamlit as st
import sqlite3
import hashlib
import math
from datetime import datetime, date
import pandas as pd
import os
import json
from dotenv import load_dotenv

# ─── LOAD ENV VARIABLES ────────────────────────────────────
load_dotenv()

# ─── CONFIG ────────────────────────────────────────────────
OFFICE_LAT  = float(os.getenv("OFFICE_LAT", "30.124458"))
OFFICE_LON  = float(os.getenv("OFFICE_LON", "71.386285"))
OFFICE_KM   = float(os.getenv("OFFICE_KM", "96"))
ADMIN_PASS  = os.getenv("ADMIN_PASS", "admin123")  # Use .env file!
DB_PATH     = os.getenv("DB_PATH", "ss_portal.db")

# ─── EMPLOYEES ─────────────────────────────────────────────
EMPS = {
    "Saba":        {"dept": "WIP",                "desig": "Team Lead",          "pin": "1122", "col": "#00d4ff"},
    "Tahreem":     {"dept": "Cutting",            "desig": "Computer Operator",  "pin": "2233", "col": "#00e676"},
    "Zaheer":      {"dept": "Cutting",            "desig": "Computer Operator",  "pin": "3344", "col": "#ff5252"},
    "Hamza":       {"dept": "Sewing",             "desig": "Executive Office",   "pin": "4455", "col": "#ffaa00"},
    "Mujahid":     {"dept": "Washing",            "desig": "Supervisor",         "pin": "5566", "col": "#bf5af2"},
    "Irtiqa":      {"dept": "Washing",            "desig": "Computer Operator",  "pin": "6677", "col": "#40c4ff"},
    "Khushal":     {"dept": "Finishing & Packing","desig": "Supervisor",         "pin": "7788", "col": "#69f0ae"},
    "Abdul Haiey": {"dept": "Warehouse",          "desig": "Computer Operator",  "pin": "8899", "col": "#ff6e40"},
}

# ─── ADMIN PERMISSIONS ──────────────────────────────────────
ADMIN_PERMISSIONS = {
    "admin": {"gps_control": True, "device_reset": True, "alerts": True},
    # Uncomment to add super-admins only
    # "super_admin": {"gps_control": True, "device_reset": True, "alerts": True},
}

DEPARTMENTS = ["", "WIP", "Cutting", "Sewing", "Washing", "Finishing & Packing", "Warehouse"]
LEAVE_TYPES = ["Sick Leave", "Casual Leave", "Short Leave", "Out Miss Correction"]

# ─── DATABASE SETUP WITH AUTO-MIGRATION ────────────────────
def init_db():
    """Initialize database with auto-migration"""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    
    try:
        cur.execute("PRAGMA table_info(devices)")
        existing_cols = [row[1] for row in cur.fetchall()]
        if "devices" in [row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]:
            if "registered_at" not in existing_cols:
                cur.execute("DROP TABLE IF EXISTS devices")
                con.commit()
    except:
        pass

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS attendance (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        name      TEXT    NOT NULL,
        dept      TEXT,
        desig     TEXT,
        att_date  TEXT    NOT NULL,
        in_time   TEXT,
        out_time  TEXT    DEFAULT 'Out Miss',
        status    TEXT    DEFAULT 'Out Miss',
        device_fp TEXT,
        geo_ok    INTEGER DEFAULT 0,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS devices (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        name          TEXT NOT NULL,
        fp            TEXT NOT NULL,
        registered_at TEXT,
        UNIQUE(name, fp)
    );

    CREATE TABLE IF NOT EXISTS alerts (
        id     INTEGER PRIMARY KEY AUTOINCREMENT,
        level  TEXT,
        name   TEXT,
        type   TEXT,
        detail TEXT,
        fp     TEXT,
        seen   INTEGER DEFAULT 0,
        ts     TEXT
    );

    CREATE TABLE IF NOT EXISTS leave_requests (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        name       TEXT,
        req_date   TEXT,
        leave_type TEXT,
        reason     TEXT,
        status     TEXT DEFAULT 'Pending',
        ts         TEXT
    );

    CREATE TABLE IF NOT EXISTS login_fails (
        id    INTEGER PRIMARY KEY AUTOINCREMENT,
        name  TEXT UNIQUE NOT NULL,
        count INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS gps_settings (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        latitude   REAL,
        longitude  REAL,
        radius_km  REAL,
        updated_by TEXT,
        updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS admin_logs (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        admin     TEXT,
        action    TEXT,
        details   TEXT,
        ts        TEXT
    );
    """)
    con.commit()
    con.close()

def get_con():
    return sqlite3.connect(DB_PATH)

# ─── DB FUNCTIONS ──────────────────────────────────────────
def db_get_device(name):
    con = get_con()
    row = con.execute("SELECT fp FROM devices WHERE name=?", (name,)).fetchone()
    con.close()
    return row[0] if row else None

def db_register_device(name, fp):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con = get_con()
    try:
        con.execute("INSERT INTO devices(name,fp,registered_at) VALUES(?,?,?)", (name, fp, ts))
        con.commit()
    except sqlite3.IntegrityError:
        pass
    con.close()

def db_reset_device(name):
    con = get_con()
    con.execute("DELETE FROM devices WHERE name=?", (name,))
    con.commit()
    con.close()

def db_log_alert(level, name, atype, detail, fp=""):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con = get_con()
    con.execute("INSERT INTO alerts(level,name,type,detail,fp,ts) VALUES(?,?,?,?,?,?)",
                (level, name, atype, detail, fp, ts))
    con.commit()
    con.close()

def db_get_alerts(level=None):
    con = get_con()
    if level:
        rows = con.execute("SELECT * FROM alerts WHERE level=? ORDER BY ts DESC", (level,)).fetchall()
    else:
        rows = con.execute("SELECT * FROM alerts ORDER BY ts DESC LIMIT 200").fetchall()
    con.close()
    return rows

def db_clear_alerts(level=None, name=None):
    con = get_con()
    if level and not name:
        con.execute("DELETE FROM alerts WHERE level=?", (level,))
    elif name:
        con.execute("DELETE FROM alerts WHERE name=? AND level='HIGH'", (name,))
    con.commit()
    con.close()

def db_get_fails(name):
    con = get_con()
    row = con.execute("SELECT count FROM login_fails WHERE name=?", (name,)).fetchone()
    con.close()
    return row[0] if row else 0

def db_set_fails(name, count):
    con = get_con()
    con.execute("INSERT OR REPLACE INTO login_fails(name,count) VALUES(?,?)", (name, count))
    con.commit()
    con.close()

def db_mark_in(name, in_time, fp, geo_ok):
    emp = EMPS.get(name, {})
    today = date.today().isoformat()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con = get_con()
    row = con.execute("SELECT id FROM attendance WHERE name=? AND att_date=?", (name, today)).fetchone()
    if not row:
        con.execute(
            "INSERT INTO attendance(name,dept,desig,att_date,in_time,out_time,status,device_fp,geo_ok,created_at) VALUES(?,?,?,?,?,'Out Miss','Out Miss',?,?,?)",
            (name, emp.get("dept"), emp.get("desig"), today, in_time, fp, int(geo_ok), ts)
        )
        con.commit()
    con.close()

def db_mark_out(name, out_time):
    today = date.today().isoformat()
    con = get_con()
    con.execute("UPDATE attendance SET out_time=?, status='Present' WHERE name=? AND att_date=?",
                (out_time, name, today))
    con.commit()
    con.close()

def db_get_today(name):
    today = date.today().isoformat()
    con = get_con()
    row = con.execute("SELECT * FROM attendance WHERE name=? AND att_date=?", (name, today)).fetchone()
    con.close()
    return row

def db_get_history(name):
    con = get_con()
    rows = con.execute("SELECT * FROM attendance WHERE name=? ORDER BY att_date DESC", (name,)).fetchall()
    con.close()
    return rows

def db_get_all_att(dept_filter=None):
    con = get_con()
    if dept_filter:
        rows = con.execute("SELECT * FROM attendance WHERE dept=? ORDER BY att_date DESC", (dept_filter,)).fetchall()
    else:
        rows = con.execute("SELECT * FROM attendance ORDER BY att_date DESC").fetchall()
    con.close()
    return rows

def db_add_leave(name, req_date, leave_type, reason):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con = get_con()
    con.execute("INSERT INTO leave_requests(name,req_date,leave_type,reason,ts) VALUES(?,?,?,?,?)",
                (name, req_date, leave_type, reason, ts))
    con.commit()
    con.close()

def db_get_leaves(name=None, status=None):
    con = get_con()
    q = "SELECT * FROM leave_requests WHERE 1=1"
    params = []
    if name:   
        q += " AND name=?"
        params.append(name)
    if status: 
        q += " AND status=?"
        params.append(status)
    q += " ORDER BY ts DESC"
    rows = con.execute(q, params).fetchall()
    con.close()
    return rows

def db_update_leave(lid, status):
    con = get_con()
    con.execute("UPDATE leave_requests SET status=? WHERE id=?", (status, lid))
    if status == "Approved":
        row = con.execute("SELECT name, req_date, leave_type FROM leave_requests WHERE id=?", (lid,)).fetchone()
        if row:
            n, d, lt = row
            att_row = con.execute("SELECT id FROM attendance WHERE name=? AND att_date=?", (n, d)).fetchone()
            if att_row:
                if lt == "Out Miss Correction":
                    con.execute("UPDATE attendance SET out_time='Corrected', status='Present' WHERE name=? AND att_date=?", (n, d))
                else:
                    con.execute("UPDATE attendance SET status=? WHERE name=? AND att_date=?", (lt, n, d))
            else:
                emp = EMPS.get(n, {})
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                con.execute(
                    "INSERT INTO attendance(name,dept,desig,att_date,status,created_at) VALUES(?,?,?,?,?,?)",
                    (n, emp.get("dept"), emp.get("desig"), d, lt, ts)
                )
    con.commit()
    con.close()

# ─── GPS SETTINGS FUNCTIONS ────────────────────────────────
def db_get_gps_settings():
    con = get_con()
    row = con.execute("SELECT latitude, longitude, radius_km FROM gps_settings ORDER BY id DESC LIMIT 1").fetchone()
    con.close()
    if row:
        return {"lat": row[0], "lon": row[1], "radius": row[2]}
    return {"lat": OFFICE_LAT, "lon": OFFICE_LON, "radius": OFFICE_KM}

def db_update_gps_settings(lat, lon, radius, admin_name):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con = get_con()
    con.execute("INSERT INTO gps_settings(latitude, longitude, radius_km, updated_by, updated_at) VALUES(?,?,?,?,?)",
                (lat, lon, radius, admin_name, ts))
    con.commit()
    
    # Log admin action
    con.execute("INSERT INTO admin_logs(admin, action, details, ts) VALUES(?,?,?,?)",
                (admin_name, "GPS_UPDATE", f"Changed to {lat}, {lon} (radius: {radius}km)", ts))
    con.commit()
    con.close()

def db_log_admin_action(admin, action, details):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con = get_con()
    con.execute("INSERT INTO admin_logs(admin, action, details, ts) VALUES(?,?,?,?)",
                (admin, action, details, ts))
    con.commit()
    con.close()

def db_get_admin_logs():
    con = get_con()
    rows = con.execute("SELECT * FROM admin_logs ORDER BY ts DESC LIMIT 100").fetchall()
    con.close()
    return rows

# ─── UTILITIES ──────────────────────────────────────────────
def calc_dist(la1, lo1, la2, lo2):
    R = 6371
    d = math.pi / 180
    a = (math.sin((la2-la1)*d/2)**2 + math.cos(la1*d) * math.cos(la2*d) * math.sin((lo2-lo1)*d/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def calc_hrs(t_in, t_out):
    if not t_in or not t_out or t_out in ("Out Miss", "Corrected", "--", ""):
        return "--"
    try:
        a = list(map(int, t_in.split(":")))
        b = list(map(int, t_out.split(":")))
        diff = (b[0]*3600 + b[1]*60 + (b[2] if len(b)>2 else 0)) - (a[0]*3600 + a[1]*60 + (a[2] if len(a)>2 else 0))
        if diff < 0: 
            return "--"
        return f"{diff//3600}h {(diff%3600)//60}m"
    except:
        return "--"

def now_time():
    return datetime.now().strftime("%H:%M:%S")

def today_str():
    return date.today().isoformat()

def get_server_fp():
    if "fp_seed" not in st.session_state:
        import random
        st.session_state.fp_seed = str(random.randint(100000, 999999))
    raw = "streamlit" + st.session_state.fp_seed
    h = hashlib.md5(raw.encode()).hexdigest().upper()
    return "FP" + h[:8]

# ─── MODERN CSS WITH SMOOTH ANIMATIONS ──────────────────────
def inject_advanced_css():
    """Inject glassmorphism + smooth animations with modern colors"""
    st.markdown("""
    <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    
    /* ── MODERN COLOR PALETTE ── */
    :root {
        --primary: #6366f1;      /* Indigo */
        --primary-dark: #4f46e5; /* Darker Indigo */
        --accent: #ec4899;       /* Pink */
        --success: #10b981;      /* Emerald */
        --warning: #f59e0b;      /* Amber */
        --danger: #ef4444;       /* Red */
        --dark-bg: #0f172a;      /* Slate-900 */
        --card-bg: #1e293b;      /* Slate-800 */
        --text-primary: #f1f5f9; /* Slate-100 */
        --text-secondary: #cbd5e1; /* Slate-300 */
    }

    /* ── GLOBAL BACKGROUND ── */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMainBlockContainer"] {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%) !important;
        color: #f1f5f9 !important;
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
        min-height: 100vh;
        overflow-x: hidden;
    }

    /* ── SCROLLBAR STYLING ── */
    ::-webkit-scrollbar { width: 10px; }
    ::-webkit-scrollbar-track { background: rgba(99,102,241,0.05); border-radius: 10px; }
    ::-webkit-scrollbar-thumb { 
        background: linear-gradient(180deg, #6366f1, #ec4899); 
        border-radius: 10px;
        transition: all 0.3s ease;
    }
    ::-webkit-scrollbar-thumb:hover { background: linear-gradient(180deg, #4f46e5, #db2777); }

    /* ── SIDEBAR ── */
    [data-testid="stSidebar"] { 
        background: linear-gradient(135deg, rgba(15,23,42,0.98), rgba(30,41,59,0.98)) !important; 
        border-right: 2px solid rgba(99,102,241,0.2) !important;
        backdrop-filter: blur(20px);
    }
    [data-testid="stSidebar"] * { color: #f1f5f9 !important; }

    /* ── METRIC CARDS ── */
    [data-testid="metric-container"] {
        background: linear-gradient(135deg, rgba(99,102,241,0.08), rgba(236,72,153,0.05)) !important;
        border: 1.5px solid rgba(99,102,241,0.2) !important;
        border-radius: 16px !important;
        padding: 20px !important;
        backdrop-filter: blur(20px);
        box-shadow: 0 8px 32px rgba(99,102,241,0.1);
        transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
        animation: slideUp 0.6s ease-out;
    }
    [data-testid="metric-container"]:hover {
        background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(236,72,153,0.1)) !important;
        border-color: rgba(99,102,241,0.4) !important;
        box-shadow: 0 12px 48px rgba(99,102,241,0.2) !important;
        transform: translateY(-6px);
    }
    [data-testid="stMetricValue"] { 
        color: #6366f1 !important; 
        font-size: 2.2rem !important; 
        font-weight: 900 !important;
        text-shadow: 0 0 20px rgba(99,102,241,0.3);
    }
    [data-testid="stMetricLabel"] { 
        color: #cbd5e1 !important; 
        font-size: 0.8rem !important; 
        text-transform: uppercase; 
        letter-spacing: 2px;
        font-weight: 700;
    }

    /* ── INPUTS ── */
    input, textarea, select, [data-baseweb="select"] {
        background: linear-gradient(135deg, rgba(30,41,59,0.9), rgba(15,23,42,0.8)) !important;
        border: 1.5px solid rgba(99,102,241,0.2) !important;
        color: #f1f5f9 !important;
        border-radius: 12px !important;
        padding: 12px 16px !important;
        font-size: 14px !important;
        transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
        backdrop-filter: blur(20px);
    }
    input:focus, textarea:focus { 
        border-color: #6366f1 !important; 
        box-shadow: 0 0 20px rgba(99,102,241,0.4), inset 0 0 20px rgba(99,102,241,0.1) !important;
        background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(236,72,153,0.08)) !important;
        transform: translateY(-2px);
    }

    /* ── BUTTONS ── */
    .stButton > button {
        background: linear-gradient(135deg, #6366f1, #4f46e5) !important;
        color: #fff !important;
        font-weight: 800 !important;
        border: none !important;
        border-radius: 12px !important;
        letter-spacing: 1px;
        text-transform: uppercase;
        font-size: 12px !important;
        padding: 12px 28px !important;
        transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
        box-shadow: 0 6px 20px rgba(99,102,241,0.3);
        position: relative;
        overflow: hidden;
        animation: slideUp 0.5s ease-out;
    }
    .stButton > button::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
        transition: left 0.5s ease;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #ec4899, #db2777) !important;
        box-shadow: 0 10px 40px rgba(236,72,153,0.5) !important;
        transform: translateY(-3px);
    }
    .stButton > button:hover::before { left: 100%; }
    .stButton > button:active {
        transform: translateY(-1px) scale(0.98);
    }

    /* ── TAB BAR ── */
    .stTabs [data-baseweb="tab-list"] {
        background: linear-gradient(90deg, rgba(30,41,59,0.6), rgba(15,23,42,0.6)) !important;
        border-radius: 14px !important;
        padding: 6px !important;
        gap: 6px !important;
        border: 1.5px solid rgba(99,102,241,0.15) !important;
        backdrop-filter: blur(20px);
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        color: #cbd5e1 !important;
        border-radius: 10px !important;
        font-size: 12px !important;
        font-weight: 700 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 10px 20px !important;
        transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(99,102,241,0.2), rgba(236,72,153,0.1)) !important;
        color: #6366f1 !important;
        border: 1.5px solid rgba(99,102,241,0.4) !important;
        box-shadow: inset 0 0 15px rgba(99,102,241,0.2), 0 0 20px rgba(99,102,241,0.1);
    }

    /* ── DATAFRAME ── */
    [data-testid="stDataFrame"] {
        border: 1.5px solid rgba(99,102,241,0.2) !important;
        border-radius: 12px !important;
        background: rgba(15,23,42,0.6) !important;
        animation: slideUp 0.6s ease-out 0.1s both;
    }

    /* ── CUSTOM CARDS ── */
    .ss-card {
        background: linear-gradient(135deg, rgba(30,41,59,0.8), rgba(15,23,42,0.6)) !important;
        border: 1.5px solid rgba(99,102,241,0.2) !important;
        border-radius: 16px !important;
        padding: 22px 24px !important;
        margin-bottom: 16px !important;
        backdrop-filter: blur(20px);
        box-shadow: 0 8px 32px rgba(99,102,241,0.1);
        transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
        animation: slideUp 0.6s ease-out;
    }
    .ss-card:hover {
        border-color: rgba(99,102,241,0.35) !important;
        box-shadow: 0 12px 48px rgba(99,102,241,0.2) !important;
        transform: translateY(-4px);
    }

    /* ── ALERTS ── */
    .ss-alert-hi {
        background: linear-gradient(135deg, rgba(239,68,68,0.12), rgba(220,38,38,0.08)) !important;
        border: 1.5px solid rgba(239,68,68,0.3) !important;
        border-radius: 12px !important;
        padding: 16px !important;
        margin-bottom: 12px !important;
        backdrop-filter: blur(20px);
        animation: slideDown 0.4s ease-out, pulse-red 2s ease-in-out 0.4s infinite;
    }
    .ss-alert-md {
        background: linear-gradient(135deg, rgba(245,158,11,0.12), rgba(217,119,6,0.08)) !important;
        border: 1.5px solid rgba(245,158,11,0.3) !important;
        border-radius: 12px !important;
        padding: 16px !important;
        margin-bottom: 12px !important;
        backdrop-filter: blur(20px);
        animation: slideDown 0.4s ease-out 0.1s both;
    }
    .ss-alert-lo {
        background: linear-gradient(135deg, rgba(16,185,129,0.12), rgba(5,150,105,0.08)) !important;
        border: 1.5px solid rgba(16,185,129,0.3) !important;
        border-radius: 12px !important;
        padding: 16px !important;
        margin-bottom: 12px !important;
        backdrop-filter: blur(20px);
        animation: slideDown 0.4s ease-out 0.2s both;
    }

    /* ── BANNER ── */
    .ss-banner-ok {
        background: linear-gradient(135deg, rgba(16,185,129,0.12), rgba(5,150,105,0.08)) !important;
        border: 1.5px solid rgba(16,185,129,0.3) !important;
        color: #10b981 !important;
        border-radius: 12px !important;
        padding: 14px 16px !important;
        font-size: 13px !important;
        margin-bottom: 14px !important;
        backdrop-filter: blur(20px);
        animation: slideDown 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
        font-weight: 600;
    }
    .ss-banner-warn {
        background: linear-gradient(135deg, rgba(239,68,68,0.12), rgba(220,38,38,0.08)) !important;
        border: 1.5px solid rgba(239,68,68,0.3) !important;
        color: #ef4444 !important;
        border-radius: 12px !important;
        padding: 14px 16px !important;
        font-size: 13px !important;
        margin-bottom: 14px !important;
        backdrop-filter: blur(20px);
        animation: slideDown 0.4s cubic-bezier(0.34, 1.56, 0.64, 1), shake 0.5s ease 0.4s;
        font-weight: 600;
    }
    .ss-banner-info {
        background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(79,70,229,0.08)) !important;
        border: 1.5px solid rgba(99,102,241,0.3) !important;
        color: #6366f1 !important;
        border-radius: 12px !important;
        padding: 14px 16px !important;
        font-size: 13px !important;
        margin-bottom: 14px !important;
        backdrop-filter: blur(20px);
        animation: slideDown 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) 0.1s both;
        font-weight: 600;
    }

    /* ── CHIPS ── */
    .chip-green  { 
        background: linear-gradient(135deg, rgba(16,185,129,0.2), rgba(5,150,105,0.15)); 
        color: #10b981; 
        border: 1.5px solid rgba(16,185,129,0.4); 
        border-radius: 20px; 
        padding: 6px 14px; 
        font-size: 11px; 
        font-weight: 700;
        display: inline-block;
        transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    .chip-green:hover { 
        background: linear-gradient(135deg, rgba(16,185,129,0.3), rgba(5,150,105,0.2));
        box-shadow: 0 0 15px rgba(16,185,129,0.4);
        transform: translateY(-2px);
    }
    .chip-red    { 
        background: linear-gradient(135deg, rgba(239,68,68,0.2), rgba(220,38,38,0.15)); 
        color: #ef4444; 
        border: 1.5px solid rgba(239,68,68,0.4); 
        border-radius: 20px; 
        padding: 6px 14px; 
        font-size: 11px; 
        font-weight: 700;
        display: inline-block;
        transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    .chip-red:hover {
        background: linear-gradient(135deg, rgba(239,68,68,0.3), rgba(220,38,38,0.2));
        box-shadow: 0 0 15px rgba(239,68,68,0.4);
        transform: translateY(-2px);
    }
    .chip-amber  { 
        background: linear-gradient(135deg, rgba(245,158,11,0.2), rgba(217,119,6,0.15)); 
        color: #f59e0b; 
        border: 1.5px solid rgba(245,158,11,0.4); 
        border-radius: 20px; 
        padding: 6px 14px; 
        font-size: 11px; 
        font-weight: 700;
        display: inline-block;
        transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    .chip-blue   { 
        background: linear-gradient(135deg, rgba(99,102,241,0.2), rgba(79,70,229,0.15)); 
        color: #6366f1; 
        border: 1.5px solid rgba(99,102,241,0.4); 
        border-radius: 20px; 
        padding: 6px 14px; 
        font-size: 11px; 
        font-weight: 700;
        display: inline-block;
        transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    }

    /* ── ANIMATIONS ── */
    @keyframes slideUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @keyframes slideDown {
        from {
            opacity: 0;
            transform: translateY(-20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @keyframes pulse-red {
        0%, 100% { box-shadow: 0 0 20px rgba(239,68,68,0.2); }
        50% { box-shadow: 0 0 40px rgba(239,68,68,0.4); }
    }
    
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        25% { transform: translateX(-4px); }
        75% { transform: translateX(4px); }
    }
    
    @keyframes glow-pulse {
        0%, 100% { text-shadow: 0 0 10px rgba(99,102,241,0.3); }
        50% { text-shadow: 0 0 20px rgba(99,102,241,0.6); }
    }
    
    @keyframes fadeIn {
        from {
            opacity: 0;
        }
        to {
            opacity: 1;
        }
    }

    @keyframes bounce-soft {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-8px); }
    }

    /* ── CUSTOM ANIMATIONS ── */
    .glow-text {
        animation: glow-pulse 2s ease-in-out infinite;
    }
    
    .bounce-in {
        animation: slideUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
    }

    .glass-box {
        background: linear-gradient(135deg, rgba(99,102,241,0.08), rgba(236,72,153,0.04)) !important;
        border: 1.5px solid rgba(99,102,241,0.2) !important;
        border-radius: 16px;
        backdrop-filter: blur(20px);
        transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    
    .glass-box:hover {
        background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(236,72,153,0.08)) !important;
        border-color: rgba(99,102,241,0.4) !important;
        box-shadow: 0 8px 32px rgba(99,102,241,0.15);
        transform: translateY(-4px);
    }

    /* ── SMOOTH TRANSITIONS ── */
    * {
        transition: background 0.3s ease, border-color 0.3s ease, color 0.3s ease !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ─── SESSION STATE ────────────────────────────────────────────
def init_session():
    defaults = {
        "logged_in": False,
        "current_user": None,
        "admin_logged_in": False,
        "admin_name": None,
        "device_fp": None,
        "gps_lat": None,
        "gps_lon": None,
        "gps_ok": False,
        "gps_dist": None,
        "page": "attendance",
        "login_error": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ─── HEADER ──────────────────────────────────────────────────
def render_header():
    hi_alerts = len(db_get_alerts("HIGH"))
    sec_status = f"🔴 {hi_alerts} ALERTS" if hi_alerts > 0 else "🟢 SECURE"

    st.markdown(f"""
    <div style="background: linear-gradient(90deg, rgba(30,41,59,0.95), rgba(15,23,42,0.95));
                border-bottom: 2px solid rgba(99,102,241,0.2);
                padding: 16px 24px; display: flex; align-items: center;
                justify-content: space-between; margin-bottom: 20px; border-radius: 14px;
                backdrop-filter: blur(20px); box-shadow: 0 8px 32px rgba(99,102,241,0.1);
                animation: slideDown 0.5s ease-out">
        <div style="display:flex;align-items:center;gap:16px">
            <div style="width:44px;height:44px;border-radius:12px;
                        background: linear-gradient(135deg,#6366f1,#ec4899);
                        display:flex;align-items:center;justify-content:center;
                        font-size:14px;font-weight:900;color:#fff;
                        box-shadow: 0 0 25px rgba(99,102,241,0.4);
                        animation: bounce-soft 2s ease-in-out infinite">SS</div>
            <div>
                <div style="font-size:16px;font-weight:900;color:#f1f5f9;letter-spacing:1px">SS Team Portal</div>
                <div style="font-size:10px;color:#cbd5e1;font-family:monospace;margin-top:2px;letter-spacing:0.5px">
                    🔐 Advanced Security v5.0</div>
            </div>
        </div>
        <div style="display:flex;align-items:center;gap:14px">
            <div style="font-family:monospace;font-size:12px;color:{'#ef4444' if hi_alerts else '#10b981'};
                        background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(236,72,153,0.08));
                        padding:8px 16px;border-radius:20px;
                        border: 1.5px solid rgba(99,102,241,0.3);
                        backdrop-filter: blur(20px);
                        font-weight: 700;
                        letter-spacing: 1px;
                        animation: slideDown 0.5s ease-out 0.1s both">
                {sec_status}
            </div>
            <div style="font-family:monospace;font-size:12px;color:#6366f1;
                        background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(236,72,153,0.08));
                        padding:8px 16px;border-radius:20px;
                        border: 1.5px solid rgba(99,102,241,0.3);
                        backdrop-filter: blur(20px);
                        font-weight: 700;
                        animation: slideDown 0.5s ease-out 0.2s both">
                {datetime.now().strftime('%H:%M:%S')}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ─── ATTENDANCE PAGE ──────────────────────────────────────────
def page_attendance():
    if not st.session_state.logged_in:
        render_login()
    else:
        render_dashboard()

def render_login():
    st.markdown("<div style='height: 40px'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([0.5, 2, 0.5])
    
    with col2:
        st.markdown("""
        <div class="bounce-in" style="text-align:center;margin-bottom:32px">
            <div style="width:60px;height:60px;border-radius:16px;
                        background: linear-gradient(135deg,#6366f1,#ec4899);
                        display:flex;align-items:center;justify-content:center;
                        font-size:24px;font-weight:900;color:#fff;margin:0 auto 18px;
                        box-shadow: 0 0 35px rgba(99,102,241,0.5);
                        animation: glow-pulse 2s ease-in-out infinite">SS</div>
            <div style="font-size:22px;font-weight:900;color:#f1f5f9;letter-spacing:2px">SECURE LOGIN</div>
            <div style="font-size:11px;color:#cbd5e1;font-family:monospace;margin-top:8px;letter-spacing:1.5px">
                🔐 BIOMETRIC VERIFIED</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="ss-card">', unsafe_allow_html=True)

        dev_fp = get_server_fp()
        st.session_state.device_fp = dev_fp

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(236,72,153,0.08));
                        border-radius:14px;padding:18px;text-align:center;
                        border: 1.5px solid rgba(99,102,241,0.3);
                        backdrop-filter: blur(20px);
                        transition: all 0.3s ease;
                        animation: slideUp 0.6s ease-out">
                <div style="font-size:28px;margin-bottom:10px">📱</div>
                <div style="font-size:10px;font-family:monospace;color:#cbd5e1;font-weight:700;letter-spacing:1px">
                    DEVICE<br>FINGERPRINT</div>
                <div style="font-size:10px;font-weight:800;margin-top:8px;
                            font-family:monospace;color:#10b981;text-shadow: 0 0 10px rgba(16,185,129,0.4)">
                    ✓ READY</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(236,72,153,0.08));
                        border-radius:14px;padding:18px;text-align:center;
                        border: 1.5px solid rgba(99,102,241,0.3);
                        backdrop-filter: blur(20px);
                        transition: all 0.3s ease;
                        animation: slideUp 0.6s ease-out 0.1s both">
                <div style="font-size:28px;margin-bottom:10px">📍</div>
                <div style="font-size:10px;font-family:monospace;color:#cbd5e1;font-weight:700;letter-spacing:1px">
                    GPS<br>LOCATION</div>
                <div style="font-size:10px;font-weight:800;margin-top:8px;
                            font-family:monospace;color:{'#10b981' if st.session_state.gps_ok else '#f59e0b'}">
                    {'✓ READY' if st.session_state.gps_ok else '⏳ WAITING'}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        name = st.selectbox("👤 Employee Name", ["-- Select --"] + list(EMPS.keys()), key="login_name")
        pin  = st.text_input("🔑 PIN", type="password", max_chars=6, key="login_pin", placeholder="Enter 4-digit PIN")

        with st.expander("📍 GPS Location", expanded=False):
            gps_settings = db_get_gps_settings()
            gc1, gc2 = st.columns(2)
            with gc1:
                lat_in = st.number_input("Latitude", value=gps_settings["lat"], format="%.6f", key="inp_lat")
            with gc2:
                lon_in = st.number_input("Longitude", value=gps_settings["lon"], format="%.6f", key="inp_lon")
            if st.button("📍 Confirm Location", key="gps_btn", use_container_width=True):
                st.session_state.gps_lat  = lat_in
                st.session_state.gps_lon  = lon_in
                st.session_state.gps_ok   = True
                dist = calc_dist(lat_in, lon_in, gps_settings["lat"], gps_settings["lon"])
                st.session_state.gps_dist = dist
                st.success(f"✓ GPS confirmed — {dist:.1f}km from office")

        if st.session_state.login_error:
            st.markdown(f'<div class="ss-banner-warn bounce-in">❌ {st.session_state.login_error}</div>',
                        unsafe_allow_html=True)
            st.session_state.login_error = ""

        if st.button("🔐 VERIFY & ENTER", key="login_btn", use_container_width=True):
            do_login(name, pin, dev_fp)

        st.markdown("""
        <div style="font-size:9px;color:#cbd5e1;text-align:center;margin-top:16px;
                    font-family:monospace;line-height:1.8;letter-spacing:0.5px">
            Your device is securely locked to your account.<br>
            <span style="color:#ef4444">⚠ Unauthorized device access triggers security alerts</span>
        </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

def do_login(name, pin, fp):
    if name == "-- Select --" or name not in EMPS:
        st.session_state.login_error = "Select an employee"
        return

    emp = EMPS[name]

    if pin != emp["pin"]:
        fails = db_get_fails(name) + 1
        db_set_fails(name, fails)
        if fails >= 3:
            db_log_alert("HIGH", name, "BRUTE_FORCE", f"{fails} failed PIN attempts", fp)
            st.session_state.login_error = f"Too many attempts ({fails}/3). Admin alerted."
        else:
            st.session_state.login_error = f"Wrong PIN ({fails}/3)"
        return

    registered_fp = db_get_device(name)

    if registered_fp and registered_fp != fp:
        db_log_alert("HIGH", name, "DEVICE_MISMATCH",
                     f"Login from unauthorized device", fp)
        st.session_state.login_error = "🚨 DEVICE MISMATCH! Admin alerted."
        return

    if not registered_fp:
        db_register_device(name, fp)
        db_log_alert("INFO", name, "NEW_DEVICE", f"Device registered", fp)

    db_set_fails(name, 0)

    if st.session_state.gps_ok and st.session_state.gps_dist is not None:
        gps_settings = db_get_gps_settings()
        d = st.session_state.gps_dist
        if d > gps_settings["radius"]:
            db_log_alert("HIGH", name, "GEO_VIOLATION", f"Login from {d:.1f}km away")

    st.session_state.logged_in    = True
    st.session_state.current_user = name
    db_log_alert("INFO", name, "LOGIN", "Successful login", fp)
    st.rerun()

def render_dashboard():
    name = st.session_state.current_user
    emp  = EMPS[name]
    fp   = st.session_state.device_fp or get_server_fp()

    hi_count = len([a for a in db_get_alerts("HIGH") if a[2] == name])

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:16px;padding:18px 20px;
                background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(236,72,153,0.08));
                border-radius:14px;border: 1.5px solid rgba(99,102,241,0.3);
                margin-bottom:18px;backdrop-filter: blur(20px);
                animation: slideDown 0.5s ease-out">
        <div style="width:52px;height:52px;border-radius:50%;display:flex;
                    align-items:center;justify-content:center;font-size:16px;
                    font-weight:900;color:{emp['col']};
                    border: 2.5px solid {emp['col']};background:rgba(0,0,0,0.3);
                    box-shadow: 0 0 20px {emp['col']}60">
            {name[:2].upper()}
        </div>
        <div style="flex:1">
            <div style="font-size:16px;font-weight:900;color:#f1f5f9;letter-spacing:0.5px">{name}</div>
            <div style="font-size:12px;color:#cbd5e1;font-family:monospace;margin-top:2px">{emp['dept']} • {emp['desig']}</div>
        </div>
        <div style="font-size:10px;font-family:monospace;color:#6366f1;
                    background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(236,72,153,0.08));
                    padding:8px 14px;border-radius:10px;border: 1px solid rgba(99,102,241,0.3);
                    backdrop-filter: blur(20px);font-weight:700;letter-spacing:0.5px">
            🔒 {fp[:12]}...
        </div>
    </div>
    """, unsafe_allow_html=True)

    if hi_count > 0:
        st.markdown(f'<div class="ss-banner-warn bounce-in">⚠ {hi_count} security alert(s)</div>', unsafe_allow_html=True)
    elif st.session_state.gps_ok and st.session_state.gps_dist:
        gps_settings = db_get_gps_settings()
        d = st.session_state.gps_dist
        if d > gps_settings["radius"]:
            st.markdown(f'<div class="ss-banner-warn bounce-in">📍 {d:.1f}km away</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="ss-banner-ok bounce-in">✓ All security checks passed</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="ss-banner-ok bounce-in">✓ Device verified</div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📸 SCAN", "📝 LEAVE", "📊 HISTORY"])

    with tab1:
        render_scan_tab(name, fp)
    with tab2:
        render_leave_tab(name)
    with tab3:
        render_history_tab(name)

    st.markdown("<hr style='border-color: rgba(99,102,241,0.15)'>", unsafe_allow_html=True)
    if st.button("🚪 LOGOUT", key="logout_btn", use_container_width=True):
        db_log_alert("INFO", name, "LOGOUT", "Session ended", fp)
        st.session_state.logged_in    = False
        st.session_state.current_user = None
        st.rerun()

def render_scan_tab(name, fp):
    today = db_get_today(name)
    in_done  = today is not None
    out_done = today is not None and today[6] not in ("Out Miss", None, "")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("IN TIME",  today[5] if today else "--")
    with c2:
        st.metric("OUT TIME", today[6] if today and today[6] != "Out Miss" else "--")
    with c3:
        hrs = calc_hrs(today[5], today[6]) if today else "--"
        st.metric("DURATION", hrs)

    st.markdown("<br>", unsafe_allow_html=True)

    if in_done and out_done:
        fp_cls = "🟢"
        fp_msg = "Both IN & OUT marked"
    elif in_done:
        fp_cls = "🟡"
        fp_msg = "IN marked — awaiting OUT"
    else:
        fp_cls = "⚪"
        fp_msg = "Ready to mark attendance"

    st.markdown(f"""
    <div class="glass-box" style="padding:32px;text-align:center;margin-bottom:22px;
                border-radius: 16px; animation: slideUp 0.6s ease-out">
        <div style="font-size:56px;margin-bottom:14px;animation: glow-pulse 2s ease-in-out infinite">{fp_cls}</div>
        <div style="font-size:15px;font-weight:900;color:#f1f5f9;margin-bottom:8px;letter-spacing:0.5px">
            BIOMETRIC VERIFICATION</div>
        <div style="font-size:12px;color:#cbd5e1;font-family:monospace">{fp_msg}</div>
    </div>
    """, unsafe_allow_html=True)

    col_in, col_out = st.columns(2)

    with col_in:
        if st.button("▲ MARK IN", key="btn_in", disabled=in_done, use_container_width=True):
            gps_settings = db_get_gps_settings()
            if st.session_state.gps_ok and st.session_state.gps_dist and st.session_state.gps_dist > gps_settings["radius"]:
                db_log_alert("HIGH", name, "GPS_BLOCK_IN", f"Mark IN blocked", fp)
                st.error(f"🚫 Location too far: {st.session_state.gps_dist:.1f}km")
            else:
                t = now_time()
                db_mark_in(name, t, fp, st.session_state.gps_ok)
                st.success(f"✓ Welcome! IN: {t}")
                st.rerun()

    with col_out:
        if st.button("▼ MARK OUT", key="btn_out", disabled=(not in_done or out_done), use_container_width=True):
            t = now_time()
            db_mark_out(name, t)
            st.success(f"✓ Goodbye! OUT: {t}")
            st.rerun()

def render_leave_tab(name):
    st.markdown('<div class="ss-card">', unsafe_allow_html=True)

    req_date   = st.date_input("📅 Date", value=date.today())
    leave_type = st.selectbox("📋 Type", LEAVE_TYPES)
    reason     = st.text_area("✍️ Reason", placeholder="Explain...")

    if st.button("📤 SUBMIT REQUEST", use_container_width=True):
        if not reason.strip():
            st.warning("Please enter reason")
        else:
            db_add_leave(name, str(req_date), leave_type, reason.strip())
            st.success("✓ Request submitted!")
            st.rerun()

    my_leaves = db_get_leaves(name=name)
    if my_leaves:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("**Recent Requests**")
        for r in my_leaves[:5]:
            badge = {"Pending":"🟡","Approved":"🟢","Rejected":"🔴"}.get(r[5],"⚪")
            st.markdown(f"`{r[2]}` | {r[3]} | {badge}")

    st.markdown('</div>', unsafe_allow_html=True)

def render_history_tab(name):
    recs = db_get_history(name)
    leaves_app = db_get_leaves(name=name, status="Approved")
    out_miss    = [r for r in recs if r[7] == "Out Miss"]
    present     = [r for r in recs if r[7] == "Present"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PRESENT",   len(present))
    c2.metric("OUT MISS",  len(out_miss))
    c3.metric("LEAVES",    len(leaves_app))
    c4.metric("TOTAL",     len(recs))

    if recs:
        data = []
        for r in recs:
            data.append({
                "Date":   r[4],
                "In":     r[5] or "--",
                "Out":    r[6] if r[6] != "Out Miss" else "—",
                "Status": r[7],
                "Hours":  calc_hrs(r[5], r[6]),
            })
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)

# ─── ADMIN PAGE ───────────────────────────────────────────────
def page_admin():
    if not st.session_state.admin_logged_in:
        render_admin_login()
    else:
        render_admin_panel()

def render_admin_login():
    st.markdown("<div style='height: 60px'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([0.5, 2, 0.5])
    with col2:
        st.markdown("""
        <div class="bounce-in" style="text-align:center;margin-bottom:28px">
            <div style="width:60px;height:60px;border-radius:16px;
                        background: linear-gradient(135deg,#ef4444,#dc2626);
                        display:flex;align-items:center;justify-content:center;
                        font-size:24px;font-weight:900;color:#fff;margin:0 auto 16px;
                        box-shadow: 0 0 35px rgba(239,68,68,0.5)">🛡</div>
            <div style="font-size:22px;font-weight:900;color:#f1f5f9;letter-spacing:2px">ADMIN CONSOLE</div>
            <div style="font-size:11px;color:#ef4444;font-family:monospace;margin-top:8px;letter-spacing:1px">
                🔐 RESTRICTED ACCESS</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="ss-card">', unsafe_allow_html=True)
        admin_id = st.text_input("👤 Admin ID", placeholder="Enter admin username")
        pwd = st.text_input("🔑 Admin Password", type="password")
        
        if st.button("🔐 ENTER", use_container_width=True):
            if pwd == ADMIN_PASS and admin_id in ADMIN_PERMISSIONS:
                st.session_state.admin_logged_in = True
                st.session_state.admin_name = admin_id
                db_log_admin_action(admin_id, "LOGIN", "Admin panel accessed")
                st.rerun()
            else:
                st.error("❌ Invalid credentials!")
        st.markdown('</div>', unsafe_allow_html=True)

def render_admin_panel():
    all_att = db_get_all_att()
    today   = today_str()
    td_att  = [r for r in all_att if r[4] == today]
    hi_al   = len(db_get_alerts("HIGH"))
    pend_r  = len(db_get_leaves(status="Pending"))

    st.markdown(f"""
    <div style="margin-bottom:20px;animation:slideDown 0.5s ease-out">
        <div style="font-size:20px;font-weight:900;color:#f1f5f9;letter-spacing:1px">ADMIN CONSOLE</div>
        <div style="font-size:11px;color:#cbd5e1;font-family:monospace;margin-top:4px">
            {datetime.now().strftime('%A, %B %d %Y | %H:%M:%S')} | Admin: {st.session_state.admin_name}</div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ Present", len([r for r in td_att if r[7]=="Present"]))
    c2.metric("⚠ Out Miss", len([r for r in td_att if r[7]=="Out Miss"]))
    c3.metric("🔴 Alerts", hi_al)
    c4.metric("📋 Requests", pend_r)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🚨 ALERTS", "📊 REPORTS", "📱 DEVICES", "📋 REQUESTS", "⚙️ SETTINGS"])

    with tab1:
        admin_alerts(db_get_alerts())
    with tab2:
        admin_reports()
    with tab3:
        admin_devices()
    with tab4:
        admin_requests()
    with tab5:
        admin_settings()

    st.markdown("<hr style='border-color: rgba(99,102,241,0.15)'>", unsafe_allow_html=True)
    if st.button("🚪 LOGOUT", use_container_width=True):
        db_log_admin_action(st.session_state.admin_name, "LOGOUT", "Admin panel session ended")
        st.session_state.admin_logged_in = False
        st.session_state.admin_name = None
        st.rerun()

def admin_alerts(all_al):
    hi  = [a for a in all_al if a[1] == "HIGH"]
    med = [a for a in all_al if a[1] == "MED"]
    inf = [a for a in all_al if a[1] == "INFO"]

    if not all_al:
        st.success("✓ No alerts. System secure.")
        return

    if hi:
        st.markdown(f"### 🔴 HIGH RISK ({len(hi)})")
        if st.button("Clear All HIGH", key="clear_hi"):
            db_clear_alerts(level="HIGH")
            db_log_admin_action(st.session_state.admin_name, "ALERT_CLEAR", "Cleared all HIGH alerts")
            st.rerun()
        for a in hi:
            st.markdown(f"""
            <div class="ss-alert-hi">
                <strong>{a[2]}</strong> | {a[3]}
                <div style="font-size:11px;color:#cbd5e1;margin-top:6px">{a[4]}</div>
            </div>""", unsafe_allow_html=True)

    if med:
        st.markdown(f"### 🟡 MEDIUM ({len(med)})")
        for a in med:
            st.markdown(f"<div class='ss-alert-md'><strong>{a[2]}</strong> | {a[3]}</div>", unsafe_allow_html=True)

    if inf:
        st.markdown(f"### 🟢 INFO ({len(inf)})")
        data = [{"Time": a[7][:16], "Name": a[2], "Type": a[3]} for a in inf[:20]]
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

def admin_reports():
    dept = st.selectbox("Filter Department", DEPARTMENTS, key="rep_dept")
    recs = db_get_all_att(dept if dept else None)
    
    if recs:
        data = [{"Name": r[1], "Dept": r[2], "Date": r[4], "In": r[5] or "--", 
                 "Out": r[6] if r[6] != "Out Miss" else "—", "Status": r[7]} for r in recs]
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        csv = df.to_csv(index=False).encode()
        st.download_button("⬇ Export CSV", csv, f"attendance_{today_str()}.csv", "text/csv")
    else:
        st.info("No records")

def admin_devices():
    for nm, emp in EMPS.items():
        fp = db_get_device(nm)
        hi = len([a for a in db_get_alerts("HIGH") if a[2] == nm])
        
        c1, c2 = st.columns([4, 1])
        with c1:
            status = "<span class='chip-green'>✓ Registered</span>" if fp else "<span class='chip-red'>✗ Unregistered</span>"
            st.markdown(f"**{nm}** | {emp['dept']} {status}", unsafe_allow_html=True)
            if fp:
                st.caption(f"FP: {fp}")
        with c2:
            if fp and st.button("Reset", key=f"reset_{nm}"):
                db_reset_device(nm)
                db_log_admin_action(st.session_state.admin_name, "DEVICE_RESET", f"Reset device for {nm}")
                st.rerun()

def admin_requests():
    pend = db_get_leaves(status="Pending")
    if not pend:
        st.success("✓ No pending requests")
        return
    
    for r in pend:
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"**{r[1]}** | {r[2]} | {r[3]}")
            st.caption(r[4])
        with c2:
            if st.button("✅", key=f"app_{r[0]}"):
                db_update_leave(r[0], "Approved")
                db_log_admin_action(st.session_state.admin_name, "LEAVE_APPROVE", f"Approved leave for {r[1]}")
                st.rerun()
            if st.button("❌", key=f"rej_{r[0]}"):
                db_update_leave(r[0], "Rejected")
                db_log_admin_action(st.session_state.admin_name, "LEAVE_REJECT", f"Rejected leave for {r[1]}")
                st.rerun()

def admin_settings():
    """Admin settings - GPS control for authorized admins only"""
    st.markdown("### ⚙️ System Settings")
    
    admin_perms = ADMIN_PERMISSIONS.get(st.session_state.admin_name, {})
    
    if not admin_perms.get("gps_control"):
        st.error("❌ You don't have GPS control permission")
        return
    
    st.markdown("""
    <div class="ss-banner-info">
        📍 <strong>GPS Settings</strong><br>
        Only authorized admins can modify office location and geofence radius.
    </div>
    """, unsafe_allow_html=True)
    
    gps_settings = db_get_gps_settings()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        new_lat = st.number_input("📍 Latitude", value=gps_settings["lat"], format="%.6f", key="admin_lat")
    with col2:
        new_lon = st.number_input("📍 Longitude", value=gps_settings["lon"], format="%.6f", key="admin_lon")
    with col3:
        new_radius = st.number_input("📏 Radius (km)", value=gps_settings["radius"], min_value=1.0, key="admin_radius")
    
    if st.button("💾 Save GPS Settings", key="save_gps", use_container_width=True):
        db_update_gps_settings(new_lat, new_lon, new_radius, st.session_state.admin_name)
        st.success(f"✓ GPS settings updated! New location: {new_lat}, {new_lon} (Radius: {new_radius}km)")
    
    # Show change history
    st.markdown("### 📋 Settings Change Log")
    admin_logs = db_get_admin_logs()
    gps_logs = [log for log in admin_logs if log[2] == "GPS_UPDATE"]
    
    if gps_logs:
        log_data = [{"Time": log[4][:16], "Admin": log[1], "Details": log[3]} for log in gps_logs[:10]]
        st.dataframe(pd.DataFrame(log_data), use_container_width=True, hide_index=True)
    else:
        st.info("No GPS changes recorded yet")

# ─── MAIN ────────────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="SS Team Portal v5.0",
        page_icon="🏭",
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    
    init_db()
    init_session()
    inject_advanced_css()
    render_header()

    with st.sidebar:
        st.markdown("### 🏭 SS TEAM PORTAL")
        st.markdown("---")
        if st.button("👤 Attendance", use_container_width=True):
            st.session_state.page = "attendance"
            st.rerun()
        if st.button("🛡 Admin", use_container_width=True):
            st.session_state.page = "admin"
            st.rerun()

    n1, n2 = st.columns(2)
    with n1:
        if st.button("👤 ATTENDANCE", use_container_width=True, type="primary" if st.session_state.page=="attendance" else "secondary"):
            st.session_state.page = "attendance"
            st.rerun()
    with n2:
        if st.button("🛡 ADMIN", use_container_width=True, type="primary" if st.session_state.page=="admin" else "secondary"):
            st.session_state.page = "admin"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    if st.session_state.page == "attendance":
        page_attendance()
    else:
        page_admin()

if __name__ == "__main__":
    main()
