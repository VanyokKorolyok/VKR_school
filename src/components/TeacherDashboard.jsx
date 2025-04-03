import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

function TeacherDashboard({ token }) {
  const [students, setStudents] = useState([]);
  const [classes, setClasses] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [selectedStudentId, setSelectedStudentId] = useState(null);
  const [grades, setGrades] = useState([]);
  const [newGrade, setNewGrade] = useState({ subject: '', score: '' });
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const fetchClasses = async () => {
      try {
        const response = await axios.get('http://localhost:8000/classes', {
          headers: { Authorization: `Bearer ${token}` },
        });
        setClasses(response.data);
        if (response.data.length > 0) {
          setSelectedClass(response.data[0].name); // Устанавливаем первый класс по умолчанию
        }
      } catch (error) {
        setError('Error fetching classes: ' + error.message);
      }
    };

    fetchClasses();
  }, [token]);

  useEffect(() => {
    const fetchStudents = async () => {
      try {
        const response = await axios.get('http://localhost:8000/students', {
          headers: { Authorization: `Bearer ${token}` },
          params: { class_name: selectedClass },
        });
        setStudents(response.data || []); // Убедимся, что это массив
        if (response.data && response.data.length > 0) {
          setSelectedStudentId(response.data[0].id); // Устанавливаем первого ученика
        } else {
          setSelectedStudentId(null);
          setGrades([]); // Сбрасываем оценки, если нет студентов
        }
      } catch (error) {
        setError('Error fetching students: ' + error.message);
      }
    };

    if (selectedClass) {
      fetchStudents();
    }
  }, [token, selectedClass]);

  useEffect(() => {
    if (selectedStudentId) {
      const fetchGrades = async () => {
        try {
          const response = await axios.get(`http://localhost:8000/grades/${selectedStudentId}`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          // Убедимся, что grades всегда массив
          if (Array.isArray(response.data)) {
            setGrades(response.data);
          } else if (response.data.message === "No grades found for this student") {
            setGrades([]);
          } else {
            setGrades(response.data.grades || []); // Если сервер возвращает объект с полем grades
          }
        } catch (error) {
          setError('Error fetching grades: ' + error.message);
          setGrades([]); // Сбрасываем на пустой массив в случае ошибки
        }
      };

      fetchGrades();
    } else {
      setGrades([]); // Сбрасываем оценки, если нет выбранного ученика
    }
  }, [selectedStudentId, token]);

  const handleAddGrade = async (e) => {
    e.preventDefault();
    if (!selectedStudentId || !newGrade.subject || !newGrade.score) {
      setError('Please select a student and fill all fields');
      return;
    }

    try {
      await axios.post('http://localhost:8000/grades', {
        student_id: parseInt(selectedStudentId),
        subject: newGrade.subject,
        score: parseInt(newGrade.score),
      }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setNewGrade({ subject: '', score: '' });
      const response = await axios.get(`http://localhost:8000/grades/${selectedStudentId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (Array.isArray(response.data)) {
        setGrades(response.data);
      } else if (response.data.message === "No grades found for this student") {
        setGrades([]);
      } else {
        setGrades(response.data.grades || []);
      }
      setError('');
    } catch (error) {
      setError('Error adding grade: ' + (error.response?.data?.detail || error.message));
    }
  };

  return (
    <div>
      <h2>Панель учителя</h2>
      {error && <p className="error">{error}</p>}

      {/* Фильтрация по классам */}
      <select onChange={(e) => setSelectedClass(e.target.value)} value={selectedClass}>
        <option value="">Все классы</option>
        {classes.map(cls => (
          <option key={cls.id} value={cls.name}>
            {cls.name}
          </option>
        ))}
      </select>

      {/* Список учеников */}
      <h3>Список учеников</h3>
      <select onChange={(e) => setSelectedStudentId(e.target.value)} value={selectedStudentId || ''}>
        <option value="">Выберите ученика</option>
        {students.map(student => (
          <option key={student.id} value={student.id}>
            {student.name} (Класс: {student.class_name})
          </option>
        ))}
      </select>

      {/* Оценки выбранного ученика */}
      {selectedStudentId && (
        <>
          <h3>Оценки ученика</h3>
          {Array.isArray(grades) && grades.length === 0 ? (
            <p>Оценок не обнаружено.</p>
          ) : Array.isArray(grades) ? (
            <ul>
              {grades.map(grade => (
                <li key={grade.id}>
                  Предмет: {grade.subject}, Оценка: {grade.score}, Дата: {new Date(grade.date).toLocaleDateString()}
                </li>
              ))}
            </ul>
          ) : (
            <p>Ошибка загрузки оценок.</p>
          )}

          {/* Форма для выставления оценки */}
          <h3>Выставить новую оценку</h3>
          <form onSubmit={handleAddGrade}>
            <input
              type="text"
              placeholder="Предмет"
              value={newGrade.subject}
              onChange={(e) => setNewGrade({ ...newGrade, subject: e.target.value })}
              required
            />
            <input
              type="number"
              placeholder="Оценка (1-5)"
              value={newGrade.score}
              onChange={(e) => setNewGrade({ ...newGrade, score: e.target.value })}
              min="1"
              max="5"
              required
            />
            <button type="submit">Выставить оценку</button>
          </form>
        </>
      )}
    </div>
  );
}

export default TeacherDashboard;