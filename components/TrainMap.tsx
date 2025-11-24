// app/components/TrainMap.tsx
// Full corrected TrainMap component (TypeScript + React + MapLibre + Zustand store compatibility)

/// <reference types="react" />

 
"use client";

import type { Feature, LineString } from "geojson";
import React, { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useRailwayStore } from "../lib/store";


/** --- Helpful local TS types (don't need to exactly match store) --- */
interface Station { name: string; lat: number; lon: number; }
interface Edge { source: string; target: string; }
interface TrainLike {
  id: string;
  name: string;
  path?: string[]; // optional — computed by store on addTrain
  progress: number;
  speed: number;
  status?: string;
  // store has source/destination fields but we don't need them here
  // we'll not mutate lat/lon in store; markers manage visual positions locally
}

/** --- Config --- */
const MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
const AURA_RADIUS_PX = 30;
const ANIMATION_STYLES = `
.train-marker-container { width: 36px; height: 36px; display:flex;align-items:center;justify-content:center; pointer-events: none; }
.train-core {
  width: 16px; height: 16px; border-radius: 50%;
  background: linear-gradient(135deg,#ff4d94 0%, #ff0055 100%);
  box-shadow: 0 0 14px #ff4d94, 0 0 6px #ff0055 inset;
  transform-origin: center;
}
.train-core.jitter { animation: jitter 600ms infinite; }

@keyframes jitter {
  0% { transform: translateY(0) rotate(0deg); }
  25% { transform: translateY(-1px) rotate(-1deg); }
  50% { transform: translateY(1px) rotate(0.5deg); }
  75% { transform: translateY(-1px) rotate(1deg); }
  100% { transform: translateY(0) rotate(0deg); }
}

/* aura elements (visual only, sized in px using transform on marker element) */
.aura {
  position: absolute;
  width: ${AURA_RADIUS_PX * 2}px;
  height: ${AURA_RADIUS_PX * 2}px;
  border-radius: 50%;
  background: radial-gradient(circle at 50% 50%, rgba(255,0,85,0.18), rgba(255,0,85,0.06) 40%, transparent 60%);
  pointer-events: none;
  transform: translate(-50%, -50%);
}
.station-marker { width: 12px; height: 12px; background: #fff; border-radius: 50%; border:2px solid #111; box-shadow:0 0 6px #00ffcc; cursor: pointer; }
`;

/** --- Utility functions --- */
function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function getStationByName(name: string | undefined, stations: Station[]) {
  if (!name) return undefined;
  return stations.find((s) => s.name === name);
}

/** Compute lat/lon for a train based on its path and progress (pure, does NOT mutate store) */
function getTrainLatLon(train: TrainLike, stations: Station[]) {
  const path = (train.path ?? []).slice();
  const coords = path.map((n) => getStationByName(n, stations)).filter(Boolean) as Station[];
  if (coords.length === 0) {
    return { lat: 0, lon: 0 };
  }
  if (coords.length === 1) {
    return { lat: coords[0].lat, lon: coords[0].lon };
  }
  const segments = coords.length - 1;
  const scaled = Math.min(Math.max(train.progress ?? 0, 0), 1) * segments;
  const segIndex = Math.floor(Math.min(scaled, segments - 1));
  const t = scaled - segIndex;
  const A = coords[segIndex];
  const B = coords[Math.min(segIndex + 1, coords.length - 1)];
  if (!A || !B) return { lat: coords[coords.length - 1].lat, lon: coords[coords.length - 1].lon };
  return { lat: lerp(A.lat, B.lat, t), lon: lerp(A.lon, B.lon, t) };
}

/** --- React component --- */
export default function TrainMap(): React.JSX.Element {
  const mapRef = useRef<maplibregl.Map | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const markersRef = useRef<Record<string, maplibregl.Marker>>({});
  const animationRef = useRef<number | null>(null);
  const rafRunningRef = useRef(false);

  // Zustand actions & slices
  const stations = useRailwayStore((s) => s.stations);
  const edges = useRailwayStore((s) => s.edges);
  // We intentionally DO NOT subscribe to trains here via hook,
  // because animation loop reads latest via getState() to avoid re-registering the effect each frame.
  const addNode = useRailwayStore((s) => s.addNode);
  const addEdge = useRailwayStore((s) => s.addEdge);
  const addTrain = useRailwayStore((s) => s.addTrain);
  const updateTrainProgress = useRailwayStore((s) => s.updateTrainProgress);
  const updateTrainStatus = useRailwayStore((s) => s.updateTrainStatus);

  const [mapReady, setMapReady] = useState(false);

  // Inject CSS once
  useEffect(() => {
    const style = document.createElement("style");
    style.id = "train-map-styles";
    style.innerText = ANIMATION_STYLES;
    document.head.appendChild(style);
    return () => {
      document.head.removeChild(style);
    };
  }, []);

  // Initialize map once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: [77.4, 23.2],
      zoom: 5,
    });
    mapRef.current = map;

    map.on("load", () => {
      // tracks source + layer
      if (!map.getSource("tracks")) {
        map.addSource("tracks", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
        map.addLayer({
          id: "tracks-line",
          type: "line",
          source: "tracks",
          paint: { "line-color": "#00ffcc", "line-width": 3, "line-opacity": 0.7 },
        });
      }

      // aura source for visualization (we still use DOM markers for animated aura)
      if (!map.getSource("train-auras")) {
        map.addSource("train-auras", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
        map.addLayer({
          id: "train-auras-layer",
          type: "circle",
          source: "train-auras",
          paint: {
            "circle-radius": AURA_RADIUS_PX,
            "circle-color": "#ff0055aa",
            "circle-opacity": 0.12,
            "circle-stroke-width": 0,
            "circle-stroke-color": "#ff4d94",
          },
        });
      }

      // current segment highlight (optional)
      if (!map.getSource("current-segment")) {
        map.addSource("current-segment", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
        map.addLayer({
          id: "current-segment-line",
          type: "line",
          source: "current-segment",
          paint: { "line-color": "#ff77aa", "line-width": 5, "line-opacity": 0.9 },
        });
      }

      setMapReady(true);
      // initial tracks draw
      refreshTracksOnMap(map, edges, stations);
      // initial station DOM markers
      refreshStationMarkers(map, stations);
    });

    // allow shift-click to add station
    map.on("click", (e) => {
      if ((e.originalEvent as MouseEvent).shiftKey) {
        const name = prompt("New Station name:");
        if (name) addNode(name, e.lngLat.lat, e.lngLat.lng);
      }
    });

    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [containerRef.current]);

  // Update tracks & station DOM markers when stations/edges change
  useEffect(() => {
    if (!mapRef.current || !mapReady) return;
    refreshTracksOnMap(mapRef.current, edges, stations);
    refreshStationMarkers(mapRef.current, stations);
  }, [stations, edges, mapReady]);

  /** Ensure markers exist for each train and remove stale markers. Pure DOM/Map operations. */
  function ensureMarkersForTrains(map: maplibregl.Map, trainsSnapshot: TrainLike[]) {
    // create markers for trains that don't have them
    trainsSnapshot.forEach((tr) => {
      if (!markersRef.current[tr.id]) {
        // container holds aura + core
        const container = document.createElement("div");
        container.className = "train-marker-container";

// aura (visual only)
const aura = document.createElement("video");
aura.className = "aura";
aura.src = "/aura.webm";
aura.autoplay = true;
aura.loop = true;
aura.muted = true;
aura.playsInline = true;
// keep pointerEvents none so marker won't block map interactions
aura.style.pointerEvents = "none";
aura.style.width = "60px";
aura.style.height = "60px";
aura.style.borderRadius = "50%";
aura.style.position = "absolute";
aura.style.top = "50%";
aura.style.left = "50%";
aura.style.transform = "translate(-50%, -50%)";
aura.style.objectFit = "cover";
container.appendChild(aura);

        // core
        const core = document.createElement("div");
        core.className = "train-core jitter";
        core.style.pointerEvents = "auto"; // allow clicking if needed
        core.title = tr.name ?? tr.id;
        container.appendChild(core);

        const marker = new maplibregl.Marker({ element: container, anchor: "center" })
          .setLngLat([0, 0])
          .addTo(map);

        markersRef.current[tr.id] = marker;
      }
    });

    // remove markers for trains that no longer exist (by base id)
    Object.keys(markersRef.current).forEach((key) => {
      if (!trainsSnapshot.find((t) => t.id === key)) {
        try {
          markersRef.current[key].remove();
        } catch { /* ignore */ }
        delete markersRef.current[key];
      }
    });
  }

  /** Updates positions of markers & aura GeoJSON source; detects collisions and updates store via updateTrainStatus */
  function animationStep() {
    const map = mapRef.current;
    if (!map) return;

    const store = useRailwayStore.getState();
    const trainsSnapshot = store.trains; // read directly from store (latest)
    const stationsSnapshot = store.stations;

    // ensure markers
    ensureMarkersForTrains(map, trainsSnapshot);

    // move each marker according to train.progress (we don't mutate store trains here)
    trainsSnapshot.forEach((tr) => {
      const { lat, lon } = getTrainLatLon(tr as TrainLike, stationsSnapshot);
      const marker = markersRef.current[tr.id];
      if (marker) {
        // MapLibre expects [lon, lat]
        marker.setLngLat([lon, lat]);
      }
    });

    // set aura source (for circle-layer visualization)
    const auraFeatures = trainsSnapshot.map((tr) => ({
      type: "Feature" as const,
      properties: { id: tr.id, name: tr.name, status: tr.status ?? "MOVING" },
      geometry: { type: "Point" as const, coordinates: (() => {
        const { lat, lon } = getTrainLatLon(tr as TrainLike, stationsSnapshot);
        return [lon, lat];
      })() },
    }));
    const auraSrc = map.getSource("train-auras") as maplibregl.GeoJSONSource | undefined;
    if (auraSrc) {
      try { auraSrc.setData({ type: "FeatureCollection", features: auraFeatures }); } catch { /* ignore */ }
    }

    // Collision detection in pixel space (using map.project)
    // Collision detection using pixel distances and AI decision server
for (let i = 0; i < trainsSnapshot.length; i++) {
  for (let j = i + 1; j < trainsSnapshot.length; j++) {

    const A = trainsSnapshot[i];
    const B = trainsSnapshot[j];

    const posA = getTrainLatLon(A as TrainLike, stationsSnapshot);
    const posB = getTrainLatLon(B as TrainLike, stationsSnapshot);

    const pA = map.project([posA.lon, posA.lat]);
    const pB = map.project([posB.lon, posB.lat]);
    const dx = pA.x - pB.x;
    const dy = pA.y - pB.y;

    const pixelDist = Math.sqrt(dx * dx + dy * dy);

    if (pixelDist <= AURA_RADIUS_PX * 2) {

      console.warn("⚠ Collision risk detected between", A.name, "and", B.name);

      // --- 🔥 DO NOT STOP TRAINS HERE ---
      // Remove any direct STOP logic
      // Let AI decide who stops

      // ----- CALL PYTHON AI SERVER -----
      (async () => {
        try {
          const response = await fetch("http://127.0.0.1:8000/decide", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              trains: [
                {
                  name: A.name,
                  lat: posA.lat,
                  lon: posA.lon,
                  speed: A.speed ?? 100,
                  priority: 1
                },
                {
                  name: B.name,
                  lat: posB.lat,
                  lon: posB.lon,
                  speed: B.speed ?? 100,
                  priority: 1
                }
              ]
            }),
          });

          const decision = await response.json();
          console.log("🤖 AI Decision:", decision);

          if (decision[0]?.action === "STOP_ONE") {
            const stopTrainName = decision[0].stop_train;
            const passTrainName = decision[0].let_pass;

            console.warn(
              `🤖 AI: STOP ${stopTrainName} — LET ${passTrainName} PASS`
            );

            // Apply the AI STOP logic
            updateTrainStatus(stopTrainName, "STOPPED");
            updateTrainStatus(passTrainName, "RUNNING");
          }

          else if (decision[0]?.action === "STOP_BOTH") {
            // Optional: if someday you need both to stop
            updateTrainStatus(A.name, "STOPPED");
            updateTrainStatus(B.name, "STOPPED");
          }

        } catch (err) {
          console.error("❌ AI Server Error:", err);
        }
      })();

      // ----- OPTIONAL: VISUAL SEGMENT HIGHLIGHT -----
      try {
       const segment: Feature<LineString> = {
      type: "Feature",
      properties: {},
      geometry: {
        type: "LineString",
        coordinates: [
          [posA.lon, posA.lat],
          [posB.lon, posB.lat]
                ]
          }
        } as const;
        const segSrc = map.getSource("current-segment") as maplibregl.GeoJSONSource;
        if (segSrc && typeof segSrc.setData === "function") {
           segSrc.setData({
            type: "FeatureCollection",
            features: [segment]
  });
}

      } catch {}
      
    }
  }
}


    // Advance progress for trains that are MOVING (store-controlled update)
    const now = Date.now();
    trainsSnapshot.forEach((tr) => {
      if (tr.status === "STOPPED") return;
      // calculate an elapsed-based progress increment using speed (purely client-side)
      // We can't read startTime reliably for all trains, so we advance progress incrementally
      // speed is arbitrary units; use delta time to compute progress increment
      // For stability, assume baseline: speed = 100 -> ~12 seconds from 0->1
    });

    // Note: We compute incremental progress USING a delta from previous RAF frame time
    // To do that, store last frame time in a ref
  }

  // Animation loop with delta timing (reads latest trains from store each frame)
  useEffect(() => {
    if (!mapReady || rafRunningRef.current) return;
    rafRunningRef.current = true;

    let lastTs = performance.now();
    function loop(ts: number) {
      const dt = Math.max(0, ts - lastTs);
      lastTs = ts;

      // Advance train progress (call updateTrainProgress on store)
      const store = useRailwayStore.getState();
      const trainsSnapshot = store.trains;
      const stationsSnapshot = store.stations;

      // For each train, compute progress increment and update store (without mutating train object directly)
      trainsSnapshot.forEach((tr) => {
        if (tr.status === "STOPPED") return;
        // baseline: speed 100 -> 12s to complete (i.e., 1/12000 per ms)
        const speed = Math.max(tr.speed ?? 100, 1);
        const totalMs = 12000 / (speed / 100); // same formula as earlier code's intent
        // We'll increment progress by dt / totalMs
        const deltaProgress = dt / totalMs;
        const nextProgress = Math.min(1, tr.progress + deltaProgress);
        if (nextProgress !== tr.progress) {
          updateTrainProgress(tr.id, nextProgress);
        }
        // Optionally, if reached end, set status to STOPPED or ARRIVED
        if (nextProgress >= 1 && tr.status !== "STOPPED") {
          updateTrainStatus(tr.id, "STOPPED");
        }
      });

      // Perform visual updates & collision detection after progress updates
      // (animationStep uses freshest store state)
      try { animationStep(); } catch (err) { /* swallow errors to keep RAF running */ }

      animationRef.current = requestAnimationFrame(loop);
    }

    animationRef.current = requestAnimationFrame(loop);

    return () => {
      rafRunningRef.current = false;
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    };
    // We intentionally do NOT include trains/stations in deps to avoid restarting loop
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapReady]);

  /** Helper: update tracks layer when stations/edges change */
  function refreshTracksOnMap(map: maplibregl.Map, edgesParam: Edge[], stationsParam: Station[]) {
    if (!map) return;
    const features = edgesParam
      .map((e) => {
        const A = getStationByName(e.source, stationsParam);
        const B = getStationByName(e.target, stationsParam);
        if (!A || !B) return undefined;
        return {
          type: "Feature" as const,
          properties: {},
          geometry: { type: "LineString" as const, coordinates: [[A.lon, A.lat], [B.lon, B.lat]] },
        };
      })
      .filter((f): f is NonNullable<typeof f> => f !== undefined);
    const src = map.getSource("tracks") as maplibregl.GeoJSONSource | undefined;
    if (src) {
      try { src.setData({ type: "FeatureCollection", features }); } catch { /* ignore */ }
    }
  }

  /** Helper: refresh station DOM markers (simple non-react DOM markers) */
  function refreshStationMarkers(map: maplibregl.Map, stationsParam: Station[]) {
    // remove previous station DOM markers
    document.querySelectorAll(".station-marker").forEach((el) => el.remove());
    stationsParam.forEach((s) => {
      const el = document.createElement("div");
      el.className = "station-marker";
      el.title = s.name;
      el.addEventListener("click", (ev) => {
        ev.stopPropagation();
        alert(`Station: ${s.name}`);
      });
      new maplibregl.Marker({ element: el, anchor: "center" }).setLngLat([s.lon, s.lat]).addTo(map);
    });
  }

  /** ---- UI form state & handlers ---- */
  const [showAddStation, setShowAddStation] = useState(false);
  const [showAddRoute, setShowAddRoute] = useState(false);
  const [showAddTrain, setShowAddTrain] = useState(false);
  const [showViewRoutes, setShowViewRoutes] = useState(false);

  const [newStationName, setNewStationName] = useState("");
  const [newStationLat, setNewStationLat] = useState("");
  const [newStationLon, setNewStationLon] = useState("");

  const [routeStartStation, setRouteStartStation] = useState("");
  const [routeEndStation, setRouteEndStation] = useState("");

  const [trainName, setTrainName] = useState("");
  const [trainStartStation, setTrainStartStation] = useState("");
  const [trainEndStation, setTrainEndStation] = useState("");
  const [trainSpeed, setTrainSpeed] = useState("100");

  function handleAddStation() {
    if (!newStationName || !newStationLat || !newStationLon) {
      alert("Please fill all fields for station.");
      return;
    }
    const latNum = parseFloat(newStationLat);
    const lonNum = parseFloat(newStationLon);
    if (isNaN(latNum) || isNaN(lonNum)) {
      alert("Please enter valid latitude and longitude numbers.");
      return;
    }
    addNode(newStationName, latNum, lonNum);
    setNewStationName("");
    setNewStationLat("");
    setNewStationLon("");
    alert(`Station "${newStationName}" added.`);
  }

  function handleAddRoute() {
    if (!routeStartStation || !routeEndStation) {
      alert("Please select both start and end stations.");
      return;
    }
    if (routeStartStation === routeEndStation) {
      alert("Start and end stations should be different.");
      return;
    }
    addEdge(routeStartStation, routeEndStation);
    alert(`Route added from "${routeStartStation}" to "${routeEndStation}".`);
  }

  function handleAddTrain() {
    if (!trainName || !trainStartStation || !trainEndStation || !trainSpeed) {
      alert("Please fill all fields for train.");
      return;
    }
    if (trainStartStation === trainEndStation) {
      alert("Start and end stations should be different.");
      return;
    }
    const speedNum = parseFloat(trainSpeed);
    if (isNaN(speedNum) || speedNum <= 0) {
      alert("Please enter a valid positive number for speed.");
      return;
    }
    addTrain(trainName, trainStartStation, trainEndStation, speedNum);
    setTrainName("");
    setTrainStartStation("");
    setTrainEndStation("");
    setTrainSpeed("100");
    alert(`Train "${trainName}" added on path from "${trainStartStation}" to "${trainEndStation}" with speed ${speedNum}.`);
  }

  /** ---- Render ---- */
  return (
    <div style={{ width: "100%", height: "100vh", position: "relative", background: "#0b0b0f" }}>
      {/* Sidebar panel */}
      <div style={{
        position: "absolute", left: 10, top: 10, zIndex: 30, background: "rgba(20,20,20,0.9)",
        padding: 10, borderRadius: 8, width: 320, color: "#eee", fontSize: 14, maxHeight: "90vh", overflowY: "auto",
        boxShadow: "0 0 10px #000"
      }}>
        <h3 style={{ marginTop: 0 }}>Train Map Controls</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <button onClick={() => { setShowAddStation(!showAddStation); setShowAddRoute(false); setShowAddTrain(false); setShowViewRoutes(false); }} style={{ padding: "6px 8px" }}>
            {showAddStation ? "Hide Add Station" : "Show Add Station"}
          </button>
          <button onClick={() => { setShowAddRoute(!showAddRoute); setShowAddStation(false); setShowAddTrain(false); setShowViewRoutes(false); }} style={{ padding: "6px 8px" }}>
            {showAddRoute ? "Hide Add Route" : "Show Add Route"}
          </button>
          <button onClick={() => { setShowAddTrain(!showAddTrain); setShowAddStation(false); setShowAddRoute(false); setShowViewRoutes(false); }} style={{ padding: "6px 8px" }}>
            {showAddTrain ? "Hide Add Train" : "Show Add Train"}
          </button>
          <button onClick={() => { setShowViewRoutes(!showViewRoutes); setShowAddStation(false); setShowAddRoute(false); setShowAddTrain(false); }} style={{ padding: "6px 8px" }}>
            {showViewRoutes ? "Hide Routes & Stations" : "View Routes & Stations"}
          </button>
        </div>

        {/* Add Station Form */}
        {showAddStation && (
          <div style={{ marginTop: 12, borderTop: "1px solid #444", paddingTop: 12 }}>
            <h4>Add Station</h4>
            <label>
              Name:<br />
              <input type="text" value={newStationName} onChange={e => setNewStationName(e.target.value)} style={{ width: "100%" }} />
            </label>
            <label>
              Latitude:<br />
              <input type="text" value={newStationLat} onChange={e => setNewStationLat(e.target.value)} style={{ width: "100%" }} />
            </label>
            <label>
              Longitude:<br />
              <input type="text" value={newStationLon} onChange={e => setNewStationLon(e.target.value)} style={{ width: "100%" }} />
            </label>
            <button onClick={handleAddStation} style={{ marginTop: 8, padding: "6px 8px", width: "100%" }}>Add Station</button>
          </div>
        )}

        {/* Add Route Form */}
        {showAddRoute && (
          <div style={{ marginTop: 12, borderTop: "1px solid #444", paddingTop: 12 }}>
            <h4>Add Route</h4>
            <label>
              Start Station:<br />
              <select value={routeStartStation} onChange={e => setRouteStartStation(e.target.value)} style={{ width: "100%" }}>
                <option value="">Select station</option>
                {stations.map(s => (
                  <option key={s.name} value={s.name}>{s.name}</option>
                ))}
              </select>
            </label>
            <label>
              End Station:<br />
              <select value={routeEndStation} onChange={e => setRouteEndStation(e.target.value)} style={{ width: "100%" }}>
                <option value="">Select station</option>
                {stations.map(s => (
                  <option key={s.name} value={s.name}>{s.name}</option>
                ))}
              </select>
            </label>
            <button onClick={handleAddRoute} style={{ marginTop: 8, padding: "6px 8px", width: "100%" }}>Add Route</button>
          </div>
        )}

        {/* Add Train Form */}
        {showAddTrain && (
          <div style={{ marginTop: 12, borderTop: "1px solid #444", paddingTop: 12 }}>
            <h4>Add Train</h4>
            <label>
              Train Name:<br />
              <input type="text" value={trainName} onChange={e => setTrainName(e.target.value)} style={{ width: "100%" }} />
            </label>
            <label>
              Start Station:<br />
              <select value={trainStartStation} onChange={e => setTrainStartStation(e.target.value)} style={{ width: "100%" }}>
                <option value="">Select station</option>
                {stations.map(s => (
                  <option key={s.name} value={s.name}>{s.name}</option>
                ))}
              </select>
            </label>
            <label>
              End Station:<br />
              <select value={trainEndStation} onChange={e => setTrainEndStation(e.target.value)} style={{ width: "100%" }}>
                <option value="">Select station</option>
                {stations.map(s => (
                  <option key={s.name} value={s.name}>{s.name}</option>
                ))}
              </select>
            </label>
            <label>
              Speed:<br />
              <input type="text" value={trainSpeed} onChange={e => setTrainSpeed(e.target.value)} style={{ width: "100%" }} />
            </label>
            <button onClick={handleAddTrain} style={{ marginTop: 8, padding: "6px 8px", width: "100%" }}>Add Train</button>
          </div>
        )}

        {/* View Routes and Stations List */}
        {showViewRoutes && (
          <div style={{ marginTop: 12, borderTop: "1px solid #444", paddingTop: 12 }}>
            <h4>Stations</h4>
            <ul style={{ listStyle: "none", paddingLeft: 0, maxHeight: 120, overflowY: "auto" }}>
              {stations.map(s => (
                <li key={s.name} style={{ padding: "2px 0" }}>{s.name} ({s.lat.toFixed(2)}, {s.lon.toFixed(2)})</li>
              ))}
            </ul>
            <h4>Routes</h4>
            <ul style={{ listStyle: "none", paddingLeft: 0, maxHeight: 120, overflowY: "auto" }}>
              {edges.map((e, i) => (
                <li key={i} style={{ padding: "2px 0" }}>
                  {e.source} ➔ {e.target}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Map container */}
      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />

      {/* Legend */}
      <div style={{
        position: "absolute", right: 16, bottom: 16, zIndex: 20,
        background: "rgba(0,0,0,0.6)", color: "white", padding: 10, borderRadius: 8, fontSize: 13,
        border: "1px solid #222"
      }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <div style={{ width: 12, height: 12, background: "#ff4d94", borderRadius: 6 }} />
          <span>Train / Aura</span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <div style={{ width: 12, height: 12, background: "#00ffcc", borderRadius: 6 }} />
          <span>Station</span>
        </div>
      </div>
    </div>
  );
}
