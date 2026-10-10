import os

from flask import Flask, flash, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
# Limit on the TOTAL size of one upload request (all files together)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
PRINT_TYPES = {
    "bw": "Black & White (₹2/page)",
    "color": "Color (₹10/page)",
}
MAX_FILES = 10
MAX_COPIES = 100


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        files = [f for f in request.files.getlist("documents") if f and f.filename]
        types = request.form.getlist("print_type")
        copies_list = request.form.getlist("copies")
        classroom = request.form.get("classroom", "").strip()

        errors = []

        if not files:
            errors.append("Please choose at least one file to upload.")
        elif len(files) > MAX_FILES:
            errors.append(f"You can upload at most {MAX_FILES} files per order.")
        elif len(types) != len(files) or len(copies_list) != len(files):
            errors.append("Something went wrong with the file options. Please try again.")

        items = []
        if not errors:
            for f, t, c in zip(files, types, copies_list):
                if not allowed_file(f.filename):
                    errors.append(f"'{f.filename}': only PDF, PNG, JPG and JPEG are allowed.")
                    continue
                if t not in PRINT_TYPES:
                    errors.append(f"'{f.filename}': invalid print type.")
                    continue
                try:
                    copies = int(c)
                except ValueError:
                    copies = 0
                if not 1 <= copies <= MAX_COPIES:
                    errors.append(f"'{f.filename}': copies must be between 1 and {MAX_COPIES}.")
                    continue
                items.append(
                    {
                        "filename": f.filename[:60],
                        "print_type": PRINT_TYPES[t],
                        "copies": copies,
                    }
                )

        if not classroom:
            errors.append("Please enter a delivery classroom / location.")
        elif len(classroom) > 100:
            errors.append("Location is too long (max 100 characters).")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("index.html", classroom=classroom), 400

        # Files are validated but not stored (you'll add storage later).
        session["order"] = {"items": items, "classroom": classroom}
        return redirect(url_for("success"))

    return render_template("index.html", classroom="")


@app.route("/success")
def success():
    order = session.get("order")
    if not order:
        return redirect(url_for("index"))
    total_copies = sum(i["copies"] for i in order["items"])
    return render_template(
        "success.html",
        items=order["items"],
        classroom=order["classroom"],
        total_copies=total_copies,
    )


@app.route("/health")
def health():
    return {"status": "ok"}


@app.errorhandler(413)
def too_large(_):
    flash("Upload too large. Total size must be under 25 MB.", "danger")
    return render_template("index.html", classroom=""), 413


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")