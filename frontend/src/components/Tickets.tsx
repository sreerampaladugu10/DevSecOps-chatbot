import { useState, useEffect } from 'react';
import { ticketsApi } from '../services/api';
import type { Ticket } from '../services/api';

export default function Tickets() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadTickets();
  }, []);

  const loadTickets = async () => {
    try {
      const { data } = await ticketsApi.list();
      setTickets(data);
    } catch {
      setError('Failed to load tickets');
    } finally {
      setLoading(false);
    }
  };

  const getPriorityColor = (priority: string) => {
    const colors: Record<string, string> = {
      critical: '#dc3545',
      high: '#fd7e14',
      medium: '#ffc107',
      low: '#28a745'
    };
    return colors[priority] || '#6c757d';
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      open: '#007bff',
      in_progress: '#ffc107',
      resolved: '#28a745',
      closed: '#6c757d'
    };
    return colors[status] || '#6c757d';
  };

  if (loading) return <div className="loading">Loading tickets...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="tickets-container">
      <h2>Tickets</h2>
      {tickets.length === 0 ? (
        <p className="empty">No tickets yet. Use the chat to create tickets.</p>
      ) : (
        <div className="tickets-list">
          {tickets.map((ticket) => (
            <div key={ticket.id} className="ticket-card">
              <div className="ticket-header">
                <span className="ticket-type">{ticket.ticket_type.toUpperCase()}</span>
                <span className="ticket-id">#{ticket.id}</span>
              </div>
              <h3>{ticket.title}</h3>
              <p>{ticket.description}</p>
              <div className="ticket-meta">
                <span
                  className="priority"
                  style={{ backgroundColor: getPriorityColor(ticket.priority) }}
                >
                  {ticket.priority}
                </span>
                <span
                  className="status"
                  style={{ backgroundColor: getStatusColor(ticket.status) }}
                >
                  {ticket.status.replace('_', ' ')}
                </span>
                {ticket.assignee && <span className="assignee">Assigned: {ticket.assignee}</span>}
              </div>
              <div className="ticket-footer">
                <small>Created by {ticket.created_by} on {new Date(ticket.created_at).toLocaleDateString()}</small>
              </div>
            </div>
          ))}
        </div>
      )}
      <button onClick={loadTickets} className="refresh-btn">Refresh</button>
    </div>
  );
}
