import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

function TeacherDashboard({ token }) {
  const [students, setStudents] = useState([]);
  const [selectedStudentId, setSelectedStudentId] = useState(null);
  const [grades, setGrades] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchStudents = async () => {
      try {
        const response = await axios.get('http://localhost:8000/students', {
          headers: { Authorization: `Bearer ${token}` },
        });
        setStudents(response.data);
        if (response.data.length > 0) {
          setSelectedStudentId(response.data[0].id); // По умолчанию выбираем первого ученика
        }
      } catch (error) {
        console.error('Error fetching students:', error);
      }
    };

    fetchStudents();
  }, [token]);

  useEffect(() => {
    if (selectedStudentId) {
      const fetchGrades = async () => {
        try {
          const response = await axios.get(`http://localhost:8000/grades/${selectedStudentId}`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          setGrades(response.data);
        } catch (error) {
          console.error('Error fetching grades:', error);
        }
      };

      fetchGrades();
    }
  }, [selectedStudentId, token]);

  return (
    <div>
      <h2>Выберите ученика</h2>
      <select onChange={(e) => setSelectedStudentId(e.target.value)} value={selectedStudentId}>
        {students.map(student => (
          <option key={student.id} value={student.id}>
            {student.name} (Класс: {student.class_name})
          </option>
        ))}
      </select>

      <h3>Оценки выбранного ученика</h3>
      <ul>
        {grades.map(grade => (
          <li key={grade.id}>
            Предмет: {grade.subject}, Оценка: {grade.score}, Дата: {new Date(grade.date).toLocaleDateString()}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default TeacherDashboard;