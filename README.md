# Lime Cabin

An interactive airline seat selection prototype built from the supplied 3D asset archives. It uses a real aircraft cabin mesh and a reusable polygonal seat model. The web app is React, TypeScript, React Three Fiber, Drei, Three.js, and Vite.

**Live demo:** https://tomiabe.github.io/cabin/

To view the included build without installing anything, run python3 run_preview.py. It starts a local server on an available port and opens the prototype in your browser. Stop it with Ctrl+C.

## Run locally

~~~bash
npm install
npm run dev
~~~

Open the Local URL printed by Vite. To build a static version:

~~~bash
npm run build
npm run preview
~~~

The static output is in dist/. The app needs an HTTP server because browser security rules usually block local GLB fetches from file://.

## What works

- 48 selectable 3D seats in a 12 row, 2+2 demonstration cabin.
- One shared seat manifest for the 2D map, 3D picks, prices, and occupied states.
- Explore, overhead overview, close inspection, seated passenger view, and a guided aisle approach.
- Occupied seats are disabled in both the map and 3D selection.
- A local choice confirmation and an optional performance panel.
- Responsive layout and keyboard accessible 2D seat selection.

The flight route, prices, inventory, and confirmation are demonstration data. No booking or reservation is created.

## Asset pipeline

source-assets/ contains the original seat and cabin GLBs and the Python builders provided in the input archives. public/assets/ contains the browser assets:

- lime_airline_seat.glb: a conservative simplification of the master chair, preserving its 22 named components and materials. It has 8,474 triangles compared with 15,012 in the input.
- lime_cabin_shell.glb: the cabin with the 1,056 duplicate seat component nodes removed. The source cabin is 991 KB; the shell is about 211 KB.
- seat_positions.json: seat IDs, coordinates, prices, and sample availability.

Regenerate both browser GLBs with:

~~~bash
npm run assets:build
~~~

The asset build uses glTF Transform and meshoptimizer. It removes duplicated chairs from the cabin file and simplifies the master chair at a 55% target with a 0.1% mesh radius error cap. The web app renders the 22 chair parts in GPU instanced batches, with separate available and occupied materials. Static cabin pieces are merged at runtime by material while retaining a separate roof group for overview mode.

## Structure

- src/App.tsx: seat state, map, controls, and booking prototype UI.
- src/Scene.tsx: GLB loading, mesh batching, selection rays, and camera movement.
- src/types.ts: shared seat and view types.
- scripts/build-assets.mjs: repeatable browser asset preparation.
- public/assets/: optimized assets used by the app.
- source-assets/: original editable inputs.

## Verification and limits

The TypeScript and Vite production build passes. In a narrow local preview, the scene ran near 60 FPS, with about 59 draw calls and 412,000–417,000 visible triangles depending on the view. These measurements are from one machine and should be repeated on representative phones and laptops.

The 3D model remains a stylised reconstruction. It is less detailed than the original concept images, and its 2+2 layout is different from the larger cabin shown there. Dimensions and sight lines are illustrative. Before using real airline inventory, add a backend that owns price and availability, aircraft specific seat maps, and a reservation flow.
