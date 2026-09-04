# Noty App — PWA pro zpěváky

PWA pro práci s notami v PDF formátu: prohlížení, anotace, setlisty.
Stejný stack jako CFSB (Vue 3 + Vite + vite-plugin-pwa + Firebase Hosting).

## Vývoj

```bash
npm install
npm run dev
```

## Build + preview

```bash
npm run build
npm run preview
```

## Deploy

```bash
firebase deploy --only hosting
```

## Sítě & větve

Pushují se POUZE `test/*` větve. Nikdy ne do `main`/`production`.
