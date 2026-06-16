import { FormEvent, useState } from "react";
import { api, HealthResponse } from "./api/client";
import "./App.css";

import { useTiles } from "./hooks/UseTiles";
import { useIndicatorState } from "./hooks/UseZState";
import MapView from "./components/MapRenderer";
import LayerPanel from "./components/LayerPanel";
import InspectPanel from "./components/InspectPanel";

export default function App() {
  const [name, setName] = useState("Purview");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [greeting, setGreeting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { tileUrl, minZoom, maxZoom } = useTiles();
  const { setClickedPixel } = useIndicatorState();

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
    <main className="app" style={{
      display:        "flex",
      flexDirection:  "column",
      alignItems:     "center",
      justifyContent: "center",
      width:          "100%",
      height:         "100%",
    }}>
      <header>
        <h1>PURVIEW</h1>
        <p>GEOSPATIAL DASHBOARD</p>
      </header>

      {/*<form className="card" onSubmit={checkApi}>
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
      </form>*/}
      <div style={{
        display: "flex",
        gap: "16px"
      }}>
        <div style={{ 
          width: "60vw", 
          height: "75vh", 
          position: "relative", 
          background: "#d5d8db",
          border: "4px solid #d5d8db",
          borderRadius: 4,
        }}>
          <MapView
            tileUrl={tileUrl}
            minZoom={minZoom}
            maxZoom={maxZoom}
            onPixelClick={setClickedPixel}
          />
        </div>

        <div style={{ 
          width: "15vw", 
          height: "75vh", 
          position: "relative", 
          borderRadius: 4,
        }}>
          <LayerPanel/>
          <InspectPanel/>
        </div>
      </div>

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
