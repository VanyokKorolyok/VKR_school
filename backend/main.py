from fastapi import FastAPI, Depends, HTTPException, status, Response, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Gauge
from prometheus_fastapi_instrumentator import Instrumentator
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional, Dict
from pydantic import BaseModel, field_validator, ValidationInfo
from reportlab.lib.utils import simpleSplit, ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
from io import BytesIO
import logging
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from databases import Database
import hashlib
import json

# Инициализация FastAPI
app = FastAPI()

# Настройка Prometheus
Instrumentator().instrument(app).expose(app)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Асинхронное подключение к PostgreSQL
DATABASE_URL = "postgresql+asyncpg://postgres:root@localhost:5432/school_db"
database = Database(DATABASE_URL, min_size=1, max_size=10)

REPORTS_DIR = "reports"
if not os.path.exists(REPORTS_DIR):
    os.makedirs(REPORTS_DIR)

# Настройки JWT
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Настройка хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Предопределенный список классов
CLASSES = ["9A", "9B", "10A", "10B", "11A", "11B"]
SUBJECTS = ["Математика", "Литература", "Физика", "Химия", "История", "География", "Биология", "Английский язык"]

# Pydantic модели
class GradeCreate(BaseModel):
    student_id: int
    subject: str
    score: int

    @field_validator('subject')
    def check_subject(cls, v):
        if v not in SUBJECTS:
            raise ValueError(f'Subject must be one of {SUBJECTS}')
        return v

    @field_validator('score')
    def check_score(cls, v):
        if not 1 <= v <= 5:
            raise ValueError('Score must be between 1 and 5')
        return v

class GradeUpdate(BaseModel):
    subject: str
    score: int

    @field_validator('subject')
    def check_subject(cls, v):
        if v not in SUBJECTS:
            raise ValueError(f'Subject must be one of {SUBJECTS}')
        return v

    @field_validator('score')
    def check_score(cls, v):
        if not 1 <= v <= 5:
            raise ValueError('Score must be between 1 and 5')
        return v

class UserCreate(BaseModel):
    username: str
    password: str
    role: str
    first_name: str
    last_name: str
    class_name: Optional[str] = None

    @field_validator('role')
    def check_role(cls, v):
        if v not in ["teacher", "student"]:
            raise ValueError('Role must be "teacher" or "student"')
        return v

    @field_validator('class_name')
    def check_class(cls, v, info: ValidationInfo):
        role = info.data.get('role')
        if role == "student" and not v:
            raise ValueError('Class is required for students')
        if v and v not in CLASSES:
            raise ValueError(f'Class must be one of {CLASSES}')
        return v

class UserInDB(BaseModel):
    username: str
    hashed_password: str
    role: str

# Жизненный цикл приложения
@app.on_event("startup")
async def startup():
    await database.connect()
    # Создание таблиц
    await database.execute("""
        CREATE TABLE IF NOT EXISTS classes (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE
        )
    """)
    await database.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            hashed_password TEXT,
            role TEXT,
            student_id INTEGER
        )
    """)
    await database.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            name TEXT,
            class_id INTEGER REFERENCES classes(id),
            user_id INTEGER REFERENCES users(id)
        )
    """)
    await database.execute("""
        CREATE TABLE IF NOT EXISTS grades (
            id SERIAL PRIMARY KEY,
            student_id INTEGER REFERENCES students(id),
            subject TEXT,
            score INTEGER,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            teacher_id INTEGER REFERENCES users(id)
        )
    """)
    await database.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            student_id INTEGER REFERENCES students(id),
            summary TEXT,
            recommendations TEXT,
            data_hash TEXT,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

# Асинхронная зависимость для получения базы данных
async def get_db():
    try:
        async with database.transaction():
            yield database
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        raise

# Функция проверки базы данных
async def check_database():
    try:
        await database.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": str(e)}

# Метрика для HealthCheck
health_gauge = Gauge("app_health_status", "Health status of the application", ["component"])

# Обновление метрик в HealthCheck
@app.get("/health")
async def health_check():
    health_status = {
        "status": "healthy",
        "fastapi": "running",
        "database": await check_database()
    }
    health_gauge.labels(component="fastapi").set(1)
    if health_status["database"]["status"] == "healthy":
        health_gauge.labels(component="database").set(1)
    else:
        health_gauge.labels(component="database").set(0)
        health_status["status"] = "unhealthy"
    return health_status

# Функции для работы с JWT
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

async def get_user(db: Database, username: str):
    user = await db.fetch_one("SELECT * FROM users WHERE username = :username", {"username": username})
    return user

async def get_current_user(token: str = Depends(oauth2_scheme), db: Database = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = await get_user(db, username)
    if not user:
        raise credentials_exception
    return {"id": user["id"], "username": user["username"], "role": user["role"]}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Эндпоинт для регистрации пользователя
@app.post("/register")
async def register_user(user: UserCreate, db: Database = Depends(get_db)):
    try:
        logger.info(f"Registering user with data: {user.model_dump()}")
        existing_user = await get_user(db, user.username)
        if existing_user:
            logger.warning(f"Username {user.username} already exists")
            raise HTTPException(status_code=400, detail="Username already exists")

        hashed_password = pwd_context.hash(user.password)
        query = "INSERT INTO users (username, hashed_password, role) VALUES (:username, :hashed_password, :role) RETURNING id"
        new_user_id = await db.execute(query, {"username": user.username, "hashed_password": hashed_password, "role": user.role})

        if user.role == "student":
            if not user.class_name:
                logger.error("Class name is missing for student registration")
                raise HTTPException(status_code=400, detail="Class name is required for students")
            logger.info(f"Creating student for class: {user.class_name}")
            class_obj = await db.fetch_one("SELECT id FROM classes WHERE name = :name", {"name": user.class_name})
            if not class_obj:
                logger.info(f"Class {user.class_name} not found, creating new one")
                class_query = "INSERT INTO classes (name) VALUES (:name) RETURNING id"
                class_id = await db.execute(class_query, {"name": user.class_name})
            else:
                class_id = class_obj["id"]
            full_name = f"{user.first_name} {user.last_name}"
            student_query = "INSERT INTO students (name, class_id, user_id) VALUES (:name, :class_id, :user_id) RETURNING id"
            new_student_id = await db.execute(student_query, {"name": full_name, "class_id": class_id, "user_id": new_user_id})
            update_user_query = "UPDATE users SET student_id = :student_id WHERE id = :user_id"
            await db.execute(update_user_query, {"student_id": new_student_id, "user_id": new_user_id})

        logger.info(f"User created with ID: {new_user_id}")
        return {
            "message": "User registered successfully",
            "username": user.username,
            "role": user.role,
            "student_id": new_student_id if user.role == "student" else None,
            "full_name": f"{user.first_name} {user.last_name}" if user.role == "student" else None
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Эндпоинт для получения токена
@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Database = Depends(get_db)):
    user = await get_user(db, form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Добавление тестовых данных
async def init_test_data(db: Database):
    class_count = await db.fetch_val("SELECT COUNT(*) FROM classes")
    if class_count == 0:
        await db.execute("INSERT INTO classes (name) VALUES ('10A'), ('11B')")

    user_count = await db.fetch_val("SELECT COUNT(*) FROM users")
    if user_count == 0:
        teacher_hash = pwd_context.hash("teacherpassword")
        student1_hash = pwd_context.hash("studentpassword1")
        student2_hash = pwd_context.hash("studentpassword2")
        await db.execute("INSERT INTO users (username, hashed_password, role) VALUES ('teacher', :teacher_hash, 'teacher'), ('student1', :student1_hash, 'student'), ('student2', :student2_hash, 'student')", {"teacher_hash": teacher_hash, "student1_hash": student1_hash, "student2_hash": student2_hash})

    student_count = await db.fetch_val("SELECT COUNT(*) FROM students")
    if student_count == 0:
        class_10a_id = await db.fetch_val("SELECT id FROM classes WHERE name = '10A'")
        class_11b_id = await db.fetch_val("SELECT id FROM classes WHERE name = '11B'")
        student1_id = await db.fetch_val("SELECT id FROM users WHERE username = 'student1'")
        student2_id = await db.fetch_val("SELECT id FROM users WHERE username = 'student2'")
        await db.execute("INSERT INTO students (name, class_id, user_id) VALUES ('Иван Иванов', :class_10a_id, :student1_id), ('Мария Петрова', :class_11b_id, :student2_id)", {"class_10a_id": class_10a_id, "class_11b_id": class_11b_id, "student1_id": student1_id, "student2_id": student2_id})
        teacher_id = await db.fetch_val("SELECT id FROM users WHERE username = 'teacher'")
        student1_id = await db.fetch_val("SELECT id FROM students WHERE name = 'Иван Иванов'")
        student2_id = await db.fetch_val("SELECT id FROM students WHERE name = 'Мария Петрова'")
        await db.execute("UPDATE users SET student_id = :student_id WHERE id = :user_id", {"student_id": student1_id, "user_id": student1_id})
        await db.execute("UPDATE users SET student_id = :student_id WHERE id = :user_id", {"student_id": student2_id, "user_id": student2_id})
        await db.execute("INSERT INTO grades (student_id, subject, score, teacher_id) VALUES (:student1_id, 'Математика', 5, :teacher_id), (:student1_id, 'Литература', 4, :teacher_id), (:student2_id, 'Математика', 4, :teacher_id), (:student2_id, 'Литература', 5, :teacher_id)", {"student1_id": student1_id, "student2_id": student2_id, "teacher_id": teacher_id})

# Эндпоинт для инициализации тестовых данных
@app.get("/init-test-data")
async def init_data(db: Database = Depends(get_db)):
    await init_test_data(db)
    return {"message": "Тестовые данные добавлены"}

@app.get("/grades/{student_id}/stats")
async def get_grade_stats(student_id: int, current_user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    student = await db.fetch_one("SELECT * FROM students WHERE id = :id", {"id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if current_user["role"] == "student" and student["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Students can only view their own stats")

    summary, recommendations = await analyze_performance(student_id, db)
    if not summary:
        return {"average_scores": {}, "recommendations": "No grades found"}

    import re
    avg_score_match = re.search(r"Средний балл: (\d+\.\d+)", summary)
    subject_avg_match = re.search(r"Средние оценки по предметам: ({.*?})", summary)

    avg_score = float(avg_score_match.group(1)) if avg_score_match else 0.0
    subject_avg = eval(subject_avg_match.group(1)) if subject_avg_match else {}

    return {
        "average_score": avg_score,
        "average_scores": subject_avg,
        "recommendations": recommendations
    }

async def analyze_performance(student_id: int, db: Database) -> tuple[Optional[str], Optional[str]]:
    grades = await db.fetch_all("SELECT subject, score FROM grades WHERE student_id = :student_id", {"student_id": student_id})
    if not grades:
        return None, None

    data = [{"subject": g["subject"], "score": g["score"]} for g in grades]
    df = pd.DataFrame(data)
    avg_score = df["score"].mean()
    subject_avg = df.groupby("subject")["score"].mean().to_dict()
    recommendations = []
    if avg_score < 4:
        recommendations.append("Уделить больше внимания учёбе.")
    for subject, score in subject_avg.items():
        if score < 4:
            recommendations.append(f"Подтянуть знания по предмету: {subject}.")
    summary = f"Средний балл: {avg_score:.2f}. Средние оценки по предметам: {subject_avg}"
    recommendations_text = " ".join(recommendations) if recommendations else "Хорошая успеваемость, продолжайте в том же духе!"
    return summary, recommendations_text

def compute_data_hash(grades_data: Dict, summary: str, recommendations: str) -> str:
    """Вычисляем хэш данных для проверки изменений."""
    data = {
        "grades_data": grades_data,
        "summary": summary,
        "recommendations": recommendations
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()

def generate_pdf_report(student_id: int, student_name: str, grades_data: Dict, summary: str, recommendations: str, average_scores: Dict) -> str:
    """Генерация PDF-отчета (выполняется в фоновом режиме)."""
    font_name = 'DejaVuSans'
    pdfmetrics.registerFont(TTFont(font_name, 'C:/Users/ivang/Desktop/reactProject/VKR/backend/DejaVuSans.ttf'))
    last_name = student_name.split()[-1] if " " in student_name else student_name
    filename = os.path.join(REPORTS_DIR, f"отчет_{last_name}_{student_id}.pdf")
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    c.setFont("DejaVuSans", 12)
    y_position = height - 50

    logger.info(f"Generating report for student {student_id}. Summary: {summary}, Recommendations: {recommendations}")

    def draw_wrapped_text(x, y, text, max_width=400):
        lines = simpleSplit(text, font_name, 12, max_width)
        for line in lines:
            c.setFont(font_name, 12)
            c.drawString(x, y, line)
            y -= 20
        return y

    y_position = draw_wrapped_text(100, y_position, f"Отчет по успеваемости (ID студента: {student_id}, ФИО: {student_name})")
    y_position = draw_wrapped_text(100, y_position - 20, f"Дата: {datetime.now().strftime('%Y-%m-%d')}")

    y_position = draw_wrapped_text(100, y_position - 30, "Оценки:")
    for subject, grade_list in grades_data.items():
        grades_text = ", ".join([
            f"{g['score']} ({datetime.fromisoformat(g['date']).strftime('%Y-%m-%d %H:%M')})"
            for g in grade_list
        ])
        y_position = draw_wrapped_text(120, y_position - 20, f"{subject}: {grades_text}")
        if y_position < 100:
            c.showPage()
            y_position = height - 50

    if average_scores:
        fig = plt.Figure(figsize=(6, 4))
        fig_canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        ax.bar(average_scores.keys(), average_scores.values(), color='skyblue')
        ax.set_title('Средний балл по предметам')
        ax.set_ylabel('Средний балл')
        buf = BytesIO()
        fig_canvas.print_png(buf)
        buf.seek(0)
        image = ImageReader(buf)
        c.drawImage(image, 100, y_position - 300, width=300, height=200)
        buf.close()
        y_position -= 320
        if y_position < 100:
            c.showPage()
            y_position = height - 50

    y_position = draw_wrapped_text(100, y_position - 30, "Анализ:")
    y_position = draw_wrapped_text(100, y_position - 20, summary)
    if y_position < 100:
        c.showPage()
        y_position = height - 50

    y_position = draw_wrapped_text(100, y_position - 30, "Рекомендации:")
    y_position = draw_wrapped_text(100, y_position - 20, recommendations)

    c.showPage()
    c.save()
    return filename

async def background_generate_report(
    student_id: int,
    student_name: str,
    grades_data: Dict,
    summary: str,
    recommendations: str,
    average_scores: Dict,
    data_hash: str,
    db: Database
):
    """Фоновая задача для генерации отчета."""
    try:
        filename = generate_pdf_report(student_id, student_name, grades_data, summary, recommendations, average_scores)
        logger.info(f"Report generated for student {student_id}: {filename}")
        # Обновляем запись отчета с новым хэшем
        await db.execute(
            "UPDATE reports SET data_hash = :data_hash WHERE student_id = :student_id AND summary = :summary AND recommendations = :recommendations",
            {"student_id": student_id, "data_hash": data_hash, "summary": summary, "recommendations": recommendations}
        )
    except Exception as e:
        logger.error(f"Failed to generate report for student {student_id}: {str(e)}")

@app.get("/generate-report/{student_id}")
async def generate_report(
    student_id: int,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    student = await db.fetch_one("SELECT * FROM students WHERE id = :id", {"id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if current_user["role"] == "student" and student["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Students can only generate their own reports")
    elif current_user["role"] == "teacher" and not await db.fetch_one("SELECT 1 FROM students WHERE id = :id", {"id": student_id}):
        raise HTTPException(status_code=403, detail="Teacher can only generate reports for existing students")

    # Собираем данные для отчета
    grades = await db.fetch_all("SELECT subject, score, date, teacher_id FROM grades WHERE student_id = :student_id", {"student_id": student_id})
    grades_data = {}
    for grade in grades:
        if grade["subject"] not in grades_data:
            grades_data[grade["subject"]] = []
        grades_data[grade["subject"]].append({
            "score": grade["score"],
            "date": grade["date"].isoformat()
        })

    summary, recommendations = await analyze_performance(student_id, db)
    if not summary:
        raise HTTPException(status_code=404, detail="Оценки для ученика не найдены")

    stats_response = await get_grade_stats(student_id, current_user, db)
    average_scores = stats_response.get("average_scores", {})

    # Вычисляем хэш данных
    data_hash = compute_data_hash(grades_data, summary, recommendations)

    # Проверяем, есть ли уже отчет с таким хэшем
    existing_report = await db.fetch_one(
        "SELECT * FROM reports WHERE student_id = :student_id AND data_hash = :data_hash",
        {"student_id": student_id, "data_hash": data_hash}
    )

    # Проверяем, существует ли файл
    last_name = student["name"].split()[-1] if " " in student["name"] else student["name"]
    pdf_file = os.path.join(REPORTS_DIR, f"отчет_{last_name}_{student_id}.pdf")
    if existing_report and os.path.exists(pdf_file):
        logger.info(f"Returning cached report for student {student_id}: {pdf_file}")
        return {
            "message": "Report already exists and is up-to-date",
            "download_url": f"/download-report/{student_id}"
        }

    # Сохраняем запись отчета в базе
    report_query = "INSERT INTO reports (student_id, summary, recommendations, data_hash) VALUES (:student_id, :summary, :recommendations, :data_hash) RETURNING id"
    await db.execute(report_query, {"student_id": student_id, "summary": summary, "recommendations": recommendations, "data_hash": data_hash})

    # Запускаем генерацию отчета в фоновом режиме
    background_tasks.add_task(
        background_generate_report,
        student_id,
        student["name"],
        grades_data,
        summary,
        recommendations,
        average_scores,
        data_hash,
        db
    )

    return {
        "message": "Report generation started in the background",
        "download_url": f"/download-report/{student_id}"
    }

@app.get("/download-report/{student_id}")
async def download_report(student_id: int, current_user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    student = await db.fetch_one("SELECT * FROM students WHERE id = :id", {"id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if current_user["role"] == "student" and student["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Students can only download their own reports")
    elif current_user["role"] == "teacher" and not await db.fetch_one("SELECT 1 FROM students WHERE id = :id", {"id": student_id}):
        raise HTTPException(status_code=403, detail="Teacher can only download reports for existing students")

    last_name = student["name"].split()[-1] if " " in student["name"] else student["name"]
    pdf_file = os.path.join(REPORTS_DIR, f"отчет_{last_name}_{student_id}.pdf")

    if not os.path.exists(pdf_file):
        raise HTTPException(status_code=404, detail="Report is not ready yet or failed to generate")

    return FileResponse(
        path=pdf_file,
        media_type="application/pdf",
        filename=os.path.basename(pdf_file)
    )

@app.get("/students")
async def get_students(class_name: Optional[str] = None, current_user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can view all students")

    query = "SELECT s.id, s.name, c.name AS class_name FROM students s JOIN classes c ON s.class_id = c.id"
    values = {}
    if class_name:
        query += " WHERE c.name = :class_name"
        values["class_name"] = class_name

    logger.info(f"Executing query: {query} with values: {values}")
    students = await db.fetch_all(query, values)
    logger.info(f"Students query result: {students}")

    result = [{"id": s["id"], "name": s["name"], "class_name": s["class_name"]} for s in students]
    logger.info(f"Returning students: {result}")
    return result

@app.get("/students/{student_id}")
async def get_student(student_id: int, current_user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    student = await db.fetch_one("SELECT s.id, s.name, c.name AS class_name FROM students s JOIN classes c ON s.class_id = c.id WHERE s.id = :id", {"id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if current_user["role"] == "student" and student["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="You can only view your own data")
    return {"id": student["id"], "name": student["name"], "class_name": student["class_name"]}

@app.get("/grades/{student_id}")
async def get_grades(
    student_id: int,
    subject: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "asc",
    page: int = 1,
    per_page: int = 5,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    student = await db.fetch_one("SELECT * FROM students WHERE id = :id", {"id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if current_user["role"] == "student":
        user_student = await db.fetch_one("SELECT * FROM students WHERE user_id = :user_id", {"user_id": current_user["id"]})
        if user_student and user_student["id"] != student_id:
            raise HTTPException(status_code=403, detail="Students can only view their own grades")

    query = "SELECT * FROM grades WHERE student_id = :student_id"
    values = {"student_id": student_id}
    if subject:
        query += " AND subject = :subject"
        values["subject"] = subject

    total_grades = await db.fetch_val("SELECT COUNT(*) FROM grades WHERE student_id = :student_id" + (" AND subject = :subject" if subject else ""), values)
    if sort_by in ["date", "score"]:
        query += f" ORDER BY {sort_by} {sort_order.upper()}"
    query += " LIMIT :per_page OFFSET :offset"
    values["per_page"] = per_page
    values["offset"] = (page - 1) * per_page
    grades = await db.fetch_all(query, values)

    grouped_grades = {}
    for grade in grades:
        if grade["subject"] not in grouped_grades:
            grouped_grades[grade["subject"]] = []
        grouped_grades[grade["subject"]].append({
            "id": grade["id"],
            "score": grade["score"],
            "date": grade["date"].isoformat(),
            "teacher_id": grade["teacher_id"]
        })

    if sort_by in ["date", "score"]:
        for subj in grouped_grades:
            grouped_grades[subj].sort(
                key=lambda x: x[sort_by],
                reverse=(sort_order == "desc")
            )

    logger.info(f"Returning grades for student {student_id}: {grouped_grades}")
    return {
        "grades": grouped_grades,
        "total": total_grades,
        "page": page,
        "per_page": per_page,
        "total_pages": (total_grades + per_page - 1) // per_page
    }

@app.get("/me")
async def get_current_user_data(current_user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    if current_user["role"] == "student":
        student = await db.fetch_one("SELECT id FROM students WHERE user_id = :user_id", {"user_id": current_user["id"]})
        return {"id": current_user["id"], "role": current_user["role"], "student_id": student["id"] if student else None}
    return {"id": current_user["id"], "role": current_user["role"]}

@app.get("/classes")
async def get_classes(current_user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Только учителя могут просматривать классы")
    classes = await db.fetch_all("SELECT id, name FROM classes")
    return [{"id": c["id"], "name": c["name"]} for c in classes]

@app.get("/reports/{student_id}")
async def get_reports(student_id: int, current_user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    student = await db.fetch_one("SELECT * FROM students WHERE id = :id", {"id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if current_user["role"] == "student" and student["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Students can only view their own reports")
    reports = await db.fetch_all("SELECT id, summary, recommendations, generated_at FROM reports WHERE student_id = :student_id", {"student_id": student_id})
    if not reports:
        raise HTTPException(status_code=404, detail="No reports found")
    return [{"id": r["id"], "summary": r["summary"], "recommendations": r["recommendations"], "generated_at": r["generated_at"]} for r in reports]

@app.post("/grades")
async def add_grade(grade: GradeCreate, current_user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can add grades")

    student = await db.fetch_one("SELECT * FROM students WHERE id = :id", {"id": grade.student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    try:
        query = "INSERT INTO grades (student_id, subject, score, teacher_id, date) VALUES (:student_id, :subject, :score, :teacher_id, :date) RETURNING *"
        values = {
            "student_id": grade.student_id,
            "subject": grade.subject,
            "score": grade.score,
            "teacher_id": current_user["id"],
            "date": datetime.utcnow()
        }
        new_grade = await db.fetch_one(query, values)

        all_grades = await db.fetch_all("SELECT * FROM grades WHERE student_id = :student_id", {"student_id": grade.student_id})
        grouped_grades = {}
        for g in all_grades:
            if g["subject"] not in grouped_grades:
                grouped_grades[g["subject"]] = []
            grouped_grades[g["subject"]].append({
                "id": g["id"],
                "score": g["score"],
                "date": g["date"].isoformat()
            })

        return {"message": "Grade added successfully", "grades": grouped_grades}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.put("/grades/{grade_id}")
async def update_grade(grade_id: int, grade: GradeUpdate, current_user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can update grades")

    db_grade = await db.fetch_one("SELECT * FROM grades WHERE id = :id AND teacher_id = :teacher_id", {"id": grade_id, "teacher_id": current_user["id"]})
    if not db_grade:
        raise HTTPException(status_code=404, detail="Grade not found or you don't have permission to edit it")

    try:
        query = "UPDATE grades SET subject = :subject, score = :score, date = :date WHERE id = :id RETURNING *"
        values = {"id": grade_id, "subject": grade.subject, "score": grade.score, "date": datetime.utcnow()}
        updated_grade = await db.fetch_one(query, values)

        all_grades = await db.fetch_all("SELECT * FROM grades WHERE student_id = :student_id", {"student_id": updated_grade["student_id"]})
        grouped_grades = {}
        for g in all_grades:
            if g["subject"] not in grouped_grades:
                grouped_grades[g["subject"]] = []
            grouped_grades[g["subject"]].append({
                "id": g["id"],
                "score": g["score"],
                "date": g["date"].isoformat(),
                "teacher_id": g["teacher_id"]
            })

        return {"message": "Grade updated successfully", "grades": grouped_grades}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.delete("/grades/{grade_id}")
async def delete_grade(grade_id: int, current_user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    if current_user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can delete grades")

    db_grade = await db.fetch_one("SELECT * FROM grades WHERE id = :id AND teacher_id = :teacher_id", {"id": grade_id, "teacher_id": current_user["id"]})
    if not db_grade:
        raise HTTPException(status_code=404, detail="Grade not found or you don't have permission to delete it")

    try:
        await db.execute("DELETE FROM grades WHERE id = :id", {"id": grade_id})

        all_grades = await db.fetch_all("SELECT * FROM grades WHERE student_id = :student_id", {"student_id": db_grade["student_id"]})
        grouped_grades = {}
        for g in all_grades:
            if g["subject"] not in grouped_grades:
                grouped_grades[g["subject"]] = []
            grouped_grades[g["subject"]].append({
                "id": g["id"],
                "score": g["score"],
                "date": g["date"].isoformat(),
                "teacher_id": g["teacher_id"]
            })

        return {"message": "Grade deleted successfully", "grades": grouped_grades}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)