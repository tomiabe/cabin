import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import type { Seat, SeatManifest, View } from './types';

const base = import.meta.env.BASE_URL;
const CabinScene = lazy(() => import('./Scene'));
const rowLabels = ['A', 'B', 'C', 'D'] as const;

function seatLabel(seat: Seat) {
  return seat.type === 'window' ? 'Window seat' : 'Aisle seat';
}

function SeatMap({ seats, selectedId, onSelect }: {
  seats: Seat[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  const rows = useMemo(() => {
    const grouped = new Map<number, Seat[]>();
    seats.forEach((seat) => {
      if (!grouped.has(seat.row)) grouped.set(seat.row, []);
      grouped.get(seat.row)!.push(seat);
    });
    return [...grouped.entries()].sort((a, b) => a[0] - b[0]);
  }, [seats]);

  return (
    <div className="map-wrap">
      <div className="map-front">FRONT OF AIRCRAFT</div>
      <div className="map-labels"><span></span>{rowLabels.map((label) => <span key={label}>{label}</span>)}</div>
      <div className="map-rows">
        {rows.map(([row, rowSeats]) => (
          <div className="map-row" key={row}>
            <span className="row-number">{row}</span>
            {rowSeats.map((seat) => (
              <button
                key={seat.id}
                className={`map-seat ${seat.available ? 'available' : 'occupied'} ${seat.id === selectedId ? 'selected' : ''}`}
                disabled={!seat.available}
                onClick={() => onSelect(seat.id)}
                aria-label={`${seat.id}, ${seatLabel(seat)}, ${seat.available ? `available, ${seat.price} dollars` : 'occupied'}`}
                aria-pressed={seat.id === selectedId}
                title={`${seat.id} · ${seat.available ? seatLabel(seat) : 'Occupied'}`}
              >
                {seat.column}
              </button>
            ))}
          </div>
        ))}
      </div>
      <div className="map-rear">REAR OF AIRCRAFT</div>
    </div>
  );
}

function App() {
  const [manifest, setManifest] = useState<SeatManifest | null>(null);
  const [loadError, setLoadError] = useState('');
  const [selectedId, setSelectedId] = useState('14A');
  const [view, setView] = useState<View>('explore');
  const [chosenId, setChosenId] = useState<string | null>(null);
  const [metrics, setMetrics] = useState({ calls: 0, triangles: 0, fps: 0 });
  const [showMetrics, setShowMetrics] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${base}assets/seat_positions.json`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Seat data failed to load (${response.status})`);
        return response.json() as Promise<SeatManifest>;
      })
      .then((data) => {
        if (!Array.isArray(data.seats) || data.seats.length !== 48) {
          throw new Error('Seat data is incomplete');
        }
        setManifest(data);
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return;
        setLoadError(error instanceof Error ? error.message : 'Unable to load the cabin');
      });
    return () => controller.abort();
  }, []);

  const selected = manifest?.seats.find((seat) => seat.id === selectedId) ?? null;
  const availableCount = manifest?.seats.filter((seat) => seat.available).length ?? 0;

  function selectSeat(id: string) {
    const seat = manifest?.seats.find((item) => item.id === id);
    if (!seat?.available) return;
    setSelectedId(id);
    setChosenId(null);
    setView('inspect');
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-symbol" aria-hidden="true"><i /><i /><i /></span>
          <span>LIME<span className="brand-light">CABIN</span></span>
          <small>SPATIAL SEAT SELECTOR</small>
        </div>
        <div className="route">
          <span className="route-code">SYD</span>
          <span className="route-line"><i /> <span>CL 420 · 4h 55m</span> <i /></span>
          <span className="route-code">PER</span>
        </div>
        <div className="top-meta"><span>ECONOMY · 2+2</span><span className="live-dot" /> DEMO FLIGHT</div>
      </header>

      <div className="workspace">
        <section className="viewer" aria-label="3D cabin view" data-view={view}>
          {manifest ? (
            <Suspense fallback={<div className="scene-loading">Loading the 3D cabin…</div>}>
              <CabinScene
                seats={manifest.seats}
                selectedId={selectedId}
                view={view}
                onSelect={selectSeat}
                onMetrics={setMetrics}
              />
            </Suspense>
          ) : (
            <div className="scene-loading">{loadError || 'Preparing your cabin…'}</div>
          )}
          <div className="viewer-top">
            <div className="scene-badge"><span className="spark" /> LIVE 3D CABIN</div>
            <button className="metrics-toggle" onClick={() => setShowMetrics((show) => !show)} aria-pressed={showMetrics}>
              {showMetrics ? 'Hide performance' : 'Performance'}
            </button>
          </div>
          <div className="viewer-title">
            <span className="kicker">THE CABIN, BEFORE THE JOURNEY</span>
            <h1>See your seat.<br /><em>Before you fly.</em></h1>
            <p>Choose a place in the cabin, then step inside it.</p>
          </div>
          <div className="camera-bar" role="group" aria-label="Camera views">
            {([
              ['explore', 'Explore'],
              ['overview', 'Overview'],
              ['inspect', 'Inspect'],
              ['sit', 'Passenger POV'],
              ['walk', 'Walk there'],
            ] as const).map(([id, label]) => (
              <button key={id} className={view === id ? 'active' : ''} onClick={() => setView(id)} aria-pressed={view === id}>
                {label}
              </button>
            ))}
          </div>
          <div className="canvas-hint">DRAG TO LOOK · SCROLL TO ZOOM · CLICK A SEAT</div>
          {showMetrics && <div className="metrics"><b>{metrics.fps} FPS</b><span>{metrics.calls} draw calls</span><span>{metrics.triangles.toLocaleString()} triangles</span></div>}
        </section>

        <aside className="sidebar" aria-label="Seat selection">
          <div className="sidebar-heading">
            <div>
              <span className="kicker">YOUR PLACE ON BOARD</span>
              <h2>Choose your seat</h2>
            </div>
            <span className="seat-count">{availableCount} open</span>
          </div>
          <p className="sidebar-copy">Pick any green seat. The 3D view and map stay in sync as you explore.</p>
          {manifest && <SeatMap seats={manifest.seats} selectedId={selectedId} onSelect={selectSeat} />}
          <div className="legend"><span><i className="available-dot" /> Available</span><span><i className="selected-dot" /> Selected</span><span><i className="occupied-dot" /> Taken</span></div>

          {selected && (
            <div className="selection-panel">
              <div className="selection-head">
                <div><span className="kicker">YOUR SELECTION</span><strong>{selected.id}</strong></div>
                <span className="type-pill">{seatLabel(selected)}</span>
              </div>
              <div className="seat-details">
                <div><span>Position</span><strong>{selected.type === 'window' ? 'By the window' : 'Beside the aisle'}</strong></div>
                <div><span>Legroom</span><strong>{selected.legroom}</strong></div>
                <div><span>Seat price</span><strong>+${selected.price}</strong></div>
              </div>
              <div className="seat-actions">
                <button className="quiet-action" onClick={() => setView('inspect')}>Inspect in 3D ↗</button>
                <button className="quiet-action" onClick={() => setView('sit')}>Sit here ↗</button>
              </div>
              <button className="confirm" onClick={() => setChosenId(selected.id)}>
                {chosenId === selected.id ? `Seat ${selected.id} chosen ✓` : `Choose seat ${selected.id} →`}
              </button>
              <p className="demo-note">Prototype selection only. No reservation is created.</p>
            </div>
          )}
        </aside>
      </div>
    </main>
  );
}

export default App;
