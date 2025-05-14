import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

function Register() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('student');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [className, setClassName] = useState('9A');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    const payload = {
      username: username,
      password: password,
      role: role,
      first_name: firstName,
      last_name: lastName,
      class_name: role === 'student' ? className : null
    };
    console.log('Sending payload:', payload);
    try {
      const response = await axios.post('http://localhost:8000/register', payload, {
        headers: { 'Content-Type': 'application/json' }
      });
      setSuccess(response.data.message);
      setTimeout(() => navigate('/login'), 2000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed');
      console.error('Registration error:', err.response?.data);
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
          <label>Имя:</label>
          <input
            type="text"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            required
          />
        </div>
        <div>
          <label>Фамилия:</label>
          <input
            type="text"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            required
          />
        </div>
        <div>
          <label>Роль:</label>
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="teacher">Учитель</option>
            <option value="student">Студент</option>
          </select>
        </div>
        {role === 'student' && (
          <div>
            <label>Класс:</label>
            <select value={className} onChange={(e) => setClassName(e.target.value)}>
              {["9A", "9B", "10A", "10B", "11A", "11B"].map(cls => (
                <option key={cls} value={cls}>
                  {cls}
                </option>
              ))}
            </select>
          </div>
        )}
        <button type="submit">Зарегистрироваться</button>
      </form>
      {error && <p className="error">{error}</p>}
      {success && <p style={{ color: 'green', textAlign: 'center' }}>{success}</p>}
      <p>Уже есть аккаунт? <a href="/login">Войти</a></p>
    </div>
  );
}

export default Register;