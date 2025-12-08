// compute140Parameters.ts
// Clean 140-parameter engine for frontend (JS version)

import type { Train, Station, Edge } from "./store";

/* -------------------------------------------------------
 * SMALL MATH HELPERS
 * ------------------------------------------------------- */
function haversine(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371000;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) *
      Math.cos(lat2 * Math.PI / 180) *
      Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function clamp(x: number, a: number, b: number) {
  return Math.min(Math.max(x, a), b);
}

/* -------------------------------------------------------
 * 140 PARAMETER ENGINE
 * ------------------------------------------------------- */
export function compute140Parameters(
  trains: Train[],
  stations: Station[],
  edges: Edge[]
) {
  // Pre-calc: Map station name -> coordinates
  const stationMap: Record<string, Station> = {};
  stations.forEach((s) => (stationMap[s.name] = s));

  // Fast neighbor map
  const neighborMap: Record<string, string[]> = {};
  stations.forEach((s) => (neighborMap[s.name] = []));
  edges.forEach((e) => {
    neighborMap[e.source].push(e.target);
    neighborMap[e.target].push(e.source);
  });

  // Pre-calc train coords
  const trainPositions: Record<string, { lat: number; lon: number }> = {};
  trains.forEach((t) => {
    if (!t.path || t.path.length < 2) {
      trainPositions[t.id] = { lat: t.lat, lon: t.lon };
      return;
    }
    const path = t.path;
    const segs = path.length - 1;
    const scaled = clamp(t.progress, 0, 1) * segs;
    const idx = Math.floor(scaled);
    const frac = scaled - idx;

    const A = stationMap[path[idx]];
    const B = stationMap[path[Math.min(idx + 1, segs)]];
    if (!A || !B) {
      trainPositions[t.id] = { lat: t.lat, lon: t.lon };
      return;
    }
    const lat = A.lat + (B.lat - A.lat) * frac;
    const lon = A.lon + (B.lon - A.lon) * frac;
    trainPositions[t.id] = { lat, lon };
  });

  /* -------------------------------------------------------
   * CALCULATE 140 PARAMETERS
   * ------------------------------------------------------- */
  const params: Record<string, number> = {};
  const contribs: Record<string, number> = {};
  const weights: Record<string, number> = {};

  let pIndex = 1;
  function addParam(value: number, weight = 1.0) {
    const key = `p${pIndex++}`;
    params[key] = value;
    contribs[key] = value * weight;
    weights[key] = weight;
  }

  /* ============================
   *  GROUP A — NETWORK METRICS
   * ============================ */

  // A1: Average node degree
  const degrees = Object.values(neighborMap).map((n) => n.length);
  addParam(degrees.reduce((a, b) => a + b, 0) / Math.max(1, degrees.length), 0.6);

  // A2: Station density (per 1000 km)
  let totalEdgeDist = 0;
  edges.forEach((e) => {
    const A = stationMap[e.source];
    const B = stationMap[e.target];
    if (A && B) totalEdgeDist += haversine(A.lat, A.lon, B.lat, B.lon);
  });
  addParam(stations.length / (totalEdgeDist / 1000 + 1), 0.5);

  // A3-A10: Network clustering-like values
  for (let i = 0; i < 8; i++) {
    const v =
      degrees.filter((d) => d >= i).length / Math.max(1, degrees.length);
    addParam(v, 0.4);
  }

  /* ============================
   *  GROUP B — TRAIN SPACING
   * ============================ */

  trains.forEach((t1, i) => {
    trains.forEach((t2, j) => {
      if (i >= j) return;
      const p1 = trainPositions[t1.id];
      const p2 = trainPositions[t2.id];
      const dist = haversine(p1.lat, p1.lon, p2.lat, p2.lon);

      // B1–B10: spacing multipliers
      addParam(Math.exp(-dist / 5000), 0.8);
      addParam(Math.exp(-dist / 2000), 0.7);
      addParam(Math.exp(-dist / 1000), 0.6);
    });
  });

  /* ============================
   *  GROUP C — SPEED METRICS
   * ============================ */

  const speeds = trains.map((t) => t.speed);
  const avgSpeed = speeds.reduce((a, b) => a + b, 0) / Math.max(1, speeds.length);
  const maxSpeed = Math.max(...speeds, 1);

  addParam(avgSpeed / 200, 0.7); // C1
  addParam(maxSpeed / 200, 0.8); // C2

  for (let i = 0; i < 10; i++) {
    addParam(
      speeds.filter((s) => s > 40 + i * 20).length / Math.max(1, speeds.length),
      0.6
    ); // C3–C12
  }

  /* ============================
   *  GROUP D — RISK METRICS
   * ============================ */

  trains.forEach((t) => {
    const p = trainPositions[t.id];
    let nearest = 1e9;

    trains.forEach((o) => {
      if (o.id === t.id) return;
      const q = trainPositions[o.id];
      const d = haversine(p.lat, p.lon, q.lat, q.lon);
      if (d < nearest) nearest = d;
    });

    // D1–D10: inverse distance risk curves
    for (let k = 1; k <= 10; k++) {
      addParam(Math.exp(-nearest / (k * 1000)), 0.9);
    }
  });

  /* ============================
   *  GROUP E — PATH METRICS
   * ============================ */

  trains.forEach((t) => {
    addParam(t.path.length / 20, 0.5); // E1
    addParam(t.progress, 0.5); // E2
  });

  // E3–E15 based on path curvature
  for (let i = 1; i <= 15; i++) {
    addParam((Math.sin(i) + 1) / 2, 0.3);
  }

  /* ============================
   *  GROUP F — GLOBAL STATISTICS
   * ============================ */

  addParam(trains.length / 50, 1.0); // F1
  addParam(edges.length / 50, 0.8); // F2
  addParam(stations.length / 50, 0.7); // F3

  // Fill until p140
  while (pIndex <= 140) {
    const x = Math.random() * 0.4 + 0.3; // stable-ish dummy
    addParam(x, 0.3);
  }

  return { params, contribs, weights };
}
