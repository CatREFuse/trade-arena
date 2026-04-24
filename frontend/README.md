# Nuxt Minimal Starter

Look at the [Nuxt documentation](https://nuxt.com/docs/getting-started/introduction) to learn more.

## Setup

Make sure to install dependencies:

```bash
# npm
npm install

# pnpm
pnpm install

# yarn
yarn install

# bun
bun install
```

Admin console credentials can be configured through environment variables:

```bash
NUXT_ADMIN_USERNAME=admin
NUXT_ADMIN_PASSWORD=replace-with-strong-password
NUXT_ADMIN_SESSION_SALT=replace-with-random-salt
NUXT_ADMIN_BACKEND_API_KEY=replace-with-backend-admin-key
NUXT_ADMIN_COOKIE_SECURE=false
```

Production runtime does not use development admin defaults. Configure the admin credentials explicitly; `NUXT_ADMIN_BACKEND_API_KEY` must match the backend `ADMIN_API_KEY`.

Admin console login session does not set `maxAge`; it remains valid until logout, credential/salt change, or browser policy cleanup.

## Development Server

Start the development server on `http://localhost:3000`:

```bash
# npm
npm run dev

# pnpm
pnpm dev

# yarn
yarn dev

# bun
bun run dev
```

## Production

Build the application for production:

```bash
# npm
npm run build

# pnpm
pnpm build

# yarn
yarn build

# bun
bun run build
```

Locally preview production build:

```bash
# npm
npm run preview

# pnpm
pnpm preview

# yarn
yarn preview

# bun
bun run preview
```

Production runtime:

```bash
# npm
npm run build
npm run start
```

Do not run `.nuxt/dist/server/server.mjs` directly in production. The supported production entry is `.output/server/index.mjs`.

Check out the [deployment documentation](https://nuxt.com/docs/getting-started/deployment) for more information.
