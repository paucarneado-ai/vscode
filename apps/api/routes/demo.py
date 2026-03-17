from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

_DEMO_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>OpenClaw — Lead Intake Demo</title>
<style>
body { font-family: system-ui, sans-serif; max-width: 480px; margin: 40px auto; padding: 0 16px; }
h1 { font-size: 1.3rem; }
label { display: block; margin-top: 12px; font-size: 0.9rem; font-weight: 600; }
input, textarea { width: 100%; padding: 6px; margin-top: 4px; box-sizing: border-box; font-size: 0.9rem; }
button { margin-top: 16px; padding: 8px 20px; font-size: 0.9rem; cursor: pointer; }
#result { margin-top: 16px; padding: 10px; font-size: 0.85rem; display: none; border: 1px solid #ccc; }
.ok { border-color: #2a2; background: #efd; }
.dup { border-color: #a80; background: #fec; }
.err { border-color: #a22; background: #fdd; }
</style>
</head>
<body>
<h1>OpenClaw — Lead Intake Demo</h1>
<form id="f">
  <label>Name *<input name="name" required></label>
  <label>Email *<input name="email" type="email" required></label>
  <label>Source *<input name="source" placeholder="landing:demo" required></label>
  <label>Phone<input name="phone"></label>
  <label>Notes<textarea name="notes" rows="3"></textarea></label>
  <button type="submit">Submit Lead</button>
</form>
<div id="result"></div>
<p style="margin-top:24px;font-size:0.75rem;color:#888;">Internal demo only — not a production surface.</p>
<script>
document.getElementById('f').addEventListener('submit', async function(e) {
  e.preventDefault();
  const d = Object.fromEntries(new FormData(this));
  if (!d.phone) delete d.phone;
  if (!d.notes) delete d.notes;
  const r = document.getElementById('result');
  r.style.display = 'none';
  try {
    const res = await fetch('/leads/external', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(d)
    });
    const j = await res.json();
    r.style.display = 'block';
    if (res.status === 200) {
      r.className = 'ok';
      r.textContent = 'Lead accepted — ID: ' + j.lead_id + ', score: ' + j.score;
    } else if (res.status === 409) {
      r.className = 'dup';
      r.textContent = 'Duplicate — lead already exists (ID: ' + j.lead_id + ')';
    } else {
      r.className = 'err';
      r.textContent = 'Error ' + res.status + ': ' + (j.detail || JSON.stringify(j));
    }
  } catch (err) {
    r.style.display = 'block';
    r.className = 'err';
    r.textContent = 'Network error: ' + err.message;
  }
});
</script>
</body>
</html>
"""


@router.get("/demo/intake", response_class=HTMLResponse)
def demo_intake_form() -> HTMLResponse:
    """Demo-only disposable surface — not an official frontend.

    Serves a minimal inline HTML form that submits to POST /leads/external.
    The form exposes the minimum visible subset of ExternalLeadPayload
    (name, email, source, phone, notes).  The ``metadata`` field accepted
    by ExternalLeadPayload is intentionally omitted from this form.
    """
    return HTMLResponse(
        content=_DEMO_HTML,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
