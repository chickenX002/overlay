"""
server.py – TikTok Follower-Goal Stream Overlay Server
with built-in Web Config Panel (password protected)

Routes:
  /            → OBS Browser Source overlay
  /config      → Web config panel (password protected)
  /api/state   → GET current state (JSON)
  /api/config  → POST new settings (requires password header or session)

Set your admin password via env var:
  OVERLAY_PASSWORD=yourpassword python server.py

Default password: admin123
"""

from flask import Flask, jsonify, render_template_string, request, session, redirect, url_for
import threading
import requests
import time
import re
import os
import json

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "overlay-secret-key-change-me")

ADMIN_PASSWORD = os.environ.get("OVERLAY_PASSWORD", "admin123")

# ── Shared state ─────────────────────────────────────────────────────────────
state = {
    "username":        "",
    "goal":            1000,
    "current":         0,
    "title":           "Follower Goal",
    "bar_color":       "#ff2d55",
    "bg_color":        "#0a0a0a",
    "text_color":      "#ffffff",
    "show_count":      True,
    "font":            "Orbitron",
    "bar_style":       "gradient",   # gradient | solid | neon
    "animation":       "shine",      # shine | pulse | none
    "bar_height":      10,
    "border_radius":   16,
    "show_username":   True,
    "show_percent":    True,
    "last_updated":    0,
    "error":           "",
}
state_lock = threading.Lock()

FONTS = ["Orbitron", "Rajdhani", "Exo 2", "Audiowide", "Press Start 2P", "Bebas Neue", "Teko"]
BAR_STYLES = ["gradient", "solid", "neon", "striped"]
ANIMATIONS = ["shine", "pulse", "wave", "none"]

# ── TikTok scraper ────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

def fetch_tiktok_followers(username: str):
    username = username.lstrip("@").strip()
    if not username:
        return None
    url = f"https://www.tiktok.com/@{username}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        resp.raise_for_status()
        m = re.search(r'"followerCount"\s*:\s*(\d+)', resp.text)
        if m:
            return int(m.group(1))
        m2 = re.search(r'"stats":\{"followerCount":(\d+)', resp.text)
        if m2:
            return int(m2.group(1))
        with state_lock:
            state["error"] = "Could not parse follower count from TikTok."
    except requests.HTTPError as e:
        with state_lock:
            state["error"] = f"HTTP {e.response.status_code} for @{username}"
    except Exception as e:
        with state_lock:
            state["error"] = str(e)
    return None

def _immediate_fetch():
    with state_lock:
        username = state["username"]
    if username:
        count = fetch_tiktok_followers(username)
        with state_lock:
            if count is not None:
                state["current"] = count
                state["error"] = ""
                state["last_updated"] = int(time.time())

def poller():
    while True:
        _immediate_fetch()
        time.sleep(60)

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def overlay():
    return render_template_string(OVERLAY_HTML)

@app.route("/api/state")
def api_state():
    with state_lock:
        return jsonify(dict(state))

@app.route("/api/config", methods=["POST"])
def api_config():
    if not session.get("authed"):
        # Allow Tkinter app via header
        if request.headers.get("X-Overlay-Password") != ADMIN_PASSWORD:
            return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(force=True)
    with state_lock:
        for key in ("username","goal","title","bar_color","bg_color","text_color",
                    "show_count","font","bar_style","animation","bar_height",
                    "border_radius","show_username","show_percent"):
            if key in data:
                state[key] = data[key]
    threading.Thread(target=_immediate_fetch, daemon=True).start()
    return jsonify({"ok": True})

@app.route("/config", methods=["GET", "POST"])
def config_panel():
    error = ""
    if not session.get("authed"):
        if request.method == "POST" and "password" in request.form:
            if request.form["password"] == ADMIN_PASSWORD:
                session["authed"] = True
                return redirect(url_for("config_panel"))
            else:
                error = "Wrong password. Try again."
        return render_template_string(LOGIN_HTML, error=error)
    with state_lock:
        s = dict(state)
    return render_template_string(CONFIG_HTML, state=s,
                                  fonts=FONTS, bar_styles=BAR_STYLES,
                                  animations=ANIMATIONS)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("config_panel"))

# ── Login page ────────────────────────────────────────────────────────────────
LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Overlay Config – Login</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet"/>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{
  background:#080c12;min-height:100vh;display:flex;align-items:center;justify-content:center;
  font-family:'DM Sans',sans-serif;
  background-image:radial-gradient(ellipse at 20% 50%,#ff2d5511 0%,transparent 60%),
                   radial-gradient(ellipse at 80% 20%,#ff2d5508 0%,transparent 50%);
}
.card{
  background:#0f1520;border:1px solid #1e2d40;border-radius:20px;
  padding:48px 40px;width:100%;max-width:380px;
  box-shadow:0 20px 60px rgba(0,0,0,.5);
}
.logo{
  font-family:'Orbitron',monospace;font-size:11px;font-weight:700;
  letter-spacing:.2em;text-transform:uppercase;color:#ff2d55;
  margin-bottom:8px;
}
h1{font-family:'Orbitron',monospace;font-size:20px;color:#fff;margin-bottom:6px}
.sub{font-size:13px;color:#4b6070;margin-bottom:36px}
label{display:block;font-size:12px;font-weight:500;color:#6b8090;margin-bottom:6px;letter-spacing:.05em}
input[type=password]{
  width:100%;padding:12px 16px;background:#151e2a;border:1px solid #1e2d40;
  border-radius:10px;color:#fff;font-size:14px;outline:none;
  transition:border-color .2s;font-family:'DM Sans',sans-serif;
}
input[type=password]:focus{border-color:#ff2d55}
.error{background:#ff2d5515;border:1px solid #ff2d5540;border-radius:8px;
  padding:10px 14px;font-size:13px;color:#ff6b80;margin-top:12px}
button{
  width:100%;margin-top:20px;padding:13px;background:#ff2d55;border:none;
  border-radius:10px;color:#fff;font-family:'Orbitron',monospace;
  font-size:12px;font-weight:700;letter-spacing:.1em;cursor:pointer;
  transition:background .2s,transform .1s;
}
button:hover{background:#e02246}
button:active{transform:scale(.98)}
</style>
</head>
<body>
<div class="card">
  <div class="logo">🎯 TikTok Overlay</div>
  <h1>Config Panel</h1>
  <p class="sub">Enter your admin password to continue</p>
  <form method="POST">
    <label>PASSWORD</label>
    <input type="password" name="password" autofocus placeholder="••••••••"/>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <button type="submit">UNLOCK →</button>
  </form>
</div>
</body>
</html>"""

# ── Config panel ──────────────────────────────────────────────────────────────
CONFIG_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Overlay Config Panel</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet"/>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#080c12;--card:#0f1520;--border:#1e2d40;
  --text:#e2eaf0;--muted:#4b6070;--accent:#ff2d55;
}
body{
  background:var(--bg);min-height:100vh;font-family:'DM Sans',sans-serif;
  color:var(--text);padding:24px;
  background-image:radial-gradient(ellipse at 10% 0%,#ff2d5510 0%,transparent 50%);
}

/* ── Layout ── */
.topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:28px}
.brand{font-family:'Orbitron',monospace;font-size:13px;color:var(--accent);letter-spacing:.15em}
.logout{font-size:12px;color:var(--muted);text-decoration:none;
  border:1px solid var(--border);padding:6px 14px;border-radius:8px;
  transition:all .2s}
.logout:hover{color:var(--text);border-color:#ff2d5560}

.grid{display:grid;grid-template-columns:1fr 380px;gap:20px;max-width:1100px;margin:0 auto}

/* ── Cards ── */
.card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:24px}
.card-title{font-family:'Orbitron',monospace;font-size:10px;font-weight:700;
  letter-spacing:.2em;text-transform:uppercase;color:var(--accent);margin-bottom:18px}

/* ── Form elements ── */
.field{margin-bottom:16px}
.field label{display:block;font-size:12px;font-weight:500;color:var(--muted);
  margin-bottom:6px;letter-spacing:.04em}
input[type=text],input[type=number],select{
  width:100%;padding:10px 14px;background:#151e2a;border:1px solid var(--border);
  border-radius:9px;color:var(--text);font-size:13px;outline:none;
  transition:border-color .2s;font-family:'DM Sans',sans-serif;
}
input:focus,select:focus{border-color:var(--accent)}
select option{background:#151e2a}

.row2{display:grid;grid-template-columns:1fr 1fr;gap:12px}

/* Color picker row */
.color-field{display:flex;align-items:center;gap:10px}
.color-field input[type=color]{
  width:40px;height:36px;padding:2px;background:#151e2a;
  border:1px solid var(--border);border-radius:8px;cursor:pointer;
}
.color-field input[type=text]{flex:1}

/* Toggle */
.toggle-row{display:flex;align-items:center;justify-content:space-between;
  padding:10px 0;border-bottom:1px solid var(--border)}
.toggle-row:last-child{border-bottom:none}
.toggle-row span{font-size:13px;color:var(--text)}
.toggle{position:relative;width:40px;height:22px}
.toggle input{opacity:0;width:0;height:0}
.slider{position:absolute;inset:0;background:#1e2d40;border-radius:99px;cursor:pointer;transition:.3s}
.slider:before{content:'';position:absolute;width:16px;height:16px;left:3px;top:3px;
  background:#fff;border-radius:50%;transition:.3s}
input:checked + .slider{background:var(--accent)}
input:checked + .slider:before{transform:translateX(18px)}

/* Range */
input[type=range]{
  width:100%;accent-color:var(--accent);
  background:transparent;cursor:pointer;
}
.range-row{display:flex;align-items:center;gap:10px}
.range-val{font-family:'Orbitron',monospace;font-size:11px;color:var(--accent);min-width:28px;text-align:right}

/* Apply button */
.apply-btn{
  width:100%;padding:14px;background:var(--accent);border:none;border-radius:11px;
  color:#fff;font-family:'Orbitron',monospace;font-size:12px;font-weight:700;
  letter-spacing:.12em;cursor:pointer;transition:background .2s,transform .1s;
  margin-top:8px;
}
.apply-btn:hover{background:#e02246}
.apply-btn:active{transform:scale(.98)}
.toast{
  display:none;text-align:center;font-size:13px;color:#34d399;
  padding:10px;border-radius:8px;background:#34d39915;border:1px solid #34d39930;
  margin-top:10px;
}

/* ── Preview panel ── */
.preview-panel{position:sticky;top:24px}
.preview-wrap{
  border-radius:12px;overflow:hidden;padding:32px 20px;
  background:repeating-conic-gradient(#141a24 0% 25%,#111720 0% 50%) 0 0/20px 20px;
  display:flex;align-items:center;justify-content:center;
  min-height:160px;margin-bottom:16px;
}
.overlay-preview{
  display:flex;flex-direction:column;gap:8px;
  padding:18px 24px;border-radius:16px;
  background:var(--prev-bg,#0a0a0a);
  box-shadow:0 8px 30px rgba(0,0,0,.5);
  min-width:280px;max-width:340px;
  border:1px solid rgba(255,255,255,.06);
}
.prev-title{font-size:10px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;
  color:var(--prev-text,#fff);opacity:.6}
.prev-uname{font-size:10px;color:var(--prev-bar,#ff2d55);font-weight:600;margin-top:-4px}
.prev-counts{display:flex;justify-content:space-between;align-items:baseline;
  color:var(--prev-text,#fff)}
.prev-current{font-size:26px;font-weight:900;line-height:1}
.prev-goal{font-size:12px;opacity:.55}
.prev-track{width:100%;height:10px;border-radius:99px;background:rgba(255,255,255,.1);overflow:hidden}
.prev-fill{height:100%;border-radius:99px;background:var(--prev-bar,#ff2d55);
  box-shadow:0 0 10px var(--prev-bar,#ff2d55);width:35%;transition:width .6s}
.prev-pct{font-size:10px;font-weight:700;color:var(--prev-bar,#ff2d55);text-align:right}

.url-box{background:#151e2a;border:1px solid var(--border);border-radius:10px;padding:14px}
.url-label{font-size:11px;color:var(--muted);margin-bottom:6px;font-weight:500}
.url-row{display:flex;align-items:center;gap:8px}
.url-text{font-family:'Courier New',monospace;font-size:12px;color:#34d399;
  flex:1;word-break:break-all;line-height:1.4}
.copy-btn{padding:6px 12px;background:#1e2d40;border:1px solid var(--border);
  border-radius:7px;color:var(--text);font-size:11px;cursor:pointer;
  white-space:nowrap;transition:all .2s}
.copy-btn:hover{background:#273548;border-color:var(--accent)}

.status{font-size:12px;color:var(--muted);margin-top:12px;padding-top:12px;
  border-top:1px solid var(--border);display:flex;align-items:center;gap:6px}
.dot{width:7px;height:7px;border-radius:50%;background:#ef4444;flex-shrink:0}
.dot.ok{background:#34d399}
</style>
</head>
<body>

<div class="topbar">
  <div class="brand">🎯 TIKTOK OVERLAY CONFIG</div>
  <a href="/logout" class="logout">Log out</a>
</div>

<div class="grid">

  <!-- ── Left: Settings ── -->
  <div>

    <!-- TikTok -->
    <div class="card" style="margin-bottom:16px">
      <div class="card-title">TikTok Settings</div>
      <div class="row2">
        <div class="field">
          <label>TIKTOK USERNAME</label>
          <input type="text" id="username" value="{{ state.username }}" placeholder="username (no @)"/>
        </div>
        <div class="field">
          <label>FOLLOWER GOAL</label>
          <input type="number" id="goal" value="{{ state.goal }}" min="1"/>
        </div>
      </div>
      <div class="field">
        <label>OVERLAY TITLE</label>
        <input type="text" id="title" value="{{ state.title }}"/>
      </div>
    </div>

    <!-- Appearance -->
    <div class="card" style="margin-bottom:16px">
      <div class="card-title">Appearance</div>

      <div class="field">
        <label>FONT FAMILY</label>
        <select id="font">
          {% for f in fonts %}
          <option value="{{ f }}" {% if state.font == f %}selected{% endif %}>{{ f }}</option>
          {% endfor %}
        </select>
      </div>

      <div class="row2">
        <div class="field">
          <label>BAR STYLE</label>
          <select id="bar_style">
            {% for s in bar_styles %}
            <option value="{{ s }}" {% if state.bar_style == s %}selected{% endif %}>{{ s|capitalize }}</option>
            {% endfor %}
          </select>
        </div>
        <div class="field">
          <label>ANIMATION</label>
          <select id="animation">
            {% for a in animations %}
            <option value="{{ a }}" {% if state.animation == a %}selected{% endif %}>{{ a|capitalize }}</option>
            {% endfor %}
          </select>
        </div>
      </div>

      <div class="row2">
        <div class="field">
          <label>BAR HEIGHT (px)</label>
          <div class="range-row">
            <input type="range" id="bar_height" min="4" max="24" value="{{ state.bar_height }}"
              oninput="document.getElementById('bh_val').textContent=this.value;updatePreview()"/>
            <span class="range-val" id="bh_val">{{ state.bar_height }}</span>
          </div>
        </div>
        <div class="field">
          <label>BORDER RADIUS (px)</label>
          <div class="range-row">
            <input type="range" id="border_radius" min="0" max="32" value="{{ state.border_radius }}"
              oninput="document.getElementById('br_val').textContent=this.value;updatePreview()"/>
            <span class="range-val" id="br_val">{{ state.border_radius }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Colors -->
    <div class="card" style="margin-bottom:16px">
      <div class="card-title">Colors</div>
      <div class="field">
        <label>PROGRESS BAR COLOR</label>
        <div class="color-field">
          <input type="color" id="bar_color_pick" value="{{ state.bar_color }}" oninput="syncColor('bar_color','bar_color_pick')"/>
          <input type="text"  id="bar_color"      value="{{ state.bar_color }}" oninput="syncColorText('bar_color','bar_color_pick')"/>
        </div>
      </div>
      <div class="field">
        <label>BACKGROUND COLOR</label>
        <div class="color-field">
          <input type="color" id="bg_color_pick" value="{{ state.bg_color }}" oninput="syncColor('bg_color','bg_color_pick')"/>
          <input type="text"  id="bg_color"      value="{{ state.bg_color }}" oninput="syncColorText('bg_color','bg_color_pick')"/>
        </div>
      </div>
      <div class="field">
        <label>TEXT COLOR</label>
        <div class="color-field">
          <input type="color" id="text_color_pick" value="{{ state.text_color }}" oninput="syncColor('text_color','text_color_pick')"/>
          <input type="text"  id="text_color"      value="{{ state.text_color }}" oninput="syncColorText('text_color','text_color_pick')"/>
        </div>
      </div>
    </div>

    <!-- Visibility toggles -->
    <div class="card" style="margin-bottom:16px">
      <div class="card-title">Visibility</div>
      <div class="toggle-row">
        <span>Show follower count</span>
        <label class="toggle"><input type="checkbox" id="show_count" {% if state.show_count %}checked{% endif %}/><span class="slider"></span></label>
      </div>
      <div class="toggle-row">
        <span>Show username</span>
        <label class="toggle"><input type="checkbox" id="show_username" {% if state.show_username %}checked{% endif %}/><span class="slider"></span></label>
      </div>
      <div class="toggle-row">
        <span>Show percentage</span>
        <label class="toggle"><input type="checkbox" id="show_percent" {% if state.show_percent %}checked{% endif %}/><span class="slider"></span></label>
      </div>
    </div>

    <button class="apply-btn" onclick="applySettings()">▶ APPLY SETTINGS</button>
    <div class="toast" id="toast">✓ Settings applied!</div>

  </div>

  <!-- ── Right: Preview + URL ── -->
  <div class="preview-panel">
    <div class="card">
      <div class="card-title">Live Preview</div>
      <div class="preview-wrap">
        <div class="overlay-preview" id="prev_box">
          <div class="prev-title" id="prev_title">Follower Goal</div>
          <div class="prev-uname" id="prev_uname">@username</div>
          <div class="prev-counts">
            <span class="prev-current" id="prev_current">–</span>
            <span class="prev-goal" id="prev_goal">/ 1,000</span>
          </div>
          <div class="prev-track" id="prev_track">
            <div class="prev-fill" id="prev_fill"></div>
          </div>
          <div class="prev-pct" id="prev_pct">0.0%</div>
        </div>
      </div>

      <div class="url-box">
        <div class="url-label">OBS BROWSER SOURCE URL</div>
        <div class="url-row">
          <span class="url-text" id="overlay_url">{{ request.host_url }}</span>
          <button class="copy-btn" onclick="copyUrl()">Copy</button>
        </div>
      </div>

      <div class="status">
        <div class="dot" id="status_dot"></div>
        <span id="status_text">Connecting…</span>
      </div>
    </div>
  </div>

</div>

<script>
// ── Sync color pickers ───────────────────────────────────────────────────
function syncColor(textId, pickId) {
  document.getElementById(textId).value = document.getElementById(pickId).value;
  updatePreview();
}
function syncColorText(textId, pickId) {
  const v = document.getElementById(textId).value;
  if (/^#[0-9a-fA-F]{6}$/.test(v)) {
    document.getElementById(pickId).value = v;
    updatePreview();
  }
}

// ── Live preview ─────────────────────────────────────────────────────────
function updatePreview() {
  const bg   = document.getElementById('bg_color').value;
  const bar  = document.getElementById('bar_color').value;
  const txt  = document.getElementById('text_color').value;
  const br   = document.getElementById('border_radius').value;
  const bh   = document.getElementById('bar_height').value;

  const box = document.getElementById('prev_box');
  box.style.setProperty('--prev-bg',  bg);
  box.style.setProperty('--prev-bar', bar);
  box.style.setProperty('--prev-text',txt);
  box.style.background = bg;
  box.style.borderRadius = br + 'px';

  document.getElementById('prev_title').textContent =
    document.getElementById('title').value || 'Follower Goal';
  const uname = document.getElementById('username').value;
  document.getElementById('prev_uname').textContent =
    document.getElementById('show_username').checked && uname ? '@'+uname : '';
  document.getElementById('prev_goal').textContent =
    '/ ' + Number(document.getElementById('goal').value).toLocaleString();

  const track = document.getElementById('prev_track');
  track.style.height = bh + 'px';
  track.style.borderRadius = '99px';
  const fill = document.getElementById('prev_fill');
  fill.style.height = bh + 'px';
  fill.style.background = bar;
  fill.style.boxShadow = `0 0 10px ${bar}`;

  document.getElementById('prev_pct').style.color = bar;
  document.getElementById('prev_pct').style.display =
    document.getElementById('show_percent').checked ? '' : 'none';
  document.getElementById('prev_current').style.display =
    document.getElementById('show_count').checked ? '' : 'none';

  // Font preview
  const font = document.getElementById('font').value;
  loadFont(font);
  document.getElementById('prev_current').style.fontFamily = `'${font}', monospace`;
  document.getElementById('prev_title').style.fontFamily   = `'${font}', monospace`;
  document.getElementById('prev_pct').style.fontFamily     = `'${font}', monospace`;
}

function loadFont(name) {
  const id = 'gf-' + name.replace(/\s/g,'');
  if (!document.getElementById(id)) {
    const l = document.createElement('link');
    l.id   = id;
    l.rel  = 'stylesheet';
    l.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(name)}:wght@700;900&display=swap`;
    document.head.appendChild(l);
  }
}

// ── Apply settings ────────────────────────────────────────────────────────
async function applySettings() {
  const payload = {
    username:      document.getElementById('username').value.trim().replace(/^@/,''),
    goal:          parseInt(document.getElementById('goal').value),
    title:         document.getElementById('title').value.trim() || 'Follower Goal',
    bar_color:     document.getElementById('bar_color').value,
    bg_color:      document.getElementById('bg_color').value,
    text_color:    document.getElementById('text_color').value,
    show_count:    document.getElementById('show_count').checked,
    show_username: document.getElementById('show_username').checked,
    show_percent:  document.getElementById('show_percent').checked,
    font:          document.getElementById('font').value,
    bar_style:     document.getElementById('bar_style').value,
    animation:     document.getElementById('animation').value,
    bar_height:    parseInt(document.getElementById('bar_height').value),
    border_radius: parseInt(document.getElementById('border_radius').value),
  };
  try {
    const r = await fetch('/api/config', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    if (r.ok) {
      const t = document.getElementById('toast');
      t.style.display = 'block';
      setTimeout(() => t.style.display='none', 2500);
    }
  } catch(e) { alert('Error: ' + e); }
}

// ── Copy URL ──────────────────────────────────────────────────────────────
function copyUrl() {
  const url = document.getElementById('overlay_url').textContent;
  navigator.clipboard.writeText(url).catch(() => {
    const el = document.createElement('textarea');
    el.value = url; document.body.appendChild(el);
    el.select(); document.execCommand('copy'); document.body.removeChild(el);
  });
  const btn = document.querySelector('.copy-btn');
  btn.textContent = 'Copied!'; btn.style.color = '#34d399';
  setTimeout(() => { btn.textContent='Copy'; btn.style.color=''; }, 1500);
}

// ── Status + follower count poller ────────────────────────────────────────
async function pollStatus() {
  try {
    const s = await fetch('/api/state').then(r=>r.json());
    const dot  = document.getElementById('status_dot');
    const txt  = document.getElementById('status_text');
    dot.className = 'dot ok';
    const fmt = n => n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e3?(n/1e3).toFixed(1)+'K':String(n);
    const pct = s.goal>0?Math.min(100,(s.current/s.goal)*100):0;
    txt.textContent = s.error
      ? '⚠ ' + s.error
      : `${fmt(s.current)} followers · ${pct.toFixed(1)}%`;

    // Update preview count
    document.getElementById('prev_current').textContent = fmt(s.current);
    const fillPct = s.goal>0?Math.min(100,(s.current/s.goal)*100):0;
    document.getElementById('prev_fill').style.width = fillPct.toFixed(1)+'%';
    document.getElementById('prev_pct').textContent   = fillPct.toFixed(1)+'%';
  } catch(_) {
    document.getElementById('status_dot').className = 'dot';
    document.getElementById('status_text').textContent = 'Server unreachable';
  }
  setTimeout(pollStatus, 5000);
}

// Init
document.querySelectorAll('input,select').forEach(el => {
  el.addEventListener('change', updatePreview);
  el.addEventListener('input',  updatePreview);
});
updatePreview();
pollStatus();
</script>
</body>
</html>"""

# ── Overlay HTML (the page OBS loads) ────────────────────────────────────────
OVERLAY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Follower Goal Overlay</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:transparent;overflow:hidden;font-family:var(--font,'Orbitron'),monospace}

.overlay{
  display:inline-flex;flex-direction:column;gap:8px;
  padding:18px 24px;
  border-radius:var(--br,16px);
  background:var(--bg,#0a0a0aee);
  box-shadow:0 8px 40px rgba(0,0,0,.55);
  min-width:300px;max-width:480px;
  border:1px solid rgba(255,255,255,.07);
  animation:fadeIn .6s ease both;
}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}

.title{font-size:11px;font-weight:700;letter-spacing:.2em;text-transform:uppercase;
  color:var(--text,#fff);opacity:.6}
.uname{font-size:11px;color:var(--bar,#ff2d55);font-weight:600;margin-top:-4px}
.counts{display:flex;justify-content:space-between;align-items:baseline;color:var(--text,#fff)}
.current{font-size:30px;font-weight:900;line-height:1}
.goal-num{font-size:13px;opacity:.55}

.track{width:100%;border-radius:99px;background:rgba(255,255,255,.1);overflow:hidden}
.fill{
  height:100%;border-radius:99px;
  background:var(--bar,#ff2d55);
  transition:width 1.4s cubic-bezier(.4,0,.2,1);
  box-shadow:0 0 14px var(--bar,#ff2d55);
  position:relative;overflow:hidden;
}

/* Animations */
.anim-shine .fill::after{
  content:'';position:absolute;inset:0;
  background:linear-gradient(90deg,transparent 55%,rgba(255,255,255,.25));
  animation:shine 2.5s ease-in-out infinite;
}
.anim-pulse .fill{animation:pulse 2s ease-in-out infinite}
.anim-wave  .fill::after{
  content:'';position:absolute;inset:0;
  background:repeating-linear-gradient(90deg,transparent,transparent 8px,rgba(255,255,255,.12) 8px,rgba(255,255,255,.12) 16px);
  animation:wave 1.2s linear infinite;
}

@keyframes shine{0%,100%{opacity:0}50%{opacity:1}}
@keyframes pulse{0%,100%{box-shadow:0 0 10px var(--bar)}50%{box-shadow:0 0 24px var(--bar)}}
@keyframes wave{from{background-position-x:0}to{background-position-x:32px}}

/* Bar styles */
.bar-gradient .fill{background:linear-gradient(90deg,var(--bar),color-mix(in srgb,var(--bar) 70%,#fff))}
.bar-neon .fill{
  background:var(--bar);
  box-shadow:0 0 8px var(--bar),0 0 20px var(--bar),0 0 40px var(--bar);
}
.bar-striped .fill{
  background:repeating-linear-gradient(45deg,var(--bar),var(--bar) 10px,
    color-mix(in srgb,var(--bar) 80%,#000) 10px,color-mix(in srgb,var(--bar) 80%,#000) 20px);
  background-size:200% 100%;animation:stripes 1s linear infinite;
}
@keyframes stripes{from{background-position-x:0}to{background-position-x:40px}}

.pct{font-size:11px;font-weight:700;color:var(--bar,#ff2d55);text-align:right}
.err{font-size:10px;color:#ff7070;margin-top:2px}
</style>
</head>
<body>
<div class="overlay" id="box">
  <div class="title"  id="title">Follower Goal</div>
  <div class="uname"  id="uname"></div>
  <div class="counts">
    <span class="current"  id="current">–</span>
    <span class="goal-num" id="goal">–</span>
  </div>
  <div class="track" id="track"><div class="fill" id="fill" style="width:0%"></div></div>
  <div class="pct" id="pct">0.0%</div>
  <div class="err" id="err"></div>
</div>

<script>
const $ = id => document.getElementById(id);
const fmt = n => n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e3?(n/1e3).toFixed(1)+'K':String(n);
let loadedFonts = new Set();

function loadFont(name) {
  if (loadedFonts.has(name)) return;
  loadedFonts.add(name);
  const l = document.createElement('link');
  l.rel  = 'stylesheet';
  l.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(name)}:wght@700;900&display=swap`;
  document.head.appendChild(l);
}

function applyState(s) {
  const b = $('box');
  b.style.setProperty('--bg',   s.bg_color  + 'ee');
  b.style.setProperty('--text', s.text_color);
  b.style.setProperty('--bar',  s.bar_color);
  b.style.setProperty('--br',   (s.border_radius ?? 16) + 'px');
  b.style.setProperty('--font', "'" + (s.font||'Orbitron') + "'");

  loadFont(s.font || 'Orbitron');

  // Animation class
  b.className = 'overlay anim-' + (s.animation||'shine') + ' bar-' + (s.bar_style||'gradient');

  $('title').textContent = s.title || 'Follower Goal';
  $('uname').style.display = s.show_username ? '' : 'none';
  $('uname').textContent   = s.username ? '@'+s.username : '';
  $('goal').textContent    = '/ ' + fmt(s.goal);
  $('err').textContent     = s.error || '';

  $('current').style.display = s.show_count ? '' : 'none';
  $('current').textContent   = fmt(s.current);

  $('track').style.height      = (s.bar_height ?? 10) + 'px';
  $('track').style.borderRadius = '99px';

  const pct = s.goal > 0 ? Math.min(100, (s.current / s.goal) * 100) : 0;
  $('fill').style.width = pct.toFixed(2) + '%';

  $('pct').style.display  = s.show_percent ? '' : 'none';
  $('pct').textContent    = pct.toFixed(1) + '%';
}

async function poll() {
  try { applyState(await fetch('/api/state').then(r=>r.json())); } catch(_){}
  setTimeout(poll, 5000);
}
poll();
</script>
</body>
</html>"""

# ── Entry point ───────────────────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", os.environ.get("OVERLAY_PORT", 5050)))

def run_server():
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

if __name__ == "__main__":
    threading.Thread(target=poller, daemon=True).start()
    print(f"[Overlay]  http://localhost:{PORT}/")
    print(f"[Config]   http://localhost:{PORT}/config  (password: {ADMIN_PASSWORD})")
    run_server()
