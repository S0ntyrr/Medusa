"use client";

import { useEffect, useMemo, useState } from "react";
import { supabase } from "../lib/supabase";

const tracks = [
  { id: "1", provider: "demo", title: "LUNA", artist: "Feid", genre: "Urbano", color: "cover-lime" },
  { id: "2", provider: "demo", title: "Classy 101", artist: "Feid, Young Miko", genre: "Urbano", color: "cover-coral" },
  { id: "3", provider: "demo", title: "Ojitos Lindos", artist: "Bad Bunny, Bomba Estereo", genre: "Tropical", color: "cover-sky" },
  { id: "4", provider: "demo", title: "Todo Contigo", artist: "Alvaro de Luna", genre: "Pop", color: "cover-yellow" },
  { id: "5", provider: "demo", title: "La Falda", artist: "Myke Towers", genre: "Urbano", color: "cover-violet" },
];

const initialQueue = [
  { id: "demo-1", position: 1, title: "Normal", artist: "Feid", votes: 18, color: "cover-violet" },
  { id: "demo-2", position: 2, title: "Qlona", artist: "Karol G, Peso Pluma", votes: 12, color: "cover-coral" },
  { id: "demo-3", position: 3, title: "Beso", artist: "Rosalia, Rauw Alejandro", votes: 9, color: "cover-sky" },
];

function Cover({ color, small = false }: { color: string; small?: boolean }) {
  return <div aria-hidden="true" className={`cover ${color} ${small ? "cover-small" : ""}`}><span>✦</span></div>;
}

export default function Home() {
  const [query, setQuery] = useState("");
  const [searchTracks, setSearchTracks] = useState(tracks);
  const [requested, setRequested] = useState<string | null>(null);
  const [voted, setVoted] = useState<number[]>([]);
  const [sessionActive, setSessionActive] = useState(false);
  const [queue, setQueue] = useState(initialQueue);
  const results = useMemo(() => searchTracks.filter((track) => `${track.title} ${track.artist}`.toLowerCase().includes(query.toLowerCase())), [query, searchTracks]);

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;
    if (!query.trim() || !apiUrl) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void fetch(`${apiUrl}/api/music/search?query=${encodeURIComponent(query)}`, { signal: controller.signal })
        .then((response) => response.ok ? response.json() : Promise.reject(new Error("Search failed")))
        .then((remoteTracks: Array<{ provider: string; provider_track_id: string; title: string; artist: string }>) => {
          setSearchTracks(remoteTracks.map((track, index) => ({
            id: track.provider_track_id,
            provider: track.provider,
            title: track.title,
            artist: track.artist,
            genre: "Música",
            color: tracks[index % tracks.length].color,
          })));
        })
        .catch(() => setSearchTracks(tracks));
    }, 220);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [query]);

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;
    if (!apiUrl) return;

    let heartbeat: number | undefined;
    const startSession = async () => {
      try {
        const response = await fetch(`${apiUrl}/api/session/create`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ venue_slug: "medusa-granizados", table_label: "Mesa 03" }),
        });
        if (!response.ok) return;
        setSessionActive(true);
        void fetch(`${apiUrl}/api/queue`, { credentials: "include" })
          .then((queueResponse) => queueResponse.ok ? queueResponse.json() : Promise.reject(new Error("Queue unavailable")))
          .then((remoteQueue: Array<{ id: string; title: string; artist: string; votes: number }>) => {
            setQueue(remoteQueue.map((track, index) => ({
              id: track.id,
              position: index + 1,
              title: track.title,
              artist: track.artist,
              votes: track.votes,
              color: tracks[index % tracks.length].color,
            })));
          })
          .catch(() => undefined);
        heartbeat = window.setInterval(() => {
          void fetch(`${apiUrl}/api/session/heartbeat`, { method: "POST", credentials: "include" })
            .then((heartbeatResponse) => setSessionActive(heartbeatResponse.ok))
            .catch(() => setSessionActive(false));
        }, 5 * 60 * 1000);
      } catch {
        setSessionActive(false);
      }
    };

    void startSession();
    return () => { if (heartbeat) window.clearInterval(heartbeat); };
  }, []);

  useEffect(() => {
    const realtimeClient = supabase;
    if (!sessionActive || !realtimeClient) return;
    const refreshQueue = () => {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL;
      if (!apiUrl) return;
      void fetch(`${apiUrl}/api/queue`, { credentials: "include" })
        .then((response) => response.ok ? response.json() : Promise.reject(new Error("Queue unavailable")))
        .then((remoteQueue: Array<{ id: string; title: string; artist: string; votes: number }>) => setQueue(remoteQueue.map((track, index) => ({ id: track.id, position: index + 1, title: track.title, artist: track.artist, votes: track.votes, color: tracks[index % tracks.length].color }))))
        .catch(() => undefined);
    };
    const channel = realtimeClient.channel("public-queue").on("postgres_changes", { event: "*", schema: "public", table: "queue_items" }, refreshQueue).subscribe();
    return () => { void realtimeClient.removeChannel(channel); };
  }, [sessionActive]);

  async function requestTrack(trackId: string) {
    const track = tracks.find((item) => item.id === trackId);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;
    if (sessionActive && apiUrl && track) {
      try {
        const response = await fetch(`${apiUrl}/api/queue/request`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ provider: track.provider, provider_track_id: track.id, title: track.title, artist: track.artist }),
        });
        if (!response.ok) return;
        const created = await response.json() as { id: string };
        setQueue((current) => [...current, { id: created.id, position: current.length + 1, title: track.title, artist: track.artist, votes: 0, color: track.color }]);
      } catch {
        return;
      }
    }
    setRequested(trackId);
    window.setTimeout(() => setRequested(null), 2400);
  }

  async function voteForTrack(trackId: string, position: number) {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;
    if (voted.includes(position)) return;
    if (sessionActive && apiUrl && !trackId.startsWith("demo-")) {
      const response = await fetch(`${apiUrl}/api/queue/${trackId}/vote`, { method: "POST", credentials: "include" });
      if (!response.ok) return;
      const result = await response.json() as { votes: number };
      setQueue((current) => current.map((track) => track.position === position ? { ...track, votes: result.votes } : track));
    } else {
      setQueue((current) => current.map((track) => track.position === position ? { ...track, votes: track.votes + 1 } : track));
    }
    setVoted((current) => [...current, position]);
  }

  return <main className="app-shell">
    <div className="ambient ambient-one" /><div className="ambient ambient-two" />
    <nav className="topbar"><div className="brand-mark"><span className="brand-icon">✦</span><span>RITMO <em>FROST</em></span></div><div className="venue-pill"><span className="live-dot" /> La Esquina · Mesa 03{sessionActive && <small> · activa</small>}</div><a className="icon-button" href="/admin" aria-label="Abrir panel de administrador">•••</a></nav>
    <section className="hero"><p className="eyebrow">Tu visita, tu soundtrack</p><h1>¿Qué quieres<br /><i>escuchar?</i></h1><p className="hero-copy">Pide una canción, súbela con votos y deja que la noche siga fluyendo.</p>
      <label className="search-box"><span aria-hidden="true">⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Busca canción o artista" aria-label="Buscar canción o artista" /><kbd>/</kbd></label>
      {query && <div className="search-results">{results.length ? results.map((track) => <div className="result-row" key={track.id}><Cover color={track.color} small /><div><strong>{track.title}</strong><small>{track.artist}</small></div><button onClick={() => requestTrack(track.id)} className="add-button" aria-label={`Solicitar ${track.title}`}>+</button></div>) : <p className="empty-state">No encontramos esa canción todavía.</p>}</div>}
    </section>
    <section className="now-playing"><div className="section-heading"><div><p className="eyebrow">Sonando ahora</p><h2>Tu mesa tiene el control</h2></div><div className="equalizer" aria-label="Reproduciendo"><i /><i /><i /><i /><i /></div></div><div className="player-card"><Cover color="cover-lime" /><div className="track-info"><p className="track-kicker">#01 · En reproducción</p><h3>Classy 101</h3><p>Feid, Young Miko</p><div className="progress"><span /><b>2:14</b><b>3:16</b></div></div><button className="play-button" aria-label="Pausar canción">Ⅱ</button></div></section>
    <section className="queue-section"><div className="section-heading"><div><p className="eyebrow">La siguiente ronda</p><h2>En la cola <span>· {queue.length}</span></h2></div><button className="text-button">Ver todo <span>↗</span></button></div><div className="queue-list">{queue.map((track) => <div className="queue-row" key={track.position}><span className="queue-position">0{track.position}</span><Cover color={track.color} small /><div className="queue-track"><strong>{track.title}</strong><small>{track.artist}</small></div><button className={`vote-button ${voted.includes(track.position) ? "is-voted" : ""}`} onClick={() => void voteForTrack(track.id, track.position)} aria-label={`Votar por ${track.title}`}><span>♥</span> {track.votes}</button></div>)}</div></section>
    {requested && <div className="toast" role="status"><span>✓</span><div><strong>¡Canción agregada!</strong><small>Está en la cola. Que siga el ritmo.</small></div></div>}
  </main>;
}
