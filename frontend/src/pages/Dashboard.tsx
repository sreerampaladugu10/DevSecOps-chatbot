/**
 * Main dashboard page component.
 * Displays tabbed interface for Chat, Tickets, and Policies.
 */

import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import Chat from '../components/Chat';
import Tickets from '../components/Tickets';
import Policies from '../components/Policies';

type Tab = 'chat' | 'tickets' | 'policies';

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<Tab>('chat');
  const { user, logout } = useAuth();

  return (
    <div className="dashboard">
      <header>
        <h1>DevSecOps Chat</h1>
        <div className="user-info">
          <span>Welcome, {user?.username}</span>
          <button className="logout-button" onClick={logout}>
            Logout
          </button>
        </div>
      </header>

      <nav className="tabs">
        <button
          className={activeTab === 'chat' ? 'active' : ''}
          onClick={() => setActiveTab('chat')}
        >
          Chat
        </button>
        <button
          className={activeTab === 'tickets' ? 'active' : ''}
          onClick={() => setActiveTab('tickets')}
        >
          Tickets
        </button>
        <button
          className={activeTab === 'policies' ? 'active' : ''}
          onClick={() => setActiveTab('policies')}
        >
          Policies
        </button>
      </nav>

      <main>
        {activeTab === 'chat' && <Chat />}
        {activeTab === 'tickets' && <Tickets />}
        {activeTab === 'policies' && <Policies />}
      </main>
    </div>
  );
}
