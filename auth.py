"""
Auth module — multi-user username/password session login.
"""
from functools import wraps
from flask import session, redirect, url_for, request

# { username_lowercase: password_lowercase }
USERS = {
    "carolinejnovak": "crap",
    "david":          "ilovecaroline",
    "teresa":         "googlegoddess",
}

# Keep these for compatibility with shared login route
APP_USERNAME = "CarolineJNovak"
APP_PASSWORD = "crap"


def check_credentials(username, password):
    return USERS.get(username.lower()) == password.lower()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated
