import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom';
import './App.css';
import { Footer } from './components/Footer';
import { Navigation } from './components/Navigation';
import { Dashboard } from './pages/Dashboard';
import { Landing } from './pages/Landing';
import { Projects } from './pages/Projects';
import ProjectCreate from './pages/ProjectCreate';

const AppShell = () => {
  const location = useLocation();
  const hideNav = location.pathname === '/dashboard';
  const hideFooter = location.pathname === '/dashboard';
  return (
    <div className="app-shell">
      {!hideNav && <Navigation />}
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/projects/new" element={<ProjectCreate />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Routes>
      </main>
      {!hideFooter && <Footer />}
    </div>
  );
};

const App = () => {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
};

export default App;

