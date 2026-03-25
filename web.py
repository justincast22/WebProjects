from flask import Flask, render_template, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

app = Flask(__name__)

# OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 🔥 FREE LIMIT SYSTEM
usage = {}  # stores usage per IP
FREE_LIMIT = 3


def build_prompt(resume_text, job_text):
    return f"""
You are an ATS-style resume evaluator.

Compare the resume to the job description.

Return your answer in this exact format:

Match Score: <number from 0 to 100>

Missing Keywords:
- keyword 1
- keyword 2

Strengths:
- strength 1
- strength 2

Improvements:
- improvement 1
- improvement 2

Be honest and specific.

Resume:
{resume_text}

Job Description:
{job_text}
"""


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        user_ip = request.remote_addr
        current_uses = usage.get(user_ip, 0)

        # 🚫 Check limit
        if current_uses >= FREE_LIMIT:
            return jsonify({
                "error": "You reached the free limit of 3 scans. Upgrade for unlimited access."
            }), 403

        data = request.get_json()

        resume_text = data.get("resume", "").strip()
        job_text = data.get("job", "").strip()

        if not resume_text or not job_text:
            return jsonify({
                "error": "Please paste both the resume and the job description."
            }), 400

        # 🔥 Build prompt
        prompt = build_prompt(resume_text, job_text)

        # 🔥 Call OpenAI
        response = client.responses.create(
            model="gpt-5.4",
            input=prompt
        )

        # ✅ Increment usage ONLY after success
        usage[user_ip] = current_uses + 1
        remaining = FREE_LIMIT - usage[user_ip]

        return jsonify({
            "result": response.output_text,
            "remaining_scans": remaining
        })

    except Exception as e:
        return jsonify({
            "error": f"Something went wrong: {str(e)}"
        }), 500


if __name__ == "__main__":
    app.run(debug=True)