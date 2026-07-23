from __future__ import annotations

import math
import random
import sqlite3
import time
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "sirius.db"

app = Flask(__name__)

MISSION_STATES = [
    "PRE_LAUNCH",
    "ASCENT",
    "DESCENT_FREE",
    "DESCENT_STABLE",
    "LANDING",
    "LANDED",
]

simulation_started_at = time.time()


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_database() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                packet_id INTEGER NOT NULL,
                mission_time INTEGER NOT NULL,
                altitude REAL NOT NULL,
                vertical_velocity REAL NOT NULL,
                voltage REAL NOT NULL,
                temperature REAL NOT NULL,
                pressure REAL NOT NULL,
                pitch REAL NOT NULL,
                roll REAL NOT NULL,
                yaw REAL NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                terrain_class INTEGER NOT NULL,
                green_percentage INTEGER NOT NULL,
                urban_percentage INTEGER NOT NULL,
                mixed_percentage INTEGER NOT NULL,
                mission_state TEXT NOT NULL,
                received_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def simulated_packet() -> dict[str, Any]:
    elapsed = int(time.time() - simulation_started_at)
    cycle = elapsed % 75

    if cycle < 10:
        state = "PRE_LAUNCH"
        altitude = 0.0
        velocity = 0.0
    elif cycle < 30:
        state = "ASCENT"
        altitude = (cycle - 10) * 5.0
        velocity = 5.0
    elif cycle < 35:
        state = "DESCENT_FREE"
        altitude = max(80.0, 100.0 - (cycle - 30) * 4.0)
        velocity = -18.0 - (cycle - 30) * 4.0
    elif cycle < 52:
        state = "DESCENT_STABLE"
        altitude = max(3.0, 80.0 - (cycle - 35) * 4.5)
        velocity = -5.2
    elif cycle < 55:
        state = "LANDING"
        altitude = max(0.0, 3.0 - (cycle - 52))
        velocity = -2.0
    else:
        state = "LANDED"
        altitude = 0.0
        velocity = 0.0

    t = elapsed
    green = int(48 + 12 * math.sin(t / 8))
    urban = int(32 + 8 * math.cos(t / 9))
    mixed = max(0, 100 - green - urban)
    terrain_class = max(
        [(green, 0), (urban, 1), (mixed, 2)],
        key=lambda item: item[0],
    )[1]

    return {
        "packet_id": elapsed % 65536,
        "mission_time": cycle,
        "altitude": round(altitude + random.uniform(-0.7, 0.7), 1),
        "vertical_velocity": round(velocity + random.uniform(-0.3, 0.3), 1),
        "voltage": round(8.2 - min(cycle, 60) * 0.004, 2),
        "temperature": round(24.0 + 1.8 * math.sin(t / 10), 1),
        "pressure": round(1013.25 - altitude * 0.12, 1),
        "pitch": round(5 * math.sin(t / 3), 1),
        "roll": round(4 * math.cos(t / 4), 1),
        "yaw": round((t * 7) % 360 - 180, 1),
        "latitude": -12.072 + random.uniform(-0.00015, 0.00015),
        "longitude": -77.080 + random.uniform(-0.00015, 0.00015),
        "terrain_class": terrain_class,
        "green_percentage": green,
        "urban_percentage": urban,
        "mixed_percentage": mixed,
        "mission_state": state,
    }


def save_packet(packet: dict[str, Any]) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO telemetry (
                packet_id, mission_time, altitude, vertical_velocity, voltage,
                temperature, pressure, pitch, roll, yaw, latitude, longitude,
                terrain_class, green_percentage, urban_percentage,
                mixed_percentage, mission_state
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                packet["packet_id"],
                packet["mission_time"],
                packet["altitude"],
                packet["vertical_velocity"],
                packet["voltage"],
                packet["temperature"],
                packet["pressure"],
                packet["pitch"],
                packet["roll"],
                packet["yaw"],
                packet["latitude"],
                packet["longitude"],
                packet["terrain_class"],
                packet["green_percentage"],
                packet["urban_percentage"],
                packet["mixed_percentage"],
                packet["mission_state"],
            ),
        )


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/telemetry/latest")
def latest_telemetry():
    packet = simulated_packet()
    save_packet(packet)
    return jsonify(packet)


@app.get("/api/telemetry/history")
def telemetry_history():
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT mission_time, altitude, vertical_velocity, temperature,
                   pressure, voltage, received_at
            FROM telemetry
            ORDER BY id DESC
            LIMIT 60
            """
        ).fetchall()

    return jsonify([dict(row) for row in reversed(rows)])


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "database": str(DB_PATH)})


if __name__ == "__main__":
    init_database()
    app.run(host="127.0.0.1", port=5000, debug=True)
