/**
 * Login and registration component.
 * Handles user authentication with JWT tokens and Azure AD SSO.
 */

import { useState } from 'react';
import { authApi } from '../services/api';
import { useAuth } from '../context/AuthContext';

/**
 * Microsoft logo SVG for SSO button.
 */
function MicrosoftLogo() {
  return (
    <svg width="20" height="20" viewBox="0 0 21 21" xmlns="http://www.w3.org/2000/svg">
      <rect x="1" y="1" width="9" height="9" fill="#f25022"/>
      <rect x="11" y="1" width="9" height="9" fill="#7fba00"/>
      <rect x="1" y="11" width="9" height="9" fill="#00a4ef"/>
      <rect x="11" y="11" width="9" height="9" fill="#ffb900"/>
    </svg>
  );
}

export default function Login() {
  const [isLogin, setIsLogin] = useState(true);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [ssoLoading, setSsoLoading] = useState(false);
  const { login, loginWithSSO, ssoEnabled } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const { data } = isLogin
        ? await authApi.login(username, password)
        : await authApi.register(username, password);

      login(data.user, data.access_token);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSSOLogin = async () => {
    setError('');
    setSsoLoading(true);

    try {
      await loginWithSSO();
      // Note: This will redirect to Azure AD, so we won't reach here
    } catch (err) {
      setError('Failed to initiate SSO login. Please try again.');
      setSsoLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <h1>DevSecOps Chat</h1>
        <p className="login-subtitle">Security Assistant with Multi-Tool Reasoning</p>

        {/* SSO Login Button */}
        {ssoEnabled && (
          <>
            <button
              type="button"
              className="sso-button"
              onClick={handleSSOLogin}
              disabled={ssoLoading || loading}
            >
              <MicrosoftLogo />
              <span>{ssoLoading ? 'Redirecting...' : 'Sign in with Microsoft'}</span>
            </button>

            <div className="login-divider">
              <span>or continue with username</span>
            </div>
          </>
        )}

        <div className="auth-tabs">
          <button
            className={`auth-tab ${isLogin ? 'active' : ''}`}
            onClick={() => setIsLogin(true)}
          >
            Login
          </button>
          <button
            className={`auth-tab ${!isLogin ? 'active' : ''}`}
            onClick={() => setIsLogin(false)}
          >
            Register
          </button>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter username"
              required
              minLength={3}
              disabled={loading || ssoLoading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password"
              required
              minLength={8}
              disabled={loading || ssoLoading}
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" className="login-button" disabled={loading || ssoLoading}>
            {loading ? 'Please wait...' : isLogin ? 'Login' : 'Create Account'}
          </button>
        </form>

        <p className="login-hint">
          {isLogin
            ? "Don't have an account? Click Register above."
            : 'Password must be at least 8 characters.'}
        </p>
      </div>
    </div>
  );
}
