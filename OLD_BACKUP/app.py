import os
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)

# -------------------------
# CONFIG
# -------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

ALLOWED_EXTENSIONS = {"mp4", "mov", "avi", "mkv"}

# ensure uploads folder exists always
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# -------------------------
# helper function
# -------------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# -------------------------
# ROUTE: upload
# -------------------------
@app.route("/upload", methods=["POST"])
def upload_video():

    # check request
    if "video" not in request.files:
        return jsonify({"error": "No video found"}), 400

    video = request.files["video"]

    # validate file
    if video.filename is None or video.filename.strip() == "":
        return jsonify({"error": "Empty filename"}), 400

    if not allowed_file(video.filename):
        return jsonify({"error": "Only mp4/mov/avi/mkv allowed"}), 400

    # safe filename
    filename = secure_filename(video.filename)

    # final path
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    try:
        video.save(file_path)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "message": "Upload successful",
        "file": filename,
        "path": file_path
    })


# -------------------------
# HOME TEST ROUTE
# -------------------------
@app.route("/")
def home():
    return "Backend running 🚀"


# -------------------------
# RUN SERVER
# -------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)