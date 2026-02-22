"""
In-memory error logger + /errors route.
Import and call register_error_handlers(app) in app.py.
"""
import traceback
from datetime import datetime, timezone
from collections import deque
from flask import render_template_string, session, redirect, url_for
from auth import login_required

MAX_ERRORS = 200
_errors = deque(maxlen=MAX_ERRORS)

def log_error(error, context=""):
    _errors.appendleft({
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "error":     type(error).__name__,
        "message":   str(error),
        "traceback": traceback.format_exc(),
        "context":   context,
    })

def register_error_handlers(app):
    @app.errorhandler(Exception)
    def handle_exception(e):
        log_error(e, context="unhandled exception")
        return render_template_string(ERROR_PAGE, error=e), 500

    @app.route("/errors")
    @login_required
    def errors_page():
        return render_template_string(ERRORS_PAGE, errors=list(_errors))


ERROR_PAGE = """
<!DOCTYPE html><html><head><title>Error</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet"/>
</head><body class="bg-light p-4">
<div class="container"><div class="alert alert-danger">
<h5>Something went wrong</h5><pre class="mb-0" style="font-size:.8rem">{{ error }}</pre>
</div><a href="/" class="btn btn-sm btn-secondary">← Back</a>
<a href="/errors" class="btn btn-sm btn-outline-danger ms-2">View error log</a>
</div></body></html>
"""

ERRORS_PAGE = """
<!DOCTYPE html><html><head><title>Error Log</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet"/>
</head><body style="background:#f5f0ff">
<div class="container py-4">
  <div class="d-flex align-items-center justify-content-between mb-3">
    <h5 class="fw-bold mb-0">🪲 Error Log</h5>
    <a href="/" class="btn btn-sm btn-outline-secondary">← Dashboard</a>
  </div>
  {% if not errors %}
    <div class="alert alert-success">No errors logged. All good! 🎉</div>
  {% else %}
    <div class="text-muted small mb-3">{{ errors|length }} error(s) since last restart — most recent first.</div>
    {% for e in errors %}
    <div class="card mb-3 border-0 shadow-sm">
      <div class="card-body">
        <div class="d-flex justify-content-between mb-1">
          <span class="fw-semibold text-danger">{{ e.error }}: {{ e.message }}</span>
          <span class="text-muted small">{{ e.timestamp }}</span>
        </div>
        {% if e.context %}<div class="text-muted small mb-2">Context: {{ e.context }}</div>{% endif %}
        <pre class="bg-light p-2 rounded" style="font-size:.75rem;max-height:200px;overflow-y:auto;margin:0">{{ e.traceback }}</pre>
      </div>
    </div>
    {% endfor %}
  {% endif %}
</div></body></html>
"""
