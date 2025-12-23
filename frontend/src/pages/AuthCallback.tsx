/**
 * OAuth callback page for handling Azure AD SSO redirects.
 * Processes the token from URL and completes authentication.
 */

import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function AuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { loginWithToken } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState(true);

  useEffect(() => {
    const processCallback = async () => {
      // Check for error from Azure AD
      const errorParam = searchParams.get('error');
      if (errorParam) {
        setError(decodeURIComponent(errorParam));
        setProcessing(false);
        return;
      }

      // Get token from URL
      const token = searchParams.get('token');
      if (!token) {
        setError('No authentication token received');
        setProcessing(false);
        return;
      }

      try {
        // Complete login with the token
        await loginWithToken(token);
        // Redirect to dashboard
        navigate('/', { replace: true });
      } catch (err) {
        setError('Failed to complete authentication. Please try again.');
        setProcessing(false);
      }
    };

    processCallback();
  }, [searchParams, loginWithToken, navigate]);

  if (processing) {
    return (
      <div className="callback-container">
        <div className="callback-box">
          <div className="callback-spinner"></div>
          <h2>Completing sign in...</h2>
          <p>Please wait while we authenticate your account.</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="callback-container">
        <div className="callback-box callback-error">
          <h2>Authentication Failed</h2>
          <p className="error-message">{error}</p>
          <button
            className="callback-button"
            onClick={() => navigate('/', { replace: true })}
          >
            Return to Login
          </button>
        </div>
      </div>
    );
  }

  return null;
}
