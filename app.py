import csv, io, json, os, uuid
from datetime import datetime
from flask import Flask, jsonify, redirect, render_template, request, session, url_for, flash
from auth import login_required, APP_USERNAME, APP_PASSWORD
from categories import CATEGORIES, SUBCATEGORY_COLORS, CHASE_CATEGORY_MAP, auto_detect_subcategory
import github_store as store

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "personal-spending-secret-2026")


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "").strip()
        if u.lower() == APP_USERNAME.lower() and p.lower() == APP_PASSWORD.lower():
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
    txns = _filter(data["transactions"], year, month)

    cat_totals = {}
    sub_totals = {}

    for t in txns:
        cat = t["category"]
        amt = t["amount"]
        cat_totals[cat] = round(cat_totals.get(cat, 0) + amt, 2)

        if t.get("subcategory") and CATEGORIES.get(cat, {}).get("subcategories"):
            sub_totals.setdefault(cat, {})
            sub = t["subcategory"]
            sub_totals[cat][sub] = round(sub_totals[cat].get(sub, 0) + amt, 2)

    total = round(sum(cat_totals.values()), 2)

    months_available = sorted({t["date"][:7] for t in data["transactions"]}, reverse=True)
    years_available  = sorted({t["date"][:4] for t in data["transactions"]}, reverse=True)

    return jsonify({
        "categories":        cat_totals,
        "subcategories":     sub_totals,
        "total":             total,
        "count":             len(txns),
        "months_available":  months_available,
        "years_available":   years_available,
        "category_colors":   {k: v["color"]  for k, v in CATEGORIES.items()},
        "subcategory_colors": SUBCATEGORY_COLORS,
        "drillable":         [k for k, v in CATEGORIES.items() if v["subcategories"]],
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
    txns = _filter(data["transactions"], year, month)
    if category != "all":
        txns = [t for t in txns if t["category"] == category]

    txns = sorted(txns, key=lambda t: t["date"], reverse=True)
    total = len(txns)
    txns  = txns[(page-1)*per_page : page*per_page]

    return jsonify({"transactions": txns, "total": total, "page": page, "per_page": per_page})


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
    for t in data["transactions"]:
        if t["id"] == trans_id:
            t["category"]    = new_cat
            t["subcategory"] = new_sub
            store.save_data(data, sha)
            return jsonify({"success": True})

    return jsonify({"error": "Transaction not found"}), 404


@app.route("/api/upload-csv", methods=["POST"])
@login_required
def api_upload_csv():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400

    raw = request.files["file"].read()
    try:
        content = raw.decode("utf-8-sig")  # handles BOM
    except UnicodeDecodeError:
        content = raw.decode("latin-1")

    new_txns = _parse_chase_csv(content)
    if not new_txns:
        return jsonify({"error": "No valid transactions found. Is this a Chase CSV?"}), 400

    data, sha = store.get_data()

    existing = {f"{t['date']}|{t['description']}|{t['amount']}" for t in data["transactions"]}
    added = 0
    for t in new_txns:
        key = f"{t['date']}|{t['description']}|{t['amount']}"
        if key not in existing:
            data["transactions"].append(t)
            existing.add(key)
            added += 1

    store.save_data(data, sha)
    return jsonify({"success": True, "added": added, "total": len(data["transactions"])})


@app.route("/api/delete-transaction", methods=["POST"])
@login_required
def api_delete_transaction():
    trans_id = request.get_json().get("id")
    data, sha = store.get_data()
    before = len(data["transactions"])
    data["transactions"] = [t for t in data["transactions"] if t["id"] != trans_id]
    if len(data["transactions"]) < before:
        store.save_data(data, sha)
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404


# ── Helpers ───────────────────────────────────────────────────────────────────

def _filter(txns, year, month):
    if year  != "all": txns = [t for t in txns if t["date"][:4]  == year]
    if month != "all": txns = [t for t in txns if t["date"][5:7] == month.zfill(2)]
    return txns


def _parse_chase_csv(content):
    reader = csv.DictReader(io.StringIO(content))
    txns   = []
    for row in reader:
        try:
            amount = float(row.get("Amount", 0))
            if amount >= 0:
                continue  # skip payments/credits
            if row.get("Type", "").strip() == "Payment":
                continue

            amount      = round(abs(amount), 2)
            chase_cat   = row.get("Category", "Miscellaneous").strip()
            category    = CHASE_CATEGORY_MAP.get(chase_cat, "Miscellaneous")
            description = row.get("Description", "").strip()
            subcategory = auto_detect_subcategory(category, description)

            date_raw = row.get("Transaction Date", row.get("Post Date", "")).strip()
            try:
                date = datetime.strptime(date_raw, "%m/%d/%Y").strftime("%Y-%m-%d")
            except ValueError:
                date = date_raw

            txns.append({
                "id":                str(uuid.uuid4()),
                "date":              date,
                "description":       description,
                "amount":            amount,
                "category":          category,
                "subcategory":       subcategory,
                "original_category": category,
            })
        except (ValueError, KeyError):
            continue
    return txns


if __name__ == "__main__":
    app.run(debug=True)
