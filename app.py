"""My Festival REST API — M10 starter (CSC Rahti).

FI: Tämä on M10-tehtävän lähtöpohja. GET /api/artists on valmiina mallina;
    toteuta loput TODO-kohdat. Aja paikallisesti:  python app.py
    ja testaa:  python test_endpoints.py http://localhost:8080
EN: This is the M10 starter. GET /api/artists is done as an example;
    implement the remaining TODOs. Run locally:  python app.py
    and test:  python test_endpoints.py http://localhost:8080
"""
import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, jsonify, request

app = Flask(__name__)

# FI: Kanta kulkee kontin mukana. Polun voi vaihtaa ympäristömuuttujalla.
# EN: The database ships inside the container. Override the path with an env var.
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "myfestival.db"))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")  # M8: sqlite3 ei valvo FK:ita oletuksena / FKs are off by default
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/")
def health():
    """FI: Rahti ja selain näkevät, että sovellus on pystyssä.
    EN: Lets Rahti and your browser see the app is up."""
    return jsonify(status="ok", endpoints=["/api/artists", "/api/days", "/api/stages",
                                           "/api/artists/<id>/events", "/api/timetable?day=YYYY-MM-DD",
                                           "POST /api/events", "DELETE /api/events/<id>"])


@app.get("/api/artists")
def get_artists():
    conn = get_db()
    rows = conn.execute("SELECT artist_id, name, country FROM Artist ORDER BY name").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/days")
def get_days():
    """FI: Apuendpoint: festivaalipäivät (tarkistin hakee tästä day_id:n).
    EN: Helper endpoint: festival days (the checker reads day_id from here)."""
    conn = get_db()
    rows = conn.execute("SELECT day_id, date FROM Day ORDER BY date").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/stages")
def get_stages():
    """FI: Apuendpoint: lavat. EN: Helper endpoint: stages."""
    conn = get_db()
    rows = conn.execute("SELECT stage_id, name FROM Stage ORDER BY stage_id").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/artists/<int:artist_id>/events")
def get_artist_events(artist_id):
    conn = get_db()

    artist = conn.execute(
        "SELECT artist_id FROM Artist WHERE artist_id = ?",
        (artist_id,)
    ).fetchone()

    if artist is None:
        conn.close()
        return jsonify(error="Artist not found"), 404

    rows = conn.execute(
        """
        SELECT
            e.event_id,
            d.date AS day,
            s.name AS stage,
            e.start_time AS starts
        FROM Event e
        JOIN Day d ON d.day_id = e.day_id
        JOIN Stage s ON s.stage_id = e.stage_id
        WHERE e.artist_id = ?
          AND e.event_type_id = 1
        ORDER BY d.date, e.start_time
        """,
        (artist_id,)
    ).fetchall()

    conn.close()

    return jsonify([dict(r) for r in rows])


@app.get("/api/timetable")
def get_timetable():
    day = request.args.get("day")

    if day:
        try:
            parsed = datetime.strptime(day, "%Y-%m-%d")
            day = parsed.strftime("%Y-%m-%d")
        except ValueError:
            return jsonify(error="Invalid date. Use YYYY-MM-DD."), 400

    conn = get_db()

    query = """
        SELECT
            d.date AS date,
            s.name AS stage,
            a.name AS artist,
            e.start_time AS starts,
            e.end_time AS ends
        FROM Event e
        JOIN Day d ON d.day_id = e.day_id
        JOIN Stage s ON s.stage_id = e.stage_id
        JOIN Artist a ON a.artist_id = e.artist_id
        WHERE e.event_type_id = 1
    """

    if day:
        query += " AND d.date = ?"
        params = (day,)
    else:
        params = ()

    query += " ORDER BY d.date, e.start_time"

    rows = conn.execute(query, params).fetchall()

    conn.close()

    return jsonify([dict(r) for r in rows])


@app.post("/api/events")
def create_event():
    body = request.get_json(silent=True) or {}

    required = ["artist_id", "stage_id", "day_id", "start_dt"]

    for field in required:
        if field not in body:
            return jsonify(error=f"Missing field: {field}"), 400

    try:
        start = datetime.fromisoformat(body["start_dt"])
    except (ValueError, TypeError):
        return jsonify(error="Invalid start_dt"), 400

    start_time = start.strftime("%H:%M")

    end = start + timedelta(minutes=45)
    end_time = end.strftime("%H:%M")

    conn = get_db()

    try:
        cur = conn.execute(
            """
            INSERT INTO Event
            (event_type_id, day_id, artist_id, stage_id,
             start_time, end_time, duration_min)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                body["day_id"],
                body["artist_id"],
                body["stage_id"],
                start_time,
                end_time,
                45
            )
        )

        conn.commit()

        event_id = cur.lastrowid

        row = conn.execute(
            """
            SELECT
                event_id,
                event_type_id,
                day_id,
                artist_id,
                stage_id,
                start_time,
                end_time,
                duration_min
            FROM Event
            WHERE event_id = ?
            """,
            (event_id,)
        ).fetchone()

        conn.close()

        return jsonify(dict(row)), 201

    except sqlite3.IntegrityError as exc:
        conn.rollback()
        conn.close()
        return jsonify(error=str(exc)), 400


@app.delete("/api/events/<int:event_id>")
def delete_event(event_id):
    conn = get_db()

    cur = conn.execute(
        "DELETE FROM Event WHERE event_id = ?",
        (event_id,)
    )

    if cur.rowcount == 0:
        conn.close()
        return jsonify(error="Event not found"), 404

    conn.commit()
    conn.close()

    return "", 204


if __name__ == "__main__":
    # FI: Paikallinen kehityspalvelin. Rahdissa sovellusta ajaa gunicorn (ks. Dockerfile).
    # EN: Local dev server. On Rahti the app is run by gunicorn (see Dockerfile).
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)
