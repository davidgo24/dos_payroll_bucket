"""
DOS Data Entry — Transit
Flask app for Railway deployment.
Each visitor gets an isolated session — upload and work independently.
"""
import os
import re
import tempfile
import uuid
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory, session
from extract_dos_data import extract_dos_data

app = Flask(__name__, static_folder="static", static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")

# Per-session DOS data: { session_id: { employees, date } }
_dos_data: dict[str, dict] = {}


def _uid():
    """Get or create a unique session id for this visitor."""
    if "uid" not in session:
        session["uid"] = str(uuid.uuid4())
    return session["uid"]


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/data")
def api_data():
    """Return extracted DOS data or 404 if none loaded."""
    uid = _uid()
    data = _dos_data.get(uid)
    if data is None:
        return jsonify({"error": "No data loaded. Upload an Excel file first."}), 404
    return jsonify(data)


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """Accept Excel file, extract data, store per-session."""
    uid = _uid()
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        return jsonify({"error": "File must be Excel (.xlsx or .xls)"}), 400
    format_hint = request.form.get("format") or None  # "standard" | "raw" | None (auto)
    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            file.save(tmp.name)
            data = extract_dos_data(tmp.name, format=format_hint)
        os.unlink(tmp.name)
        # Prefer first date from filename (schedule date; ignore generated_at date)
        m = re.search(r"\d{4}-\d{2}-\d{2}", file.filename or "")
        if m:
            data["date"] = m.group(0)
        _dos_data[uid] = data
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(data)


@app.route("/api/clear", methods=["POST"])
def api_clear():
    """Clear this session's DOS data (resets to upload screen on reload)."""
    uid = _uid()
    if uid in _dos_data:
        del _dos_data[uid]
    return jsonify({"ok": True})


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
