import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { jwtDecode } from 'jwt-decode';

function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    try {
      const response = await axios.post('http://localhost:8000/token', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });

      const token = response.data.access_token;
      const decodedToken = jwtDecode(token);
      const role = decodedToken.role;

      onLogin(token, role);
      localStorage.setItem('token', token);
      localStorage.setItem('role', role);

      if (role === 'student') {
        const userResponse = await axios.get('/api/me', { // Используем прокси
          headers: { Authorization: `Bearer ${token}` },
        });
        const { student_id, message } = userResponse.data;
        if (!student_id) {
          setError(message || "Student not found. Contact administrator.");
          return;
        }
        localStorage.setItem('student_id', student_id);
        navigate(`/grades/${student_id}`);
      } else if (role === 'teacher') {
        navigate('/teacher');
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid credentials');
    }
  };

  return (
    <div>
      <h2>Вход в систему</h2>
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
        <button type="submit">Login</button>
      </form>
      {error && <p className="error">{error}</p>}
      <p>Нет аккаунта? <a href="/register">Регистрация</a></p>
    </div>
  );
}

export default Login;