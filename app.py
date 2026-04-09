import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from flask_wtf.csrf import CSRFProtect
import bcrypt

app = Flask(__name__)

# Secret key for sessions - in production, load this from an environment variable
app.secret_key = os.environ.get("SECRET_KEY", "change-this-in-production")

# CSRF protection - this token is verified on every POST request
csrf = CSRFProtect(app)

# Tighten up session cookies a bit
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,   # JS can't read the cookie
    SESSION_COOKIE_SAMESITE="Lax",  # helps prevent CSRF
)

DATABASE = "users.db"


# ---------- database helpers ----------

def get_db():
    """Open a db connection that lives for the duration of the request."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT    NOT NULL UNIQUE,
            password TEXT    NOT NULL   -- stores the bcrypt hash, never plaintext
        )
        """
    )
    db.commit()


# ---------- routes ----------

@app.route("/")
def index():
    return redirect(url_for("dashboard") if "user_id" in session else url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        # Basic validation
        if not username or not password:
            flash("Both fields are required.", "error")
            return render_template("register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("register.html")

        # bcrypt handles the salt automatically - we never store the raw password
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, hashed),
            )
            db.commit()
            flash("Account created! You can log in now.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That username is already taken.", "error")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        # bcrypt.checkpw does a constant-time comparison to avoid timing attacks
        if user and bcrypt.checkpw(password.encode(), user["password"]):
            session.clear()             # clear any leftover session data first
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))
        else:
            # Same message for wrong username OR wrong password (don't leak which one)
            flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html", username=session["username"])


@app.route("/logout")
def logout():
    session.clear()
    flash("You've been logged out.", "info")
    return redirect(url_for("login"))


# ---------- entry point ----------

if __name__ == "__main__":
    with app.app_context():
        init_db()
    # debug=False in any real deployment
    app.run(debug=True)
