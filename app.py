from flask import Flask, render_template, request, session, redirect, url_for, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = "super_secret_key"

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

users_db = {}
messages_db = {}

# ----------------
# MAIN PAGES
# ----------------

@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET","POST"])
def signup():

    if request.method == "POST":

        user = request.form.get("username")
        pw = request.form.get("password")

        if not user or not pw:
            return "INVALID DATA"

        if user in users_db:
            return "USER EXISTS"

        users_db[user] = pw
        messages_db[user] = {}

        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        user = request.form.get("username")
        pw = request.form.get("password")

        if users_db.get(user) == pw:
            session["user"] = user
            return redirect(url_for("dashboard"))

        return "WRONG LOGIN"

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect(url_for("login"))

    user = session["user"]
    recents = list(messages_db.get(user, {}).keys())

    return render_template(
        "dashboard.html",
        current_user=user,
        recents=recents
    )


# ----------------
# USER SEARCH
# ----------------

@app.route("/search_user")
def search_user():

    q = request.args.get("q","").lower()

    result = [u for u in users_db if q in u.lower()]

    return jsonify(result)


# ----------------
# LOAD CHAT
# ----------------

@app.route("/load_chat/<user>")
def load_chat(user):

    if "user" not in session:
        return jsonify([])

    me = session["user"]

    if user not in users_db:
        return jsonify([])

    messages_db.setdefault(me,{})
    messages_db.setdefault(user,{})

    messages_db[me].setdefault(user,[])
    messages_db[user].setdefault(me,[])

    return jsonify(messages_db[me][user])


# ----------------
# SEND MESSAGE
# ----------------

@app.route("/send_message", methods=["POST"])
def send_message():

    if "user" not in session:
        return "not logged"

    sender = session["user"]
    receiver = request.form.get("to")
    text = request.form.get("text","")

    if not text:
        return "empty"

    if receiver not in users_db:
        return "user not found"

    msg = {
        "type":"text",
        "content":text,
        "sender":sender
    }

    messages_db[sender].setdefault(receiver,[]).append(msg)
    messages_db[receiver].setdefault(sender,[]).append(msg)

    return "ok"


# ----------------
# FILE UPLOAD
# ----------------

@app.route("/upload", methods=["POST"])
def upload():

    if "user" not in session:
        return "not logged"

    sender = session["user"]
    receiver = request.form.get("to")

    if receiver not in users_db:
        return "user not found"

    if "file" not in request.files:
        return "no file"

    file = request.files["file"]

    if file.filename == "":
        return "empty file"

    filename = secure_filename(file.filename)

    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    ext = filename.split(".")[-1].lower()

    if ext in ["png","jpg","jpeg","gif"]:
        ftype="image"
    elif ext in ["mp4","webm"]:
        ftype="video"
    elif ext in ["mp3","wav","ogg"]:
        ftype="audio"
    else:
        ftype="file"

    msg = {
        "type":ftype,
        "content":filename,
        "sender":sender
    }

    messages_db[sender].setdefault(receiver,[]).append(msg)
    messages_db[receiver].setdefault(sender,[]).append(msg)

    return "ok"


# ----------------
# LOCATION
# ----------------

@app.route("/send_location", methods=["POST"])
def send_location():

    if "user" not in session:
        return "not logged"

    sender = session["user"]
    receiver = request.form.get("to")

    lat = request.form.get("lat")
    lon = request.form.get("lon")

    msg = {
        "type":"location",
        "content":f"{lat},{lon}",
        "sender":sender
    }

    messages_db[sender].setdefault(receiver,[]).append(msg)
    messages_db[receiver].setdefault(sender,[]).append(msg)

    return "ok"


# ----------------
# FILE SERVE
# ----------------

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ----------------

if __name__ == "__main__":
    app.run(debug=True, port=8080)