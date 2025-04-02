import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";

function Grades({ token, role }) {
  const { studentId: urlStudentId } = useParams(); // ID из URL
  const [grades, setGrades] = useState([]);
  const [error, setError] = useState("");
  const [finalStudentId, setFinalStudentId] = useState(null); // Добавляем состояние для finalStudentId

  // Определяем finalStudentId один раз при монтировании
  useEffect(() => {
    let idToUse = urlStudentId;

    if (role === "student") {
      const storedStudentId = localStorage.getItem('student_id');
      if (!storedStudentId) {
        setError("Student ID not found. Please login again.");
        return;
      }
      idToUse = storedStudentId;
    }

    setFinalStudentId(idToUse); // Сохраняем в состояние
  }, [urlStudentId, role]); // Зависимости: urlStudentId и role

  // Загружаем оценки, только если finalStudentId определён
  useEffect(() => {
    if (!finalStudentId) return; // Не делаем запрос, если ID ещё не определён

    const fetchGrades = async () => {
      try {
        const response = await axios.get(`http://localhost:8000/grades/${finalStudentId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setGrades(response.data);
      } catch (err) {
        setError("Failed to fetch grades: " + (err.response?.data?.detail || err.message));
      }
    };

    fetchGrades();
  }, [finalStudentId, token]); // Теперь зависимость корректна

  // Если finalStudentId ещё не определён, показываем загрузку
  if (!finalStudentId) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      <h2>Grades for Student ID: {finalStudentId}</h2>
      {error && <p className="error">{error}</p>}
      {grades.length > 0 ? (
        <table>
          <thead>
            <tr>
              <th>Subject</th>
              <th>Score</th>
              <th>Date</th>
            </tr>
          </thead>
          <tbody>
            {grades.map((grade) => (
              <tr key={grade.id}>
                <td>{grade.subject}</td>
                <td>{grade.score}</td>
                <td>{new Date(grade.date).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p>No grades found for this student.</p>
      )}
    </div>
  );
}

export default Grades;