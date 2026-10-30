"""LearnLyt Flask application."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import json
import os
import sqlite3

from flask import (
    Flask, abort, flash, redirect, render_template, request, send_file, url_for
)

from database import Database


BASE_DIR = Path(__file__).resolve().parent
database = Database()
database.initialize()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("LEARNLYT_SECRET_KEY", "learnlyt-local-development")
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024


@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        active_page="dashboard",
        stats=database.dashboard_stats(),
        subjects=database.list_subjects()[:4],
        topics=database.list_topics()[:5],
    )


@app.route("/library")
def library():
    selected_subject = request.args.get("subject_id", type=int)
    selected_category = request.args.get("category", "")
    selected_difficulty = request.args.get("difficulty", "")
    search = request.args.get("search", "").strip()
    return render_template(
        "library.html",
        active_page="library",
        subjects=database.list_subjects(),
        topics=database.list_topics(selected_subject, selected_category, selected_difficulty, search),
        categories=database.list_categories(),
        selected_subject=selected_subject,
        selected_category=selected_category,
        selected_difficulty=selected_difficulty,
        search=search,
    )


@app.route("/subjects/new", methods=["GET", "POST"])
def new_subject():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Subject name is required.", "error")
        else:
            try:
                subject_id = database.create_subject(
                    name,
                    request.form.get("description", ""),
                    request.form.get("color", "#6C5CE7"),
                )
                flash("Subject created successfully.", "success")
                return redirect(url_for("subject_detail", subject_id=subject_id))
            except sqlite3.IntegrityError:
                flash("A subject with that name already exists.", "error")
    return render_template("subject_form.html", active_page="library", subject=None)


@app.route("/subjects/<int:subject_id>")
def subject_detail(subject_id: int):
    subject = database.get_subject(subject_id)
    if not subject:
        abort(404)
    topics = database.list_topics(subject_id=subject_id)
    return render_template(
        "subject_detail.html", active_page="library", subject=subject, topics=topics
    )


@app.route("/subjects/<int:subject_id>/edit", methods=["GET", "POST"])
def edit_subject(subject_id: int):
    subject = database.get_subject(subject_id)
    if not subject:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Subject name is required.", "error")
        else:
            try:
                database.update_subject(
                    subject_id, name, request.form.get("description", ""),
                    request.form.get("color", "#6C5CE7")
                )
                flash("Subject updated.", "success")
                return redirect(url_for("subject_detail", subject_id=subject_id))
            except sqlite3.IntegrityError:
                flash("A subject with that name already exists.", "error")
    return render_template("subject_form.html", active_page="library", subject=subject)


@app.post("/subjects/<int:subject_id>/delete")
def delete_subject(subject_id: int):
    if not database.delete_subject(subject_id):
        abort(404)
    flash("Subject and its topics were deleted.", "success")
    return redirect(url_for("library"))


@app.route("/topics/new", methods=["GET", "POST"])
def new_topic():
    subjects = database.list_subjects()
    if not subjects:
        flash("Create a subject before adding a topic.", "error")
        return redirect(url_for("new_subject"))
    if request.method == "POST":
        error = _validate_topic_form()
        if error:
            flash(error, "error")
        else:
            topic_id = database.create_topic(
                int(request.form["subject_id"]), request.form["title"],
                request.form.get("category", "General"), request.form.get("difficulty", "Medium"),
                request.form.get("notes", "")
            )
            flash("Topic created. Now add flashcards.", "success")
            return redirect(url_for("topic_detail", topic_id=topic_id))
    return render_template(
        "topic_form.html", active_page="library", topic=None, subjects=subjects,
        selected_subject=request.args.get("subject_id", type=int)
    )


@app.route("/topics/<int:topic_id>")
def topic_detail(topic_id: int):
    topic = database.get_topic(topic_id)
    if not topic:
        abort(404)
    return render_template(
        "topic_detail.html", active_page="library", topic=topic,
        cards=database.list_flashcards(topic_id)
    )


@app.route("/topics/<int:topic_id>/edit", methods=["GET", "POST"])
def edit_topic(topic_id: int):
    topic = database.get_topic(topic_id)
    if not topic:
        abort(404)
    subjects = database.list_subjects()
    if request.method == "POST":
        error = _validate_topic_form()
        if error:
            flash(error, "error")
        else:
            database.update_topic(
                topic_id, int(request.form["subject_id"]), request.form["title"],
                request.form.get("category", "General"), request.form.get("difficulty", "Medium"),
                request.form.get("notes", "")
            )
            flash("Topic updated.", "success")
            return redirect(url_for("topic_detail", topic_id=topic_id))
    return render_template(
        "topic_form.html", active_page="library", topic=topic, subjects=subjects,
        selected_subject=topic["subject_id"]
    )


@app.post("/topics/<int:topic_id>/delete")
def delete_topic(topic_id: int):
    if not database.delete_topic(topic_id):
        abort(404)
    flash("Topic and its flashcards were deleted.", "success")
    return redirect(url_for("library"))


@app.route("/flashcards/new", methods=["GET", "POST"])
def new_flashcard():
    topics = database.list_topics()
    if not topics:
        flash("Create a topic before adding a flashcard.", "error")
        return redirect(url_for("new_topic"))
    if request.method == "POST":
        error = _validate_card_form()
        if error:
            flash(error, "error")
        else:
            topic_id = int(request.form["topic_id"])
            database.create_flashcard(topic_id, request.form["question"], request.form["answer"])
            flash("Flashcard added and scheduled for review today.", "success")
            if request.form.get("add_another"):
                return redirect(url_for("new_flashcard", topic_id=topic_id))
            return redirect(url_for("topic_detail", topic_id=topic_id))
    return render_template(
        "flashcard_form.html", active_page="library", card=None, topics=topics,
        selected_topic=request.args.get("topic_id", type=int)
    )


@app.route("/flashcards/<int:card_id>/edit", methods=["GET", "POST"])
def edit_flashcard(card_id: int):
    card = database.get_flashcard(card_id)
    if not card:
        abort(404)
    topics = database.list_topics()
    if request.method == "POST":
        error = _validate_card_form()
        if error:
            flash(error, "error")
        else:
            topic_id = int(request.form["topic_id"])
            database.update_flashcard(card_id, topic_id, request.form["question"], request.form["answer"])
            flash("Flashcard updated.", "success")
            return redirect(url_for("topic_detail", topic_id=topic_id))
    return render_template(
        "flashcard_form.html", active_page="library", card=card, topics=topics,
        selected_topic=card["topic_id"]
    )


@app.post("/flashcards/<int:card_id>/delete")
def delete_flashcard(card_id: int):
    card = database.get_flashcard(card_id)
    if not card:
        abort(404)
    database.delete_flashcard(card_id)
    flash("Flashcard deleted.", "success")
    return redirect(url_for("topic_detail", topic_id=card["topic_id"]))


@app.route("/review", methods=["GET", "POST"])
def review():
    if request.method == "POST":
        card_id = request.form.get("card_id", type=int)
        quality = request.form.get("quality", type=int)
        if card_id is None or quality not in range(6):
            abort(400)
        result = database.record_review(card_id, quality)
        if not result:
            abort(404)
        message = "Remembered!" if result.remembered else "Keep practising—this card returns tomorrow."
        flash(f"{message} Next review: {result.next_review}.", "success")
        return redirect(url_for("review"))

    cards = database.due_flashcards()
    card = cards[0] if cards else None
    return render_template(
        "review.html", active_page="review", card=card,
        remaining=len(cards), stats=database.dashboard_stats()
    )


@app.route("/reports")
def reports():
    return render_template(
        "reports.html", active_page="reports", report=database.report_data()
    )


@app.route("/backup")
def backup():
    return render_template("backup.html", active_page="backup")


@app.route("/backup/export")
def export_backup():
    payload = database.export_data()
    payload["exported_at"] = datetime.now(timezone.utc).isoformat()
    data = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    return send_file(
        BytesIO(data), mimetype="application/json", as_attachment=True,
        download_name=f"learnlyt_backup_{datetime.now().date().isoformat()}.json"
    )


@app.post("/backup/import")
def import_backup():
    upload = request.files.get("backup_file")
    if not upload or not upload.filename:
        flash("Choose a JSON backup file.", "error")
        return redirect(url_for("backup"))
    if not upload.filename.lower().endswith(".json"):
        flash("Only JSON backup files are supported.", "error")
        return redirect(url_for("backup"))
    try:
        payload = json.loads(upload.read().decode("utf-8"))
        imported = database.import_data(payload)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, sqlite3.IntegrityError) as error:
        flash(f"Import failed: {error}", "error")
        return redirect(url_for("backup"))
    flash(
        f"Imported {imported['subjects']} subjects, {imported['topics']} topics and {imported['flashcards']} flashcards.",
        "success"
    )
    return redirect(url_for("library"))


@app.post("/demo/load")
def load_demo():
    demo_path = BASE_DIR / "sample_data" / "learnlyt_demo.json"
    try:
        result = database.import_data(json.loads(demo_path.read_text(encoding="utf-8")))
        flash(f"Demo loaded with {result['flashcards']} flashcards.", "success")
    except (ValueError, KeyError, sqlite3.IntegrityError) as error:
        flash(f"Could not load demo data: {error}", "error")
    return redirect(url_for("dashboard"))


@app.errorhandler(413)
def too_large(_error):
    flash("Backup file is too large. Maximum size is 2 MB.", "error")
    return redirect(url_for("backup"))


@app.errorhandler(404)
def not_found(_error):
    return render_template("404.html", active_page=""), 404


def _validate_topic_form():
    if not request.form.get("title", "").strip():
        return "Topic title is required."
    subject_id = request.form.get("subject_id", type=int)
    if not subject_id or not database.get_subject(subject_id):
        return "Choose a valid subject."
    if request.form.get("difficulty") not in {"Easy", "Medium", "Hard"}:
        return "Choose a valid difficulty."
    return None


def _validate_card_form():
    if not request.form.get("question", "").strip() or not request.form.get("answer", "").strip():
        return "Both question and answer are required."
    topic_id = request.form.get("topic_id", type=int)
    if not topic_id or not database.get_topic(topic_id):
        return "Choose a valid topic."
    return None


if __name__ == "__main__":
    app.run(
        host="127.0.0.1", port=5000,
        debug=os.environ.get("FLASK_DEBUG") == "1"
    )
