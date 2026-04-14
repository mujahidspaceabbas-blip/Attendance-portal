"""
╔══════════════════════════════════════════════════════════╗
║    SS TEAM PORTAL — Animated UI + SQLite Backend         ║
║    Glassmorphism • Cyberpunk Aesthetic • Full Features    ║
║    Version 4.0 FINAL                                     ║
╚══════════════════════════════════════════════════════════╝
"""

import streamlit as st
import sqlite3
import hashlib
import math
from datetime import datetime, date
import pandas as pd
import os
import json

# ─── CONFIG ────────────────────────────────────────────────
OFFICE_LAT  = 30.124458
OFFICE_LON  = 71.386285
OFFICE_KM   = 96
ADMIN_PASS  = "admin123"
DB_PATH     = "ss_portal.db"

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

# ─── ADVANCED CSS WITH ANIMATIONS ──────────────────────────
def inject_advanced_css():
    """Inject glassmorphism + cyberpunk CSS with animations"""
    st.markdown("""
    <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    
    /* ── GLOBAL BACKGROUND ── */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMainBlockContainer"] {
        background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 50%, #0d1117 100%) !important;
        color: #e0e6ed !important;
        font-family: 'Segoe UI', 'Courier New', sans-serif !important;
        min-height: 100vh;
    }

    /* ── SCROLLBAR ── */
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: rgba(0,212,255,0.05); }
    ::-webkit-scrollbar-thumb { background: linear-gradient(180deg, #00d4ff, #0088aa); border-radius: 10px; }

    /* ── SIDEBAR ── */
    [data-testid="stSidebar"] { 
        background: linear-gradient(135deg, rgba(10,14,39,0.95), rgba(26,31,58,0.95)) !important; 
        border-right: 2px solid rgba(0,212,255,0.15) !important;
        backdrop-filter: blur(10px);
    }
    [data-testid="stSidebar"] * { color: #e0e6ed !important; }

    /* ── METRIC CARDS ── */
    [data-testid="metric-container"] {
        background: linear-gradient(135deg, rgba(0,212,255,0.08), rgba(0,136,170,0.05)) !important;
        border: 1.5px solid rgba(0,212,255,0.2) !important;
        border-radius: 15px !important;
        padding: 18px !important;
        backdrop-filter: blur(10px);
        box-shadow: 0 8px 32px rgba(0,212,255,0.1);
        transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    [data-testid="metric-container"]:hover {
        background: linear-gradient(135deg, rgba(0,212,255,0.15), rgba(0,136,170,0.1)) !important;
        border-color: rgba(0,212,255,0.4) !important;
        box-shadow: 0 12px 48px rgba(0,212,255,0.2) !important;
        transform: translateY(-4px);
    }
    [data-testid="stMetricValue"] { 
        color: #00d4ff !important; 
        font-size: 2rem !important; 
        font-weight: 800 !important;
        text-shadow: 0 0 20px rgba(0,212,255,0.5);
    }
    [data-testid="stMetricLabel"] { 
        color: #7a8fa6 !important; 
        font-size: 0.75rem !important; 
        text-transform: uppercase; 
        letter-spacing: 2px;
        font-weight: 700;
    }

    /* ── INPUTS ── */
    input, textarea, select, [data-baseweb="select"] {
        background: linear-gradient(135deg, rgba(20,28,38,0.8), rgba(13,17,23,0.8)) !important;
        border: 1.5px solid rgba(0,212,255,0.15) !important;
        color: #e0e6ed !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
        font-size: 14px !important;
        transition: all 0.3s ease !important;
        backdrop-filter: blur(10px);
    }
    input:focus, textarea:focus { 
        border-color: #00d4ff !important; 
        box-shadow: 0 0 20px rgba(0,212,255,0.3) !important;
        background: linear-gradient(135deg, rgba(0,212,255,0.1), rgba(0,136,170,0.05)) !important;
    }

    /* ── BUTTONS ── */
    .stButton > button {
        background: linear-gradient(135deg, #00d4ff, #0088aa) !important;
        color: #000 !important;
        font-weight: 800 !important;
        border: none !important;
        border-radius: 10px !important;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        font-size: 12px !important;
        padding: 12px 28px !important;
        transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
        box-shadow: 0 6px 20px rgba(0,212,255,0.3);
        position: relative;
        overflow: hidden;
    }
    .stButton > button::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
        transition: left 0.5s ease;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #00bbee, #0077aa) !important;
        box-shadow: 0 10px 40px rgba(0,212,255,0.5) !important;
        transform: translateY(-2px);
    }
    .stButton > button:hover::before { left: 100%; }

    /* ── TAB BAR ── */
    .stTabs [data-baseweb="tab-list"] {
        background: linear-gradient(90deg, rgba(20,28,38,0.6), rgba(26,37,47,0.6)) !important;
        border-radius: 12px !important;
        padding: 5px !important;
        gap: 5px !important;
        border: 1px solid rgba(0,212,255,0.1) !important;
        backdrop-filter: blur(10px);
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        color: #7a8fa6 !important;
        border-radius: 8px !important;
        font-size: 12px !important;
        font-weight: 700 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 10px 18px !important;
        transition: all 0.3s ease !important;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(0,212,255,0.15), rgba(0,136,170,0.1)) !important;
        color: #00d4ff !important;
        border: 1px solid rgba(0,212,255,0.3) !important;
        box-shadow: inset 0 0 15px rgba(0,212,255,0.2);
    }

    /* ── DATAFRAME ── */
    [data-testid="stDataFrame"] {
        border: 1.5px solid rgba(0,212,255,0.15) !important;
        border-radius: 10px !important;
        background: rgba(13,17,23,0.5) !important;
    }

    /* ── CUSTOM CARDS ── */
    .ss-card {
        background: linear-gradient(135deg, rgba(13,17,23,0.8), rgba(20,28,38,0.6)) !important;
        border: 1.5px solid rgba(0,212,255,0.15) !important;
        border-radius: 15px !important;
        padding: 20px 22px !important;
        margin-bottom: 14px !important;
        backdrop-filter: blur(10px);
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        transition: all 0.3s ease !important;
    }
    .ss-card:hover {
        border-color: rgba(0,212,255,0.25) !important;
        box-shadow: 0 12px 48px rgba(0,212,255,0.15) !important;
    }

    /* ── ALERTS ── */
    .ss-alert-hi {
        background: linear-gradient(135deg, rgba(255,68,68,0.08), rgba(255,100,100,0.04)) !important;
        border: 1.5px solid rgba(255,68,68,0.25) !important;
        border-radius: 10px !important;
        padding: 14px !important;
        margin-bottom: 10px !important;
        backdrop-filter: blur(10px);
        animation: pulse-red 2s ease-in-out infinite;
    }
    .ss-alert-md {
        background: linear-gradient(135deg, rgba(255,170,0,0.08), rgba(255,170,0,0.04)) !important;
        border: 1.5px solid rgba(255,170,0,0.2) !important;
        border-radius: 10px !important;
        padding: 14px !important;
        margin-bottom: 10px !important;
        backdrop-filter: blur(10px);
    }
    .ss-alert-lo {
        background: linear-gradient(135deg, rgba(0,230,118,0.08), rgba(0,230,118,0.04)) !important;
        border: 1.5px solid rgba(0,230,118,0.18) !important;
        border-radius: 10px !important;
        padding: 14px !important;
        margin-bottom: 10px !important;
        backdrop-filter: blur(10px);
    }

    /* ── BANNER ── */
    .ss-banner-ok {
        background: linear-gradient(135deg, rgba(0,230,118,0.08), rgba(0,200,150,0.05)) !important;
        border: 1.5px solid rgba(0,230,118,0.2) !important;
        color: #00e676 !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
        font-size: 13px !important;
        margin-bottom: 12px !important;
        backdrop-filter: blur(10px);
        animation: slide-in-down 0.5s ease-out;
    }
    .ss-banner-warn {
        background: linear-gradient(135deg, rgba(255,68,68,0.08), rgba(255,100,100,0.04)) !important;
        border: 1.5px solid rgba(255,68,68,0.2) !important;
        color: #ff4444 !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
        font-size: 13px !important;
        margin-bottom: 12px !important;
        backdrop-filter: blur(10px);
        animation: shake 0.5s ease;
    }
    .ss-banner-info {
        background: linear-gradient(135deg, rgba(0,212,255,0.08), rgba(0,136,170,0.05)) !important;
        border: 1.5px solid rgba(0,212,255,0.15) !important;
        color: #00d4ff !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
        font-size: 13px !important;
        margin-bottom: 12px !important;
        backdrop-filter: blur(10px);
    }

    /* ── CHIPS ── */
    .chip-green  { 
        background: linear-gradient(135deg, rgba(0,230,118,0.15), rgba(0,200,150,0.1)); 
        color:#00e676; 
        border:1.5px solid rgba(0,230,118,0.3); 
        border-radius:20px; 
        padding:4px 12px; 
        font-size:11px; 
        font-weight:700;
        display: inline-block;
        transition: all 0.3s ease;
    }
    .chip-green:hover { 
        background: linear-gradient(135deg, rgba(0,230,118,0.25), rgba(0,200,150,0.15));
        box-shadow: 0 0 15px rgba(0,230,118,0.3);
    }
    .chip-red    { 
        background:linear-gradient(135deg, rgba(255,68,68,0.15), rgba(255,100,100,0.1)); 
        color:#ff4444; 
        border:1.5px solid rgba(255,68,68,0.3); 
        border-radius:20px; 
        padding:4px 12px; 
        font-size:11px; 
        font-weight:700;
        display: inline-block;
        transition: all 0.3s ease;
    }
    .chip-red:hover {
        background: linear-gradient(135deg, rgba(255,68,68,0.25), rgba(255,100,100,0.15));
        box-shadow: 0 0 15px rgba(255,68,68,0.3);
    }
    .chip-amber  { 
        background:linear-gradient(135deg, rgba(255,170,0,0.15), rgba(255,200,0,0.1)); 
        color:#ffaa00; 
        border:1.5px solid rgba(255,170,0,0.3); 
        border-radius:20px; 
        padding:4px 12px; 
        font-size:11px; 
        font-weight:700;
        display: inline-block;
        transition: all 0.3s ease;
    }
    .chip-blue   { 
        background:linear-gradient(135deg, rgba(0,212,255,0.15), rgba(0,136,170,0.1)); 
        color:#00d4ff; 
        border:1.5px solid rgba(0,212,255,0.3); 
        border-radius:20px; 
        padding:4px 12px; 
        font-size:11px; 
        font-weight:700;
        display: inline-block;
        transition: all 0.3s ease;
    }

    /* ── ANIMATIONS ── */
    @keyframes pulse-red {
        0%, 100% { box-shadow: 0 0 20px rgba(255,68,68,0.2); }
        50% { box-shadow: 0 0 40px rgba(255,68,68,0.4); }
    }
    
    @keyframes slide-in-down {
        from {
            opacity: 0;
            transform: translateY(-20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        25% { transform: translateX(-5px); }
        75% { transform: translateX(5px); }
    }
    
    @keyframes glow-pulse {
        0%, 100% { text-shadow: 0 0 10px rgba(0,212,255,0.3); }
        50% { text-shadow: 0 0 20px rgba(0,212,255,0.6); }
    }
    
    @keyframes float-in {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @keyframes spin-slow {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }

    /* ── CUSTOM ANIMATIONS ── */
    .glow-text {
        animation: glow-pulse 2s ease-in-out infinite;
    }
    
    .float-in {
        animation: float-in 0.6s ease-out;
    }

    .spin {
        animation: spin-slow 3s linear infinite;
    }

    /* ── HOVER EFFECTS ── */
    .glass-box {
        background: linear-gradient(135deg, rgba(0,212,255,0.08), rgba(0,136,170,0.04)) !important;
        border: 1.5px solid rgba(0,212,255,0.2) !important;
        border-radius: 15px;
        backdrop-filter: blur(10px);
        transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    
    .glass-box:hover {
        background: linear-gradient(135deg, rgba(0,212,255,0.15), rgba(0,136,170,0.08)) !important;
        border-color: rgba(0,212,255,0.4) !important;
        box-shadow: 0 8px 32px rgba(0,212,255,0.15);
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
    <div style="background: linear-gradient(90deg, rgba(13,17,23,0.95), rgba(20,28,38,0.95));
                border-bottom: 2px solid rgba(0,212,255,0.15);
                padding: 15px 22px; display: flex; align-items: center;
                justify-content: space-between; margin-bottom: 20px; border-radius: 12px;
                backdrop-filter: blur(10px); box-shadow: 0 8px 32px rgba(0,0,0,0.3)">
        <div style="display:flex;align-items:center;gap:14px">
            <div style="width:40px;height:40px;border-radius:10px;
                        background: linear-gradient(135deg,#00d4ff,#0088aa);
                        display:flex;align-items:center;justify-content:center;
                        font-size:14px;font-weight:800;color:#000;
                        box-shadow: 0 0 20px rgba(0,212,255,0.4)">SS</div>
            <div>
                <div style="font-size:16px;font-weight:800;color:#e0e6ed;letter-spacing:1px">SS Team Portal</div>
                <div style="font-size:10px;color:#7a8fa6;font-family:monospace;margin-top:2px;letter-spacing:0.5px">
                    Anti-Spoof Security v4.0 | Glassmorphism UI</div>
            </div>
        </div>
        <div style="display:flex;align-items:center;gap:12px">
            <div style="font-family:monospace;font-size:12px;color:{'#ff4444' if hi_alerts else '#00e676'};
                        background: linear-gradient(135deg, rgba(0,212,255,0.1), rgba(0,136,170,0.05));
                        padding:7px 14px;border-radius:20px;
                        border: 1.5px solid rgba(0,212,255,0.2);
                        backdrop-filter: blur(10px);
                        font-weight: 700;
                        letter-spacing: 1px">
                {sec_status}
            </div>
            <div style="font-family:monospace;font-size:12px;color:#00d4ff;
                        background: linear-gradient(135deg, rgba(0,212,255,0.1), rgba(0,136,170,0.05));
                        padding:7px 14px;border-radius:20px;
                        border: 1.5px solid rgba(0,212,255,0.2);
                        backdrop-filter: blur(10px);
                        font-weight: 700">
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
        <div class="float-in" style="text-align:center;margin-bottom:28px">
            <div style="width:56px;height:56px;border-radius:14px;
                        background: linear-gradient(135deg,#00d4ff,#0088aa);
                        display:flex;align-items:center;justify-content:center;
                        font-size:22px;font-weight:800;color:#000;margin:0 auto 16px;
                        box-shadow: 0 0 30px rgba(0,212,255,0.5);
                        animation: glow-pulse 2s ease-in-out infinite">SS</div>
            <div style="font-size:20px;font-weight:800;color:#e0e6ed;letter-spacing:2px">SECURE LOGIN</div>
            <div style="font-size:10px;color:#7a8fa6;font-family:monospace;margin-top:6px;letter-spacing:1.5px">
                🔐 2-LAYER VERIFICATION</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="ss-card">', unsafe_allow_html=True)

        dev_fp = get_server_fp()
        st.session_state.device_fp = dev_fp

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, rgba(0,212,255,0.1), rgba(0,136,170,0.05));
                        border-radius:12px;padding:16px;text-align:center;
                        border: 1.5px solid rgba(0,212,255,0.2);
                        backdrop-filter: blur(10px);
                        transition: all 0.3s ease;
                        animation: float-in 0.6s ease-out">
                <div style="font-size:24px;margin-bottom:8px">📱</div>
                <div style="font-size:10px;font-family:monospace;color:#7a8fa6;font-weight:700;letter-spacing:1px">
                    DEVICE<br>FINGERPRINT</div>
                <div style="font-size:10px;font-weight:800;margin-top:8px;
                            font-family:monospace;color:#00d4ff;text-shadow: 0 0 10px rgba(0,212,255,0.4)">
                    ✓ READY</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, rgba(0,212,255,0.1), rgba(0,136,170,0.05));
                        border-radius:12px;padding:16px;text-align:center;
                        border: 1.5px solid rgba(0,212,255,0.2);
                        backdrop-filter: blur(10px);
                        transition: all 0.3s ease;
                        animation: float-in 0.6s ease-out 0.1s both">
                <div style="font-size:24px;margin-bottom:8px">📍</div>
                <div style="font-size:10px;font-family:monospace;color:#7a8fa6;font-weight:700;letter-spacing:1px">
                    GPS<br>LOCATION</div>
                <div style="font-size:10px;font-weight:800;margin-top:8px;
                            font-family:monospace;color:{'#00e676' if st.session_state.gps_ok else '#ffaa00'}">
                    {'✓ READY' if st.session_state.gps_ok else '⏳ WAITING'}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        name = st.selectbox("👤 Employee Name", ["-- Select --"] + list(EMPS.keys()), key="login_name")
        pin  = st.text_input("🔑 PIN", type="password", max_chars=6, key="login_pin", placeholder="Enter 4-digit PIN")

        with st.expander("📍 GPS Location", expanded=False):
            gc1, gc2 = st.columns(2)
            with gc1:
                lat_in = st.number_input("Latitude", value=OFFICE_LAT, format="%.6f", key="inp_lat")
            with gc2:
                lon_in = st.number_input("Longitude", value=OFFICE_LON, format="%.6f", key="inp_lon")
            if st.button("📍 Confirm Location", key="gps_btn", use_container_width=True):
                st.session_state.gps_lat  = lat_in
                st.session_state.gps_lon  = lon_in
                st.session_state.gps_ok   = True
                dist = calc_dist(lat_in, lon_in, OFFICE_LAT, OFFICE_LON)
                st.session_state.gps_dist = dist
                st.success(f"✓ GPS confirmed — {dist:.1f}km from office")

        if st.session_state.login_error:
            st.markdown(f'<div class="ss-banner-warn float-in">❌ {st.session_state.login_error}</div>',
                        unsafe_allow_html=True)
            st.session_state.login_error = ""

        if st.button("🔐 VERIFY & ENTER", key="login_btn", use_container_width=True):
            do_login(name, pin, dev_fp)

        st.markdown("""
        <div style="font-size:9px;color:#7a8fa6;text-align:center;margin-top:14px;
                    font-family:monospace;line-height:1.8;letter-spacing:0.5px">
            Your device is securely locked to your account.<br>
            <span style="color:#ff4444">⚠ Unauthorized device access triggers security alerts</span>
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
        d = st.session_state.gps_dist
        if d > OFFICE_KM:
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
    <div style="display:flex;align-items:center;gap:14px;padding:16px 18px;
                background: linear-gradient(135deg, rgba(0,212,255,0.08), rgba(0,136,170,0.04));
                border-radius:12px;border: 1.5px solid rgba(0,212,255,0.2);
                margin-bottom:16px;backdrop-filter: blur(10px);
                animation: float-in 0.6s ease-out">
        <div style="width:48px;height:48px;border-radius:50%;display:flex;
                    align-items:center;justify-content:center;font-size:14px;
                    font-weight:800;color:{emp['col']};
                    border: 2.5px solid {emp['col']};background:rgba(0,0,0,0.4);
                    box-shadow: 0 0 15px {emp['col']}40">
            {name[:2].upper()}
        </div>
        <div style="flex:1">
            <div style="font-size:15px;font-weight:800;color:#e0e6ed;letter-spacing:0.5px">{name}</div>
            <div style="font-size:11px;color:#7a8fa6;font-family:monospace;margin-top:2px">{emp['dept']} | {emp['desig']}</div>
        </div>
        <div style="font-size:10px;font-family:monospace;color:#00d4ff;
                    background: linear-gradient(135deg, rgba(0,212,255,0.1), rgba(0,136,170,0.05));
                    padding:7px 12px;border-radius:8px;border: 1px solid rgba(0,212,255,0.2);
                    backdrop-filter: blur(10px);font-weight:700;letter-spacing:0.5px">
            🔒 {fp[:12]}...
        </div>
    </div>
    """, unsafe_allow_html=True)

    if hi_count > 0:
        st.markdown(f'<div class="ss-banner-warn float-in">⚠ {hi_count} security alert(s)</div>', unsafe_allow_html=True)
    elif st.session_state.gps_ok and st.session_state.gps_dist:
        d = st.session_state.gps_dist
        if d > OFFICE_KM:
            st.markdown(f'<div class="ss-banner-warn float-in">📍 {d:.1f}km away</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="ss-banner-ok float-in">✓ All security checks passed</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="ss-banner-ok float-in">✓ Device verified</div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📸 SCAN", "📝 LEAVE", "📊 HISTORY"])

    with tab1:
        render_scan_tab(name, fp)
    with tab2:
        render_leave_tab(name)
    with tab3:
        render_history_tab(name)

    st.markdown("<hr style='border-color: rgba(0,212,255,0.1)'>", unsafe_allow_html=True)
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
    <div class="glass-box" style="padding:28px;text-align:center;margin-bottom:20px;
                border-radius: 15px; animation: float-in 0.6s ease-out">
        <div style="font-size:48px;margin-bottom:12px;animation: glow-pulse 2s ease-in-out infinite">{fp_cls}</div>
        <div style="font-size:14px;font-weight:800;color:#e0e6ed;margin-bottom:6px;letter-spacing:1px">
            BIOMETRIC VERIFICATION</div>
        <div style="font-size:11px;color:#7a8fa6;font-family:monospace">{fp_msg}</div>
    </div>
    """, unsafe_allow_html=True)

    col_in, col_out = st.columns(2)

    with col_in:
        if st.button("▲ MARK IN", key="btn_in", disabled=in_done, use_container_width=True):
            if st.session_state.gps_ok and st.session_state.gps_dist and st.session_state.gps_dist > OFFICE_KM:
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
        <div class="float-in" style="text-align:center;margin-bottom:24px">
            <div style="width:56px;height:56px;border-radius:14px;
                        background: linear-gradient(135deg,#ff4444,#aa1111);
                        display:flex;align-items:center;justify-content:center;
                        font-size:22px;font-weight:800;color:#fff;margin:0 auto 14px;
                        box-shadow: 0 0 30px rgba(255,68,68,0.5)">🛡</div>
            <div style="font-size:20px;font-weight:800;color:#e0e6ed;letter-spacing:2px">ADMIN CONSOLE</div>
            <div style="font-size:10px;color:#ff4444;font-family:monospace;margin-top:6px;letter-spacing:1px">
                🔐 RESTRICTED ACCESS</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="ss-card">', unsafe_allow_html=True)
        pwd = st.text_input("🔑 Admin Password", type="password")
        if st.button("🔐 ENTER", use_container_width=True):
            if pwd == ADMIN_PASS:
                st.session_state.admin_logged_in = True
                st.rerun()
            else:
                st.error("❌ Wrong password!")
        st.markdown('</div>', unsafe_allow_html=True)

def render_admin_panel():
    all_att = db_get_all_att()
    today   = today_str()
    td_att  = [r for r in all_att if r[4] == today]
    hi_al   = len(db_get_alerts("HIGH"))
    pend_r  = len(db_get_leaves(status="Pending"))

    st.markdown(f"""
    <div style="margin-bottom:18px">
        <div style="font-size:18px;font-weight:800;color:#e0e6ed;letter-spacing:1px">ADMIN CONSOLE</div>
        <div style="font-size:10px;color:#7a8fa6;font-family:monospace;margin-top:2px">
            {datetime.now().strftime('%A, %B %d %Y | %H:%M:%S')}</div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ Present", len([r for r in td_att if r[7]=="Present"]))
    c2.metric("⚠ Out Miss", len([r for r in td_att if r[7]=="Out Miss"]))
    c3.metric("🔴 Alerts", hi_al)
    c4.metric("📋 Requests", pend_r)

    tab1, tab2, tab3, tab4 = st.tabs(["🚨 ALERTS", "📊 REPORTS", "📱 DEVICES", "📋 REQUESTS"])

    with tab1:
        admin_alerts(db_get_alerts())
    with tab2:
        admin_reports()
    with tab3:
        admin_devices()
    with tab4:
        admin_requests()

    st.markdown("<hr style='border-color: rgba(0,212,255,0.1)'>", unsafe_allow_html=True)
    if st.button("🚪 LOGOUT", use_container_width=True):
        st.session_state.admin_logged_in = False
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
            st.rerun()
        for a in hi:
            st.markdown(f"""
            <div class="ss-alert-hi">
                <strong>{a[2]}</strong> | {a[3]}
                <div style="font-size:11px;color:#8899aa;margin-top:6px">{a[4]}</div>
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
            status = "<span class='chip-green'>Registered</span>" if fp else "<span class='chip-red'>Unregistered</span>"
            st.markdown(f"**{nm}** | {emp['dept']} {status}", unsafe_allow_html=True)
            if fp:
                st.caption(f"FP: {fp}")
        with c2:
            if fp and st.button("Reset", key=f"reset_{nm}"):
                db_reset_device(nm)
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
                st.rerun()
            if st.button("❌", key=f"rej_{r[0]}"):
                db_update_leave(r[0], "Rejected")
                st.rerun()

# ─── MAIN ────────────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="SS Team Portal v4.0",
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