from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import Session, sessionmaker, declarative_base
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
from pydantic import BaseModel, ValidationError, validator

# Инициализация FastAPI
app = FastAPI()

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Обновите порт на 5173
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение к PostgreSQL
DATABASE_URL = "postgresql://postgres:root@localhost:5432/school_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Настройки JWT
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Настройка хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Модели таблиц
# Модели таблиц
class Class(Base):
    __tablename__ = "classes"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)  # Например, "10A", "11B"

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String)  # "teacher" или "student"
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
class Grade(Base):
    __tablename__ = "grades"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), index=True)
    subject = Column(String)
    score = Column(Integer)
    date = Column(DateTime, default=datetime.utcnow)
    teacher_id = Column(Integer, ForeignKey("users.id"), index=True)  # Кто поставил оценку

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), index=True)
    summary = Column(String)
    recommendations = Column(String)
    generated_at = Column(DateTime, default=datetime.utcnow)

class GradeCreate(BaseModel):
    student_id: int
    subject: str
    score: int

    @validator('score')
    def check_score(cls, v):
        if not 1 <= v <= 5:
            raise ValueError('Оценка должна быть от 1 до 5')
        return v

# Создание таблиц
Base.metadata.create_all(bind=engine)


# Вспомогательная функция для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Модель Pydantic для валидации
class UserInDB(BaseModel):
    username: str
    hashed_password: str
    role: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str


# Функции для работы с JWT
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_user(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
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
    user = get_user(db, username)
    if user is None:
        raise credentials_exception
    return user


# Эндпоинт для регистрации пользователя
@app.post("/register")
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    try:
        existing_user = get_user(db, user.username)
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already exists")

        hashed_password = pwd_context.hash(user.password)

        new_user = User(
            username=user.username,
            hashed_password=hashed_password,
            role=user.role
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        if user.role == "student":
            # Создаём запись для нового студента
            default_class = db.query(Class).filter(Class.name == "10A").first()
            if not default_class:
                default_class = Class(name="10A")
                db.add(default_class)
                db.commit()

            new_student = Student(name=user.username, class_id=default_class.id, user_id=new_user.id)
            db.add(new_student)
            db.commit()

        return {"message": "User registered successfully", "username": new_user.username, "role": new_user.role, "student_id": new_student.id if user.role == "student" else None}
    except Exception as e:
        db.rollback()
        print(f"Error during registration: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Эндпоинт для получения токена
@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = get_user(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


# Добавление тестовых данных
def init_test_data(db: Session):
    if db.query(Class).count() == 0:
        class_10a = Class(name="10A")
        class_11b = Class(name="11B")
        db.add_all([class_10a, class_11b])
        db.commit()

    if db.query(User).count() == 0:
        teacher = User(username="teacher", hashed_password=pwd_context.hash("teacherpassword"), role="teacher")
        student1 = User(username="student1", hashed_password=pwd_context.hash("studentpassword1"), role="student")
        student2 = User(username="student2", hashed_password=pwd_context.hash("studentpassword2"), role="student")
        db.add_all([teacher, student1, student2])
        db.commit()

    if db.query(Student).count() == 0:
        student_ivan = Student(name="Иван Иванов", class_id=db.query(Class).filter(Class.name == "10A").first().id, user_id=db.query(User).filter(User.username == "student1").first().id)
        student_maria = Student(name="Мария Петрова", class_id=db.query(Class).filter(Class.name == "11B").first().id, user_id=db.query(User).filter(User.username == "student2").first().id)
        db.add_all([student_ivan, student_maria])
        db.commit()

        grades = [
            Grade(student_id=student_ivan.id, subject="Математика", score=5, teacher_id=db.query(User).filter(User.username == "teacher").first().id),
            Grade(student_id=student_ivan.id, subject="Литература", score=4, teacher_id=db.query(User).filter(User.username == "teacher").first().id),
            Grade(student_id=student_maria.id, subject="Математика", score=4, teacher_id=db.query(User).filter(User.username == "teacher").first().id),
            Grade(student_id=student_maria.id, subject="Литература", score=5, teacher_id=db.query(User).filter(User.username == "teacher").first().id),
        ]
        db.add_all(grades)
        db.commit()


# Эндпоинт для инициализации тестовых данных
@app.get("/init-test-data")
def init_data(db: Session = Depends(get_db)):
    init_test_data(db)
    return {"message": "Тестовые данные добавлены"}


# Модуль анализа успеваемости
def analyze_performance(student_id: int, db: Session):
    grades = db.query(Grade).filter(Grade.student_id == student_id).all()
    if not grades:
        return None, None

    data = [{"subject": g.subject, "score": g.score} for g in grades]
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
    return summary, " ".join(recommendations) if recommendations else "Хорошая успеваемость, продолжайте в том же духе!"


# Генерация PDF-отчета
def generate_pdf_report(student_id: int, summary: str, recommendations: str):
    pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
    filename = f"report_student_{student_id}.pdf"
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    c.setFont("DejaVuSans", 12)
    y_position = height - 50

    def draw_wrapped_text(x, y, text, max_width=400):
        lines = simpleSplit(text, 'DejaVuSans', 12, max_width)
        for line in lines:
            c.drawString(x, y, line)
            y -= 20
        return y

    y_position = draw_wrapped_text(100, y_position, f"Отчет по успеваемости (ID student: {student_id})")
    y_position = draw_wrapped_text(100, y_position - 20, f"Дата: {datetime.now().strftime('%Y-%m-%d')}")
    y_position = draw_wrapped_text(100, y_position - 30, "Анализ:")
    y_position = draw_wrapped_text(100, y_position - 20, summary)
    y_position = draw_wrapped_text(100, y_position - 30, "Рекомендации:")
    y_position = draw_wrapped_text(100, y_position - 20, recommendations)

    if y_position < 50:
        c.showPage()
        y_position = height - 50

    c.showPage()
    c.save()
    return filename


# Эндпоинт для генерации отчета (защищенный)
@app.get("/generate-report/{student_id}")
async def generate_report(student_id: int, current_user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    summary, recommendations = analyze_performance(student_id, db)
    if not summary:
        raise HTTPException(status_code=404, detail="Оценки для ученика не найдены")
    report = Report(student_id=student_id, summary=summary, recommendations=recommendations)
    db.add(report)
    db.commit()
    pdf_file = generate_pdf_report(student_id, summary, recommendations)
    return FileResponse(pdf_file, media_type="application/pdf", filename=f"report_{student_id}.pdf")


# Эндпоинт для получения списка учеников (только для учителей)
@app.get("/students")
async def get_students(class_name: Optional[str] = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can view all students")

    query = db.query(Student).join(Class)
    if class_name:
        query = query.filter(Class.name == class_name)

    students = query.all()
    return [{"id": s.id, "name": s.name, "class_name": db.query(Class).filter(Class.id == s.class_id).first().name} for s in students]

# Эндпоинт для получения оценок ученика (только свои оценки для учеников)
@app.get("/grades/{student_id}")
async def get_grades(student_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Ученик не найден")

    if current_user.role == "student":
        # Проверяем, что student_id соответствует текущему пользователю
        user_student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if user_student.id != student_id:
            raise HTTPException(status_code=403, detail="Ученики не могут просматривать чужие оценки")

    grades = db.query(Grade).filter(Grade.student_id == student_id).all()
    if not grades:
        return {"message": "Нет обнаржуенных оценок для этого ученика", "grades": []} # Возвращаем пустой список вместо ошибки

    return [{"id": g.id, "subject": g.subject, "score": g.score, "date": g.date.isoformat()} for g in grades]

@app.get("/me")
async def get_current_user_data(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role == "student":
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        return {"role": current_user.role, "student_id": student.id}
    return {"role": current_user.role}


@app.get("/classes")
async def get_classes(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "teacher":
        raise HTTPException(status_code=403, detail="Только учителяя могут просматривать классы")

    classes = db.query(Class).all()
    return [{"id": c.id, "name": c.name} for c in classes]

# Эндпоинт для получения отчетов ученика (только свои отчеты для учеников)
@app.get("/reports/{student_id}")
async def get_reports(student_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if current_user.role == "student" and current_user.id != db.query(Student).filter(Student.id == student_id).first().id:
        raise HTTPException(status_code=403, detail="Students can only view their own reports")
    reports = db.query(Report).filter(Report.student_id == student_id).all()
    if not reports:
        raise HTTPException(status_code=404, detail="No reports found")
    return [{"id": r.id, "summary": r.summary, "recommendations": r.recommendations, "generated_at": r.generated_at} for r in reports]

# Модель Pydantic для добавления оценки
class GradeCreate(BaseModel):
    student_id: int
    subject: str
    score: int


# Обновленный эндпоинт для добавления оценки с валидацией и возвратом более подробной информации
@app.post("/grades")
async def add_grade(grade: GradeCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can add grades")

    # Проверяем, существует ли студент
    student = db.query(Student).filter(Student.id == grade.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    try:
        # Убедимся, что все поля корректны
        new_grade = Grade(
            student_id=grade.student_id,
            subject=grade.subject,
            score=grade.score,
            teacher_id=current_user.id,
            date=datetime.utcnow()
        )
        db.add(new_grade)
        db.commit()
        db.refresh(new_grade)
        return {
            "message": "Grade added successfully",
            "grade": {
                "id": new_grade.id,
                "student_id": new_grade.student_id,
                "subject": new_grade.subject,
                "score": new_grade.score,
                "date": new_grade.date.isoformat()
            }
        }
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e.errors()))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Новый эндпоинт для редактирования оценки
@app.put("/grades/{grade_id}")
async def update_grade(grade_id: int, grade: GradeCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can update grades")

    db_grade = db.query(Grade).filter(Grade.id == grade_id, Grade.teacher_id == current_user.id).first()
    if not db_grade:
        raise HTTPException(status_code=404, detail="Grade not found or you don't have permission")

    db_grade.subject = grade.subject
    db_grade.score = grade.score
    db_grade.date = datetime.utcnow()
    db.commit()
    db.refresh(db_grade)
    return {"message": "Grade updated successfully", "grade": db_grade}

# Новый эндпоинт для удаления оценки
@app.delete("/grades/{grade_id}")
async def delete_grade(grade_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can delete grades")

    db_grade = db.query(Grade).filter(Grade.id == grade_id, Grade.teacher_id == current_user.id).first()
    if not db_grade:
        raise HTTPException(status_code=404, detail="Grade not found or you don't have permission")

    db.delete(db_grade)
    db.commit()
    return {"message": "Grade deleted successfully"}

# Запуск сервера
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)