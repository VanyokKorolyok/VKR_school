import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'; // Убедимся, что импорт здесь
import Login from './components/Login.jsx';
import Register from './components/Register.jsx';
import Grades from './components/Grades.jsx';
import TeacherDashboard from './components/TeacherDashboard.jsx';
import './App.css';

// Создаем экземпляр QueryClient
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 минут кэширования
      cacheTime: 10 * 60 * 1000, // 10 минут хранения в кэше
      retry: 1, // Повтор запроса при ошибке
    },
  },
});

function App() {
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [role, setRole] = useState(localStorage.getItem('role') || '');

  useEffect(() => {
    const storedToken = localStorage.getItem('token');
    const storedRole = localStorage.getItem('role');
    if (storedToken && storedRole) {
      setToken(storedToken);
      setRole(storedRole);
    }
  }, []);

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
    localStorage.removeItem('student_id');
  };

  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <div className="app" style={{ minHeight: '100vh', backgroundColor: '#f0f2f5' }}>
          <header style={{ padding: '10px 20px', backgroundColor: '#fff', borderBottom: '1px solid #ddd' }}>
            <h1 style={{ fontSize: '24px', margin: 0 }}>Электронный журнал</h1>
            {token && (
              <button onClick={handleLogout} style={{ marginLeft: '20px', padding: '5px 10px' }}>
                Logout
              </button>
            )}
          </header>
          <main style={{ padding: '20px' }}>
            <Routes>
              <Route path="/login" element={<Login onLogin={handleLogin} />} />
              <Route path="/register" element={<Register />} />
              <Route
                path="/grades/:studentId"
                element={token && role === 'student' ? <Grades token={token} role={role} /> : <Navigate to="/login" />}
              />
              <Route
                path="/teacher"
                element={token && role === 'teacher' ? <TeacherDashboard token={token} /> : <Navigate to="/login" />}
              />
              <Route
                path="/"
                element={<Navigate to={token ? (role === 'teacher' ? '/teacher' : '/grades/1') : '/login'} />}
              />
            </Routes>
          </main>
        </div>
      </Router>
    </QueryClientProvider>
  );
}

export default App;