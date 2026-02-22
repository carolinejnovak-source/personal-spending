import csv, io, json, os, re, uuid
from datetime import datetime, date as dateobj
from dateutil.relativedelta import relativedelta
from flask import Flask, jsonify, redirect, render_template, request, session, url_for, flash
from auth import login_required, check_credentials
from categories import CATEGORIES, SUBCATEGORY_COLORS, CHASE_CATEGORY_MAP, auto_detect_subcategory
from error_log import register_error_handlers, log_error
import github_store as store

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "personal-spending-secret-2026")
register_error_handlers(app)


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "").strip()
        if check_credentials(u, p):
            session["logged_in"] = True
            session["username"]  = u
            return redirect(request.args.get("next") or url_for("index"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    return render_template("index.html",
        categories=CATEGORIES,
        category_names=list(CATEGORIES.keys()),
    )


# ── API ───────────────────────────────────────────────────────────────────────

@app.route("/api/chart-data")
@login_required
def api_chart_data():
    month = request.args.get("month", "all")
    year  = request.args.get("year",  "all")

    data, _ = store.get_data()
    txns = _filter(data.get("transactions", []), year, month)

    cat_totals = {}
    sub_totals = {}

    for t in txns:
        if t.get("amount", 0) <= 0:
            continue  # skip zeroed-out fully-returned transactions
        cat = t["category"]
        amt = t["amount"]
        cat_totals[cat] = round(cat_totals.get(cat, 0) + amt, 2)
        if t.get("subcategory") and CATEGORIES.get(cat, {}).get("subcategories"):
            sub_totals.setdefault(cat, {})
            sub = t["subcategory"]
            sub_totals[cat][sub] = round(sub_totals[cat].get(sub, 0) + amt, 2)

    total = round(sum(cat_totals.values()), 2)
    months_available = sorted({t["date"][:7] for t in data.get("transactions", [])}, reverse=True)
    years_available  = sorted({t["date"][:4] for t in data.get("transactions", [])}, reverse=True)

    return jsonify({
        "categories":         cat_totals,
        "subcategories":      sub_totals,
        "total":              total,
        "count":              len([t for t in txns if t.get("amount", 0) > 0]),
        "months_available":   months_available,
        "years_available":    years_available,
        "category_colors":    {k: v["color"]  for k, v in CATEGORIES.items()},
        "subcategory_colors": SUBCATEGORY_COLORS,
        "drillable":          [k for k, v in CATEGORIES.items() if v["subcategories"]],
    })


@app.route("/api/transactions")
@login_required
def api_transactions():
    month    = request.args.get("month",    "all")
    year     = request.args.get("year",     "all")
    category = request.args.get("category", "all")
    page     = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))

    data, _ = store.get_data()
    txns = _filter(data.get("transactions", []), year, month)
    if category != "all":
        txns = [t for t in txns if t["category"] == category]

    txns  = sorted(txns, key=lambda t: t["date"], reverse=True)
    total = len(txns)
    txns  = txns[(page-1)*per_page : page*per_page]

    # Also return credits for the filtered period
    credits = _filter(data.get("credits", []), year, month)
    credits = sorted(credits, key=lambda c: c["date"], reverse=True)

    return jsonify({"transactions": txns, "credits": credits, "total": total, "page": page, "per_page": per_page})


@app.route("/api/recategorize", methods=["POST"])
@login_required
def api_recategorize():
    body     = request.get_json()
    trans_id = body.get("id")
    new_cat  = body.get("category")
    new_sub  = body.get("subcategory", None)

    if new_cat not in CATEGORIES:
        return jsonify({"error": "Invalid category"}), 400

    data, sha = store.get_data()
    for t in data.get("transactions", []):
        if t["id"] == trans_id:
            t["category"]    = new_cat
            t["subcategory"] = new_sub
            store.save_data(data, sha)
            return jsonify({"success": True})

    return jsonify({"error": "Transaction not found"}), 404


@app.route("/api/edit-transaction", methods=["POST"])
@login_required
def api_edit_transaction():
    body     = request.get_json()
    trans_id = body.get("id")
    new_amt  = body.get("amount")
    new_note = body.get("notes")

    data, sha = store.get_data()
    for t in data.get("transactions", []):
        if t["id"] == trans_id:
            if new_amt is not None:
                try:
                    t["amount"] = round(float(new_amt), 2)
                except ValueError:
                    return jsonify({"error": "Invalid amount"}), 400
            if new_note is not None:
                t["notes"] = new_note.strip() or None
            store.save_data(data, sha)
            return jsonify({"success": True, "transaction": t})

    return jsonify({"error": "Transaction not found"}), 404


@app.route("/api/upload-csv", methods=["POST"])
@login_required
def api_upload_csv():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400

    raw = request.files["file"].read()
    try:    content = raw.decode("utf-8-sig")
    except: content = raw.decode("latin-1")

    new_txns, new_returns = _parse_chase_csv(content)
    if not new_txns and not new_returns:
        return jsonify({"error": "No valid transactions found. Is this a Chase CSV?"}), 400

    data, sha = store.get_data()

    # Deduplicate purchases
    existing_keys = {f"{t['date']}|{t['description']}|{t.get('original_amount', t['amount'])}" for t in data.get("transactions", [])}
    added_txns = []
    for t in new_txns:
        key = f"{t['date']}|{t['description']}|{t['amount']}"
        if key not in existing_keys:
            added_txns.append(t)
            existing_keys.add(key)

    # Match returns against all transactions (existing + new)
    all_txns = data.get("transactions", []) + added_txns
    existing_credits = data.get("credits", [])
    existing_credit_keys = {f"{c['date']}|{c['description']}|{c['amount']}" for c in existing_credits}

    new_credits = []
    for ret in new_returns:
        key = f"{ret['date']}|{ret['description']}|{ret['amount']}"
        if key not in existing_credit_keys:
            new_credits.append(ret)

    all_txns, unmatched = _match_returns(all_txns, new_credits)

    data["transactions"] = all_txns
    data["credits"] = existing_credits + unmatched
    store.save_data(data, sha)

    return jsonify({
        "success":  True,
        "added":    len(added_txns),
        "returns_matched": len(new_credits) - len(unmatched),
        "credits":  len(unmatched),
        "total":    len(data["transactions"]),
    })


@app.route("/api/delete-transaction", methods=["POST"])
@login_required
def api_delete_transaction():
    trans_id = request.get_json().get("id")
    data, sha = store.get_data()
    before = len(data.get("transactions", []))
    data["transactions"] = [t for t in data.get("transactions", []) if t["id"] != trans_id]
    if len(data["transactions"]) < before:
        store.save_data(data, sha)
        return jsonify({"success": True})
    # Try credits
    before = len(data.get("credits", []))
    data["credits"] = [c for c in data.get("credits", []) if c["id"] != trans_id]
    if len(data.get("credits", [])) < before:
        store.save_data(data, sha)
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404


@app.route("/api/delete-many", methods=["POST"])
@login_required
def api_delete_many():
    ids = set(request.get_json().get("ids", []))
    data, sha = store.get_data()
    before = len(data.get("transactions", [])) + len(data.get("credits", []))
    data["transactions"] = [t for t in data.get("transactions", []) if t["id"] not in ids]
    data["credits"]      = [c for c in data.get("credits", []) if c["id"] not in ids]
    removed = before - len(data.get("transactions", [])) - len(data.get("credits", []))
    if removed:
        store.save_data(data, sha)
    return jsonify({"success": True, "removed": removed})


# ── Helpers ───────────────────────────────────────────────────────────────────

def _filter(txns, year, month):
    if year  != "all": txns = [t for t in txns if t["date"][:4]  == year]
    if month != "all": txns = [t for t in txns if t["date"][5:7] == month.zfill(2)]
    return txns


def _normalize_vendor(desc):
    d = desc.upper()
    d = re.sub(r'\s*#\d+', '', d)
    d = re.sub(r'\b\d{5,}\b', '', d)
    for pat in [r'\.COM\b', r'\bMKTPL\*', r'\bMKTPLACE\b', r'\bSTORES?\b',
                r'\bFACTORY\b', r'^SP\s+', r'^TST\*', r'^SQ\s*\*', r'^DD\s*\*',
                r'^IC\*\s*', r'^BLT\*', r'^ACT\*', r'^FWD\*']:
        d = re.sub(pat, '', d)
    return d.strip()


def _vendors_match(d1, d2):
    v1, v2 = _normalize_vendor(d1), _normalize_vendor(d2)
    if v1 == v2: return True
    if len(v1) >= 4 and (v1 in v2 or v2 in v1): return True
    w1 = {w for w in v1.split() if len(w) >= 3}
    w2 = {w for w in v2.split() if len(w) >= 3}
    if w1 and w2:
        overlap = w1 & w2
        if overlap and len(overlap) / min(len(w1), len(w2)) >= 0.5:
            return True
    return False


def _match_returns(txns, returns):
    """Match returns to purchases. Returns (updated_txns, unmatched_returns)."""
    # Build a lookup of transactions by id for fast access
    txn_map = {t["id"]: t for t in txns}
    unmatched = []

    for ret in returns:
        ret_amt  = ret["amount"]
        ret_date = ret["date"]

        # Search this month + previous month
        try:
            rd = datetime.strptime(ret_date, "%Y-%m-%d")
            cutoff = (rd - relativedelta(months=2)).strftime("%Y-%m-%d")
        except:
            cutoff = "2000-01-01"

        best = None
        for t in txns:
            if t["date"] < cutoff or t["date"] > ret_date:
                continue
            if not _vendors_match(ret["description"], t["description"]):
                continue
            orig = t.get("original_amount", t["amount"])
            if orig >= ret_amt:
                if best is None or t["date"] > best["date"]:
                    best = t

        if best:
            orig = best.get("original_amount", best["amount"])
            best["original_amount"] = orig
            best["amount"] = round(orig - ret_amt, 2)
            best["notes"]  = "return" if ret_amt >= orig else "partial return"
            ret["matched"]     = True
            ret["matched_id"]  = best["id"]
        else:
            ret["matched"] = False
            unmatched.append(ret)

    return list(txn_map.values()), unmatched


def _parse_chase_csv(content):
    reader  = csv.DictReader(io.StringIO(content))
    txns    = []
    returns = []

    for row in reader:
        try:
            amount     = float(row.get("Amount", 0))
            trans_type = row.get("Type", "").strip()
            if trans_type == "Payment":
                continue

            desc      = row.get("Description", "").strip()
            chase_cat = row.get("Category", "Miscellaneous").strip()
            category  = CHASE_CATEGORY_MAP.get(chase_cat, "Miscellaneous")

            date_raw = row.get("Transaction Date", row.get("Post Date", "")).strip()
            post_raw = row.get("Post Date", "").strip()
            try:    date = datetime.strptime(date_raw, "%m/%d/%Y").strftime("%Y-%m-%d")
            except: date = date_raw
            try:    post_date = datetime.strptime(post_raw, "%m/%d/%Y").strftime("%Y-%m-%d")
            except: post_date = post_raw

            if amount < 0:
                amount = round(abs(amount), 2)
                sub    = auto_detect_subcategory(category, desc)
                txns.append({
                    "id":                str(uuid.uuid4()),
                    "date":              date,
                    "post_date":         post_date,
                    "description":       desc,
                    "amount":            amount,
                    "original_amount":   amount,
                    "category":          category,
                    "subcategory":       sub,
                    "original_category": category,
                    "notes":             None,
                })
            elif amount > 0 and trans_type in ("Return", "Credit"):
                returns.append({
                    "id":          str(uuid.uuid4()),
                    "date":        date,
                    "post_date":   post_date,
                    "description": desc,
                    "amount":      round(amount, 2),
                    "category":    category,
                    "matched":     False,
                    "matched_id":  None,
                })
        except (ValueError, KeyError):
            continue

    return txns, returns


if __name__ == "__main__":
    app.run(debug=True)
