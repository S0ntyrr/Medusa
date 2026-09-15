# Medusa Granizados

MVP de música interactiva para clientes dentro del establecimiento. El cliente entra mediante QR/NFC sin crear una cuenta; el negocio controla la cola desde un panel administrativo.

## Estado actual

- Frontend Next.js + TypeScript + Tailwind en `Front/App`, preparado para Cloudflare Workers mediante exportación estática y Wrangler.
- Backend FastAPI en `Back/App` con configuración por entorno y endpoint de salud.
- Cliente Supabase preparado en `Front/App/lib/supabase.ts`.
- Esquema PostgreSQL inicial en `Back/App/schema.sql` para venues, sesiones, canciones, cola y votos.

## Configuración local

1. Copia `Front/App/.env.example` a `Front/App/.env.local` y completa la URL de Supabase y la publishable key desde el dashboard de Supabase.
2. Copia `Back/App/.env.example` a `Back/App/.env` y completa `DATABASE_URL` y `SECRET_KEY`.
3. Ejecuta `Back/App/schema.sql` desde el SQL Editor de Supabase.

La publishable key puede exponerse al navegador con el prefijo `NEXT_PUBLIC_`, pero nunca uses aquí una `service_role` key. La clave compartida en el chat no se ha guardado en ningún archivo.

## Arranque

```powershell
cd Front/App
npm run dev
```

```powershell
cd Back/App
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Despliegue

El frontend no se despliega en Vercel. En Cloudflare Workers usa `Front/App` como directorio raíz, `npm run build` como comando de compilación y `npx wrangler deploy` como comando de despliegue. El backend FastAPI se desplegará de forma independiente en un proveedor cloud compatible con Python.

La autenticación administrativa utiliza Supabase Auth. Crea el usuario desde **Authentication → Users** y vincúlalo a `admin_users` con su UUID; ya no se usan `ADMIN_EMAIL` ni `ADMIN_PASSWORD` en el backend.

Spotify se conecta desde el panel mediante OAuth Authorization Code. Configura en `Back/App/.env` el Client ID, Client Secret y Redirect URI creados en el dashboard de Spotify. El `client_secret` y los tokens se quedan en el backend y los tokens se almacenan cifrados. El Web Playback SDK requiere una cuenta Premium y autorización de Spotify para el uso previsto; no debe considerarse automáticamente una solución de reproducción comercial para el establecimiento.

### URLs de Spotify y del despliegue

Debes manejar tres URLs distintas:

```env
# Frontend publicado en Cloudflare
FRONTEND_URL=https://TU-FRONTEND.workers.dev

# Backend publicado en Render
NEXT_PUBLIC_API_URL=https://medusa-api-hytt.onrender.com

# Callback OAuth del backend
SPOTIFY_REDIRECT_URI=https://medusa-api-hytt.onrender.com/api/admin/spotify/callback
```

En desarrollo local utiliza:

```env
# Back/App/.env
FRONTEND_URL=http://localhost:3000
ALLOWED_ORIGINS=http://localhost:3000
SPOTIFY_REDIRECT_URI=http://localhost:8000/api/admin/spotify/callback

# Front/App/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Para conectar Spotify:

1. Entra en [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) y crea una aplicación.
2. Copia el `Client ID` y el `Client Secret` solamente a las variables del backend. Nunca al frontend.
3. En **Edit Settings → Redirect URIs**, registra exactamente la URL de `SPOTIFY_REDIRECT_URI` que vayas a utilizar. Spotify distingue entre `localhost` y producción.
4. En Render crea las variables `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI`, `FRONTEND_URL` y `ALLOWED_ORIGINS`.
5. En el frontend configura `NEXT_PUBLIC_API_URL` con la URL de Render y vuelve a ejecutar el build/deploy.
6. Crea el usuario administrador en Supabase Auth, vincúlalo en `admin_users`, inicia sesión en `/admin` y pulsa **Conectar Spotify**.

Si el botón muestra `Spotify OAuth is not configured`, faltan el Client ID o el Client Secret en el backend. Si Spotify rechaza la autorización, revisa que el Redirect URI coincida carácter por carácter.

## Bloques completados

- Sesiones anónimas temporales con heartbeat y expiración por establecimiento.
- Cola con votos, cooldown, máximo por sesión, límite de artista y score por prioridad.
- Panel admin protegido por Supabase Auth, gestión de sesiones, reglas y bloqueos.
- Spotify OAuth, refresh de tokens cifrados, Web API y preparación del Web Playback SDK.
- Estadísticas protegidas y actualización de cola mediante Supabase Realtime.
- RLS activado en las tablas de aplicación; las mutaciones pasan por FastAPI.

## Desplegar el backend

El archivo `render.yaml` y `Back/App/Dockerfile` dejan preparado un despliegue de FastAPI en Render. Crea un Web Service desde el repositorio y configura las variables marcadas como `sync: false`. Cuando Render entregue la URL pública:

```env
NEXT_PUBLIC_API_URL=https://medusa-api.onrender.com
```

En el backend configura `ALLOWED_ORIGINS` con la URL de Cloudflare y `FRONTEND_URL` con la misma URL usada por OAuth/redirecciones. Después vuelve a desplegar el frontend para incorporar `NEXT_PUBLIC_API_URL`.

```sql
insert into admin_users (venue_id, email, provider_user_id)
select id, 'TU_EMAIL', 'UUID_DEL_USUARIO_EN_AUTH'
from venues
where slug = 'medusa-granizados';
```