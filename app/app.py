from werkzeug.security import check_password_hash
from flask import Flask, render_template, request, session, redirect, url_for
from werkzeug.security import generate_password_hash
from db import users_collection
import re   # for pattern checking
import os
from werkzeug.utils import secure_filename
from flask import send_from_directory
import random
import string
from db import classrooms_collection
from bson.objectid import ObjectId
from db import study_materials_collection
from datetime import datetime
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from groq import Groq
from gtts import gTTS
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips
from db import videos_collection
from datetime import datetime
from db import questions_collection
import json
import re
from db import student_results_collection
from db import community_posts_collection
import uuid
from db import assignments_collection
from db import assignment_submissions_collection
from flask_socketio import SocketIO, emit, join_room, leave_room
from db import live_classes_collection
GROQ_CHAT_MODEL = "llama-3.3-70b-versatile"

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

app = Flask(__name__)
socketio = SocketIO(app)
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config["STUDY_MATERIAL_FOLDER"] = os.path.join(BASE_DIR, "study_materials")
os.makedirs(app.config["STUDY_MATERIAL_FOLDER"], exist_ok=True)
app.secret_key = "supersecretkey"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "..", "uploads")
ALLOWED_EXTENSIONS = {"pdf", "docx", "ppt", "pptx"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

AUDIO_FOLDER = os.path.join(BASE_DIR, "..", "audio")
os.makedirs(AUDIO_FOLDER, exist_ok=True)

VIDEO_FOLDER = os.path.join(BASE_DIR, "..", "videos")
ASSETS_FOLDER = os.path.join(BASE_DIR, "..", "assets", "presenters")

os.makedirs(VIDEO_FOLDER, exist_ok=True)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def is_valid_email(email):
    pattern = r"^[a-zA-Z0-9]+([._]?[a-zA-Z0-9]+)*@[a-zA-Z0-9]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email)

def is_strong_password(password):
    if len(password) < 10:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"[^A-Za-z0-9]", password):
        return False
    return True
def generate_invite_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
def extract_text_from_file(file_path):
    text = ""

    if file_path.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

    elif file_path.endswith(".pdf"):
        reader = PdfReader(file_path)
        for page in reader.pages:
            text += page.extract_text() or ""

    return text.strip()
def generate_narration(text):
    prompt = f"""
You are a friendly, experienced teacher.

Explain the following content in a very simple, natural,
and descriptive way, as if you are teaching a student.

Do NOT read line by line.
Do NOT mention that this is from a document.
Just explain smoothly like a lecture.

Content:
{text}
"""

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content.strip()
import json
import random

def generate_ai_questions(narration_text):

    prompt = f"""
Generate 15 high-quality multiple choice questions strictly based on the lecture content below.

Rules:
- Each question must have exactly 4 options.
- Do NOT include A/B/C/D in the option text.
- Options must be clear and meaningful.
- Questions must test understanding and application.
- Avoid repetitive patterns.
- Do NOT go outside the lecture content.
- Mix conceptual and practical questions.
- Ensure correct answers are not always in the same position.

Return ONLY valid JSON in this format:

[
  {{
    "question": "Question text here?",
    "options": [
      "Option text 1",
      "Option text 2",
      "Option text 3",
      "Option text 4"
    ],
    "correct_answer": "Option text 1",
    "explanation": "Short explanation"
  }}
]

Lecture Content:
{narration_text}
"""

    response = groq_client.chat.completions.create(
        model=GROQ_CHAT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4
    )

    content = response.choices[0].message.content.strip()

    start = content.find("[")
    end = content.rfind("]") + 1
    json_text = content[start:end]

    questions = json.loads(json_text)

    # 🔥 IMPORTANT PART — RANDOMIZE OPTIONS SAFELY
    for q in questions:
        correct_option_text = q["correct_answer"]

        options = q["options"]
        random.shuffle(options)

        q["options"] = options

        # Convert correct answer text → letter
        correct_index = options.index(correct_option_text)
        q["correct_answer"] = ["A", "B", "C", "D"][correct_index]

    return questions



def text_to_audio(text, filename):
    tts = gTTS(text=text, lang="en")
    audio_path = os.path.join(AUDIO_FOLDER, filename)
    tts.save(audio_path)
    return filename
def create_lecture_video(audio_filename, video_filename, presenter=None):

    if not presenter:
        presenter = "ai_girl.mp4"   # default fallback

    audio_path = os.path.join(AUDIO_FOLDER, audio_filename)
    video_path = os.path.join(VIDEO_FOLDER, video_filename)

    BASE_DIR = os.path.dirname(app.root_path)

    presenter_path = os.path.join(
        BASE_DIR,
        "assets",
        "presenters",
        presenter
    )



    # 🎧 Load audio
    audio = AudioFileClip(audio_path)

    # 🎥 Load presenter video (remove original audio)
    base_video = VideoFileClip(presenter_path).without_audio()

    audio_duration = audio.duration
    video_duration = base_video.duration

    # 🟢 Case 1: Presenter video longer → trim
    if video_duration >= audio_duration:
        final_video = base_video.subclip(0, audio_duration)

    # 🔵 Case 2: Presenter video shorter → loop
    else:
        loops_needed = int(audio_duration // video_duration) + 1
        final_video = concatenate_videoclips(
            [base_video] * loops_needed
        ).subclip(0, audio_duration)

    # 🔊 Attach narration audio
    final_video = final_video.set_audio(audio)

    # 🎬 Export final video
    final_video.write_videofile(
        video_path,
        codec="libx264",
        audio_codec="aac",
        fps=24
    )

    return video_filename

def make_one_word(answer):
    # 1. remove leading/trailing spaces
    answer = answer.strip()

    # 2. split by space and take ONLY first word
    first_word = answer.split()[0]

    # 3. remove symbols (keep letters & numbers only)
    clean_word = re.sub(r'[^a-zA-Z0-9]', '', first_word)

    return clean_word

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]

        # Email format check
        if not is_valid_email(email):
            return "Invalid email format!"

        # Password strength check
        if not is_strong_password(password):
            return ("Password must be at least 10 characters long and include "
                    "uppercase, lowercase, number, and special character.")

        # Duplicate email check
        if users_collection.find_one({"email": email}):
            return "Email already registered!"

        hashed_password = generate_password_hash(password)

        user = {
            "name": name,
            "email": email,
            "password": hashed_password,
            "role": role
        }

        users_collection.insert_one(user)

        return "Registration successful!"

    return render_template("register.html")
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = users_collection.find_one({"email": email})

        if not user:
            return "Email not registered!"

        if not check_password_hash(user["password"], password):
            return "Incorrect password!"

        # STORE USER INFO IN SESSION
        session["user_id"] = str(user["_id"])
        session["user_name"] = user["name"]
        session["user_role"] = user["role"]

        return redirect(url_for("dashboard"))

    return render_template("login.html")
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session["user_role"] == "teacher":
        return redirect(url_for("teacher_dashboard"))
    elif session["user_role"] == "student":
        return redirect(url_for("student_dashboard"))
    else:
        return "Invalid role"
@app.route("/teacher/dashboard")
def teacher_dashboard():
    if "user_id" not in session or session.get("user_role") != "teacher":
        return redirect(url_for("login"))

    # Get classrooms created by this teacher
    classrooms = list(
        classrooms_collection.find(
            {"teacher_id": session["user_id"]}
        )
    )

    return render_template(
        "teacher_dashboard.html",
        name=session["user_name"],
        classrooms=classrooms
    )

@app.route("/student/dashboard")
def student_dashboard():
    if "user_id" not in session or session.get("user_role") != "student":
        return redirect(url_for("login"))

    # Get classrooms the student has joined
    classrooms = list(
        classrooms_collection.find(
            {"students": session["user_id"]}
        )
    )

    return render_template(
        "student_dashboard.html",
        name=session["user_name"],
        classrooms=classrooms
    )

@app.route("/teacher/upload", methods=["GET", "POST"])
def upload_material():
    # Allow only logged-in teachers
    if "user_id" not in session or session.get("user_role") != "teacher":
        return redirect(url_for("login"))

    if request.method == "POST":
        if "file" not in request.files:
            return "No file part"

        file = request.files["file"]

        if file.filename == "":
            return "No selected file"

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            return "File uploaded successfully!"

        return "Invalid file type!"

    return render_template("upload.html")
@app.route("/teacher/view/<path:filename>")
def view_file(filename):
    if "user_id" not in session or session.get("user_role") != "teacher":
        return redirect(url_for("login"))

    safe_filename = secure_filename(filename)

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        safe_filename,
        as_attachment=False
    )
@app.route("/teacher/create-classroom", methods=["GET", "POST"])
def create_classroom():
    if "user_id" not in session or session.get("user_role") != "teacher":
        return redirect(url_for("login"))

    if request.method == "POST":
        class_name = request.form["class_name"]
        invite_code = generate_invite_code()

        classroom = {
            "class_name": class_name,
            "invite_code": invite_code,
            "teacher_id": session["user_id"],
            "students": []
        }

        classrooms_collection.insert_one(classroom)

        return "Classroom created successfully!"

    return render_template("create_classroom.html")
@app.route("/student/join-classroom", methods=["GET", "POST"])
def join_classroom():
    if "user_id" not in session or session.get("user_role") != "student":
        return redirect(url_for("login"))

    if request.method == "POST":
        invite_code = request.form["invite_code"]

        classroom = classrooms_collection.find_one(
            {"invite_code": invite_code}
        )

        if not classroom:
            return "Invalid invite code!"

        # Avoid duplicate joining
        if session["user_id"] in classroom["students"]:
            return "You are already in this classroom."

        classrooms_collection.update_one(
            {"_id": classroom["_id"]},
            {"$push": {"students": session["user_id"]}}
        )

        return "Successfully joined the classroom!"

    return render_template("join_classroom.html")
@app.route("/student/classroom/<classroom_id>")
def student_classroom(classroom_id):
    if "user_id" not in session or session.get("user_role") != "student":
        return redirect(url_for("login"))

    classroom = classrooms_collection.find_one(
        {"_id": ObjectId(classroom_id)}
    )

    if not classroom:
        return "Classroom not found!"

    if session["user_id"] not in classroom["students"]:
        return "Access denied!"

    # Get study materials for this classroom
    study_materials = list(
        study_materials_collection.find(
            {"classroom_id": str(classroom["_id"])}
        )
    )


    # Get participants
    students = list(
        users_collection.find(
            {"_id": {"$in": [ObjectId(sid) for sid in classroom["students"]]}},
            {"name": 1}
        )
    )
    videos = list(
        videos_collection.find(
            {
                "classroom_id": str(classroom["_id"]),
                "is_published": True
            }
        )
    )
    
    # 🔵 Fetch posts (sorted)
    posts = list(
        community_posts_collection.find(
            {"classroom_id": classroom_id}
        ).sort("created_at", -1)
    )

    # 🔵 Mark posts as seen
    for post in posts:
        if session["user_id"] not in post.get("seen_by", []):
            community_posts_collection.update_one(
                {"_id": post["_id"]},
                {"$push": {"seen_by": session["user_id"]}}
            )

    assignments = list(
        assignments_collection.find({"classroom_id": classroom_id})
    )

    for a in assignments:

        # 🔁 Convert due_date to datetime if string
        if isinstance(a["due_date"], str):
            a["due_date"] = datetime.strptime(a["due_date"], "%Y-%m-%d")

        # 🔎 Find submission
        submission = assignment_submissions_collection.find_one({
            "assignment_id": str(a["_id"]),
            "student_id": session["user_id"]
        })

        a["submitted"] = submission is not None

        if submission:
            a["answer_file"] = submission["answer_file"]

        # 🔒 Lock check
        a["locked"] = datetime.utcnow() > a["due_date"]

    live_class = live_classes_collection.find_one({
        "classroom_id": classroom_id,
        "status": "live"
    })

    
    return render_template(
        "student_classroom.html",
        classroom=classroom,
        students=students,
        study_materials=study_materials,
        posts=posts,
        videos=videos,
        assignments=assignments,
        live_class=live_class
    )

@app.route("/teacher/classroom/<classroom_id>")
def teacher_classroom(classroom_id):
    if "user_id" not in session or session.get("user_role") != "teacher":
        return redirect(url_for("login"))

    classroom = classrooms_collection.find_one(
        {"_id": ObjectId(classroom_id)}
    )

    if not classroom:
        return "Classroom not found!"

    if classroom["teacher_id"] != session["user_id"]:
        return "Access denied!"

    # ✅ FETCH VIDEOS FOR THIS CLASSROOM
    videos = list(
        videos_collection.find(
            {"classroom_id": classroom_id}
        )
    )

    # 🔥 Add mapping indicator
    for video in videos:
        mapped_count = questions_collection.count_documents({
            "video_id": str(video["_id"]),
            "ask_time": {"$ne": None}
        })

        video["is_mapped"] = mapped_count > 0

    posts = list(
        community_posts_collection.find(
            {"classroom_id": classroom_id}
        ).sort("created_at", -1)
    )

    assignments = list(
        assignments_collection.find({"classroom_id": classroom_id})
    )
    return render_template(
        "teacher_classroom.html",
        classroom=classroom,
        videos=videos,
        posts=posts,
        assignments=assignments,
        open_community=True   
    )


@app.route("/teacher/classroom/<classroom_id>/upload-material", methods=["GET", "POST"])
def upload_study_material(classroom_id):
    if "user_id" not in session or session.get("user_role") != "teacher":
        return redirect(url_for("login"))

    classroom = classrooms_collection.find_one({"_id": ObjectId(classroom_id)})
    if not classroom or classroom["teacher_id"] != session["user_id"]:
        return "Access denied!"

    if request.method == "POST":
        file = request.files.get("file")

        if not file or file.filename == "":
            return "No file selected!"

        filename = secure_filename(file.filename)
        save_path = os.path.join(app.config["STUDY_MATERIAL_FOLDER"], filename)
        file.save(save_path)

        study_materials_collection.insert_one({
            "classroom_id": classroom_id,
            "teacher_id": session["user_id"],
            "filename": filename,
            "filepath": save_path,
            "uploaded_at": datetime.utcnow()
        })

    # ✅ FETCH STUDY MATERIALS FOR THIS CLASSROOM
    materials = list(study_materials_collection.find({
        "classroom_id": classroom_id,
        "teacher_id": session["user_id"]
    }))

    return render_template(
        "upload_study_material.html",
        classroom_id=classroom_id,
        materials=materials
    )

@app.route("/materials/view/<path:filename>")
def view_material(filename):
    # Allow both teachers and students
    if "user_id" not in session:
        return redirect(url_for("login"))

    safe_filename = secure_filename(filename)

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        safe_filename,
        as_attachment=False
    )
@app.route("/teacher/classroom/<classroom_id>/create-video", methods=["GET", "POST"])
def create_video(classroom_id):
    if "user_id" not in session or session.get("user_role") != "teacher":
        return redirect(url_for("login"))

    classroom = classrooms_collection.find_one(
        {"_id": ObjectId(classroom_id)}
    )

    if not classroom or classroom["teacher_id"] != session["user_id"]:
        return "Access denied!"

    if request.method == "POST":
        action = request.form.get("action")

        # STEP 1: File upload & text extraction
        if action is None:
            title = request.form.get("title")
            description = request.form.get("description")
            presenter = request.form.get("presenter", "ai_girl.mp4")

            file = request.files.get("file")

            if not file or file.filename == "":
                return "No file uploaded!"

            if not allowed_file(file.filename):
                return "Invalid file type!"

            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(file_path)

            extracted_text = extract_text_from_file(file_path)

            session["temp_extracted_text"] = extracted_text
            session["temp_title"] = title
            session["temp_description"] = description

            return render_template(
                "video_preview.html",
                classroom_id=classroom_id,
                extracted_text=extracted_text,
                title=title,
                description=description,
                presenter=presenter
            )


        # STEP 2: Generate AI narration
        if action == "generate_narration":
            title = request.form.get("title")
            description = request.form.get("description")
            presenter = request.form.get("presenter", "ai_girl.mp4")

            extracted_text = session.get("temp_extracted_text", "").strip()
            title = session.get("temp_title")
            description = session.get("temp_description")


            if not extracted_text:
                return "Extracted text missing. Please upload file again."

            narration = generate_narration(extracted_text)

            return render_template(
                "video_preview.html",
                classroom_id=classroom_id,
                extracted_text=extracted_text,
                narration=narration,
                title=title,
                description=description,
                presenter=presenter
            )


        # STEP 3: Generate audio
        if action == "generate_audio":
            title = request.form.get("title")
            description = request.form.get("description")
            presenter = request.form.get("presenter", "ai_girl.mp4")

            narration = request.form.get("narration", "")
            extracted_text = session.get("temp_extracted_text", "")


            if not narration:
                return "Narration missing. Please generate narration first."

            audio_filename = f"narration_{uuid.uuid4().hex}.mp3"
            text_to_audio(narration, audio_filename)

            return render_template(
                "video_preview.html",
                classroom_id=classroom_id,
                extracted_text=extracted_text,
                narration=narration,
                audio_file=audio_filename,
                title=title,
                description=description,
                presenter=presenter
            )

        # STEP 4: Generate final lecture video
        if action == "generate_video":
            title = request.form.get("title")
            description = request.form.get("description")
            presenter = request.form.get("presenter", "ai_girl.mp4")

            audio_file = request.form.get("audio_file")
            narration = request.form.get("narration")
            extracted_text = session.get("temp_extracted_text", "")
            presenter = request.form.get("presenter") or "ai_girl.mp4"
            video_filename = f"final_{uuid.uuid4().hex}.mp4"

            create_lecture_video(
                audio_filename=audio_file,
                video_filename=video_filename,
                presenter=presenter
            )

            # ✅ SAVE VIDEO METADATA IN DB
            title = request.form.get("title")
            description = request.form.get("description")

            videos_collection.insert_one({
                "classroom_id": classroom_id,
                "teacher_id": session["user_id"],
                "title": title,
                "description": description,
                "video_filename": video_filename,
                "audio_filename": audio_file,
                "narration_text": narration,
                "is_published": False,
                "created_at": datetime.utcnow()
            })


            return render_template(
                "video_preview.html",
                classroom_id=classroom_id,
                extracted_text=extracted_text,
                narration=narration,
                audio_file=audio_file,
                video_file=video_filename
            )

    # GET request
    return render_template(
        "create_video.html",
        classroom_id=classroom_id
    )

@app.route("/audio/<filename>")
def serve_audio(filename):
    return send_from_directory(AUDIO_FOLDER, filename)
@app.route("/videos/<filename>")
def serve_video(filename):
    return send_from_directory(VIDEO_FOLDER, filename)
@app.route("/teacher/video/<video_id>/publish", methods=["POST"])
def publish_video(video_id):
    videos_collection.update_one(
        {"_id": ObjectId(video_id), "teacher_id": session["user_id"]},
        {"$set": {"is_published": True}}
    )
    return redirect(request.referrer)
@app.route("/teacher/video/<video_id>/unpublish", methods=["POST"])
def unpublish_video(video_id):
    videos_collection.update_one(
        {"_id": ObjectId(video_id), "teacher_id": session["user_id"]},
        {"$set": {"is_published": False}}
    )
    return redirect(request.referrer)
@app.route("/teacher/video/<video_id>/delete", methods=["POST"])
def delete_video(video_id):
    video = videos_collection.find_one(
        {"_id": ObjectId(video_id), "teacher_id": session["user_id"]}
    )

    if video:
        video_path = os.path.join(VIDEO_FOLDER, video["video_filename"])
        if os.path.exists(video_path):
            os.remove(video_path)

        videos_collection.delete_one({"_id": ObjectId(video_id)})

    return redirect(request.referrer)

@app.route("/teacher/material/<material_id>/delete", methods=["POST"])
def delete_study_material(material_id):
    material = study_materials_collection.find_one({"_id": ObjectId(material_id)})

    if material:
        if os.path.exists(material["filepath"]):
            os.remove(material["filepath"])

        study_materials_collection.delete_one({"_id": ObjectId(material_id)})

    return redirect(request.referrer)
@app.route("/student/classroom/<classroom_id>/video/<video_id>")
def watch_video(classroom_id, video_id):

    if "user_id" not in session or session.get("user_role") != "student":
        return redirect(url_for("login"))

    classroom = classrooms_collection.find_one(
        {"_id": ObjectId(classroom_id)}
    )

    if not classroom or session["user_id"] not in classroom["students"]:
        return "Access denied!"

    video = videos_collection.find_one(
        {"_id": ObjectId(video_id), "is_published": True}
    )

    if not video:
        return "Video not found!"

    # 🔥 GET QUESTIONS FOR THIS VIDEO
    raw_questions = list(
        questions_collection.find({
            "video_id": video_id,
            "ask_mode": "during",
            "ask_time": {"$ne": None}
        })
    )

    # 🔥 CONVERT TO JSON-SAFE FORMAT
    questions = []

    for q in raw_questions:
        questions.append({
            "_id": str(q["_id"]),
            "question": q["question"],
            "options": q.get("options", []),
            "correct_answer": q["correct_answer"],
            "explanation": q.get("explanation", ""),
            "ask_time": q["ask_time"]
        })

    return render_template(
        "student_watch_video.html",
        classroom=classroom,
        video=video,
        questions=questions
    )

@app.route("/teacher/video/<video_id>/map-questions", methods=["GET", "POST"])
def map_questions(video_id):

    if "user_id" not in session or session.get("user_role") != "teacher":
        return redirect(url_for("login"))

    video = videos_collection.find_one({"_id": ObjectId(video_id)})

    if not video:
        return "Video not found!"

    if request.method == "POST":

        questions = list(questions_collection.find({"video_id": video_id}))

        for q in questions:
            qid = str(q["_id"])

            selected_mode = request.form.get(f"mode_{qid}")
            selected_time = request.form.get(f"time_{qid}")

            if selected_mode == "during":
                questions_collection.update_one(
                    {"_id": q["_id"]},
                    {
                        "$set": {
                            "ask_mode": "during",
                            "ask_time": int(selected_time) if selected_time else None
                        }
                    }
                )

            elif selected_mode == "after":
                questions_collection.update_one(
                    {"_id": q["_id"]},
                    {
                        "$set": {
                            "ask_mode": "after",
                            "ask_time": None
                        }
                    }
                )

        return redirect(url_for("teacher_classroom", classroom_id=video["classroom_id"]))

    # GET
    ai_questions = list(
        questions_collection.find({"video_id": video_id})
    )

    return render_template(
        "teacher_map_questions.html",
        video=video,
        ai_questions=ai_questions
    )

@app.route("/teacher/video/<video_id>/generate-questions", methods=["POST"])
def generate_questions(video_id):
    if "user_id" not in session or session.get("user_role") != "teacher":
        return redirect(url_for("login"))

    video = videos_collection.find_one({"_id": ObjectId(video_id)})

    if not video:
        return "Video not found!"

    narration = video.get("narration_text")

    if not narration:
        return "Narration text not found for this video."

    # 1️⃣ Generate AI questions (returns a LIST)
    ai_questions = generate_ai_questions(narration)

    # 2️⃣ Optional: clear old questions for this video
    questions_collection.delete_many({"video_id": video_id})

    # 3️⃣ Save each question
    for q in ai_questions:
        questions_collection.insert_one({
            "video_id": video_id,
            "question": q["question"],
            "options": q["options"],
            "correct_answer": q["correct_answer"],
            "explanation": q["explanation"],
            "ask_time": None,
            "ask_mode": "during",
            "created_at": datetime.utcnow()
        })


    # 4️⃣ Redirect to mapping UI
    return redirect(url_for("map_questions", video_id=video_id))
@app.route("/teacher/video/<video_id>/toggle-publish", methods=["POST"])
def toggle_publish(video_id):

    if "user_id" not in session or session.get("user_role") != "teacher":
        return redirect(url_for("login"))

    video = videos_collection.find_one({"_id": ObjectId(video_id)})

    if not video:
        return "Video not found"

    new_status = not video.get("is_published", False)

    videos_collection.update_one(
        {"_id": ObjectId(video_id)},
        {"$set": {"is_published": new_status}}
    )

    return redirect(url_for("teacher_classroom", classroom_id=video["classroom_id"]))
@app.route("/student/classroom/<classroom_id>/video/<video_id>/quiz")
def after_class_quiz(classroom_id, video_id):

    if "user_id" not in session or session.get("user_role") != "student":
        return redirect(url_for("login"))

    classroom = classrooms_collection.find_one(
        {"_id": ObjectId(classroom_id)}
    )

    if not classroom or session["user_id"] not in classroom["students"]:
        return "Access denied!"

    video = videos_collection.find_one(
        {"_id": ObjectId(video_id), "is_published": True}
    )

    if not video:
        return "Video not found!"

    raw_questions = list(
        questions_collection.find({
            "video_id": video_id,
            "ask_mode": "after"
        })
    )

    questions = []
    for q in raw_questions:
        questions.append({
            "_id": str(q["_id"]),
            "question": q["question"],
            "options": q["options"],
            "correct_answer": q["correct_answer"],
            "explanation": q["explanation"]
        })

    return render_template(
        "student_after_quiz.html",
        classroom=classroom,
        video=video,
        questions=questions
    )
@app.route("/student/classroom/<classroom_id>/video/<video_id>/quiz/submit", methods=["POST"])
def submit_after_quiz(classroom_id, video_id):

    if "user_id" not in session or session.get("user_role") != "student":
        return redirect(url_for("login"))

    raw_questions = list(
        questions_collection.find({
            "video_id": video_id,
            "ask_mode": "after"
        })
    )

    score = 0
    total = len(raw_questions)

    results = []

    for q in raw_questions:

        qid = str(q["_id"])
        selected = request.form.get(f"question_{qid}")
        correct = q["correct_answer"]

        if selected == correct:
            score += 1
            status = "Correct"
        else:
            status = "Wrong"

        results.append({
            "question": q["question"],
            "selected": selected,
            "correct": correct,
            "status": status,
            "explanation": q["explanation"]
        })

    percentage = round((score / total) * 100, 2)

    # 🔥 SAVE RESULT
    student_results_collection.insert_one({
        "student_id": session["user_id"],
        "video_id": video_id,
        "classroom_id": classroom_id,
        "total_questions": total,
        "correct_answers": score,
        "score_percentage": percentage,
        "submitted_at": datetime.utcnow()
    })

    return render_template(
        "student_quiz_result.html",
        score=score,
        total=total,
        percentage=percentage,
        results=results
    )
@app.route("/teacher/classroom/<classroom_id>/results")
def view_results(classroom_id):

    if "user_id" not in session or session.get("user_role") != "teacher":
        return redirect(url_for("login"))

    raw_results = list(
        student_results_collection.find({"classroom_id": classroom_id})
    )

    results = []

    for r in raw_results:

        student = users_collection.find_one(
            {"_id": ObjectId(r["student_id"])}
        )

        video = videos_collection.find_one(
            {"_id": ObjectId(r["video_id"])}
        )

        results.append({
            "student_name": student["name"] if student else "Unknown",
            "video_title": video["title"] if video else "Unknown",
            "correct": r["correct_answers"],
            "total": r["total_questions"],
            "score": r["score_percentage"]
        })

    return render_template(
        "teacher_results.html",
        results=results
    )
@app.route("/student/classroom/<classroom_id>/performance")
def student_performance(classroom_id):

    if "user_id" not in session or session.get("user_role") != "student":
        return redirect(url_for("login"))

    classroom = classrooms_collection.find_one(
        {"_id": ObjectId(classroom_id)}
    )

    if not classroom or session["user_id"] not in classroom["students"]:
        return "Access denied!"

    # 🔵 Fetch student results
    raw_results = list(
        student_results_collection.find({
            "student_id": session["user_id"],
            "classroom_id": classroom_id
        }).sort("submitted_at", 1)
    )

    student_results = []
    test_labels = []
    scores = []

    for r in raw_results:

        video = videos_collection.find_one(
            {"_id": ObjectId(r["video_id"])}
        )

        video_title = video["title"] if video else "Test"

        score = r["score_percentage"]

        # 🔥 ADD GRADE LOGIC HERE
        if score >= 90:
            grade = "Excellent"
        elif score >= 75:
            grade = "Good"
        elif score >= 60:
            grade = "Average"
        else:
            grade = "Needs Improvement"

        student_results.append({
            "video_title": video_title,
            "correct": r["correct_answers"],
            "total": r["total_questions"],
            "score": score,
            "grade": grade   # 🔥 NEW FIELD
        })

        test_labels.append(video_title)
        scores.append(score)


    total_tests = questions_collection.distinct(
        "video_id",
        {"ask_mode": "after"}
    )

    return render_template(
        "student_performance.html",
        classroom=classroom,
        total_tests=len(total_tests),
        attended_count=len(student_results),
        student_results=student_results,
        test_labels=test_labels,
        scores=scores
    )
@app.route("/teacher/classroom/<classroom_id>/community/post", methods=["POST"])
def post_community(classroom_id):

    if "user_id" not in session or session.get("user_role") != "teacher":
        return redirect(url_for("login"))

    content = request.form.get("content")

    if not content:
        return "Post cannot be empty"

    community_posts_collection.insert_one({
        "classroom_id": classroom_id,
        "teacher_id": session["user_id"],
        "content": content,
        "seen_by": [],
        "reactions": [],
        "created_at": datetime.utcnow()
    })


    return redirect(url_for("teacher_classroom", classroom_id=classroom_id))
@app.route("/student/classroom/<classroom_id>/community/react/<post_id>", methods=["POST"])
def react_to_post(classroom_id, post_id):

    if "user_id" not in session or session.get("user_role") != "student":
        return redirect(url_for("login"))

    post = community_posts_collection.find_one({"_id": ObjectId(post_id)})

    if not post:
        return "Post not found"

    student_id = str(session["user_id"])   # 🔥 FORCE STRING

    post = community_posts_collection.find_one({"_id": ObjectId(post_id)})

    if student_id in post.get("reactions", []):
        community_posts_collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$pull": {"reactions": student_id}}
        )
    else:
        community_posts_collection.update_one(
            {"_id": ObjectId(post_id)},
            {"$addToSet": {"reactions": student_id}}  # 🔥 use addToSet instead of push
        )


    return redirect(url_for("student_classroom", classroom_id=classroom_id))
@app.route("/teacher/classroom/<classroom_id>/create-assignment", methods=["GET", "POST"])
def create_assignment(classroom_id):

    if "user_id" not in session or session.get("user_role") != "teacher":
        return redirect(url_for("login"))

    if request.method == "POST":

        title = request.form.get("title")
        description = request.form.get("description")
        due_date = request.form.get("due_date")

        file = request.files.get("file")

        filename = None
        if file and file.filename != "":
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        assignments_collection.insert_one({
            "classroom_id": classroom_id,
            "teacher_id": session["user_id"],
            "title": title,
            "description": description,
            "question_file": filename,
            "due_date": due_date,
            "created_at": datetime.utcnow()
        })

        return redirect(url_for("teacher_classroom", classroom_id=classroom_id))

    return render_template("create_assignment.html", classroom_id=classroom_id)
@app.route("/student/classroom/<classroom_id>/assignment/<assignment_id>", methods=["GET", "POST"])
def submit_assignment(classroom_id, assignment_id):

    if "user_id" not in session or session.get("user_role") != "student":
        return redirect(url_for("login"))

    assignment = assignments_collection.find_one(
        {"_id": ObjectId(assignment_id)}
    )

    if not assignment:
        return "Assignment not found."

    # 🔥 Lock check
    due_date = assignment["due_date"]

    if isinstance(due_date, str):
        due_date = datetime.strptime(due_date, "%Y-%m-%d")

    if datetime.utcnow() > due_date:
        return "Submission Closed. Deadline Passed."

    if request.method == "POST":

        file = request.files.get("file")

        if not file or file.filename == "":
            return "No file uploaded!"

        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        existing = assignment_submissions_collection.find_one({
            "assignment_id": assignment_id,
            "student_id": session["user_id"]
        })

        if existing:
            assignment_submissions_collection.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "answer_file": filename,
                        "submitted_at": datetime.utcnow()
                    }
                }
            )
        else:
            assignment_submissions_collection.insert_one({
                "assignment_id": assignment_id,
                "classroom_id": classroom_id,
                "student_id": session["user_id"],
                "answer_file": filename,
                "submitted_at": datetime.utcnow(),
                "marks": None
            })

        return redirect(url_for("student_classroom", classroom_id=classroom_id))

    return render_template("submit_assignment.html", assignment=assignment)
@app.route("/teacher/assignment/<assignment_id>/submissions")
def view_submissions(assignment_id):

    if "user_id" not in session or session.get("user_role") != "teacher":
        return redirect(url_for("login"))

    raw_submissions = list(
        assignment_submissions_collection.find({
            "assignment_id": assignment_id
        })
    )

    submissions = []

    for s in raw_submissions:

        student = users_collection.find_one(
            {"_id": ObjectId(s["student_id"])},
            {"name": 1}
        )

        student_name = student["name"] if student else "Unknown Student"

        submissions.append({
            "student_name": student_name,
            "answer_file": s["answer_file"],
            "submitted_at": s["submitted_at"]
        })

    return render_template(
        "assignment_submissions.html",
        submissions=submissions
    )  
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)   

@app.route("/teacher/classroom/<classroom_id>/start-live", methods=["POST"])
def start_live_class(classroom_id):

    room_id = str(uuid.uuid4())

    live_classes_collection.insert_one({
        "classroom_id": classroom_id,
        "teacher_id": session["user_id"],
        "room_id": room_id,
        "status": "live",
        "created_at": datetime.utcnow()
    })

    return redirect(url_for("live_room", room_id=room_id))
@app.route("/live/<room_id>")
def live_room(room_id):

    live_class = live_classes_collection.find_one({
        "room_id": room_id,
        "status": "live"
    })

    if not live_class:
        return "No live class active right now."

    return render_template(
        "live_class.html",
        room_id=room_id,
        user_name=session["user_name"],
        role=session["user_role"]
    )
@app.route("/teacher/end-live/<room_id>", methods=["POST"])
def end_live_class(room_id):

    live_classes_collection.update_one(
        {"room_id": room_id},
        {"$set": {"status": "ended"}}
    )

    return "Class ended"
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@socketio.on("join_room")
def handle_join(data):

    room = data["room"]
    username = data["username"]

    join_room(room)

    # notify everyone in the room
    emit(
        "user_joined",
        {"username": username},
        room=room
    )


@socketio.on("send_message")
def handle_message(data):

    room = data["room"]

    emit(
        "receive_message",
        data,
        room=room
    )
@socketio.on("end_class")
def handle_end_class(data):

    room = data["room"]

    live_classes_collection.update_one(
        {"room_id": room},
        {
            "$set": {
                "status": "ended",
                "ended_at": datetime.utcnow()
            }
        }
    )

    emit(
        "class_ended",
        {"message": "Live class has ended"},
        room=room
    )
@socketio.on("request_stream")
def handle_stream_request(data):

    room = data["room"]

    emit(
        "start_stream",
        {},
        room=room
    )
@socketio.on("video_offer")
def handle_video_offer(data):

    emit(
        "video_offer",
        data,
        room=data["room"],
        include_self=False
    )


@socketio.on("video_answer")
def handle_video_answer(data):

    emit(
        "video_answer",
        data,
        room=data["room"],
        include_self=False
    )


@socketio.on("ice_candidate")
def handle_ice_candidate(data):

    emit(
        "ice_candidate",
        data,
        room=data["room"],
        include_self=False
    )
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Server starting on port {port}...")
    socketio.run(app, host="0.0.0.0", port=port, debug=True)