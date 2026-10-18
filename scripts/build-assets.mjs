import { resolve } from 'node:path';
import { NodeIO } from '@gltf-transform/core';
import { prune, simplify, weld } from '@gltf-transform/functions';
import { MeshoptSimplifier } from 'meshoptimizer';

const root = resolve(import.meta.dirname, '..');
const io = new NodeIO();
await MeshoptSimplifier.ready;

const seatSource = resolve(root, 'source-assets/lime_airline_seat.glb');
const seatOutput = resolve(root, 'public/assets/lime_airline_seat.glb');
const seat = await io.read(seatSource);
await seat.transform(
  weld(),
  simplify({ simplifier: MeshoptSimplifier, ratio: 0.55, error: 0.001 }),
);
await io.write(seatOutput, seat);

const cabinSource = resolve(root, 'source-assets/lime_cabin_full.glb');
const cabinOutput = resolve(root, 'public/assets/lime_cabin_shell.glb');
const cabin = await io.read(cabinSource);
const nodes = cabin.getRoot().listNodes();
let removed = 0;
for (const node of nodes) {
  if (node.getName().startsWith('Seat_')) {
    node.dispose();
    removed += 1;
  }
}
await cabin.transform(prune());
await io.write(cabinOutput, cabin);

console.log(`Seat asset: ${seat.getRoot().listMeshes().length} meshes → ${seatOutput}`);
console.log(`Cabin shell: removed ${removed} duplicated seat nodes → ${cabinOutput}`);
