
import json
import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from groq import Groq

BASE_DIR = Path(__file__).resolve().parent
PROFILE_FILE = BASE_DIR / "public_profile.json"

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024

MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")


def load_public_profile():
    """Expose only explicitly approved public profile fields."""
    try:
        with PROFILE_FILE.open("r", encoding="utf-8") as file:
            profile = json.load(file)

        if not isinstance(profile, dict):
            return {}

        if profile.get("show_publicly") is not True:
            return {}

        allowed = (
            "project_name",
            "creator_name",
            "creator_title",
            "project_description",
            "interests",
            "vision",
        )

        return {
            key: profile[key]
            for key in allowed
            if key in profile
        }
    except (OSError, ValueError, TypeError):
        app.logger.exception("Public profile could not be loaded")
        return {}


@app.get("/")
def home():
    # Keep the original sci-fi interface.
    return render_template("index.html")


@app.get("/api/status")
def status():
    profile = load_public_profile()

    return jsonify({
        "online": True,
        "ai_ready": bool(os.getenv("GROQ_API_KEY")),
        "voice_files_ready": False,
        "facts_count": "PRIVATE",
        "creator": profile.get("creator_name", "NEXUS Creator"),
        "project": "NEXUS BETA",
        "public_mode": True,
    })


@app.get("/api/profile")
def profile():
    public = load_public_profile()

    # Match the field names expected by the original UI.
    return jsonify({
        "name": public.get("creator_name", "Not provided"),
        "creator": public.get("creator_title", "Not provided"),
        "goal": public.get("vision", "Not provided"),
        "release_plan": public.get(
            "project_description", "Not provided"
        ),
        "interests": public.get("interests", []),
    })


@app.get("/api/history")
def history():
    # Never load or expose local/private conversation history.
    return jsonify({"messages": []})


@app.get("/api/facts")
def facts():
    # Never read personal_memory.json in public mode.
    return jsonify({
        "facts": [],
        "message": "Private saved facts are not available on this public website."
    })


@app.post("/api/clear")
def clear():
    # There is no server-side public chat history to delete.
    return jsonify({
        "ok": True,
        "message": "Only the browser chat session can be cleared."
    })


@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Please send a valid message."}), 400

    message = data.get("message")

    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Message cannot be empty."}), 400

    message = message.strip()

    if len(message) > 2000:
        return jsonify({"error": "Keep each message under 2000 characters."}), 400

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return jsonify({
            "error": "Public AI is not configured yet. Please try again later."
        }), 503

    public_profile = load_public_profile()

    system_prompt = f"""
You are NEXUS BETA, a helpful public-facing AI assistant.
Respond in the language and script the visitor uses, including Hindi,
Hinglish, or English. Be friendly, clear, and honest.

Approved public project/creator information:
{json.dumps(public_profile, ensure_ascii=False)}

When asked about the creator, use only the approved public information above.
Do not invent private details. You cannot access the creator's private
memories, local chat history, personal files, API keys, or computer.
Do not execute PC automation or claim to have performed local actions.
This is the public website, not the creator's private local assistant.
"""

    try:
        client = Groq(api_key=api_key)

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            max_completion_tokens=800,
        )

        answer = response.choices[0].message.content or ""
        if not answer.strip():
            answer = "Sorry, I couldn't prepare a response. Please try again."

        return jsonify({
            "answer": answer,
            "speech_queued": False,
        })

    except Exception:
        app.logger.exception("Public AI request failed")
        return jsonify({
            "error": "NEXUS couldn't answer right now. Please try again later."
        }), 502


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)
