// app/components/TrainMap.tsx — FINAL VERSION (Segment-Based Animation)
"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { useRailwayStore, Station, Train } from "../lib/store";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

export default function TrainMap() {
  const { stations, edges, trains, updateTrainStatus } = useRailwayStore();

  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  const trainMarkers = useRef<Map<string, maplibregl.Marker>>(new Map());
  const stationMarkers = useRef<Map<string, maplibregl.Marker>>(new Map());
  const edgeLayers = useRef<string[]>([]);

  const [selectedTrain, setSelectedTrain] = useState<Train | null>(null);
  const [theme, setTheme] = useState<"cyberpunk" | "official" | "matrix">("cyberpunk");
  const [parameters, setParameters] = useState<any>(null); 
  const [showHeatmaps, setShowHeatmaps] = useState(false);
  const [showRiskHeatmaps, setShowRiskHeatmaps] = useState(false);
  const [showSpeedLabels, setShowSpeedLabels] = useState(true);
  const [showTTCIndicators, setShowTTCIndicators] = useState(true);
  const [autoSpawnEnabled, setAutoSpawnEnabled] = useState(false);
  const [speedMultiplier, setSpeedMultiplier] = useState(10000);
  const [followTrains, setFollowTrains] = useState(false);

  // ============================================================
  // MAP INITIALIZATION
  // ============================================================
  useEffect(() => {
    if (!mapContainer.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: getMapStyle(theme),
      center: [78.0, 22.0],
      zoom: 4.5,
    });

    mapRef.current = map;

    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.addControl(new maplibregl.FullscreenControl(), "top-right");

    map.on("load", () => {
      addStationsToMap(map);
      addEdgesToMap(map);
      updateTrainsOnMap();
    });

    return () => {
      map.remove();
    };
  }, []);

  // =============================================================
  // UPDATE THEME
  // =============================================================
  useEffect(() => {
    if (!mapRef.current) return;
    mapRef.current.setStyle(getMapStyle(theme));
  }, [theme]);

  // =============================================================
  // UPDATE STATIONS + EDGES
  // =============================================================
  useEffect(() => {
    if (!mapRef.current || !mapRef.current.isStyleLoaded()) return;
    updateStationsOnMap();
    updateEdgesOnMap();
  }, [stations, edges]);

  // =============================================================
  // UPDATE STATIONS ON MAP
  // =============================================================
  const updateStationsOnMap = () => {
    const map = mapRef.current;
    if (!map) return;

    // Remove existing station markers
    stationMarkers.current.forEach((marker) => marker.remove());
    stationMarkers.current.clear();

    // Add new station markers
    stations.forEach((station) => {
      const el = document.createElement("div");
      el.className = "station-marker";
      el.style.width = "18px";
      el.style.height = "18px";
      el.style.borderRadius = "0%";
      el.style.background = "#0ff";
      el.style.border = "2px solid white";

      const marker = new maplibregl.Marker(el)
        .setLngLat([station.lon, station.lat])
        .addTo(map);

      stationMarkers.current.set(station.name, marker);
    });
  };

  // =============================================================
  // UPDATE EDGES ON MAP
  // =============================================================
  const updateEdgesOnMap = () => {
    const map = mapRef.current;
    if (!map) return;

    // Remove existing edge layers
    edgeLayers.current.forEach((id) => {
      if (map.getLayer(id)) map.removeLayer(id);
      if (map.getSource(id)) map.removeSource(id);
    });
    edgeLayers.current = [];

    // Add new edge layers
    edges.forEach((edge, index) => {
      const a = stations.find((s) => s.name === edge.source);
      const b = stations.find((s) => s.name === edge.target);

      if (!a || !b) return;

      const layerId = `edge-${index}`;

      map.addSource(layerId, {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: {
            type: "LineString",
            coordinates: [
              [a.lon, a.lat],
              [b.lon, b.lat],
            ],
          },
        },
      });

      map.addLayer({
        id: layerId,
        type: "line",
        source: layerId,
        paint: {
          "line-color": "#00eaff",
          "line-width": 3,
        },
      });

      edgeLayers.current.push(layerId);
    });
  };

  // =============================================================
  // UPDATE TRAINS (MARKER CREATION)
  // =============================================================
  useEffect(() => {
    if (!mapRef.current) return;
    updateTrainsOnMap();
  }, [trains]);

  // =============================================================
  // FETCH PARAMETERS
  // =============================================================
  useEffect(() => {
    const fetchParameters = async () => {
      try {
        const response = await fetch("http://localhost:8001/parameters_full");
        const data = await response.json();
        setParameters(data);
      } catch (error) {
        console.error("Failed loading parameters:", error);
      }
    };

    fetchParameters();
    const interval = setInterval(fetchParameters, 5000);

    return () => clearInterval(interval);
  }, []);

  // =============================================================
  // HEATMAP UPDATES
  // =============================================================
  useEffect(() => {
    if (!mapRef.current || !mapRef.current.isStyleLoaded()) return;
    updateHeatmaps();
  }, [parameters, showHeatmaps, showRiskHeatmaps, stations, edges]);

  // =============================================================
  // AUTO SPAWN
  // =============================================================
  useEffect(() => {
    if (!autoSpawnEnabled) return;

    const autoSpawnInterval = setInterval(() => {
      const paths = [
        ["New Delhi", "Jaipur", "Ahmedabad", "Mumbai CST"],
        ["Chennai", "Bangalore Cantt", "Bangalore City", "Hubli"],
        ["Delhi", "Ghaziabad", "New Delhi", "Kanpur", "Lucknow"],
        ["Howrah", "Bhubaneswar", "Visakhapatnam", "Chennai"],
        ["Trivandrum", "Ernakulam", "Mangalore", "Hubli", "Bangalore City"],
      ];

      const randomPath = paths[Math.floor(Math.random() * paths.length)];

      useRailwayStore
        .getState()
        .addTrainOnGraphPath(`AutoTrain-${Date.now()}`, randomPath, 80 + Math.random() * 40);
    }, 8000);

    return () => clearInterval(autoSpawnInterval);
  }, [autoSpawnEnabled]);

  // =============================================================
  //  HELPER: MAP STYLE
  // =============================================================
  const getMapStyle = (theme: string): maplibregl.StyleSpecification => {
    const base: maplibregl.StyleSpecification = {
      version: 8,
      sources: {
        osm: {
          type: "raster",
          tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
          tileSize: 256,
        },
      },
      layers: [
        { id: "osm-layer", type: "raster", source: "osm", minzoom: 0, maxzoom: 19 },
      ],
    };

    if (theme === "cyberpunk")
      return { ...base, layers: [...base.layers] };

    if (theme === "matrix")
      return { ...base, layers: [...base.layers] };

    return base;
  };

  // =============================================================
  // ADD STATIONS
  // =============================================================
  const addStationsToMap = (map: maplibregl.Map) => {
    stations.forEach((station) => {
      const el = document.createElement("div");
      el.className = "station-marker";
      el.style.width = "18px";
      el.style.height = "18px";
      el.style.borderRadius = "50%";
      el.style.background = "#0ff";
      el.style.border = "2px solid white";

      const marker = new maplibregl.Marker(el)
        .setLngLat([station.lon, station.lat])
        .addTo(map);

      stationMarkers.current.set(station.name, marker);
    });
  };

  // =============================================================
  // ADD EDGES
  // =============================================================
  const addEdgesToMap = (map: maplibregl.Map) => {
    edgeLayers.current.forEach((id) => {
      if (map.getLayer(id)) map.removeLayer(id);
      if (map.getSource(id)) map.removeSource(id);
    });
    edgeLayers.current = [];

    edges.forEach((edge, index) => {
      const a = stations.find((s) => s.name === edge.source);
      const b = stations.find((s) => s.name === edge.target);

      if (!a || !b) return;

      const layerId = `edge-${index}`;

      map.addSource(layerId, {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: {
            type: "LineString",
            coordinates: [
              [a.lon, a.lat],
              [b.lon, b.lat],
            ],
          },
        },
      });

      map.addLayer({
        id: layerId,
        type: "line",
        source: layerId,
        paint: {
          "line-color": "#00eaff",
          "line-width": 3,
        },
      });

      edgeLayers.current.push(layerId);
    });
  };

  // =============================================================
  // CREATE OR UPDATE TRAIN MARKERS
  // =============================================================
  const updateTrainsOnMap = () => {
    const map = mapRef.current;
    if (!map) return;

    const existing = new Set(trainMarkers.current.keys());
    const incoming = new Set(trains.map((t) => t.id));

    // remove
    for (const id of existing) {
      if (!incoming.has(id)) {
        trainMarkers.current.get(id)?.remove();
        trainMarkers.current.delete(id);
      }
    }

    // add new
    trains.forEach((train) => {
      if (!trainMarkers.current.has(train.id)) {
        const pos = getTrainPosition(train);
        if (!pos) return;

        const wrapper = document.createElement("div");
        wrapper.className = "train-wrapper";

        const dot = document.createElement("div");
        dot.className = "train-marker";
        dot.style.width = "14px";
        dot.style.height = "14px";
        dot.style.borderRadius = "50%";
        dot.style.background = "red";
        dot.style.border = "2px solid white";
        dot.style.transformOrigin = "center";

        wrapper.appendChild(dot);

        const m = new maplibregl.Marker(wrapper)
          .setLngLat([pos.lon, pos.lat])
          .addTo(map);

        wrapper.addEventListener("click", () => setSelectedTrain(train));

        trainMarkers.current.set(train.id, m);
      }
    });
  };

  // =============================================================
  //  SEGMENT-BASED TRAIN POSITION
  // =============================================================
  function getTrainPosition(train: Train) {
    const seg = train.currentSegment;
    const path = train.path;

    if (!path || seg >= path.length - 1) return null;

    const a = stations.find((s) => s.name === path[seg]);
    const b = stations.find((s) => s.name === path[seg + 1]);

    if (!a || !b) return null;

    const t = train.segmentProgress;
    const lat = a.lat + (b.lat - a.lat) * t;
    const lon = a.lon + (b.lon - a.lon) * t;

    if (isNaN(lat) || isNaN(lon)) return null;

    return { lat, lon };
  }

  // =============================================================
  // SEGMENT-BASED BEARING
  // =============================================================
  function getTrainBearing(train: Train): number | null {
    const seg = train.currentSegment;
    const path = train.path;

    if (!path || seg >= path.length - 1) return null;

    const a = stations.find((s) => s.name === path[seg]);
    const b = stations.find((s) => s.name === path[seg + 1]);
    if (!a || !b) return null;

    const dLon = (b.lon - a.lon) * Math.PI / 180;

    const lat1 = a.lat * Math.PI / 180;
    const lat2 = b.lat * Math.PI / 180;

    const y = Math.sin(dLon) * Math.cos(lat2);
    const x =
      Math.cos(lat1) * Math.sin(lat2) -
      Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);

    return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
  }

  // =============================================================
  // DISTANCE (m)
  // =============================================================
  function getDistance(a: Station, b: Station) {
    const dx = (b.lon - a.lon) * 111320 * Math.cos(((a.lat + b.lat) * Math.PI) / 360);
    const dy = (b.lat - a.lat) * 111320;
    return Math.hypot(dx, dy);
  }

  // =============================================================
  // COLLISION DETECTION
  // =============================================================
  const detectCollision = useCallback(() => {
    trains.forEach((t1) => {
      trains.forEach((t2) => {
        if (t1.id === t2.id) return;

        const p1 = getTrainPosition(t1);
        const p2 = getTrainPosition(t2);
        if (!p1 || !p2) return;

        const dist =
          Math.sqrt(Math.pow(p1.lat - p2.lat, 2) + Math.pow(p1.lon - p2.lon, 2)) *
          111320;

        if (dist < 1000) {
          updateTrainStatus(t1.id, "BRAKING");
          updateTrainStatus(t2.id, "BRAKING");
        }
      });
    });
  }, [trains]);

  // =============================================================
  // THE REAL ANIMATION ENGINE
  // =============================================================
  useEffect(() => {
    let anim: number;

    const step = () => {
      const state = useRailwayStore.getState();
      const trains = state.trains;

      trains.forEach((train) => {
        if (train.status === "ARRIVED") return;

        const seg = train.currentSegment;

        if (!train.path || seg >= train.path.length - 1) return;

        const a = stations.find((s) => s.name === train.path[seg]);
        const b = stations.find((s) => s.name === train.path[seg + 1]);
        if (!a || !b) return;

        const dist = getDistance(a, b);

        let speed =
          train.status === "BRAKING" ? train.speed * 0.3 : train.speed;

        // Apply health factor based on segment health
        const health = parameters ? parameters[`P${1 + (train.currentSegment % 10)}`] : 1;
        const healthFactor = 1 - (1 - health) * 0.5;
        const effectiveSpeed = speed * healthFactor;

        const speedMs = (effectiveSpeed * 1000) / 3600;

        const delta = (speedMs * 0.016) / dist * speedMultiplier;

        train.segmentProgress += delta;

        if (train.segmentProgress >= 1) {
          train.currentSegment++;

          // If reached last station → stop forever
          if (train.currentSegment >= train.path.length - 1) {
            train.currentSegment = train.path.length - 1;
            train.segmentProgress = 1;
            train.status = "ARRIVED";

            // Lock marker on final station
            const finalPos = getTrainPosition(train);
            const marker = trainMarkers.current.get(train.id);
            if (marker && finalPos) marker.setLngLat([finalPos.lon, finalPos.lat]);

            return; // <-- STOP ANIMATION FOR THIS TRAIN
          }

          // Otherwise continue to next segment
          train.segmentProgress = 0;
        }

        // UPDATE MARKER
        const marker = trainMarkers.current.get(train.id);
        if (marker) {
          const pos = getTrainPosition(train);
          if (pos && !isNaN(pos.lon) && !isNaN(pos.lat)) marker.setLngLat([pos.lon, pos.lat]);

          const bearing = getTrainBearing(train);
          const inner = marker.getElement().querySelector(".train-marker") as HTMLElement;
          if (inner && bearing !== null) inner.style.transform = `rotate(${bearing}deg)`;
        }
      });

      // FOLLOW TRAINS - Center map on active trains
      if (followTrains && trains.length > 0) {
        const activeTrains = trains.filter(t => t.status !== "ARRIVED");
        if (activeTrains.length > 0) {
          const positions = activeTrains.map(t => getTrainPosition(t)).filter(p => p !== null) as {lat: number, lon: number}[];

          if (positions.length > 0) {
            // Calculate center of all active trains
            const avgLat = positions.reduce((sum, p) => sum + p.lat, 0) / positions.length;
            const avgLon = positions.reduce((sum, p) => sum + p.lon, 0) / positions.length;

            // Smooth camera movement
            const map = mapRef.current;
            if (map) {
              map.easeTo({
                center: [avgLon, avgLat],
                duration: 100, // Smooth transition
                zoom: 6 // Closer zoom to see speed differences clearly
              });
            }
          }
        }
      }

      detectCollision();

      anim = requestAnimationFrame(step);
    };

    anim = requestAnimationFrame(step);

    return () => cancelAnimationFrame(anim);
  }, [speedMultiplier, followTrains]);

  // =============================================================
  // HEATMAPS (unchanged)
  // =============================================================
  const updateHeatmaps = () => {};

  // =============================================================
  // DEPLOY TRAINS (BUTTON)
  // =============================================================
  const deployTrains = () => {
    console.log("Deploying 2 trains with different speeds...");

    // Deploy only 2 trains with different speeds for clear observation
    const trainConfigs = [
      {
        name: "Fast Express",
        path: ["New Delhi", "Mumbai CST"],
        speed: 150 // Fast train
      },
      {
        name: "Slow Express",
        path: ["New Delhi", "Mumbai CST"],
        speed: 80  // Slower train on same path
      }
    ];

    trainConfigs.forEach((config, i) => {
      console.log(`Adding train: ${config.name} on path: ${config.path.join(" -> ")} at ${config.speed} km/h`);
      useRailwayStore
        .getState()
        .addTrainOnGraphPath(config.name, config.path, config.speed);
    });

    // Check if trains were added to store
    setTimeout(() => {
      const currentTrains = useRailwayStore.getState().trains;
      console.log("Trains in store after deployment:", currentTrains.length);
      currentTrains.forEach((train, i) => {
        console.log(`Train ${i}: ${train.name} on path ${train.path.join(" -> ")} at ${Math.round(train.speed)} km/h`);
      });

      console.log("Updating trains on map...");
      updateTrainsOnMap();
    }, 100);
  };

  // =============================================================
  // UI
  // =============================================================
  return (
    <div className="relative w-screen h-screen bg-black">
      <div ref={mapContainer} className="w-full h-full" />

      {selectedTrain && (
        <div className="absolute right-8 top-1/2 -translate-y-1/2 bg-black/90 text-white p-6 rounded-xl border border-cyan-400 w-80">
          <h2 className="text-xl font-bold text-cyan-300">{selectedTrain.name}</h2>
          <p>Status: {selectedTrain.status}</p>
          <p>Speed: {Math.round(selectedTrain.speed)} km/h</p>
          <p>Path: {selectedTrain.path.join(" → ")}</p>

          <button
            onClick={() => setSelectedTrain(null)}
            className="mt-4 bg-red-600 px-4 py-2 rounded"
          >
            Close
          </button>
        </div>
      )}

      <div className="absolute left-8 top-8 z-10 space-y-4">
        <div className="bg-black/90 p-4 border border-cyan-400 rounded-xl">
          <label className="text-cyan-300 font-bold">
            Speed Multiplier: {speedMultiplier}x
          </label>
          <input
            type="range"
            min={1000}
            max={50000}
            value={speedMultiplier}
            onChange={(e) => setSpeedMultiplier(Number(e.target.value))}
            className="w-full"
          />
        </div>

        <button
          onClick={deployTrains}
          className="bg-cyan-500 px-4 py-2 rounded text-black font-bold"
        >
          DEPLOY TRAINS
        </button>

        <button
          onClick={() => setAutoSpawnEnabled((v) => !v)}
          className="bg-green-500 px-4 py-2 rounded"
        >
          {autoSpawnEnabled ? "Disable Auto Spawn" : "Enable Auto Spawn"}
        </button>

        <button
          onClick={() => setFollowTrains((v) => !v)}
          className="bg-purple-500 px-4 py-2 rounded"
        >
          {followTrains ? "Disable Follow Trains" : "Enable Follow Trains"}
        </button>
      </div>
    </div>
  );
}
