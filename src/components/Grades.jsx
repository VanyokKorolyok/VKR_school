import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { Bar } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import './Grades.css';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

function Grades({ token, role }) {
  const { studentId: urlStudentId } = useParams();
  const navigate = useNavigate();
  const [finalStudentId, setFinalStudentId] = useState(null);
  const [showStats, setShowStats] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  // Установка finalStudentId
  useEffect(() => {
    let idToUse = urlStudentId;
    if (role === "student") {
      const storedStudentId = localStorage.getItem('student_id');
      if (!storedStudentId) {
        alert("Student ID not found. Please login again.");
        return;
      }
      idToUse = storedStudentId;
    }
    setFinalStudentId(idToUse);
  }, [urlStudentId, role]);

  // Запрос данных пользователя
  const { data: userData, error: userError } = useQuery({
    queryKey: ['userData', token],
    queryFn: async () => {
      const response = await axios.get('http://localhost:8000/me', {
        headers: { Authorization: `Bearer ${token}` },
      });
      const student = await axios.get(`http://localhost:8000/students/${response.data.student_id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return { fullName: student.data.name };
    },
    enabled: !!token,
  });

  // Запрос оценок
  const { data: gradesData = { grades: {} }, error: gradesError } = useQuery({
    queryKey: ['grades', token, finalStudentId],
    queryFn: async () => {
      const response = await axios.get(`http://localhost:8000/grades/${finalStudentId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return response.data;
    },
    enabled: !!token && !!finalStudentId,
  });

  // Запрос статистики
  const { data: stats = { average_score: 0, average_scores: {}, recommendations: '' }, error: statsError } = useQuery({
    queryKey: ['stats', token, finalStudentId],
    queryFn: async () => {
      const response = await axios.get(`http://localhost:8000/grades/${finalStudentId}/stats`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return response.data;
    },
    enabled: showStats && !!token && !!finalStudentId,
  });

  const handleShowStats = () => {
    setShowStats(!showStats);
  };

  const generateReport = async () => {
    if (!finalStudentId) {
      alert('ID студента не найден');
      return;
    }
    setIsGenerating(true);
    try {
      const generateResponse = await axios.get(`http://localhost:8000/generate-report/${finalStudentId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      let attempts = 0;
      const maxAttempts = 10;
      while (attempts < maxAttempts) {
        try {
          const downloadResponse = await axios.get(`http://localhost:8000/download-report/${finalStudentId}`, {
            headers: { Authorization: `Bearer ${token}` },
            responseType: 'blob',
          });
          const url = window.URL.createObjectURL(new Blob([downloadResponse.data]));
          const link = document.createElement('a');
          link.href = url;
          link.setAttribute('download', `отчет_${finalStudentId}.pdf`);
          document.body.appendChild(link);
          link.click();
          link.remove();
          window.URL.revokeObjectURL(url);
          setIsGenerating(false);
          return;
        } catch (downloadError) {
          if (downloadError.response?.status === 404) {
            await new Promise(resolve => setTimeout(resolve, 1000));
            attempts++;
          } else {
            throw downloadError;
          }
        }
      }
      alert('Отчет не был сгенерирован в течение заданного времени');
    } catch (error) {
      alert('Ошибка генерации отчета: ' + (error.response?.data?.detail || error.message));
    } finally {
      setIsGenerating(false);
    }
  };

  const chartData = {
    labels: Object.keys(stats.average_scores),
    datasets: [{
      label: 'Средний балл по предметам',
      data: Object.values(stats.average_scores),
      backgroundColor: 'rgba(75, 192, 192, 0.2)',
      borderColor: 'rgba(75, 192, 192, 1)',
      borderWidth: 1,
    }],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    height: 300,
    plugins: { legend: { position: 'top' }, title: { display: true, text: 'Анализ успеваемости' } },
  };

  if (!finalStudentId) return <div>Loading...</div>;

  const error = userError || gradesError || statsError;
  const grades = gradesData.grades;

  return (
    <div className="grades-container">
      <header className="grades-header">
        <h1 className="grades-title">Электронный журнал</h1>
        {token && <button className="logout-btn" onClick={() => navigate('/login')}>Logout</button>}
      </header>
      <main className="grades-main">
        {error && <p className="error-message">{error.message}</p>}
        <h2 className="student-title">Оценки для {userData?.fullName || 'Loading...'} (ID: {finalStudentId})</h2>

        {Object.keys(grades).length === 0 ? (
          <p className="no-grades">Оценок не обнаружено.</p>
        ) : (
          Object.entries(grades).map(([subject, subjectGrades]) => (
            <div key={subject} className="grade-card">
              <h3 className="card-title">{subject}</h3>
              <table className="grades-table">
                <thead>
                  <tr>
                    <th>Оценка</th>
                    <th>Дата</th>
                  </tr>
                </thead>
                <tbody>
                  {subjectGrades.map(grade => (
                    <tr key={grade.id}>
                      <td>{grade.score}</td>
                      <td>{new Date(grade.date).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))
        )}

        <div className="button-group">
          <button className="stats-btn" onClick={handleShowStats}>
            {showStats ? 'Скрыть анализ успеваемости' : 'Показать анализ успеваемости'}
          </button>
          <button className="stats-btn" onClick={generateReport} disabled={isGenerating}>
            {isGenerating ? 'Генерация...' : 'Сгенерировать отчет'}
          </button>
        </div>

        {showStats && (
          <div className="stats-card">
            <div className="stats-header">
              <h3 className="card-title">Анализ успеваемости</h3>
              <button className="close-btn" onClick={() => setShowStats(false)}>Закрыть</button>
            </div>
            <p className="stats-text">Общий средний балл: {stats.average_score.toFixed(2)}</p>
            <div className="chart-container">
              <Bar data={chartData} options={chartOptions} />
            </div>
            <p className="stats-text">Рекомендации: {stats.recommendations}</p>
          </div>
        )}
      </main>
    </div>
  );
}

export default Grades;