import { Suspense, useEffect, useMemo, useRef } from 'react';
import { Canvas, ThreeEvent, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, useGLTF } from '@react-three/drei';
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import type { Seat, View } from './types';

type SceneProps = {
  seats: Seat[];
  selectedId: string;
  view: View;
  onSelect: (id: string) => void;
  onMetrics: (metrics: { calls: number; triangles: number; fps: number }) => void;
};

const asset = (name: string) => `${import.meta.env.BASE_URL}assets/${name}`;

function CabinShell({ roofVisible }: { roofVisible: boolean }) {
  const gltf = useGLTF(asset('lime_cabin_shell.glb'));
  const shell = useMemo(() => {
    const fixed = new THREE.Group();
    fixed.name = 'Merged fixed cabin';
    const roof = new THREE.Group();
    roof.name = 'Merged roof and overhead bins';
    const result = new THREE.Group();
    result.add(fixed, roof);
    gltf.scene.updateMatrixWorld(true);

    const groups = new Map<string, {
      material: THREE.Material;
      roof: boolean;
      geometries: THREE.BufferGeometry[];
    }>();
    gltf.scene.traverse((object) => {
      if (!(object instanceof THREE.Mesh) || object.name.startsWith('Seat_')) return;
      const material = Array.isArray(object.material) ? object.material[0] : object.material;
      const isRoof = /^(Roof|Bin|Light)/.test(object.name);
      const key = `${isRoof ? 'roof' : 'fixed'}:${material.uuid}`;
      if (!groups.has(key)) groups.set(key, { material, roof: isRoof, geometries: [] });
      groups.get(key)!.geometries.push(object.geometry.clone().applyMatrix4(object.matrixWorld));
    });

    groups.forEach(({ material, roof: isRoof, geometries }) => {
      const merged = mergeGeometries(geometries, false);
      const parent = isRoof ? roof : fixed;
      if (!merged) {
        geometries.forEach((geometry) => {
          const mesh = new THREE.Mesh(geometry, material);
          mesh.name = material.name;
          parent.add(mesh);
        });
        return;
      }
      geometries.forEach((geometry) => geometry.dispose());
      const mesh = new THREE.Mesh(merged, material);
      mesh.frustumCulled = false;
      mesh.name = material.name;
      parent.add(mesh);
    });
    roof.visible = roofVisible;
    return result;
  }, [gltf.scene]);

  useEffect(() => {
    const roof = shell.getObjectByName('Merged roof and overhead bins');
    if (roof) roof.visible = roofVisible;
  }, [shell, roofVisible]);

  useEffect(() => () => {
    shell.traverse((object) => {
      if (object instanceof THREE.Mesh) object.geometry.dispose();
    });
  }, [shell]);

  return <primitive object={shell} />;
}

type SeatBatch = {
  key: string;
  mesh: THREE.InstancedMesh;
  seatIds: string[];
};

function SeatInstances({ seats, selectedId, onSelect }: Pick<SceneProps, 'seats' | 'selectedId' | 'onSelect'>) {
  const gltf = useGLTF(asset('lime_airline_seat.glb'));
  const batches = useMemo(() => {
    gltf.scene.updateMatrixWorld(true);
    const parts: THREE.Mesh[] = [];
    gltf.scene.traverse((object) => {
      if (object instanceof THREE.Mesh) parts.push(object);
    });

    const available = seats.filter((seat) => seat.available);
    const occupied = seats.filter((seat) => !seat.available);
    const translation = new THREE.Matrix4();
    const transform = new THREE.Matrix4();
    const result: SeatBatch[] = [];

    for (const part of parts) {
      const sourceMaterial = Array.isArray(part.material) ? part.material[0] : part.material;
      for (const [status, list] of [
        ['available', available],
        ['occupied', occupied],
      ] as const) {
        if (!list.length) continue;
        const material = sourceMaterial.clone();
        const isFabric = /lime|upholster|cushion|stitch/i.test(part.name + ' ' + sourceMaterial.name);
        if (status === 'occupied' && isFabric) {
          if (material instanceof THREE.MeshStandardMaterial) {
            material.map = null;
            material.color.set('#aab4a9');
            material.roughness = 0.94;
          }
        }
        const mesh = new THREE.InstancedMesh(part.geometry, material, list.length);
        mesh.name = `${part.name} / ${status}`;
        mesh.instanceMatrix.setUsage(THREE.StaticDrawUsage);
        mesh.frustumCulled = false;
        list.forEach((seat, index) => {
          translation.makeTranslation(seat.x, seat.y, seat.z);
          transform.multiplyMatrices(translation, part.matrixWorld);
          mesh.setMatrixAt(index, transform);
        });
        mesh.instanceMatrix.needsUpdate = true;
        result.push({
          key: `${part.name}-${status}`,
          mesh,
          seatIds: list.map((seat) => seat.id),
        });
      }
    }
    return result;
  }, [gltf.scene, seats]);

  // The regular seats stay instanced. Only the two upholstery pieces of the
  // selected seat are drawn again with a brighter, emissive finish.
  const selectedUpholstery = useMemo(() => {
    const group = new THREE.Group();
    gltf.scene.updateMatrixWorld(true);
    gltf.scene.traverse((object) => {
      if (!(object instanceof THREE.Mesh) || !/lime.*upholstered/i.test(object.name)) return;
      const sourceMaterial = Array.isArray(object.material) ? object.material[0] : object.material;
      if (!(sourceMaterial instanceof THREE.MeshStandardMaterial)) return;
      const material = sourceMaterial.clone();
      material.map = null;
      material.color.set('#c8ed39');
      material.emissive.set('#83bf12');
      material.emissiveIntensity = 0.25;
      material.roughness = 0.64;
      material.polygonOffset = true;
      material.polygonOffsetFactor = -2;
      material.polygonOffsetUnits = -2;
      const mesh = new THREE.Mesh(object.geometry, material);
      mesh.matrix.copy(object.matrixWorld);
      mesh.matrixAutoUpdate = false;
      mesh.renderOrder = 1;
      group.add(mesh);
    });
    return group;
  }, [gltf.scene]);

  useEffect(() => () => {
    for (const batch of batches) {
      batch.mesh.dispose();
      (batch.mesh.material as THREE.Material).dispose();
    }
  }, [batches]);

  useEffect(() => () => {
    selectedUpholstery.traverse((object) => {
      if (object instanceof THREE.Mesh) (object.material as THREE.Material).dispose();
    });
  }, [selectedUpholstery]);

  const selected = seats.find((seat) => seat.id === selectedId);

  function select(event: ThreeEvent<MouseEvent>, batch: SeatBatch) {
    event.stopPropagation();
    if (event.instanceId === undefined) return;
    const id = batch.seatIds[event.instanceId];
    if (seats.find((seat) => seat.id === id)?.available) onSelect(id);
  }

  return (
    <>
      {batches.map((batch) => (
        <primitive
          key={batch.key}
          object={batch.mesh}
          onClick={(event: ThreeEvent<MouseEvent>) => select(event, batch)}
          onPointerOver={(event: ThreeEvent<PointerEvent>) => {
            if (event.instanceId !== undefined && batch.seatIds[event.instanceId]) {
              document.body.style.cursor = 'pointer';
            }
          }}
          onPointerOut={() => { document.body.style.cursor = ''; }}
        />
      ))}
      {selected && (
        <>
          <primitive object={selectedUpholstery} position={[selected.x, selected.y, selected.z]} />
          <group position={[selected.x, 0.055, selected.z]}>
            <mesh rotation={[-Math.PI / 2, 0, 0]}>
              <ringGeometry args={[0.40, 0.46, 36]} />
              <meshBasicMaterial color="#b7ff63" transparent opacity={0.95} depthWrite={false} />
            </mesh>
            <pointLight color="#adff57" intensity={2.2} distance={1.7} />
          </group>
        </>
      )}
    </>
  );
}

type Flight = {
  start: number;
  duration: number;
  from: THREE.Vector3;
  to: THREE.Vector3;
  lookFrom: THREE.Vector3;
  lookTo: THREE.Vector3;
};

// Keep manually controlled views inside the cabin, with a little clearance
// from the walls, ceiling, and end panels. The overview is intentionally above it.
const cabinCameraBounds = {
  x: [-1.65, 1.65],
  y: [0.65, 2.0],
  z: [-6.9, 6.9],
} as const;

const maxZoomOut: Record<View, number> = {
  explore: 12.05,
  overview: 10.5,
  inspect: 2.25,
  sit: 2.68,
  walk: 2.25,
};

function CameraDirector({ view, selected, onMetrics }: {
  view: View;
  selected: Seat;
  onMetrics: SceneProps['onMetrics'];
}) {
  const { camera, gl } = useThree();
  const controls = useRef<{ target: THREE.Vector3; update: () => void; enabled: boolean } | null>(null);
  const flight = useRef<Flight | null>(null);
  const walkStage = useRef(0);
  const metricAt = useRef(0);
  const frames = useRef(0);
  const lastFpsAt = useRef(0);

  useEffect(() => {
    if (!controls.current) return;
    const target = controls.current.target;
    let destination: THREE.Vector3;
    let look: THREE.Vector3;
    let duration = 1050;
    walkStage.current = 0;

    if (view === 'overview') {
      destination = new THREE.Vector3(0, 9.6, 3.0);
      look = new THREE.Vector3(0, .7, 0);
    } else if (view === 'inspect') {
      destination = new THREE.Vector3(selected.x < 0 ? -.15 : .15, 1.33, selected.z + .78);
      look = new THREE.Vector3(selected.x, .86, selected.z);
    } else if (view === 'sit') {
      destination = new THREE.Vector3(selected.x, 1.21, selected.z + .07);
      look = new THREE.Vector3(selected.x, 1.25, selected.z + 2.75);
    } else if (view === 'walk') {
      destination = new THREE.Vector3(0, 1.57, selected.z + 1.35);
      look = new THREE.Vector3(0, 1.43, selected.z - 1.2);
      duration = 1800;
      walkStage.current = 1;
    } else {
      destination = new THREE.Vector3(0, 1.62, 7.25);
      look = new THREE.Vector3(0, 1.35, -4.8);
    }
    flight.current = {
      start: performance.now(),
      duration,
      from: camera.position.clone(),
      to: destination,
      lookFrom: target.clone(),
      lookTo: look,
    };
    controls.current.enabled = false;
  }, [camera, view, selected.id, selected.x, selected.z]);

  useFrame((_, delta) => {
    const now = performance.now();
    if (flight.current && controls.current) {
      const f = flight.current;
      const progress = Math.min(1, (now - f.start) / f.duration);
      const ease = 1 - (1 - progress) ** 3;
      camera.position.lerpVectors(f.from, f.to, ease);
      controls.current.target.lerpVectors(f.lookFrom, f.lookTo, ease);
      if (progress === 1) {
        flight.current = null;
        controls.current.enabled = true;
        if (view === 'walk' && walkStage.current === 1) {
          walkStage.current = 2;
          flight.current = {
            start: now,
            duration: 780,
            from: camera.position.clone(),
            to: new THREE.Vector3(selected.x < 0 ? -.18 : .18, 1.35, selected.z + .72),
            lookFrom: controls.current.target.clone(),
            lookTo: new THREE.Vector3(selected.x, .91, selected.z),
          };
          controls.current.enabled = false;
        }
      }
      controls.current.update();
    }
    frames.current += 1;
    if (!lastFpsAt.current) lastFpsAt.current = now;
    if (now - metricAt.current > 1400) {
      const elapsed = now - lastFpsAt.current;
      const fps = elapsed > 0 ? Math.round((frames.current * 1000) / elapsed) : 0;
      onMetrics({
        calls: gl.info.render.calls,
        triangles: gl.info.render.triangles,
        fps: Math.min(fps, 120),
      });
      frames.current = 0;
      lastFpsAt.current = now;
      metricAt.current = now;
    }
    void delta;
  });

  return (
    <OrbitControls
      ref={(value) => { controls.current = value; }}
      makeDefault
      enableDamping
      dampingFactor={0.065}
      minDistance={0.3}
      maxDistance={22}
      maxPolarAngle={Math.PI * 0.88}
      target={[0, 1.35, -4.8]}
      onChange={() => {
        if (flight.current || !controls.current) return;
        const offset = camera.position.clone().sub(controls.current.target);
        if (offset.length() > maxZoomOut[view]) {
          camera.position.copy(controls.current.target).add(offset.setLength(maxZoomOut[view]));
        }
        if (view === 'overview') return;
        camera.position.set(
          THREE.MathUtils.clamp(camera.position.x, ...cabinCameraBounds.x),
          THREE.MathUtils.clamp(camera.position.y, ...cabinCameraBounds.y),
          THREE.MathUtils.clamp(camera.position.z, ...cabinCameraBounds.z),
        );
      }}
    />
  );
}

function Experience({ seats, selectedId, view, onSelect, onMetrics }: SceneProps) {
  const selected = seats.find((seat) => seat.id === selectedId) ?? seats[0];
  return (
    <>
      <color attach="background" args={['#e9f3e7']} />
      <fog attach="fog" args={['#eef5ea', 16, 36]} />
      <ambientLight intensity={0.45} color="#f6ffe9" />
      <hemisphereLight args={['#fffdea', '#8eb47b', 0.9]} />
      <directionalLight position={[-4, 7, 6]} intensity={1.35} color="#fffde7" />
      <pointLight position={[-1.7, 2.2, 0]} color="#d3ffae" intensity={4.5} distance={11} />
      <pointLight position={[1.7, 2.2, 0]} color="#d3ffae" intensity={4.5} distance={11} />
      <CabinShell roofVisible={view !== 'overview'} />
      <SeatInstances seats={seats} selectedId={selectedId} onSelect={onSelect} />
      <CameraDirector view={view} selected={selected} onMetrics={onMetrics} />
    </>
  );
}

export default function CabinScene(props: SceneProps) {
  return (
    <Canvas
      camera={{ position: [0, 1.62, 7.25], fov: 62, near: 0.06, far: 80 }}
      dpr={[1, 1.65]}
      gl={{ antialias: true, powerPreference: 'high-performance' }}
      onPointerMissed={() => { document.body.style.cursor = ''; }}
    >
      <Suspense fallback={null}>
        <Experience {...props} />
      </Suspense>
    </Canvas>
  );
}

useGLTF.preload(asset('lime_airline_seat.glb'));
useGLTF.preload(asset('lime_cabin_shell.glb'));
