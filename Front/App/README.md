# Medusa Granizados - Frontend

Frontend mobile-first para la experiencia musical de los clientes. Esta aplicación está preparada para desplegarse como Worker estático en **Cloudflare**, con el backend FastAPI desplegado por separado.

## Desarrollo local

Copia `.env.example` como `.env.local` y completa la publishable key de Supabase:

```powershell
Copy-Item .env.example .env.local
npm run dev
```

Abre <http://localhost:3000>.

## Cloudflare Workers

Crea un Worker conectado al repositorio y utiliza esta configuración:

| Ajuste | Valor |
| --- | --- |
| Root directory | `Front/App` |
| Build command | `npm run build` |
| Deploy command | `npx wrangler deploy --config wrangler.jsonc` |
| Node.js version | `22` |

El `wrangler.jsonc` del proyecto publica la carpeta `out` como assets estáticos. En el panel de Cloudflare selecciona **Framework preset: None** si aparece esa opción. En **Settings > Environment variables** configura, tanto para Preview como para Production:

```env
NEXT_PUBLIC_SUPABASE_URL=https://cpgnabqabuuebkjizykt.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=tu-clave-publicable
NEXT_PUBLIC_API_URL=https://tu-backend.example.com
```

El `output: "export"` de `next.config.ts` genera la carpeta `out`, que Wrangler publica como assets estáticos. No se utiliza Vercel ni se necesita un servidor Node para el frontend en producción.

La publishable key puede estar disponible en el navegador. Nunca configures una clave `service_role` en variables `NEXT_PUBLIC_*`.

El acceso administrativo usa Supabase Auth con `signInWithPassword`; la cuenta debe existir también en la tabla `admin_users` del backend para poder controlar el reproductor y las sesiones.

El botón de Spotify inicia OAuth en el backend. Registra exactamente este Redirect URI en Spotify Developer Dashboard durante el desarrollo local:

```text
http://localhost:8000/api/admin/spotify/callback
```

## Comandos

```powershell
npm run lint
npm run build
npm run deploy
```
