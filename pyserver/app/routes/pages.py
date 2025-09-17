from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter()


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page():
    # Minimal HTML login page with a real "Forgot Password" button that calls the API
    html = """
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Future-Compass - Login</title>
        <style>
          body { font-family: system-ui, Arial, Helvetica, sans-serif; background:#f6f8fb; margin:0; }
          .wrap { max-width: 420px; margin: 8vh auto; background:#fff; border:1px solid #e6e9ef; border-radius:8px; padding:24px; }
          h1 { font-size: 20px; margin: 0 0 16px; color:#0b1f33; text-align:center; }
          label { display:block; margin: 8px 0 4px; color:#0b1f33; font-weight:600; }
          input { width: 100%; padding: 10px 12px; border-radius:6px; border:1px solid #cbd5e1; font-size:14px; }
          .row { display:flex; gap: 8px; align-items:center; margin-top: 12px; }
          .btn { cursor:pointer; background:#0b6efb; color:#fff; border:none; border-radius:6px; padding:10px 14px; font-weight:600; }
          .btn.secondary { background:#eef2ff; color:#0b1f33; }
          .muted { color:#6b7280; font-size:12px; margin-top:8px; }
          .msg { margin-top: 12px; font-size: 14px; }
          .msg.ok { color: #065f46; }
          .msg.err { color: #7f1d1d; }
          .between { display:flex; justify-content:space-between; align-items:center; gap: 10px; }
        </style>
      </head>
      <body>
        <div class="wrap">
          <h1>Sign in</h1>
          <label for="email">Email</label>
          <input id="email" type="email" placeholder="you@example.com" />
          <label for="password">Password</label>
          <input id="password" type="password" placeholder="********" />
          <div class="row between">
            <button class="btn" id="loginBtn">Login</button>
            <button class="btn secondary" id="forgotBtn" type="button">Forgot Password</button>
          </div>
          <div class="msg" id="msg"></div>
          <p class="muted">This demo page posts to the API endpoints directly.</p>
        </div>
        <script>
          const $ = (id) => document.getElementById(id);
          function showMsg(text, ok=false){
            const el = $('msg');
            el.textContent = text;
            el.className = 'msg ' + (ok ? 'ok' : 'err');
          }
          $('loginBtn').addEventListener('click', async () => {
            const email = $('email').value.trim();
            const password = $('password').value;
            if(!email || !password){ return showMsg('Enter email and password'); }
            try{
              const r = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
              });
              const data = await r.json();
              if(r.ok){ showMsg('Logged in', true); }
              else{ showMsg(data?.message || data?.detail || 'Login failed'); }
            }catch(e){ showMsg('Network error'); }
          });
          $('forgotBtn').addEventListener('click', async () => {
            const email = $('email').value.trim();
            if(!email){ return showMsg('Enter your email first'); }
            try{
              const r = await fetch('/api/auth/forgot-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email })
              });
              if(r.ok){ showMsg('If the email exists, a reset link was sent.', true); }
              else{
                let data; try{ data = await r.json(); }catch(e){}
                showMsg(data?.message || data?.detail || 'Unable to send reset link');
              }
            }catch(e){ showMsg('Network error'); }
          });
        </script>
      </body>
    </html>
    """
    return HTMLResponse(content=html)

