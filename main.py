import hmac
import os
import re
import time
import uuid
from datetime import timezone
from functools import wraps
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from sqlalchemy.orm import selectinload

import media
import storage
from models import STATUSES, Order, OrderItem, db

load_dotenv()  # reads FLASK/.env when running locally


def database_uri():
    url = os.environ.get("DATABASE_URL") or "sqlite:///campusprint.db"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
    MAX_CONTENT_LENGTH=25 * 1024 * 1024,  # total size of one upload request
    SQLALCHEMY_DATABASE_URI=database_uri(),
    SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
db.init_app(app)
with app.app_context():
    db.create_all()

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
CONTENT_TYPES = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}
PRINT_TYPES = {"bw", "color"}
MAX_FILES = 10
MAX_COPIES = 100
PHONE_RE = re.compile(r"^[0-9+\-\s]{7,20}$")
IST = ZoneInfo("Asia/Kolkata")


class UploadRejected(Exception):
    """A file failed validation; the message is shown to the student."""


@app.template_filter("ist")
def ist(dt, fmt="%d %b, %I:%M %p"):
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST).strftime(fmt)


def clean_filename(name):
    name = name.replace("\\", "/").split("/")[-1]
    name = "".join(ch for ch in name if ch.isprintable())
    return name.strip()[:120] or "document"


def file_ext(name):
    return name.rsplit(".", 1)[1].lower() if "." in name else ""


def form_errors(errors, status=400):
    for e in errors:
        flash(e, "danger")
    return render_template("index.html", form=request.form), status


# ---------------------------------------------------------------- students

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("index.html", form={})

    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    classroom = request.form.get("classroom", "").strip()
    files = [f for f in request.files.getlist("documents") if f and f.filename]
    types = request.form.getlist("print_type")
    copies_raw = request.form.getlist("copies")

    errors = []
    if not name:
        errors.append("Please enter your name.")
    elif len(name) > 80:
        errors.append("Name is too long (max 80 characters).")
    if phone and not PHONE_RE.match(phone):
        errors.append("Please enter a valid phone number, or leave it blank.")
    if not classroom:
        errors.append("Please enter a delivery classroom / location.")
    elif len(classroom) > 100:
        errors.append("Location is too long (max 100 characters).")

    options = []
    if not files:
        errors.append("Please choose at least one file to upload.")
    elif len(files) > MAX_FILES:
        errors.append(f"You can upload at most {MAX_FILES} files per order.")
    elif len(types) != len(files) or len(copies_raw) != len(files):
        errors.append("Something went wrong with the file options. Please try again.")
    else:
        for f, ptype, c in zip(files, types, copies_raw):
            label = clean_filename(f.filename)
            ext = file_ext(label)
            try:
                copies = int(c)
            except ValueError:
                copies = 0
            if ext not in ALLOWED_EXTENSIONS:
                errors.append(f"'{label}': only PDF, PNG, JPG and JPEG are allowed.")
            elif ptype not in PRINT_TYPES:
                errors.append(f"'{label}': invalid print type.")
            elif not 1 <= copies <= MAX_COPIES:
                errors.append(f"'{label}': copies must be between 1 and {MAX_COPIES}.")
            else:
                options.append((f, label, ext, ptype, copies))

    if errors:
        return form_errors(errors)

    order = Order(name=name, phone=phone or None, classroom=classroom)
    uploaded_keys = []
    try:
        db.session.add(order)
        db.session.flush()  # gives the order an id

        for f, label, ext, ptype, copies in options:
            data = f.read()
            try:
                pages, thumb = media.inspect(data, ext)
            except ValueError as exc:
                raise UploadRejected(f"'{label}': {exc}") from exc

            key = f"orders/{order.id}/{uuid.uuid4().hex}.{ext}"
            storage.save(key, data, CONTENT_TYPES[ext])
            uploaded_keys.append(key)

            thumb_key = None
            if thumb:
                thumb_key = key.rsplit(".", 1)[0] + "_thumb.jpg"
                storage.save(thumb_key, thumb, "image/jpeg")
                uploaded_keys.append(thumb_key)

            order.items.append(
                OrderItem(
                    filename=label,
                    storage_key=key,
                    thumb_key=thumb_key,
                    content_type=CONTENT_TYPES[ext],
                    size_bytes=len(data),
                    pages=pages,
                    print_type=ptype,
                    copies=copies,
                )
            )
        db.session.commit()
    except UploadRejected as exc:
        db.session.rollback()
        storage.delete_many(uploaded_keys)
        return form_errors([str(exc)])
    except Exception:
        app.logger.exception("Saving order failed")
        db.session.rollback()
        storage.delete_many(uploaded_keys)
        return form_errors(
            ["We couldn't save your order right now. Please try again in a moment."], 500
        )

    session["last_order_id"] = order.id
    return redirect(url_for("success"))


@app.route("/success")
def success():
    order_id = session.get("last_order_id")
    order = db.session.get(Order, order_id) if order_id else None
    if not order:
        return redirect(url_for("index"))
    return render_template("success.html", order=order)


# ------------------------------------------------------------------ runner

def runner_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("runner"):
            return redirect(url_for("runner_login"))
        return view(*args, **kwargs)

    return wrapped


@app.route("/runner/login", methods=["GET", "POST"])
def runner_login():
    if session.get("runner"):
        return redirect(url_for("runner"))
    if request.method == "POST":
        expected = os.environ.get("RUNNER_PASSWORD", "")
        given = request.form.get("password", "")
        if not expected:
            flash("Runner login isn't set up yet. Set the RUNNER_PASSWORD variable.", "danger")
        elif hmac.compare_digest(given.encode(), expected.encode()):
            session["runner"] = True
            return redirect(url_for("runner"))
        else:
            time.sleep(0.7)  # slows down password guessing
            flash("Wrong password.", "danger")
    return render_template("runner_login.html")


@app.route("/runner/logout")
def runner_logout():
    session.pop("runner", None)
    return redirect(url_for("runner_login"))


@app.route("/runner")
@runner_required
def runner():
    view = request.args.get("status", "active")
    if view not in ("active", "all") + STATUSES:
        view = "active"

    query = Order.query.options(selectinload(Order.items)).order_by(Order.created_at.desc())
    if view == "active":
        query = query.filter(Order.status != "delivered")
    elif view in STATUSES:
        query = query.filter_by(status=view)
    orders = query.limit(50).all()

    counts = {s: 0 for s in STATUSES}
    for status, n in db.session.query(Order.status, db.func.count(Order.id)).group_by(Order.status):
        counts[status] = n

    return render_template("runner.html", orders=orders, view=view, counts=counts)


@app.post("/runner/order/<int:order_id>/status")
@runner_required
def runner_set_status(order_id):
    new_status = request.form.get("status")
    if new_status not in STATUSES:
        abort(400)
    order = db.get_or_404(Order, order_id)
    order.status = new_status
    db.session.commit()
    view = request.form.get("view", "active")
    if view not in ("active", "all") + STATUSES:
        view = "active"
    return redirect(url_for("runner", status=view))


@app.route("/runner/file/<int:item_id>/<kind>")
@runner_required
def runner_file(item_id, kind):
    """Redirects to a short-lived link for the file (or its thumbnail)."""
    if kind not in ("file", "thumb"):
        abort(404)
    item = db.get_or_404(OrderItem, item_id)
    key = item.thumb_key if kind == "thumb" else item.storage_key
    if not key:
        abort(404)
    try:
        url = storage.signed_url(key)
    except Exception:
        app.logger.exception("Could not create signed URL")
        abort(502)
    resp = redirect(url)
    resp.headers["Cache-Control"] = "private, max-age=240"
    return resp


@app.route("/runner/local/<path:key>")
@runner_required
def runner_local_file(key):
    """Only used when running without Supabase (local development)."""
    return send_from_directory(storage.LOCAL_DIR, key)


# -------------------------------------------------------------------- misc

@app.route("/health")
def health():
    return {"status": "ok"}


@app.errorhandler(413)
def too_large(_):
    flash("Upload too large. Total size must be under 25 MB.", "danger")
    return render_template("index.html", form={}), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")