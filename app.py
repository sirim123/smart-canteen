import os
import re
import logging
from datetime import datetime, timezone
from functools import wraps

from bson import ObjectId
from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from flask_wtf.csrf import CSRFProtect
from pymongo import MongoClient, DESCENDING
from pymongo.errors import PyMongoError
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "development-only-change-this"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 4,
)
csrf = CSRFProtect(app)

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "smart_canteen")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI is missing. Add it to your .env file or deployment environment.")

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
db = client[DB_NAME]
users = db["users"]
menu = db["menu"]
orders = db["orders"]

ORDER_STATUSES = ["Received", "Preparing", "Ready", "Completed", "Cancelled"]


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    try:
        return users.find_one({"_id": ObjectId(user_id)}, {"password_hash": 0})
    except Exception:
        return None


@app.context_processor
def inject_user():
    return {"logged_in_user": current_user()}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        if user.get("role") != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def seed_menu():
    """Insert starter products only when the menu collection is empty."""
    if menu.count_documents({}) == 0:
        starter_items = [
            {"name": "Veg Sandwich", "category": "Snacks", "price": 45, "description": "Fresh vegetable sandwich", "available": True, "emoji": "🥪"},
            {"name": "Masala Dosa", "category": "South Indian", "price": 60, "description": "Crispy dosa with chutney and sambar", "available": True, "emoji": "🥞"},
            {"name": "Veg Fried Rice", "category": "Meals", "price": 80, "description": "Vegetable fried rice", "available": True, "emoji": "🍚"},
            {"name": "Paneer Roll", "category": "Snacks", "price": 70, "description": "Paneer wrapped in a soft roll", "available": True, "emoji": "🌯"},
            {"name": "Lime Juice", "category": "Drinks", "price": 25, "description": "Fresh lime cooler", "available": True, "emoji": "🍋"},
            {"name": "Tea", "category": "Drinks", "price": 15, "description": "Hot tea", "available": True, "emoji": "☕"},
        ]
        menu.insert_many(starter_items)


def bootstrap_admin():
    """Create the first admin from environment variables; never hard-code credentials."""
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    if email and password and not users.find_one({"email": email}):
        users.insert_one({
            "name": "Canteen Administrator",
            "email": email,
            "password_hash": generate_password_hash(password),
            "role": "admin",
            "created_at": datetime.now(timezone.utc),
        })


@app.route("/")
def index():
    try:
        seed_menu()
        items = list(menu.find({"available": True}).sort("category", 1))
        return render_template("index.html", items=items)
    except PyMongoError:
        return render_template("error.html", message="The cloud database is temporarily unavailable."), 503


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or len(name) > 80 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            flash("Enter a valid name and email address.", "danger")
        elif len(password) < 8:
            flash("Password must contain at least 8 characters.", "danger")
        elif users.find_one({"email": email}):
            flash("An account with this email already exists.", "danger")
        else:
            users.insert_one({
                "name": name,
                "email": email,
                "password_hash": generate_password_hash(password),
                "role": "student",
                "created_at": datetime.now(timezone.utc),
            })
            flash("Account created. You can now log in.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = users.find_one({"email": email})
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = str(user["_id"])
            session.permanent = True
            flash(f"Welcome, {user['name']}!", "success")
            return redirect(url_for("admin_dashboard" if user["role"] == "admin" else "my_orders"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/order", methods=["POST"])
@login_required
def place_order():
    user = current_user()
    item_ids = request.form.getlist("item_id")
    quantities = request.form.getlist("quantity")
    if not item_ids or len(item_ids) != len(quantities):
        flash("Please select at least one menu item.", "warning")
        return redirect(url_for("index"))

    order_items = []
    total = 0
    try:
        for item_id, quantity_text in zip(item_ids, quantities):
            quantity = int(quantity_text)
            if quantity < 1 or quantity > 20:
                raise ValueError
            item = menu.find_one({"_id": ObjectId(item_id), "available": True})
            if item:
                line_total = int(item["price"]) * quantity
                order_items.append({
                    "item_id": str(item["_id"]),
                    "name": item["name"],
                    "price": int(item["price"]),
                    "quantity": quantity,
                    "line_total": line_total,
                })
                total += line_total
    except (ValueError, TypeError):
        flash("Invalid quantity or menu item.", "danger")
        return redirect(url_for("index"))
    except Exception:
        flash("One of the selected menu items is invalid.", "danger")
        return redirect(url_for("index"))

    if not order_items:
        flash("No available items were selected.", "warning")
        return redirect(url_for("index"))

    orders.insert_one({
        "user_id": str(user["_id"]),
        "student_name": user["name"],
        "student_email": user["email"],
        "items": order_items,
        "total": total,
        "status": "Received",
        "created_at": datetime.now(timezone.utc),
    })
    flash("Your order has been placed successfully!", "success")
    return redirect(url_for("my_orders"))


@app.route("/my-orders")
@login_required
def my_orders():
    try:
        user = current_user()

        if not user:
            flash("Please log in again.", "warning")
            return redirect(url_for("login"))

        print("MY ORDERS: User ID:", user["_id"])

        user_orders = list(
            orders.find({
                "user_id": str(user["_id"])
            }).sort("created_at", DESCENDING)
        )

        print("MY ORDERS: Records found:", len(user_orders))

        return render_template(
            "my_orders.html",
            orders=user_orders
        )

    except Exception as e:
        app.logger.exception("ERROR IN MY ORDERS ROUTE")
        return f"My Orders Error: {str(e)}", 500

def admin_dashboard():
    all_orders = list(orders.find().sort("created_at", DESCENDING).limit(100))
    all_items = list(menu.find().sort("category", 1))
    stats = {
        "orders": orders.count_documents({}),
        "pending": orders.count_documents({"status": "Received"}),
        "preparing": orders.count_documents({"status": "Preparing"}),
        "menu_items": menu.count_documents({}),
    }
    return render_template("admin.html", orders=all_orders, items=all_items, stats=stats, statuses=ORDER_STATUSES)


@app.route("/admin/order/<order_id>/status", methods=["POST"])
@admin_required
def update_order_status(order_id):
    status = request.form.get("status")
    if status not in ORDER_STATUSES:
        abort(400)
    try:
        result = orders.update_one({"_id": ObjectId(order_id)}, {"$set": {"status": status}})
    except Exception:
        abort(404)
    if result.matched_count == 0:
        abort(404)
    flash("Order status updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/menu/add", methods=["POST"])
@admin_required
def add_menu_item():
    name = request.form.get("name", "").strip()
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    emoji = request.form.get("emoji", "🍽️").strip()[:8]
    try:
        price = int(request.form.get("price", ""))
        if not name or not category or price < 1 or price > 10000:
            raise ValueError
    except ValueError:
        flash("Enter a name, category and valid price.", "danger")
        return redirect(url_for("admin_dashboard"))
    menu.insert_one({
        "name": name[:80], "category": category[:40], "description": description[:200],
        "emoji": emoji, "price": price, "available": True,
    })
    flash("Menu item added.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/menu/<item_id>/toggle", methods=["POST"])
@admin_required
def toggle_menu_item(item_id):
    try:
        item = menu.find_one({"_id": ObjectId(item_id)})
    except Exception:
        abort(404)
    if not item:
        abort(404)
    menu.update_one({"_id": item["_id"]}, {"$set": {"available": not item.get("available", True)}})
    flash("Menu availability updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", message="You do not have permission to access this page."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", message="The requested page or record was not found."), 404

@app.errorhandler(500)
def server_error(error):
    err = getattr(error, "original_exception", error)
    return render_template("error.html", message=f"{type(err).__name__}: {err}"), 500
if __name__ == "__main__":
    # Local development only. Render runs the app with Gunicorn.
    bootstrap_admin()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
