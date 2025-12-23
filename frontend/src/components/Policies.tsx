import { useState, useEffect } from 'react';
import { policiesApi } from '../services/api';
import type { Policy } from '../services/api';

export default function Policies() {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ id: '', title: '', content: '', category: '', severity: '' });

  useEffect(() => {
    loadPolicies();
  }, []);

  const loadPolicies = async () => {
    try {
      const { data } = await policiesApi.list();
      setPolicies(data);
    } catch {
      setError('Failed to load policies');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await policiesApi.create({
        id: form.id,
        title: form.title,
        content: form.content,
        category: form.category || null,
        severity: form.severity || null
      });
      setForm({ id: '', title: '', content: '', category: '', severity: '' });
      setShowForm(false);
      loadPolicies();
    } catch {
      setError('Failed to create policy');
    }
  };

  const getSeverityColor = (severity: string | null) => {
    const colors: Record<string, string> = {
      critical: '#dc3545',
      high: '#fd7e14',
      medium: '#ffc107',
      low: '#28a745'
    };
    return colors[severity?.toLowerCase() || ''] || '#6c757d';
  };

  if (loading) return <div className="loading">Loading policies...</div>;

  return (
    <div className="policies-container">
      <div className="policies-header">
        <h2>Security Policies</h2>
        <button onClick={() => setShowForm(!showForm)} className="add-btn">
          {showForm ? 'Cancel' : '+ Add Policy'}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {showForm && (
        <form onSubmit={handleSubmit} className="policy-form">
          <input
            type="text"
            placeholder="Policy ID (e.g., SEC-011)"
            value={form.id}
            onChange={(e) => setForm({ ...form, id: e.target.value })}
            required
          />
          <input
            type="text"
            placeholder="Title"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            required
          />
          <textarea
            placeholder="Policy content..."
            value={form.content}
            onChange={(e) => setForm({ ...form, content: e.target.value })}
            required
            rows={4}
          />
          <div className="form-row">
            <input
              type="text"
              placeholder="Category"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
            />
            <select
              value={form.severity}
              onChange={(e) => setForm({ ...form, severity: e.target.value })}
            >
              <option value="">Select Severity</option>
              <option value="Critical">Critical</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
          </div>
          <button type="submit">Create Policy</button>
        </form>
      )}

      <div className="policies-list">
        {policies.map((policy) => (
          <div key={policy.id} className="policy-card">
            <div className="policy-header">
              <span className="policy-id">{policy.id}</span>
              {policy.severity && (
                <span
                  className="severity"
                  style={{ backgroundColor: getSeverityColor(policy.severity) }}
                >
                  {policy.severity}
                </span>
              )}
            </div>
            <h3>{policy.title}</h3>
            <p>{policy.content}</p>
            {policy.category && <span className="category">{policy.category}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
