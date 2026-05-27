import { FormEvent, useState } from "react";
import { api, HealthResponse } from "./api/client";
import "./App.css";

export default function App() {
  const [name, setName] = useState("Purview");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [greeting, setGreeting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function checkApi(event?: FormEvent) {
    event?.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const [healthData, helloData] = await Promise.all([
        api.getHealth(),
        api.getHello(name),
      ]);
      setHealth(healthData);
      setGreeting(helloData.message);
    } catch (err) {
      setHealth(null);
      setGreeting(null);
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app">
      <header>
        <h1>Purview Dashboard</h1>
        <p>React frontend with FastAPI REST backend</p>
      </header>

      <form className="card" onSubmit={checkApi}>
        <label htmlFor="name">Name for greeting</label>
        <input
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Your name"
        />
        <button type="submit" disabled={loading}>
          {loading ? "Checking…" : "Test API connection"}
        </button>
      </form>

      {error && (
        <section className="card error" role="alert">
          <h2>Connection failed</h2>
          <p>{error}</p>
          <p className="hint">
            Ensure the backend is running on port 8000, or start both with{" "}
            <code>npm run dev</code> from the project root.
          </p>
        </section>
      )}

      {(health || greeting) && (
        <section className="results">
          {health && (
            <article className="card">
              <h2>Health</h2>
              <dl>
                <dt>Status</dt>
                <dd>{health.status}</dd>
                <dt>Service</dt>
                <dd>{health.service}</dd>
                <dt>Timestamp</dt>
                <dd>{health.timestamp}</dd>
              </dl>
            </article>
          )}
          {greeting && (
            <article className="card">
              <h2>Greeting</h2>
              <p>{greeting}</p>
            </article>
          )}
        </section>
      )}
    </main>
  );
}
