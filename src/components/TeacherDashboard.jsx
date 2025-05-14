import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { Bar } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend } from 'chart.js';
import { FixedSizeList } from 'react-window';
import './TeacherDashboard.css';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

function TeacherDashboard({ token }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedClass, setSelectedClass] = useState('');
  const [selectedStudentId, setSelectedStudentId] = useState(null);
  const [newGrade, setNewGrade] = useState({ subject: '', score: '' });
  const [editGrade, setEditGrade] = useState(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [gradeToDelete, setGradeToDelete] = useState(null);
  const [filterSubject, setFilterSubject] = useState('');
  const [sortBy, setSortBy] = useState('date');
  const [sortOrder, setSortOrder] = useState('desc');
  const [page, setPage] = useState(1);
  const [showStats, setShowStats] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false); // Состояние для управления списком

  const SUBJECTS = ["Математика", "Литература", "Физика", "Химия", "История", "География", "Биология", "Английский язык"];

  // Запрос текущего учителя
  const { data: currentTeacherId, error: teacherError } = useQuery({
    queryKey: ['teacherMe', token],
    queryFn: async () => {
      const response = await axios.get('http://localhost:8000/me', {
        headers: { Authorization: `Bearer ${token}` },
      });
      return response.data.id;
    },
    enabled: !!token,
  });

  // Запрос классов
  const { data: classes = [], error: classesError } = useQuery({
    queryKey: ['classes', token],
    queryFn: async () => {
      const response = await axios.get('http://localhost:8000/classes', {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (response.data.length > 0 && !selectedClass) {
        setSelectedClass(response.data[0].name);
      }
      return response.data;
    },
    enabled: !!token,
  });

  // Запрос студентов
  const { data: students = [], error: studentsError } = useQuery({
    queryKey: ['students', token, selectedClass],
    queryFn: async () => {
      const response = await axios.get('http://localhost:8000/students', {
        headers: { Authorization: `Bearer ${token}` },
        params: { class_name: selectedClass },
      });
      const fetchedStudents = response.data || [];
      if (fetchedStudents.length > 0 && !selectedStudentId) {
        setSelectedStudentId(fetchedStudents[0].id);
      }
      return fetchedStudents;
    },
    enabled: !!token && !!selectedClass,
  });

  // Запрос оценок
  const { data: gradesData, error: gradesError } = useQuery({
    queryKey: ['grades', token, selectedStudentId, filterSubject, sortBy, sortOrder, page],
    queryFn: async () => {
      const response = await axios.get(`http://localhost:8000/grades/${selectedStudentId}`, {
        headers: { Authorization: `Bearer ${token}` },
        params: { subject: filterSubject, sort_by: sortBy, sort_order: sortOrder, page },
      });
      return response.data;
    },
    enabled: !!token && !!selectedStudentId && currentTeacherId !== null,
  });

  const grades = gradesData?.grades || {};
  const totalPages = gradesData?.total_pages || 1;

  // Запрос статистики
  const { data: stats = { average_score: 0, average_scores: {}, recommendations: '' }, error: statsError } = useQuery({
    queryKey: ['stats', token, selectedStudentId],
    queryFn: async () => {
      const response = await axios.get(`http://localhost:8000/grades/${selectedStudentId}/stats`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return response.data;
    },
    enabled: showStats && !!token && !!selectedStudentId,
  });

  // Мутации (оставляем без изменений)
  const addGradeMutation = useMutation({
    mutationFn: async (newGradeData) => {
      const response = await axios.post('http://localhost:8000/grades', newGradeData, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(
        ['grades', token, selectedStudentId, filterSubject, sortBy, sortOrder, page],
        { grades: data.grades, total_pages: totalPages }
      );
      setNewGrade({ subject: '', score: '' });
    },
    onError: (error) => {
      alert('Error adding grade: ' + (error.response?.data?.detail || error.message));
    },
  });

  const updateGradeMutation = useMutation({
    mutationFn: async ({ id, subject, score }) => {
      const response = await axios.put(`http://localhost:8000/grades/${id}`, { subject, score }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(
        ['grades', token, selectedStudentId, filterSubject, sortBy, sortOrder, page],
        { grades: data.grades, total_pages: totalPages }
      );
      setEditGrade(null);
      setIsEditModalOpen(false);
    },
    onError: (error) => {
      alert('Error updating grade: ' + (error.response?.data?.detail || error.message));
    },
  });

  const deleteGradeMutation = useMutation({
    mutationFn: async (gradeId) => {
      const response = await axios.delete(`http://localhost:8000/grades/${gradeId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(
        ['grades', token, selectedStudentId, filterSubject, sortBy, sortOrder, page],
        { grades: data.grades, total_pages: totalPages }
      );
      setIsDeleteModalOpen(false);
      setGradeToDelete(null);
    },
    onError: (error) => {
      alert('Error deleting grade: ' + (error.response?.data?.detail || error.message));
    },
  });

  const handleAddGrade = (e) => {
    e.preventDefault();
    if (!selectedStudentId || !newGrade.subject || !newGrade.score) {
      alert('Please select a student and fill all fields');
      return;
    }
    if (!SUBJECTS.includes(newGrade.subject)) {
      alert('Invalid subject. Choose from the list.');
      return;
    }
    addGradeMutation.mutate({
      student_id: parseInt(selectedStudentId),
      subject: newGrade.subject,
      score: parseInt(newGrade.score),
    });
  };

  const handleEditGrade = (gradeId, subject, score) => {
    setEditGrade({ id: gradeId, subject, score });
    setIsEditModalOpen(true);
  };

  const handleUpdateGrade = (e) => {
    e.preventDefault();
    if (!editGrade.subject || !editGrade.score) {
      alert('Please fill all fields');
      return;
    }
    updateGradeMutation.mutate({
      id: editGrade.id,
      subject: editGrade.subject,
      score: parseInt(editGrade.score),
    });
  };

  const handleDeleteGrade = (gradeId) => {
    setGradeToDelete(gradeId);
    setIsDeleteModalOpen(true);
  };

  const confirmDeleteGrade = () => {
    deleteGradeMutation.mutate(gradeToDelete);
  };

  const handleShowStats = () => {
    setShowStats(!showStats);
  };

  const generateReport = async () => {
    if (!selectedStudentId) {
      alert('Пожалуйста, выберите ученика');
      return;
    }
    setIsGenerating(true);
    try {
      const generateResponse = await axios.get(`http://localhost:8000/generate-report/${selectedStudentId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      let attempts = 0;
      const maxAttempts = 10;
      while (attempts < maxAttempts) {
        try {
          const downloadResponse = await axios.get(`http://localhost:8000/download-report/${selectedStudentId}`, {
            headers: { Authorization: `Bearer ${token}` },
            responseType: 'blob',
          });
          const url = window.URL.createObjectURL(new Blob([downloadResponse.data]));
          const link = document.createElement('a');
          link.href = url;
          link.setAttribute('download', `отчет_${selectedStudentId}.pdf`);
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

  const error = teacherError || classesError || studentsError || gradesError || statsError;

  // Компонент для рендера строки в кастомном списке
  const Row = ({ index, style }) => {
    const student = students[index];
    const isSelected = student.id === selectedStudentId;
    return (
      <div
        style={{
          ...style,
          backgroundColor: isSelected ? '#e0f7fa' : 'transparent',
          padding: '8px 12px',
          cursor: 'pointer',
        }}
        onClick={() => {
          setSelectedStudentId(student.id);
          setIsDropdownOpen(false); // Закрываем список при выборе
        }}
        className="student-option"
      >
        {student.name} (Класс: {student.class_name})
      </div>
    );
  };

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1 className="dashboard-title">Электронный журнал</h1>
        {token && (
          <button
            className="logout-btn"
            onClick={() => navigate('/login')}
            style={{ padding: '5px 10px', fontSize: '14px' }} // Адаптивный размер
          >
            Logout
          </button>
        )}
      </header>
      <main className="dashboard-main">
        {error && <p className="error-message">{error.message}</p>}
        <p className="teacher-id">Current Teacher ID: {currentTeacherId}</p>

        <div className="filter-section">
          <label>Выберите класс:</label>
          <select
            value={selectedClass}
            onChange={(e) => setSelectedClass(e.target.value)}
            className="select-input"
            style={{ padding: '5px', fontSize: '14px' }} // Адаптивный размер
          >
            <option value="">Все классы</option>
            {classes.map(cls => <option key={cls.id} value={cls.name}>{cls.name}</option>)}
          </select>
        </div>

        <h3 className="section-title">Список учеников</h3>
        <div className="custom-select-container">
          <button
            className="dropdown-toggle"
            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            style={{ width: '100%', padding: '8px', fontSize: '14px' }} // Адаптивный размер
          >
            {selectedStudentId
              ? students.find(s => s.id === selectedStudentId)?.name || 'Выберите ученика'
              : 'Выберите ученика'}
            {isDropdownOpen ? ' ▼' : ' ▶'}
          </button>
          {isDropdownOpen && (
            <div className="custom-select">
              {students.length > 0 ? (
                <FixedSizeList
                  height={200}
                  width="auto" // Убрана фиксированная ширина, адаптация к содержимому
                  itemCount={students.length}
                  itemSize={35}
                  style={{ outline: 'none', minWidth: '200px' }} // Минимальная ширина
                >
                  {Row}
                </FixedSizeList>
              ) : (
                <div style={{ padding: '10px', fontSize: '14px' }}>Нет учеников</div>
              )}
            </div>
          )}
        </div>
        <div style={{ marginTop: '10px', fontSize: '14px' }}>
          Выбранный ученик: {students.find(s => s.id === selectedStudentId)?.name || 'Не выбран'}
        </div>

        {selectedStudentId && (
          <>
            <button className="stats-btn" onClick={generateReport} disabled={isGenerating}>
              {isGenerating ? 'Генерация...' : 'Сгенерировать отчет'}
            </button>

            <h3 className="section-title">Оценки ученика</h3>
            <div className="filter-options">
              <div className="filter-group">
                <label>Фильтр по предмету:</label>
                <select
                  value={filterSubject}
                  onChange={(e) => setFilterSubject(e.target.value)}
                  className="select-input"
                  style={{ padding: '5px', fontSize: '14px' }}
                >
                  <option value="">Все предметы</option>
                  {SUBJECTS.map(subj => <option key={subj} value={subj}>{subj}</option>)}
                </select>
              </div>
              <div className="filter-group">
                <label>Сортировать по:</label>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="select-input"
                  style={{ padding: '5px', fontSize: '14px' }}
                >
                  <option value="date">Дате</option>
                  <option value="score">Оценке</option>
                </select>
              </div>
              <div className="filter-group">
                <label>Порядок:</label>
                <select
                  value={sortOrder}
                  onChange={(e) => setSortOrder(e.target.value)}
                  className="select-input"
                  style={{ padding: '5px', fontSize: '14px' }}
                >
                  <option value="asc">По возрастанию</option>
                  <option value="desc">По убыванию</option>
                </select>
              </div>
            </div>

            {Object.keys(grades).length === 0 ? (
              <p className="no-grades">Оценок не обнаружено.</p>
            ) : (
              Object.entries(grades).map(([subject, subjectGrades]) => (
                <div key={subject} className="grade-card">
                  <h4 className="card-title">{subject}</h4>
                  <ul className="grade-list">
                    {subjectGrades.map(grade => (
                      <li key={grade.id} className="grade-item">
                        Оценка: {grade.score}, Дата: {new Date(grade.date).toLocaleDateString()}
                        {grade.teacher_id === currentTeacherId && (
                          <>
                            <button className="edit-btn" onClick={() => handleEditGrade(grade.id, subject, grade.score)}>Редактировать</button>
                            <button className="delete-btn" onClick={() => handleDeleteGrade(grade.id)}>Удалить</button>
                          </>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              ))
            )}

            <div className="pagination">
              <button disabled={page === 1} onClick={() => setPage(page - 1)} className="pagination-btn">
                Предыдущая
              </button>
              <span className="pagination-info">Страница {page} из {totalPages}</span>
              <button disabled={page === totalPages} onClick={() => setPage(page + 1)} className="pagination-btn">
                Следующая
              </button>
            </div>

            <button className="stats-btn" onClick={handleShowStats}>
              {showStats ? 'Скрыть анализ успеваемости' : 'Показать анализ успеваемости'}
            </button>

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

            {isEditModalOpen && (
              <div className="modal-overlay">
                <div className="modal-content">
                  <h3 className="modal-title">Редактировать оценку</h3>
                  <form onSubmit={handleUpdateGrade}>
                    <div className="modal-field">
                      <label>Предмет:</label>
                      <select
                        value={editGrade.subject}
                        onChange={(e) => setEditGrade({ ...editGrade, subject: e.target.value })}
                        className="select-input"
                        style={{ padding: '5px', fontSize: '14px' }}
                      >
                        {SUBJECTS.map(subj => <option key={subj} value={subj}>{subj}</option>)}
                      </select>
                    </div>
                    <div className="modal-field">
                      <label>Оценка:</label>
                      <input
                        type="number"
                        value={editGrade.score}
                        onChange={(e) => setEditGrade({ ...editGrade, score: e.target.value })}
                        min="1"
                        max="5"
                        required
                        className="input-field"
                        style={{ padding: '5px', fontSize: '14px' }}
                      />
                    </div>
                    <div className="modal-actions">
                      <button type="submit" className="save-btn">Сохранить</button>
                      <button type="button" onClick={() => setIsEditModalOpen(false)} className="cancel-btn">Закрыть</button>
                    </div>
                  </form>
                </div>
              </div>
            )}

            {isDeleteModalOpen && (
              <div className="modal-overlay">
                <div className="modal-content">
                  <h3 className="modal-title">Подтверждение удаления</h3>
                  <p className="modal-text">Вы уверены, что хотите удалить эту оценку?</p>
                  <div className="modal-actions">
                    <button onClick={confirmDeleteGrade} className="delete-confirm-btn">Удалить</button>
                    <button onClick={() => setIsDeleteModalOpen(false)} className="cancel-btn">Отмена</button>
                  </div>
                </div>
              </div>
            )}

            <h3 className="section-title">Выставить новую оценку</h3>
            <form onSubmit={handleAddGrade} className="grade-form">
              <select
                value={newGrade.subject}
                onChange={(e) => setNewGrade({ ...newGrade, subject: e.target.value })}
                required
                className="select-input"
                style={{ padding: '5px', fontSize: '14px' }}
              >
                <option value="">Выберите предмет</option>
                {SUBJECTS.map(subject => <option key={subject} value={subject}>{subject}</option>)}
              </select>
              <input
                type="number"
                placeholder="Оценка (1-5)"
                value={newGrade.score}
                onChange={(e) => setNewGrade({ ...newGrade, score: e.target.value })}
                min="1"
                max="5"
                required
                className="input-field"
                style={{ padding: '5px', fontSize: '14px' }}
              />
              <button type="submit" className="submit-btn">Выставить оценку</button>
            </form>
          </>
        )}
      </main>
    </div>
  );
}

export default TeacherDashboard;