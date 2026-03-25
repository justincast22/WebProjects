from flask import Flask, render_template, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Free scan tracking
usage = {}
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

If it doesn't look like a job description or resume, return Not a job description or resume.

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

        # Hard stop after 3 successful scans
        if current_uses >= FREE_LIMIT:
            return jsonify({
                "error": "You have used all 3 free scans. More access is coming soon."
            }), 403

        data = request.get_json()

        resume_text = data.get("resume", "").strip()
        job_text = data.get("job", "").strip()

        if not resume_text or not job_text:
            return jsonify({
                "error": "Please paste both the resume and the job description."
            }), 400

        prompt = build_prompt(resume_text, job_text)

        response = client.responses.create(
            model="gpt-5.4",
            input=prompt
        )

        # Count only after a successful OpenAI response
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