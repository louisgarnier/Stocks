'use client';

import { useEffect, useState } from 'react';

interface HealthResponse {
  status: string;
  database: string;
  transactions: number;
  positions: number;
}

export default function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = async () => {
    try {
      const response = await fetch('/api/proxy/health');
      if (!response.ok) throw new Error('API not reachable');
      const data = await response.json();
      setHealth(data);
      setError(null);
    } catch (err) {
      setError('Cannot connect to API');
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(() => {
      fetchHealth();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const isConnected = health?.database === 'connected';

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f9fafb' }}>
        <p style={{ color: '#6b7280' }}>Chargement...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f9fafb' }}>
        <div style={{ textAlign: 'center', color: '#dc2626', maxWidth: '600px', padding: '20px' }}>
          <h2 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '16px' }}>Erreur de connexion</h2>
          <p style={{ marginBottom: '16px' }}>{error}</p>
          <button onClick={() => window.location.reload()} style={{ padding: '12px 24px', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer' }}>
            Recharger
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f9fafb' }}>
      <header style={{ backgroundColor: 'white', borderBottom: '1px solid #e5e7eb', padding: '16px 20px' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1 style={{ fontSize: '24px', fontWeight: 'bold', color: '#1f2937' }}>IBKR Portfolio Tracker</h1>
          <span style={{ display: 'inline-flex', alignItems: 'center', padding: '6px 12px', borderRadius: '9999px', fontSize: '14px', fontWeight: '500', backgroundColor: isConnected ? '#dcfce7' : '#fef2f2', color: isConnected ? '#166534' : '#dc2626' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', marginRight: '8px', backgroundColor: isConnected ? '#22c55e' : '#ef4444' }} />
            {isConnected ? 'Connecté' : 'Déconnecté'}
          </span>
        </div>
      </header>

      <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '32px 20px' }}>
        {/* Stats Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px', marginBottom: '32px' }}>
          <div style={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
            <h3 style={{ fontSize: '14px', fontWeight: '500', color: '#6b7280', marginBottom: '8px' }}>Base de données</h3>
            <p style={{ fontSize: '24px', fontWeight: '600', color: '#1f2937' }}>{health?.database === 'connected' ? '✅ Connectée' : '❌ Erreur'}</p>
          </div>
          <div style={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
            <h3 style={{ fontSize: '14px', fontWeight: '500', color: '#6b7280', marginBottom: '8px' }}>Transactions</h3>
            <p style={{ fontSize: '24px', fontWeight: '600', color: '#1f2937' }}>{health?.transactions ?? 0}</p>
          </div>
          <div style={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
            <h3 style={{ fontSize: '14px', fontWeight: '500', color: '#6b7280', marginBottom: '8px' }}>Positions</h3>
            <p style={{ fontSize: '24px', fontWeight: '600', color: '#1f2937' }}>{health?.positions ?? 0}</p>
          </div>
        </div>

        {/* Empty state */}
        <div style={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '48px 24px', textAlign: 'center', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>🚀</div>
          <h3 style={{ fontSize: '18px', fontWeight: '500', color: '#1f2937', marginBottom: '8px' }}>Prêt à démarrer</h3>
          <p style={{ fontSize: '14px', color: '#6b7280' }}>L'application est prête. Les fonctionnalités seront ajoutées ici.</p>
        </div>
      </main>
    </div>
  );
}
