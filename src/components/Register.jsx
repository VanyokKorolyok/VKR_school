import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

function Register() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('student'); // Установим значение по умолчанию как "student"
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.post('/api/register', {
        username,
        password,
        role
      });
      setSuccess(response.data.message);
      setTimeout(() => navigate('/login'), 2000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed');
    }
  };

  return (
    <div>
      <h2>Регистрация</h2>
      <form onSubmit={handleSubmit}>
        <div>
          <label>Логин:</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>
        <div>
          <label>Пароль:</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        <div>
          <label>Роль:</label>
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="teacher">Учитель</option>
            <option value="admin">Администратор</option>
            <option value="student">Студент</option> {/* Добавляем роль "student" */}
          </select>
        </div>
        <button type="submit">Зарегистрироваться</button>
      </form>
      {error && <p className="error">{error}</p>}
      {success && <p style={{ color: 'green', textAlign: 'center' }}>{success}</p>}
      <p>Уже есть аккаунт? <a href="/login">Войти</a></p>
    </div>
  );
}

export default Register;