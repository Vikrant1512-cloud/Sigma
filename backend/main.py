import os
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager

import jwt
from dotenv import load_dotenv
from fastapi import (
    FastAPI, HTTPException, Depends, UploadFile, File,
    Form, status
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pwdlib import PasswordHash


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
STUDENT_SHARED_PASSWORD = os.getenv("STUDENT_SHARED_PASSWORD")

if not all([
    SECRET_KEY,
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    STUDENT_SHARED_PASSWORD
]):
    raise RuntimeError("Missing configuration in backend/.env")

ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60 * 12

DATABASE = BASE_DIR / "sigma.db"
PDF_FOLDER = BASE_DIR / "storage" / "pdfs"
PDF_FOLDER.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

password_hasher = PasswordHash.recommended()

ADMIN_PASSWORD_HASH = password_hasher.hash(ADMIN_PASSWORD)
STUDENT_PASSWORD_HASH = password_hasher.hash(STUDENT_SHARED_PASSWORD)

security = HTTPBearer()


# --------------------------------------------------
# APP
# --------------------------------------------------

app = FastAPI(title="Sigma API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# DATABASE
# --------------------------------------------------

@contextmanager
def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialise_database():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                filename TEXT NOT NULL,
                category_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(category_id) REFERENCES categories(id)
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL
            )
        """)

        db.execute("PRAGMA foreign_keys = ON")

        db.execute("""
            INSERT OR IGNORE INTO categories (name, created_at)
            VALUES (?, ?)
        """, ("General", datetime.now(timezone.utc).isoformat()))


initialise_database()


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def current_time():
    return datetime.now(timezone.utc).isoformat()


def log_activity(username, role, action, details=""):
    with get_db() as db:
        db.execute("""
            INSERT INTO activity
            (username, role, action, details, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (username, role, action, details, current_time()))


def create_token(username, role):
    expiry = datetime.now(timezone.utc) + timedelta(
        minutes=TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": username,
        "role": role,
        "exp": expiry
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")
        role = payload.get("role")

        if not username or role not in ["admin", "student"]:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token."
            )

        return {
            "username": username,
            "role": role
        }

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Your session has expired. Please log in again."
        )


def require_admin(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator access required."
        )

    return user


# --------------------------------------------------
# REQUEST MODELS
# --------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class CategoryRequest(BaseModel):
    name: str


# --------------------------------------------------
# BASIC ROUTES
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "Sigma API is running",
        "project": "Sigma"
    }


# --------------------------------------------------
# AUTHENTICATION
# --------------------------------------------------

@app.post("/api/login")
def login(data: LoginRequest):
    username = data.username.strip()

    if not username or not data.password:
        raise HTTPException(
            status_code=400,
            detail="Enter your username and password."
        )

    if username.lower() == ADMIN_USERNAME.lower():
        valid = password_hasher.verify(
            data.password,
            ADMIN_PASSWORD_HASH
        )

        if not valid:
            raise HTTPException(
                status_code=401,
                detail="Incorrect username or password."
            )

        role = "admin"
        username = ADMIN_USERNAME

    else:
        valid = password_hasher.verify(
            data.password,
            STUDENT_PASSWORD_HASH
        )

        if not valid:
            raise HTTPException(
                status_code=401,
                detail="Incorrect username or password."
            )

        role = "student"

    token = create_token(username, role)

    log_activity(username, role, "Login", "Successful login")

    return {
        "access_token": token,
        "token_type": "bearer",
        "username": username,
        "role": role
    }


@app.get("/api/me")
def get_me(user=Depends(get_current_user)):
    return user


# --------------------------------------------------
# CATEGORIES
# --------------------------------------------------

@app.get("/api/categories")
def get_categories(user=Depends(get_current_user)):
    with get_db() as db:
        rows = db.execute("""
            SELECT id, name, created_at
            FROM categories
            ORDER BY name
        """).fetchall()

    return [dict(row) for row in rows]


@app.post("/api/categories")
def create_category(
    data: CategoryRequest,
    user=Depends(require_admin)
):
    name = data.name.strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Category name cannot be empty."
        )

    try:
        with get_db() as db:
            cursor = db.execute("""
                INSERT INTO categories (name, created_at)
                VALUES (?, ?)
            """, (name, current_time()))

            category_id = cursor.lastrowid

    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="This category already exists."
        )

    log_activity(
        user["username"],
        user["role"],
        "Created category",
        name
    )

    return {
        "id": category_id,
        "name": name
    }


# --------------------------------------------------
# DOCUMENTS
# --------------------------------------------------

@app.get("/api/documents")
def get_documents(user=Depends(get_current_user)):
    with get_db() as db:
        rows = db.execute("""
            SELECT
                documents.id,
                documents.title,
                documents.category_id,
                categories.name AS category,
                documents.created_at
            FROM documents
            JOIN categories
                ON documents.category_id = categories.id
            ORDER BY documents.created_at DESC
        """).fetchall()

    return [dict(row) for row in rows]


@app.post("/api/documents")
async def upload_document(
    title: str = Form(...),
    category_id: int = Form(...),
    file: UploadFile = File(...),
    user=Depends(require_admin)
):
    title = title.strip()

    if not title:
        raise HTTPException(
            status_code=400,
            detail="Enter a document title."
        )

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed."
        )

    with get_db() as db:
        category = db.execute(
            "SELECT id FROM categories WHERE id = ?",
            (category_id,)
        ).fetchone()

    if not category:
        raise HTTPException(
            status_code=404,
            detail="Category not found."
        )

    content = await file.read(MAX_FILE_SIZE + 1)

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File size must not exceed 25 MB."
        )

    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid PDF."
        )

    stored_filename = f"{uuid.uuid4().hex}.pdf"
    destination = PDF_FOLDER / stored_filename
    destination.write_bytes(content)

    with get_db() as db:
        cursor = db.execute("""
            INSERT INTO documents
            (title, filename, category_id, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            title,
            stored_filename,
            category_id,
            current_time()
        ))

        document_id = cursor.lastrowid

    log_activity(
        user["username"],
        user["role"],
        "Uploaded document",
        title
    )

    return {
        "id": document_id,
        "title": title,
        "message": "Document uploaded successfully."
    }


@app.get("/api/documents/{document_id}/file")
def view_document(
    document_id: int,
    user=Depends(get_current_user)
):
    with get_db() as db:
        document = db.execute("""
            SELECT title, filename
            FROM documents
            WHERE id = ?
        """, (document_id,)).fetchone()

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )

    file_path = PDF_FOLDER / document["filename"]

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="The PDF file is missing from storage."
        )

    log_activity(
        user["username"],
        user["role"],
        "Opened document",
        document["title"]
    )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=document["title"] + ".pdf"
    )


@app.delete("/api/documents/{document_id}")
def delete_document(
    document_id: int,
    user=Depends(require_admin)
):
    with get_db() as db:
        document = db.execute("""
            SELECT title, filename
            FROM documents
            WHERE id = ?
        """, (document_id,)).fetchone()

        if not document:
            raise HTTPException(
                status_code=404,
                detail="Document not found."
            )

        db.execute(
            "DELETE FROM documents WHERE id = ?",
            (document_id,)
        )

    file_path = PDF_FOLDER / document["filename"]

    if file_path.exists():
        file_path.unlink()

    log_activity(
        user["username"],
        user["role"],
        "Deleted document",
        document["title"]
    )

    return {"message": "Document deleted successfully."}


# --------------------------------------------------
# ADMIN ACTIVITY
# --------------------------------------------------

@app.get("/api/admin/activity")
def get_activity(user=Depends(require_admin)):
    with get_db() as db:
        rows = db.execute("""
            SELECT username, role, action, details, created_at
            FROM activity
            ORDER BY id DESC
            LIMIT 200
        """).fetchall()

    return [dict(row) for row in rows]