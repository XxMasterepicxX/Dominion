# Dominion Frontend

The Dominion frontend uses [Vite](https://vitejs.dev/) with React and TypeScript for development and build tooling.

## Scripts

- `npm run dev` – start the Vite development server with hot module replacement.
- `npm run build` – run TypeScript type-checking before emitting the production bundle to `dist/`.
- `npm run preview` – serve the production build locally for smoke testing.
- `npm test` – execute the Vitest test suite (jsdom environment + Testing Library).

## Project Notes

- Static assets in `public/` are copied to the site root and can be referenced with absolute paths such as `/favicon.ico`.
- Global DOM matchers come from `@testing-library/jest-dom/vitest` and are initialised in `src/setupTests.ts`.
- The application entry point is `src/main.tsx`, mounted via the `#root` element declared in `index.html`.
