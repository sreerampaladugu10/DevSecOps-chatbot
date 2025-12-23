/**
 * Main application component.
 * Handles routing and authentication state.
 * Supports both local authentication and Azure AD SSO.
 */

import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Dashboard from './pages/Dashboard';
import AuthCallback from './pages/AuthCallback';
import Login from './components/Login';
import './App.css';

/**
 * Main app content with routing logic.
 * Handles authentication state and SSO callback routing.
 */
function AppContent() {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <div className="loading-screen">Loading...</div>;
  }

  // Always allow access to the auth callback route
  if (location.pathname === '/auth/callback') {
    return <AuthCallback />;
  }

  if (!isAuthenticated) {
    return <Login />;
  }

  return (
    <Routes>
      <Route path="/*" element={<Dashboard />} />
    </Routes>
  );
}

/**
 * Root application component.
 * Wraps the app with AuthProvider and BrowserRouter.
 */
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </BrowserRouter>
  );
}
