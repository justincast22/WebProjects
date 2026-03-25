from flask import Flask, render_template, request, jsonify
from openai import OpenAI
from dotenv import load_dotenv
import os

# Load variables from .env into the environment
load_dotenv()

app = Flask(__name__)

# The OpenAI SDK can read OPENAI_API_KEY from the environment
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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

Keep the feedback practical, specific, and easy to understand.
Do not be overly nice. Be honest.

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

        return jsonify({
            "result": response.output_text
        })

    except Exception as e:
        return jsonify({
            "error": f"Something went wrong: {str(e)}"
        }), 500


if __name__ == "__main__":
    app.run(debug=True)