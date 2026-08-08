"""
mock_server.py

Minimal local Flask server standing in for the teammate's real backend,
so the attendance pipeline can be tested end-to-end before the real
backend is ready. Run with: python mock_server.py
Listens on http://localhost:5000/api/attendance
"""

from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route("/api/attendance", methods=["POST"])
def receive_attendance():
    payload = request.get_json(force=True, silent=True) or {}
    print(f"[mock_server] Received attendance event: {payload}")
    return jsonify({"status": "ok", "received": payload}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)