from flask import Flask, render_template, request, jsonify, make_response
from openai import OpenAI
from dotenv import load_dotenv
import os
import sqlite3
import uuid
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-this")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

FREE_LIMIT = 3
DB_FILE = "matchscore.db"


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage (
            visitor_id TEXT PRIMARY KEY,
            ip_address TEXT,
            scans_used INTEGER NOT NULL DEFAULT 0,
            last_used TEXT
        )
    """)
    conn.commit()
    conn.close()


init_db()


def build_prompt(resume_text, job_text):
    return f"""
You are an ATS-style resume evaluator.

Compare the resume to the job description.

Return your answer in this exact format:

Match Score: <number from 0 to 100>

Missing Keywords:
- keyword 1
- keyword 2
- keyword 3

Strengths:
- strength 1
- strength 2
- strength 3

Improvements:
- improvement 1
- improvement 2
- improvement 3

Be honest, specific, and practical.
Focus heavily on matching technical skills, tools, and job-related concepts.

If it doesn't look like a job description or resume, return:
Not a job description or resume.

Resume:
{resume_text}

Job Description:
{job_text}
"""


def get_or_create_visitor_id():
    visitor_id = request.cookies.get("visitor_id")
    if not visitor_id:
        visitor_id = str(uuid.uuid4())
    return visitor_id


def get_usage(visitor_id):
    conn = get_db_connection()
    row = conn.execute(
        "SELECT scans_used FROM usage WHERE visitor_id = ?",
        (visitor_id,)
    ).fetchone()
    conn.close()

    if row:
        return row["scans_used"]
    return 0


def increment_usage(visitor_id, ip_address):
    conn = get_db_connection()
    current_time = datetime.utcnow().isoformat()

    existing = conn.execute(
        "SELECT scans_used FROM usage WHERE visitor_id = ?",
        (visitor_id,)
    ).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE usage
            SET scans_used = scans_used + 1,
                ip_address = ?,
                last_used = ?
            WHERE visitor_id = ?
            """,
            (ip_address, current_time, visitor_id)
        )
    else:
        conn.execute(
            """
            INSERT INTO usage (visitor_id, ip_address, scans_used, last_used)
            VALUES (?, ?, ?, ?)
            """,
            (visitor_id, ip_address, 1, current_time)
        )

    conn.commit()

    updated = conn.execute(
        "SELECT scans_used FROM usage WHERE visitor_id = ?",
        (visitor_id,)
    ).fetchone()

    conn.close()
    return updated["scans_used"]


@app.route("/")
def home():
    visitor_id = get_or_create_visitor_id()
    response = make_response(render_template("index.html"))

    if not request.cookies.get("visitor_id"):
        response.set_cookie(
            "visitor_id",
            visitor_id,
            max_age=60 * 60 * 24 * 30,  # 30 days
            httponly=True,
            samesite="Lax",
            secure=not app.debug
        )

    return response


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        visitor_id = get_or_create_visitor_id()
        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")

        current_uses = get_usage(visitor_id)

        if current_uses >= FREE_LIMIT:
            response = make_response(jsonify({
                "error": "You have used all 3 free scans. More access is coming soon.",
                "remaining_scans": 0
            }), 403)

            if not request.cookies.get("visitor_id"):
                response.set_cookie(
                    "visitor_id",
                    visitor_id,
                    max_age=60 * 60 * 24 * 30,
                    httponly=True,
                    samesite="Lax",
                    secure=not app.debug
                )

            return response

        data = request.get_json()

        if not data:
            return jsonify({
                "error": "Invalid request. No data received."
            }), 400

        resume_text = data.get("resume", "").strip()
        job_text = data.get("job", "").strip()

        if not resume_text or not job_text:
            return jsonify({
                "error": "Please paste both the resume and the job description."
            }), 400

        prompt = build_prompt(resume_text, job_text)

        response_openai = client.responses.create(
            model="gpt-5.4",
            input=prompt
        )

        result_text = response_openai.output_text.strip()

        new_total = increment_usage(visitor_id, user_ip)
        remaining = max(FREE_LIMIT - new_total, 0)

        response = make_response(jsonify({
            "result": result_text,
            "remaining_scans": remaining
        }))

        if not request.cookies.get("visitor_id"):
            response.set_cookie(
                "visitor_id",
                visitor_id,
                max_age=60 * 60 * 24 * 30,
                httponly=True,
                samesite="Lax",
                secure=not app.debug
            )

        return response

    except Exception as e:
        return jsonify({
            "error": f"Something went wrong: {str(e)}"
        }), 500


if __name__ == "__main__":
    app.run(debug=True)