"use client";

import { type FormEvent, useEffect, useState } from "react";
import Link from "next/link";

import { supabase } from "../../lib/supabase";

const demoQueue = [
  { id: "1", track_id: "1", title: "LUNA", artist: "Feid", votes: 18 },
  { id: "2", track_id: "2", title: "Classy 101", artist: "Feid, Young Miko", votes: 12 },
  { id: "3", track_id: "3", title: "Ojitos Lindos", artist: "Bad Bunny, Bomba Estereo", votes: 9 },
];

type PlayerState = { track: { title: string; artist: string; artwork_url?: string | null } | null; is_playing: boolean };
type ActiveSession = { id: string; table_id: string | null; last_activity: string; status: string };
type VenueSettings = { session_max_hours: number; session_idle_minutes: number; request_cooldown_minutes: number; max_pending_per_session: number; explicit_content_allowed: boolean; same_artist_window: number; same_artist_limit: number };
type AdminStats = { requests_today: number; pending_tracks: number; votes_total: number; active_sessions: number };
type SpotifyPlayer = { addListener: (event: string, callback: (payload: { device_id?: string }) => void) => void; connect: () => Promise<boolean> };
type SpotifySdk = { Player: new (options: { name: string; getOAuthToken: (callback: (token: string) => void) => void; volume: number }) => SpotifyPlayer };

declare global {
  interface Window {
    Spotify?: SpotifySdk;
    onSpotifyWebPlaybackSDKReady?: () => void;
  }
}
type QueueItem = { id: string; track_id?: string; title: string; artist: string; votes: number };

export default function AdminPage() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  const [player, setPlayer] = useState<PlayerState>({ track: { title: "Classy 101", artist: "Feid, Young Miko" }, is_playing: true });
  const [queue, setQueue] = useState<QueueItem[]>(demoQueue);
  const [notice, setNotice] = useState("");
  const [authenticated, setAuthenticated] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [sessions, setSessions] = useState<ActiveSession[]>([]);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [settings, setSettings] = useState<VenueSettings>({ session_max_hours: 3, session_idle_minutes: 30, request_cooldown_minutes: 10, max_pending_per_session: 3, explicit_content_allowed: false, same_artist_window: 5, same_artist_limit: 2 });
  const [spotifyConnected, setSpotifyConnected] = useState(false);
  const [spotifyPlayerReady, setSpotifyPlayerReady] = useState(false);
  const [stats, setStats] = useState<AdminStats>({ requests_today: 0, pending_tracks: 0, votes_total: 0, active_sessions: 0 });

  useEffect(() => {
    if (!apiUrl || !supabase) return;
    void supabase.auth.getSession().then(({ data }) => {
      const token = data.session?.access_token;
      if (!token) return;
      setAccessToken(token);
      void fetch(`${apiUrl}/api/admin/status`, { headers: { Authorization: `Bearer ${token}` } })
        .then((response) => { if (response.ok) setAuthenticated(true); })
        .catch(() => undefined);
    });
  }, [apiUrl]);

  useEffect(() => {
    if (!apiUrl || !authenticated) return;
    const headers = accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined;
    void fetch(`${apiUrl}/api/player/current`, { headers })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Player unavailable")))
      .then((state: PlayerState) => setPlayer(state))
      .catch(() => undefined);
    void fetch(`${apiUrl}/api/admin/queue`, { headers })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Queue unavailable")))
      .then((items: Array<{ id: string; track_id?: string; title: string; artist: string; votes: number }>) => setQueue(items.map((item) => ({ id: item.id, track_id: item.track_id, title: item.title, artist: item.artist, votes: item.votes }))))
      .catch(() => undefined);
    void fetch(`${apiUrl}/api/admin/sessions`, { headers })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Sessions unavailable")))
      .then((items: ActiveSession[]) => setSessions(items))
      .catch(() => undefined);
    void fetch(`${apiUrl}/api/admin/settings`, { headers })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Settings unavailable")))
      .then((value: VenueSettings) => setSettings(value))
      .catch(() => undefined);
    void fetch(`${apiUrl}/api/admin/spotify/status`, { headers })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Spotify status unavailable")))
      .then((value: { connected: boolean }) => setSpotifyConnected(value.connected))
      .catch(() => undefined);
    void fetch(`${apiUrl}/api/admin/stats`, { headers })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Stats unavailable")))
      .then((value: AdminStats) => setStats(value))
      .catch(() => undefined);
  }, [apiUrl, authenticated, accessToken]);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!apiUrl || !supabase) {
      setLoginError("Configura Supabase y el backend local para acceder al panel");
      return;
    }
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error || !data.session) {
      setLoginError(error?.message ?? "Correo o contraseña incorrectos");
      return;
    }
    setAccessToken(data.session.access_token);
    setLoginError("");
    setAuthenticated(true);
  }

  async function control(action: "pause" | "resume" | "skip") {
    if (!apiUrl) {
      setPlayer((current) => action === "skip" ? { track: null, is_playing: false } : { ...current, is_playing: action === "resume" });
      setNotice("Modo local: control actualizado");
      return;
    }
    try {
      const response = await fetch(`${apiUrl}/api/player/${action}`, { method: "POST", headers: { Authorization: `Bearer ${accessToken}` } });
      if (!response.ok) throw new Error("Player unavailable");
      setPlayer(await response.json() as PlayerState);
      setNotice(action === "skip" ? "Canción saltada" : action === "pause" ? "Reproducción pausada" : "Reproducción activa");
    } catch {
      setPlayer((current) => action === "skip" ? { track: null, is_playing: false } : { ...current, is_playing: action === "resume" });
      setNotice("API no disponible: control aplicado en modo local");
    }
  }

  async function revokeSession(sessionId: string) {
    if (!apiUrl || !accessToken) {
      setSessions((current) => current.filter((session) => session.id !== sessionId));
      setNotice("Sesión revocada en modo local");
      return;
    }
    try {
      const response = await fetch(`${apiUrl}/api/admin/sessions/${sessionId}/revoke`, { method: "POST", headers: { Authorization: `Bearer ${accessToken}` } });
      if (!response.ok) throw new Error("Session unavailable");
      setSessions((current) => current.filter((session) => session.id !== sessionId));
      setNotice("Sesión revocada");
    } catch {
      setNotice("No se pudo revocar la sesión");
    }
  }

  async function toggleExplicitContent() {
    const next = { ...settings, explicit_content_allowed: !settings.explicit_content_allowed };
    if (!apiUrl || !accessToken) {
      setSettings(next);
      setNotice("Regla actualizada en modo local");
      return;
    }
    const response = await fetch(`${apiUrl}/api/admin/settings`, { method: "PATCH", headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" }, body: JSON.stringify(next) });
    if (response.ok) {
      setSettings(await response.json() as VenueSettings);
      setNotice(next.explicit_content_allowed ? "Contenido explícito permitido" : "Contenido explícito bloqueado");
    }
  }

  async function removeQueueItem(queueId: string) {
    if (!apiUrl || !accessToken) {
      setQueue((current) => current.filter((item) => item.id !== queueId));
      setNotice("Canción retirada en modo local");
      return;
    }
    const response = await fetch(`${apiUrl}/api/admin/queue/${queueId}`, { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } });
    if (response.ok) {
      setQueue((current) => current.filter((item) => item.id !== queueId));
      setNotice("Canción retirada de la cola");
    }
  }

  async function queueAction(queueId: string, action: "skip" | "recalculate") {
    if (!apiUrl || !accessToken) {
      if (action === "skip") setQueue((current) => current.filter((item) => item.id !== queueId));
      setNotice(action === "skip" ? "Canción saltada en modo local" : "Prioridades recalculadas en modo local");
      return;
    }
    const endpoint = action === "recalculate" ? `${apiUrl}/api/admin/queue/recalculate` : `${apiUrl}/api/admin/queue/${queueId}/skip`;
    const response = await fetch(endpoint, { method: "POST", headers: { Authorization: `Bearer ${accessToken}` } });
    if (!response.ok) return;
    if (action === "skip") setQueue((current) => current.filter((item) => item.id !== queueId));
    setNotice(action === "skip" ? "Canción saltada" : "Prioridades recalculadas");
  }

  async function blockArtist(artist: string) {
    if (!apiUrl || !accessToken) {
      setNotice(`${artist} bloqueado en modo local`);
      return;
    }
    const response = await fetch(`${apiUrl}/api/admin/blocklist/artists`, { method: "POST", headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" }, body: JSON.stringify({ artist_name: artist }) });
    if (response.ok) setNotice(`${artist} bloqueado para este local`);
  }

  async function blockTrack(trackId: string | undefined) {
    if (!trackId) return;
    if (!apiUrl || !accessToken) {
      setNotice("Canción bloqueada en modo local");
      return;
    }
    const response = await fetch(`${apiUrl}/api/admin/blocklist/tracks/${trackId}`, { method: "POST", headers: { Authorization: `Bearer ${accessToken}` } });
    if (response.ok) setNotice("Canción bloqueada para este local");
  }

  async function saveRules(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!apiUrl || !accessToken) {
      setNotice("Reglas guardadas en modo local");
      return;
    }
    const response = await fetch(`${apiUrl}/api/admin/settings`, { method: "PATCH", headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" }, body: JSON.stringify(settings) });
    if (response.ok) {
      setSettings(await response.json() as VenueSettings);
      setNotice("Reglas guardadas");
    }
  }

  async function connectSpotify() {
    if (!apiUrl || !accessToken) return;
    const response = await fetch(`${apiUrl}/api/admin/spotify/connect`, { headers: { Authorization: `Bearer ${accessToken}` } });
    if (!response.ok) {
      setNotice("Configura Spotify OAuth en el backend");
      return;
    }
    const value = await response.json() as { authorization_url: string };
    window.location.assign(value.authorization_url);
  }

  useEffect(() => {
    if (!spotifyConnected || !apiUrl || !accessToken || document.querySelector("#spotify-player-sdk")) return;
    const script = document.createElement("script");
    script.id = "spotify-player-sdk";
    script.src = "https://sdk.scdn.co/spotify-player.js";
    script.async = true;
    document.body.appendChild(script);
    const initialize = async () => {
      const response = await fetch(`${apiUrl}/api/admin/spotify/player-token`, { headers: { Authorization: `Bearer ${accessToken}` } });
      if (!response.ok || !window.Spotify) return;
      const { access_token: token } = await response.json() as { access_token: string };
      const player = new window.Spotify.Player({ name: "Ritmo Frost Player", getOAuthToken: (callback) => callback(token), volume: 0.7 });
      player.addListener("ready", () => setSpotifyPlayerReady(true));
      await player.connect();
    };
    window.onSpotifyWebPlaybackSDKReady = () => { void initialize(); };
    return () => { script.remove(); delete window.onSpotifyWebPlaybackSDKReady; };
  }, [spotifyConnected, apiUrl, accessToken]);

  if (!authenticated) return <main className="admin-shell admin-login-shell"><div className="admin-login"><Link href="/" className="brand-mark"><span className="brand-icon">✦</span><span>RITMO <em>FROST</em></span></Link><p className="eyebrow">Acceso restringido</p><h1>Control de sala</h1><p>Inicia sesión para gestionar la música de tu establecimiento.</p><form onSubmit={login}><label>Correo<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="admin@medusa.local" required /></label><label>Contraseña<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••" required /></label><button type="submit">Entrar al panel <span>↗</span></button>{loginError && <small role="alert">{loginError}</small>}</form><Link href="/" className="back-link">← Volver a la experiencia del cliente</Link></div></main>;

  return <main className="admin-shell">
    <header className="admin-topbar"><Link href="/" className="brand-mark"><span className="brand-icon">✦</span><span>RITMO <em>FROST</em></span></Link><div className="admin-venue"><span className="live-dot" /> La Esquina <span>/</span> Panel del local</div><button className="admin-user" aria-label="Menú de administrador">S</button></header>
    <div className="admin-layout">
      <aside className="admin-sidebar"><p className="sidebar-label">Gestión</p><a className="sidebar-link active" href="#overview">◈ <span>Resumen</span></a><a className="sidebar-link" href="#queue">≡ <span>Cola musical</span><b>{queue.length}</b></a><a className="sidebar-link" href="#sessions">◎ <span>Sesiones</span><b>12</b></a><p className="sidebar-label settings-label">Configuración</p><a className="sidebar-link" href="#rules">⌘ <span>Reglas y bloqueos</span></a><a className="sidebar-link" href="#provider">↗ <span>Proveedor musical</span></a></aside>
      <section className="admin-content" id="overview"><div className="admin-heading"><div><p className="eyebrow">Martes, 14 de septiembre</p><h1>Control de sala</h1></div><span className="status-badge"><i /> Sistema activo</span></div>
        <div className="admin-stats"><div><span>Reproduciendo</span><strong>{player.track ? "01" : "--"}</strong><small>{player.is_playing ? "En vivo ahora" : "Pausado"}</small></div><div><span>En la cola</span><strong>{stats.pending_tracks || queue.length}</strong><small>canciones pendientes</small></div><div><span>Sesiones activas</span><strong>{stats.active_sessions}</strong><small>actualizadas ahora</small></div><div><span>Solicitudes hoy</span><strong>{stats.requests_today}</strong><small>{stats.votes_total} votos acumulados</small></div></div>
        <div className="admin-grid"><section className="admin-card player-admin"><div className="card-heading"><div><p className="eyebrow">Reproduciendo ahora</p><h2>Control del player</h2></div><span className="live-label"><i /> LIVE</span></div><div className="admin-now"><div className="admin-art" style={player.track?.artwork_url ? { backgroundImage: `url(${player.track.artwork_url})` } : undefined}><span>✦</span></div><div><p className="track-kicker">Ritmo Frost · Sala principal</p><h3>{player.track?.title ?? "Sin canción"}</h3><p>{player.track?.artist ?? "La cola está en pausa"}</p></div></div><div className="admin-controls"><button onClick={() => void control(player.is_playing ? "pause" : "resume")} aria-label={player.is_playing ? "Pausar" : "Reanudar"}>{player.is_playing ? "Ⅱ" : "▶"}</button><button onClick={() => void control("skip")} aria-label="Saltar canción">↠</button><span>{player.is_playing ? "Reproduciendo" : "Pausado"}</span></div></section>
          <section className="admin-card queue-admin" id="queue"><div className="card-heading"><div><p className="eyebrow">Próximamente</p><h2>Cola musical</h2></div><button className="outline-button" onClick={() => void queueAction("", "recalculate")}>Recalcular ↻</button></div><div className="admin-queue">{queue.map((item, index) => <div className="admin-queue-row" key={item.id}><span>{String(index + 1).padStart(2, "0")}</span><div><strong>{item.title}</strong><small>{item.artist}</small></div><b>♥ {item.votes}</b><button onClick={() => void queueAction(item.id, "skip")} aria-label={`Saltar ${item.title}`}>↠</button><button onClick={() => void blockTrack(item.track_id)} aria-label={`Bloquear ${item.title}`}>⊘</button><button onClick={() => void blockArtist(item.artist)} aria-label={`Bloquear artista ${item.artist}`}>A</button><button onClick={() => void removeQueueItem(item.id)} aria-label={`Retirar ${item.title} de la cola`}>×</button></div>)}</div></section>
        </div>
        <div className="admin-lower"><section className="admin-card sessions-card" id="sessions"><div className="card-heading"><div><p className="eyebrow">Presencia en sala</p><h2>Sesiones activas</h2></div><a href="#sessions">Ver todas ↗</a></div><div className="session-summary"><strong>{sessions.length || 12}</strong><span>personas están participando<br />en este momento</span><div className="avatar-stack"><i>J</i><i>M</i><i>A</i><i>+</i></div></div>{sessions.slice(0, 3).map((session) => <div className="session-row" key={session.id}><span className="session-pulse" /><div><strong>{session.table_id ? `Mesa ${session.table_id.slice(0, 4)}` : "Mesa sin asignar"}</strong><small>Activa · {new Date(session.last_activity).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}</small></div><button onClick={() => void revokeSession(session.id)}>Revocar</button></div>)}</section><section className="admin-card rules-card" id="rules"><div className="card-heading"><div><p className="eyebrow">Protección</p><h2>Reglas rápidas</h2></div><a href="#rules">Editar ↗</a></div><form className="rules-form" onSubmit={saveRules}><div className="rule-row"><span>Contenido explícito</span><button type="button" className={`toggle ${settings.explicit_content_allowed ? "on" : "off"}`} onClick={() => void toggleExplicitContent()} aria-label="Cambiar contenido explícito" /> <small>{settings.explicit_content_allowed ? "Permitido" : "Desactivado"}</small></div><label className="rule-input"><span>Máximo por sesión</span><input type="number" min="1" max="20" value={settings.max_pending_per_session} onChange={(event) => setSettings({ ...settings, max_pending_per_session: Number(event.target.value) })} /></label><label className="rule-input"><span>Inactividad (minutos)</span><input type="number" min="5" max="240" value={settings.session_idle_minutes} onChange={(event) => setSettings({ ...settings, session_idle_minutes: Number(event.target.value) })} /></label><button className="save-rules" type="submit">Guardar reglas</button></form></section><section className="admin-card provider-card" id="provider"><div className="card-heading"><div><p className="eyebrow">Integración oficial</p><h2>Spotify</h2></div><span className={`provider-state ${spotifyConnected ? "connected" : ""}`}><i /> {spotifyConnected ? "Conectado" : "Sin conectar"}</span></div><p>Autoriza el reproductor del local mediante OAuth. El secreto nunca llega al navegador.</p><button className="save-rules" onClick={() => void connectSpotify()}>{spotifyConnected ? "Reconectar Spotify" : "Conectar Spotify"} ↗</button>{spotifyConnected && <small className="player-device-state">{spotifyPlayerReady ? "Dispositivo del local listo" : "Preparando dispositivo..."}</small>}</section></div>
        {notice && <div className="admin-notice" role="status">{notice}</div>}
      </section>
    </div>
  </main>;
}