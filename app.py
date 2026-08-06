from __future__ import annotations

import math
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

from ml.flair_inference import FlairSegmenter

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
RESULT_DIR = BASE_DIR / "static" / "results"
DEFAULT_MODEL_PATH = BASE_DIR / "models" / "FLAIR-INC_rgb_15cl_resnet34-deeplabv3_weights.pth"
MODEL_PATH = Path(os.environ.get("SIRIUS_MODEL_PATH", DEFAULT_MODEL_PATH))
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
MAX_UPLOAD_BYTES = 12 * 1024 * 1024

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULT_DIR.mkdir(parents=True, exist_ok=True)

started_at = time.time()
segmenter = FlairSegmenter(MODEL_PATH)
CAPTURES: list[dict[str, Any]] = []


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/telemetry/latest")
def latest():
    elapsed = int(time.time() - started_at)
    cycle = elapsed % 75

    if cycle < 10:
        state, altitude, velocity = "PRE_LAUNCH", 0.0, 0.0
    elif cycle < 30:
        state, altitude, velocity = "ASCENT", (cycle - 10) * 5.0, 5.0
    elif cycle < 35:
        state, altitude, velocity = "DESCENT_FREE", max(80.0, 100.0 - (cycle - 30) * 4.0), -18.0
    elif cycle < 52:
        state, altitude, velocity = "DESCENT_STABLE", max(3.0, 80.0 - (cycle - 35) * 4.5), -5.2
    elif cycle < 55:
        state, altitude, velocity = "LANDING", max(0.0, 3.0 - (cycle - 52)), -2.0
    else:
        state, altitude, velocity = "LANDED", 0.0, 0.0

    latitude = -12.071921 + math.sin(elapsed / 20) * 0.00008
    longitude = -77.079842 + math.cos(elapsed / 22) * 0.00008

    return jsonify(
        {
            "packet_id": 452 + elapsed,
            "mission_time": elapsed,
            "mission_state": state,
            "altitude": round(altitude + random.uniform(-0.5, 0.5), 1),
            "vertical_velocity": round(velocity + random.uniform(-0.2, 0.2), 1),
            "voltage": round(7.84 - min(elapsed, 300) * 0.0003, 2),
            "temperature": round(23.6 + math.sin(elapsed / 8), 1),
            "pressure": round(1011.3 - altitude * 0.11, 1),
            "rssi": -67,
            "pitch": round(-3.2 + math.sin(elapsed / 4), 1),
            "roll": round(1.7 + math.cos(elapsed / 5), 1),
            "yaw": round((142.6 + elapsed * 2.4) % 360, 1),
            "latitude": round(latitude, 6),
            "longitude": round(longitude, 6),
            "gps_altitude": round(max(0.0, altitude + random.uniform(-1.5, 1.5)), 1),
            "gps_accuracy": round(random.uniform(1.8, 3.4), 1),
            "satellites": 8,
        }
    )


@app.get("/api/captures")
def captures():
    return jsonify(CAPTURES)


@app.get("/api/model/status")
def model_status():
    return jsonify(
        {
            "ready": MODEL_PATH.is_file(),
            "model_path": str(MODEL_PATH),
            "device": str(segmenter.device),
        }
    )


@app.post("/api/captures/reset")
def reset_captures():
    """Elimina capturas y resultados generados durante la sesión actual."""
    deleted_files = 0

    for capture in CAPTURES:
        for key, base_directory in (
            ("image", UPLOAD_DIR),
            ("overlay", RESULT_DIR),
            ("mask", RESULT_DIR),
        ):
            stored_path = capture.get(key)
            if not stored_path:
                continue

            candidate = (base_directory / Path(stored_path).name).resolve()
            if candidate.parent == base_directory.resolve() and candidate.is_file():
                candidate.unlink()
                deleted_files += 1

    cleared_captures = len(CAPTURES)
    CAPTURES.clear()

    return jsonify(
        {
            "status": "ok",
            "cleared_captures": cleared_captures,
            "deleted_files": deleted_files,
        }
    )


@app.post("/api/captures/analyze")
def analyze_capture():
    if "image" not in request.files:
        return jsonify({"error": "No se recibió el campo 'image'."}), 400

    uploaded = request.files["image"]
    if not uploaded.filename:
        return jsonify({"error": "Selecciona una imagen."}), 400
    if not allowed_file(uploaded.filename):
        return jsonify({"error": "Formato no permitido. Usa JPG, JPEG o PNG."}), 400
    if not MODEL_PATH.is_file():
        return jsonify(
            {
                "error": "No se encontró el archivo de pesos FLAIR.",
                "expected_path": str(MODEL_PATH),
            }
        ), 503

    safe_name = secure_filename(uploaded.filename)
    suffix = Path(safe_name).suffix.lower()
    capture_id = len(CAPTURES) + 1
    token = uuid4().hex[:10]
    filename = f"capture_{capture_id:03d}_{token}{suffix}"
    image_path = UPLOAD_DIR / filename
    uploaded.save(image_path)

    try:
        result = segmenter.analyze(image_path, RESULT_DIR)
    except Exception as exc:  # Mantiene un mensaje claro en la interfaz.
        image_path.unlink(missing_ok=True)
        return jsonify({"error": f"No se pudo procesar la imagen: {exc}"}), 500

    now = datetime.now()
    latitude = float(request.form.get("latitude", -12.071921))
    longitude = float(request.form.get("longitude", -77.079842))
    altitude = float(request.form.get("altitude", 0.0))

    capture = {
        "id": capture_id,
        "time": now.strftime("%H:%M:%S"),
        "altitude": round(altitude, 1),
        "latitude": latitude,
        "longitude": longitude,
        "green": round(result.green_percentage, 2),
        "urban": round(result.urban_percentage, 2),
        "other": round(result.other_percentage, 2),
        "image": f"/static/uploads/{image_path.name}",
        "overlay": f"/static/results/{result.overlay_path.name}",
        "mask": f"/static/results/{result.mask_path.name}",
        "model": "FLAIR DeepLabV3 + ResNet34",
        "source": "real_model",
    }
    CAPTURES.append(capture)
    return jsonify(capture), 201


@app.errorhandler(413)
def file_too_large(_error):
    return jsonify({"error": "La imagen supera el límite de 12 MB."}), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
