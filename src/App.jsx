import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import Login from './components/Login.jsx';
import Register from './components/Register.jsx';
import Grades from './components/Grades.jsx';
import TeacherDashboard from './components/TeacherDashboard.jsx'; // Новый компонент
import './App.css';

function App() {
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [role, setRole] = useState(localStorage.getItem('role') || '');

  const handleLogin = (newToken, userRole) => {
    setToken(newToken);
    setRole(userRole);
    localStorage.setItem('token', newToken);
    localStorage.setItem('role', userRole);
  };

  const handleLogout = () => {
    setToken('');
    setRole('');
    localStorage.removeItem('token');
    localStorage.removeItem('role');
  };

  return (
    <Router>
      <div className="app">
        <header>
          <h1>Электронный журнал</h1>
          {token && <button onClick={handleLogout}>Logout</button>}
        </header>
        <main>
          <Routes>
            <Route path="/login" element={<Login onLogin={handleLogin} />} />
            <Route path="/register" element={<Register />} />
            <Route
              path="/grades/:studentId"
              element={token && role === 'student' ? <Grades token={token} /> : <Navigate to="/login" />}
            />
            <Route
              path="/teacher"
              element={token && role === 'teacher' ? <TeacherDashboard token={token} /> : <Navigate to="/login" />}
            />
            <Route path="/" element={<Navigate to={token ? (role === 'teacher' ? '/teacher' : '/grades/1') : '/login'} />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;