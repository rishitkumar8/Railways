// lib/store.ts
import { create } from "zustand";
import { compute140Parameters } from "./compute140Parameters";
<<<<<<< HEAD
import { computeTrackParameters } from "./computeTrackParameters";
import { computeTrainParameters } from "./computeTrainParameters";
import { computeCollisionParameters } from "./computeCollisionParameters";
import { computeEnvironmentParameters, generateStationEnvironment } from "./computeEnvironmentParameters";
import { computeNetworkLoadParameters } from "./computeNetworkLoadParameters";
import { computeHealthParameters } from "./computeHealthParameters";
import { computeSafetyParameters } from "./computeSafetyParameters";

/**
 * Full store.ts (Phase 1, "C" = full compatibility)
 * - Provides stations, edges, ~50 trains
 * - Every train has params: Record<string, number> (p1..p140)
 * - All state mutators recompute params where appropriate
 */

interface TrackSegment {
    id: string;
    start: { lat: number; lon: number };
    end: { lat: number; lon: number };
    env: Record<string, number>;
}

interface Station {
    id: string;
    name: string;
    lat: number;
    lon: number;
    environment: Record<string, number>;
}
interface Edge { source: string; target: string; }
interface Train {
  id: string;
  name: string;
  source: string;
  destination: string;
  progress: number;
  speed: number;
  path?: string[];
  startTime?: number;
  status?: string;
  lat: number;
  lon: number;
  priority?: number;
  reachedDestination?: boolean;
  params: Record<string, number>;
=======
import { NODES } from "./graph";

// ================================================================
// TYPES
// ================================================================
export interface Station {
  name: string;
  lat: number;
  lon: number;
>>>>>>> 42b56fc74ed4d9318fd8a98b55c9f9214c9b0ffd
}

export interface Edge {
  source: string;
  target: string;
}

export interface Train {
  id: string;
  name: string;
  path: string[];
  progress: number;
  currentSegment: number;
  segmentProgress: number;
  speed: number;
  status: string;
  lat: number;
  lon: number;
  reachedDestination: boolean;
  riskLevel?: number;
  ttc?: number;
}

// NEW: Environment data from backend (p81–p100)
export interface EnvironmentData {
  stations?: Record<string, Record<string, number>>;   // e.g. { "DEL": { p81: 0.2, p91: 0.8 } }
  segments?: Record<string, Record<string, number>>;   // e.g. { "DEL-NDLS-0": { p91: 0.9 } }
}

// ================================================================
// STATION CODE TO NAME MAPPING
// ================================================================
const stationAlias: Record<string, string> = {
  "DEL": "Delhi",
  "GZB": "Ghaziabad",
  "NDLS": "New Delhi",
  "JP": "Jaipur",
  "ADI": "Ahmedabad",
  "RJT": "Rajkot",
  "CSTM": "Mumbai CST",
  "PNQ": "Pune",
  "KYN": "Kalyan",
  "SUR": "Solapur",
  "HYB": "Hyderabad",
  "SC": "Secunderabad",
  "NGP": "Nagpur",
  "BPL": "Bhopal",
  "ET": "Itarsi",
  "CNB": "Kanpur",
  "LKO": "Lucknow",
  "PNBE": "Patna",
  "HWH": "Howrah",
  "BBS": "Bhubaneswar",
  "VSKP": "Visakhapatnam",
  "MAS": "Chennai",
  "BNC": "Bangalore Cantt",
  "SBC": "Bangalore City",
  "UBL": "Hubli",
  "MAQ": "Mangalore",
  "ERS": "Ernakulam",
  "TVC": "Trivandrum"
};

// ================================================================
// PRELOADED INDIA NETWORK - EXPANDED WITH MORE STATIONS AND EDGES
// ================================================================
const INDIA_STATIONS: Station[] = [
  { name: "New Delhi", lat: 28.6431, lon: 77.2195 },
  { name: "Jaipur", lat: 26.9124, lon: 75.7873 },
  { name: "Ahmedabad", lat: 23.0225, lon: 72.5714 },
  { name: "Mumbai CST", lat: 18.9398, lon: 72.8355 },
  { name: "Chennai", lat: 13.0827, lon: 80.2707 },
  { name: "Bangalore City", lat: 12.9716, lon: 77.5946 },
  { name: "Hubli", lat: 15.3647, lon: 75.1240 },
  { name: "Howrah", lat: 22.5726, lon: 88.3639 },
  { name: "Bhubaneswar", lat: 20.2961, lon: 85.8245 },
  { name: "Visakhapatnam", lat: 17.6868, lon: 83.2185 },
  { name: "Trivandrum", lat: 8.5241, lon: 76.9366 },
  { name: "Ernakulam", lat: 9.9816, lon: 76.2999 },
  { name: "Mangalore", lat: 12.9141, lon: 74.8560 },
  { name: "Delhi", lat: 28.7041, lon: 77.1025 },
  { name: "Ghaziabad", lat: 28.6692, lon: 77.4538 },
  { name: "Kanpur", lat: 26.4499, lon: 80.3319 },
  { name: "Lucknow", lat: 26.8467, lon: 80.9462 }
];

const INDIA_EDGES: Edge[] = [
  // Northern route: Delhi -> Mumbai
  { source: "Delhi", target: "Ghaziabad" },
  { source: "Ghaziabad", target: "New Delhi" },
  { source: "New Delhi", target: "Jaipur" },
  { source: "Jaipur", target: "Ahmedabad" },
  { source: "Ahmedabad", target: "Mumbai CST" },
  // Southern route: Chennai -> Bangalore -> Hubli
  { source: "Chennai", target: "Bangalore City" },
  { source: "Bangalore City", target: "Hubli" },
  // Eastern route: Howrah -> Bhubaneswar -> Visakhapatnam -> Chennai
  { source: "Howrah", target: "Bhubaneswar" },
  { source: "Bhubaneswar", target: "Visakhapatnam" },
  { source: "Visakhapatnam", target: "Chennai" },
  // Western route: Trivandrum -> Ernakulam -> Mangalore -> Hubli
  { source: "Trivandrum", target: "Ernakulam" },
  { source: "Ernakulam", target: "Mangalore" },
  { source: "Mangalore", target: "Hubli" },
  // Additional connections
  { source: "New Delhi", target: "Kanpur" },
  { source: "Kanpur", target: "Lucknow" }
];

// ================================================================
// UTILS
// ================================================================
function bfsPath(source: string, dest: string, edges: Edge[]): string[] | null {
  const adj: Record<string, string[]> = {};
  INDIA_STATIONS.forEach(s => (adj[s.name] = []));
  edges.forEach(e => {
    adj[e.source].push(e.target);
    adj[e.target].push(e.source);
  });

  const q = [source];
  const visited = new Set([source]);
  const parent: Record<string, string> = {};

  while (q.length) {
    const cur = q.shift()!;
    if (cur === dest) break;
    for (const nxt of adj[cur]) {
      if (!visited.has(nxt)) {
        visited.add(nxt);
        parent[nxt] = cur;
        q.push(nxt);
      }
    }
  }

  if (!parent[dest]) return null;

  const path: string[] = [];
  let x = dest;
  while (x !== source) {
    path.unshift(x);
    x = parent[x];
  }
  path.unshift(source);
  return path;
}

// ================================================================
// ZUSTAND STORE – NOW WITH ENVIRONMENT SUPPORT
// ================================================================
interface RailwayState {
  stations: Station[];
  edges: Edge[];
  trains: Train[];
<<<<<<< HEAD
  blockedEdges: [string,string][];
  trackSegments: Record<string, TrackSegment[]>;

  addNode: (name: string, lat: number, lon: number) => void;
  addEdge: (sourceName: string, targetName: string) => void;
  updateTrainProgress: (id: string, progress: number) => void;
  updateTrainStatus: (id: string, status: string) => void;
  updateTrainPath: (id: string, newPath: string[]) => void;
  updateTrainSpeed: (id: string, newSpeed: number) => void;
  getPath: (source: string, dest: string) => string[] | null;
  addTrain: (name: string, source: string, dest: string, speed?: number) => void;
  setBlockedEdge: (edge: [string,string]) => void;
  clearBlockedEdge: (edge: [string,string]) => void;
}

function makeParamsForSnapshot(trains: Train[], stations: Station[], edges: Edge[]) {
  // Frontend stub expects single-record return (params object)
  return compute140Parameters(trains, stations, edges);
}

export const useRailwayStore = create<RailwayState>((set, get) => {
  // base station list (realistic Indian major stations for a large map)
  const baseStations: Station[] = [
    { id: "DEL", name: "DEL", lat: 28.6139, lon: 77.2090, environment: {} },
    { id: "GZB", name: "GZB", lat: 28.6692, lon: 77.4538, environment: {} },
    { id: "NDLS", name: "NDLS", lat: 28.6431, lon: 77.2195, environment: {} },
    { id: "JP", name: "JP", lat: 26.9124, lon: 75.7873, environment: {} },
    { id: "ADI", name: "ADI", lat: 23.0225, lon: 72.5714, environment: {} },
    { id: "RJT", name: "RJT", lat: 22.3072, lon: 70.8022, environment: {} },
    { id: "CSTM", name: "CSTM", lat: 18.9398, lon: 72.8355, environment: {} },
    { id: "PNQ", name: "PNQ", lat: 18.5204, lon: 73.8567, environment: {} },
    { id: "KYN", name: "KYN", lat: 19.2183, lon: 73.0867, environment: {} },
    { id: "SUR", name: "SUR", lat: 21.1702, lon: 72.8311, environment: {} },
    { id: "HYB", name: "HYB", lat: 17.3850, lon: 78.4867, environment: {} },
    { id: "SC", name: "SC", lat: 17.4399, lon: 78.4983, environment: {} },
    { id: "NGP", name: "NGP", lat: 21.1458, lon: 79.0882, environment: {} },
    { id: "BPL", name: "BPL", lat: 23.2599, lon: 77.4126, environment: {} },
    { id: "ET", name: "ET", lat: 21.9050, lon: 77.4830, environment: {} },
    { id: "CNB", name: "CNB", lat: 26.4499, lon: 80.3319, environment: {} },
    { id: "LKO", name: "LKO", lat: 26.8467, lon: 80.9462, environment: {} },
    { id: "PNBE", name: "PNBE", lat: 25.5941, lon: 85.1376, environment: {} },
    { id: "HWH", name: "HWH", lat: 22.5850, lon: 88.3460, environment: {} },
    { id: "BBS", name: "BBS", lat: 20.2961, lon: 85.8245, environment: {} },
    { id: "VSKP", name: "VSKP", lat: 17.6868, lon: 83.2185, environment: {} },
    { id: "MAS", name: "MAS", lat: 13.0827, lon: 80.2707, environment: {} },
    { id: "BNC", name: "BNC", lat: 12.9716, lon: 77.5946, environment: {} },
    { id: "SBC", name: "SBC", lat: 12.9779, lon: 77.5795, environment: {} },
    { id: "UBL", name: "UBL", lat: 15.3647, lon: 75.1240, environment: {} },
    { id: "MAQ", name: "MAQ", lat: 12.9141, lon: 74.8560, environment: {} },
    { id: "TVC", name: "TVC", lat: 8.5241, lon: 76.9366, environment: {} },
    { id: "ERS", name: "ERS", lat: 9.9816, lon: 76.2999, environment: {} },
    { id: "JHS", name: "JHS", lat: 25.4484, lon: 78.5685, environment: {} }
  ];

  const filledStations = baseStations.map(st => ({
    ...st,
    environment: generateStationEnvironment(st.id)
  }));

  const baseEdges: Edge[] = [
    { source: "DEL", target: "GZB" },
    { source: "GZB", target: "NDLS" },
    { source: "NDLS", target: "JP" },
    { source: "JP", target: "ADI" },
    { source: "ADI", target: "RJT" },
    { source: "ADI", target: "CSTM" },
    { source: "CSTM", target: "PNQ" },
    { source: "PNQ", target: "KYN" },
    { source: "KYN", target: "SUR" },
    { source: "SUR", target: "HYB" },
    { source: "HYB", target: "SC" },
    { source: "SC", target: "NGP" },
    { source: "NGP", target: "BPL" },
    { source: "BPL", target: "ET" },
    { source: "ET", target: "CNB" },
    { source: "CNB", target: "LKO" },
    { source: "LKO", target: "PNBE" },
    { source: "PNBE", target: "HWH" },
    { source: "HWH", target: "BBS" },
    { source: "BBS", target: "VSKP" },
    { source: "VSKP", target: "MAS" },
    { source: "MAS", target: "BNC" },
    { source: "BNC", target: "SBC" },
    { source: "SBC", target: "UBL" },
    { source: "UBL", target: "MAQ" },
    { source: "MAQ", target: "ERS" },
    { source: "ERS", target: "TVC" }
  ];

  const scenario10Trains: Train[] = [
    {
      id: "T1",
      name: "Rajdhani Express DEL → MAS",
      source: "DEL",
      destination: "MAS",
      path: ["DEL", "NDLS", "CNB", "LKO", "BPL", "SC", "MAS"],
      speed: 150,
      priority: 3,
      progress: 0.13,
      lat: 26.594844,
      lon: 77.607021,
      status: "RUNNING",
      params: {}
    },
    {
      id: "T2",
      name: "Shatabdi CNB → DEL",
      source: "CNB",
      destination: "DEL",
      path: ["CNB", "LKO", "NDLS", "DEL"],
      speed: 120,
      priority: 3,
      progress: 0.51,
      lat: 27.55354,
      lon: 78.739221,
      status: "RUNNING",
      params: {}
    },
    {
      id: "T3",
      name: "Hyderabad Superfast HYB → DEL",
      source: "HYB",
      destination: "DEL",
      path: ["HYB", "SC", "BPL", "LKO", "NDLS", "DEL"],
      speed: 110,
      priority: 2,
      progress: 0.37,
      lat: 21.539693,
      lon: 77.913951,
      status: "RUNNING",
      params: {}
    },
    {
      id: "T4",
      name: "South India Express MAS → TVC",
      source: "MAS",
      destination: "TVC",
      path: ["MAS", "BNC", "SBC", "ERS", "TVC"],
      speed: 100,
      priority: 1,
      progress: 0.24,
      lat: 12.988636,
      lon: 79.470516,
      status: "RUNNING",
      params: {}
    },
    {
      id: "T5",
      name: "Kolkata Jan Shatabdi BBS → PNBE",
      source: "BBS",
      destination: "PNBE",
      path: ["BBS", "HWH", "PNBE"],
      speed: 90,
      priority: 2,
      progress: 0.62,
      lat: 23.58086,
      lon: 85.398782,
      status: "RUNNING",
      params: {}
    },
    {
      id: "T6",
      name: "VSKP Express VSKP → MAS",
      source: "VSKP",
      destination: "MAS",
      path: ["VSKP", "BBS", "HWH", "MAS"],
      speed: 130,
      priority: 2,
      progress: 0.44,
      lat: 15.660996,
      lon: 81.921868,
      status: "RUNNING",
      params: {}
    },
    {
      id: "T7",
      name: "Bangalore Mail BNC → SC",
      source: "BNC",
      destination: "SC",
      path: ["BNC", "SBC", "UBL", "HYB", "SC"],
      speed: 100,
      priority: 1,
      progress: 0.29,
      lat: 14.267407,
      lon: 77.856673,
      status: "RUNNING",
      params: {}
    },
    {
      id: "T8",
      name: "Coastal Express MAS → VSKP",
      source: "MAS",
      destination: "VSKP",
      path: ["MAS", "BNC", "SBC", "MAS", "VSKP"],
      speed: 95,
      priority: 2,
      progress: 0.15,
      lat: 13.773315,
      lon: 80.71287,
      status: "RUNNING",
      params: {}
    },
    {
      id: "T9",
      name: "Patna SF PNBE → DEL",
      source: "PNBE",
      destination: "DEL",
      path: ["PNBE", "LKO", "CNB", "NDLS", "DEL"],
      speed: 105,
      priority: 3,
      progress: 0.33,
      lat: 26.590634,
      lon: 82.521162,
      status: "RUNNING",
      params: {}
    },
    {
      id: "T10",
      name: "Local Shuttle LKO → CNB",
      source: "LKO",
      destination: "CNB",
      path: ["LKO", "CNB"],
      speed: 60,
      priority: 1,
      progress: 0.78,
      lat: 26.537196,
      lon: 80.467046,
      status: "RUNNING",
      params: {}
    }
  ];

  const builtinTrains = scenario10Trains;

  // ensure each train has params computed
  const allTrains = builtinTrains.map(t => ({
    ...t,
    params: makeParamsForSnapshot([], filledStations, baseEdges)
  }));

  return {
    stations: filledStations,
    edges: baseEdges,
    trains: allTrains,
    blockedEdges: [],
    trackSegments: {},

    addNode: (name, lat, lon) => set(state => {
      const newStations = [...state.stations, { id: name, name, lat, lon, environment: {} }];
      // Compute new TRACK parameters when adding a station
      const trackParams = computeTrackParameters(newStations, state.edges);
      // Compute ENVIRONMENT parameters
      const envParams = computeEnvironmentParameters(newStations, trackParams);
      // Update all trains to include updated track and env params
      const updatedTrains = state.trains.map((t) => ({
        ...t,
        params: {
          ...t.params,
          ...trackParams, // inject p21 - p40
          ...envParams,   // inject p81 - p100
        },
      }));
      return {
        stations: newStations,
        trains: updatedTrains,
      };
    }),

    addEdge: (sourceName, targetName) => set(state => {
      const exists = get().edges.some(e =>
        (e.source === sourceName && e.target === targetName) ||
        (e.source === targetName && e.target === sourceName)
      );
      if (exists) return get();
      const newEdges = [...get().edges, { source: sourceName, target: targetName }];
      // Compute new TRACK parameters when declaring a track
      const trackParams = computeTrackParameters(get().stations, newEdges);
      // Compute ENVIRONMENT parameters
      const envParams = computeEnvironmentParameters(get().stations, trackParams);
      // Update all trains to include updated track and env params
      const updatedTrains = get().trains.map((t) => ({
        ...t,
        params: {
          ...t.params,
          ...trackParams,   // p21–p40
          ...envParams      // p81–p100
        },
      }));
      return {
        edges: newEdges,
        trains: updatedTrains,
      };
    }),

    updateTrainProgress: (id, progress) => set(state => {
      const newTrains = state.trains.map(t => {
        if (t.id === id) {
          const reached = progress >= 0.98;
          return { ...t, progress, reachedDestination: reached };
        }
        return t;
      });

      // recompute p1-p20 after movement
      const newParams = computeTrainParameters(newTrains);

      const collisionParams = computeCollisionParameters(newTrains);
      const networkParams = computeNetworkLoadParameters(newTrains, state.stations, state.edges, collisionParams);
      const trackParams = computeTrackParameters(state.stations, state.edges);
      const envParams = computeEnvironmentParameters(state.stations, trackParams);
      const safetyParams = computeSafetyParameters(newTrains, state.edges);
      const healthParams = computeHealthParameters(newTrains);

      const finalList = newTrains.map((t) => ({
        ...t,
        params: {
          ...t.params,
          ...newParams,
          ...collisionParams,
          ...networkParams,
          ...envParams,
          ...safetyParams,
          ...healthParams
        },
      }));

      return { trains: finalList };
    }),

    updateTrainStatus: (id, status) => set(state => {
      const newTrains = state.trains.map(t => {
        if (t.id === id) {
          return { ...t, status };
        }
        return t;
      });

      // recompute p1-p20 after status change
      const newParams = computeTrainParameters(newTrains);

      const finalList = newTrains.map((t) => ({
        ...t,
        params: {
          ...t.params,
          ...newParams,
        },
      }));

      return { trains: finalList };
    }),

    updateTrainPath: (id, newPath) => set(state => {
      const newTrains = state.trains.map(t => {
        if (t.id === id) {
          const changed = JSON.stringify(t.path) !== JSON.stringify(newPath);
          return { ...t, path: newPath, progress: changed ? 0 : t.progress, status: "MOVING", params: makeParamsForSnapshot(state.trains, state.stations, state.edges) };
        }
        return t;
      });
      return { trains: newTrains };
    }),

    updateTrainSpeed: (id, newSpeed) => set(state => {
      const changed = state.trains.map(t =>
        t.id === id ? { ...t, speed: newSpeed } : t
      );

      const collisionParams = computeCollisionParameters(changed);

      return {
        trains: changed.map((t) => ({
          ...t,
          params: { ...t.params, ...collisionParams }
        })),
      };
    }),

    getPath: (source, dest) => {
      // simple BFS on edges (undirected)
      const adj: Record<string, string[]> = {};
      get().stations.forEach(s => adj[s.name] = []);
      get().edges.forEach(e => { adj[e.source].push(e.target); adj[e.target].push(e.source); });
      const q: string[] = [source];
      const visited = new Set<string>([source]);
      const parent: Record<string,string> = {};
      while (q.length) {
        const cur = q.shift()!;
        if (cur === dest) break;
        for (const n of adj[cur] || []) {
          if (!visited.has(n)) { visited.add(n); parent[n] = cur; q.push(n); }
        }
      }
      if (!parent[dest]) return null;
      const path: string[] = [];
      let cur = dest;
      while (cur !== source) { path.unshift(cur); cur = parent[cur]; }
      path.unshift(source);
      return path;
    },

    addTrain: (name, source, dest, speed = 100) => set(state => {
      const id = crypto.randomUUID();

      // Path must have starting and ending stations
      const path = [source, dest];

      const start = get().stations.find(s => s.name === source);
      const newTrain: Train = {
        id,
        name,
        source,
        destination: dest,
        progress: 0,
        speed,
        path,
        startTime: Date.now(),
        status: "RUNNING",
        lat: start?.lat ?? 0,
        lon: start?.lon ?? 0,
        priority: 1,
        reachedDestination: false,
        params: {} // will be filled below
      };
      const allTrains = [...state.trains, newTrain];
      // Compute TRAIN parameters for all trains including the new one
      const trainParams = computeTrainParameters(allTrains);
      // Also include track params
      const trackParams = computeTrackParameters(state.stations, state.edges);
      // Compute COLLISION parameters
      const collisionParams = computeCollisionParameters(allTrains);
      // Compute ENVIRONMENT parameters
      const envParams = computeEnvironmentParameters(state.stations, trackParams);
      const finalTrains = allTrains.map((t) => ({
        ...t,
        params: {
          ...trainParams, // p1 - p20
          ...trackParams, // p21 - p40
          ...collisionParams, // p61 - p80
          ...envParams, // p81 - p100
        },
      }));
      return { trains: finalTrains };
    }),

    setBlockedEdge: (edge) => set(state => {
      const next = [...state.blockedEdges, edge];
      const newParams = makeParamsForSnapshot(state.trains, state.stations, state.edges);
      return { blockedEdges: next, trains: state.trains.map(t => ({ ...t, params: newParams })) };
    }),

    clearBlockedEdge: (edge) => set(state => {
      const filtered = state.blockedEdges.filter(([a,b]) => !(a === edge[0] && b === edge[1]) && !(a === edge[1] && b === edge[0]));
      const newParams = makeParamsForSnapshot(state.trains, state.stations, state.edges);
      return { blockedEdges: filtered, trains: state.trains.map(t => ({ ...t, params: newParams })) };
    })
  };
});
=======
  blockedEdges: [string, string][];
  environment: EnvironmentData | null;        // ← NEW!
  switchStates: Record<string, string>; // map switchNodeId -> selected edgeId

  addNode(name: string, lat: number, lon: number): void;
  addEdge(a: string, b: string): void;
  addTrain(name: string, source: string, dest: string, speed: number): void;
  addTrainOnGraphPath: (name: string, path: string[], speed?: number) => void;
  toggleSwitch: (switchNodeId: string, chooseEdgeId?: string) => void;

  updateTrainProgress(id: string, p: number): void;
  updateTrainStatus(id: string, s: string): void;
  updateTrainPath(id: string, path: string[]): void;
  updateTrainParameters(id: string, ttc?: number, riskLevel?: number): void;

  getPath(source: string, dest: string): string[] | null;
  getPathRespectingSwitches: (source: string, dest: string) => string[] | null;

  // Optional: clean way to set environment from backend
  setEnvironment(env: EnvironmentData): void;
}

export const useRailwayStore = create<RailwayState>((set, get) => ({
  // --------------------------------------------------------------
  // INITIAL STATE
  // --------------------------------------------------------------
  stations: INDIA_STATIONS,
  edges: INDIA_EDGES,
  trains: [],
  blockedEdges: [],
  environment: null,                         // ← initialized
  switchStates: {},                           // ← initialized

  // --------------------------------------------------------------
  addNode: (name, lat, lon) =>
    set(state => ({
      stations: [...state.stations, { name, lat, lon }]
    })),

  addEdge: (a, b) =>
    set(state => {
      if (state.edges.find(e =>
        (e.source === a && e.target === b) ||
        (e.source === b && e.target === a)
      )) return state;

      return {
        edges: [...state.edges, { source: a, target: b }]
      };
    }),

  getPath: (source, dest) => bfsPath(source, dest, get().edges),

  addTrain: (name, source, dest, speed) =>
    set(state => {
      const path = bfsPath(source, dest, state.edges);
      if (!path) return state;

      const id = `T${Date.now()}`;
      const s = state.stations.find(st => st.name === path[0]);

      const newTrain: Train = {
        id,
        name,
        path,
        progress: 0,
        currentSegment: 0,
        segmentProgress: 0,
        speed,
        status: "MOVING",
        lat: s?.lat ?? 0,
        lon: s?.lon ?? 0,
        reachedDestination: false
      };

      return { trains: [...state.trains, newTrain] };
    }),

  addTrainOnGraphPath: (name: string, path: string[], speed = 90) => {
    const id = crypto.randomUUID();

    const s = get().stations.find(st => st.name === path[0]);

    set(state => ({
      trains: [
        ...state.trains,
        {
          id,
          name,
          path,
          progress: 0,
          currentSegment: 0,
          segmentProgress: 0,
          speed,
          status: "MOVING",
          lat: s?.lat ?? 0,
          lon: s?.lon ?? 0,
          reachedDestination: false
        }
      ]
    }));
  },

  toggleSwitch: (switchNodeId: string, chooseEdgeId?: string) => set(state => {
    // find outgoing edges from this switch node
    const outs = state.edges.filter(e => e.source === switchNodeId || e.target === switchNodeId)
      .map(e => {
        // produce canonical edge id consistent with edge definitions
        return (e.source === switchNodeId) ? `${e.source}-${e.target}` : `${e.target}-${e.source}`;
      });

    // If user provided chooseEdgeId validate, else toggle between available outs
    let newChoice = chooseEdgeId ?? outs[0];
    if (!outs.includes(newChoice)) {
      // choose first valid if provided invalid
      newChoice = outs[0];
    }

    const next = { ...state.switchStates, [switchNodeId]: newChoice };
    return { switchStates: next };
  }),

  updateTrainProgress: (id, p) =>
    set(state => ({
      trains: state.trains.map(t =>
        t.id === id
          ? { ...t, progress: p, reachedDestination: p >= 0.995 }
          : t
      )
    })),

  updateTrainStatus: (id, s) =>
    set(state => ({
      trains: state.trains.map(t =>
        t.id === id ? { ...t, status: s } : t
      )
    })),

  updateTrainPath: (id, newPath) =>
    set(state => ({
      trains: state.trains.map(t =>
        t.id === id
          ? { ...t, path: newPath, progress: 0, status: "MOVING" }
          : t
      )
    })),

  updateTrainParameters: (id, ttc, riskLevel) =>
    set(state => ({
      trains: state.trains.map(t =>
        t.id === id ? { ...t, ttc, riskLevel } : t
      )
    })),

  getPathRespectingSwitches: (source: string, dest: string) => {
    // build adjacency but filter edges by switch states
    const adj: Record<string, string[]> = {};
    get().stations.forEach(s => adj[s.name] = []);

    // helper to canonical edge id
    function edgeId(a: string, b: string) { return `${a}-${b}`; }

    get().edges.forEach(e => {
      const a = e.source, b = e.target;
      // check if a is a switch and whether it's selecting this edge
      const aIsSwitch = !!NODES.find(n => n.id === a && n.isSwitch);
      const bIsSwitch = !!NODES.find(n => n.id === b && n.isSwitch);

      // For undirected: consider both directions but respect switch at source of direction
      const allowAtoB = !(aIsSwitch) || get().switchStates[a] === edgeId(a,b) || !get().switchStates[a];
      const allowBtoA = !(bIsSwitch) || get().switchStates[b] === edgeId(b,a) || !get().switchStates[b];

      if (allowAtoB) adj[a].push(b);
      if (allowBtoA) adj[b].push(a);
    });

    // BFS
    const q: string[] = [source];
    const visited = new Set<string>([source]);
    const parent: Record<string,string> = {};
    while (q.length) {
      const cur = q.shift()!;
      if (cur === dest) break;
      for (const n of adj[cur] || []) {
        if (!visited.has(n)) { visited.add(n); parent[n] = cur; q.push(n); }
      }
    }
    if (!parent[dest] && source !== dest) return null;
    const path: string[] = [];
    let cur = dest;
    while (cur !== source) { path.unshift(cur); cur = parent[cur]; }
    path.unshift(source);
    return path;
  },

  // NEW: Receive full environment from backend
  setEnvironment: (env) => set({ environment: env }),
}));

// Optional convenience selector (highly recommended)
export const useEnvironment = () => useRailwayStore(s => s.environment);
>>>>>>> 42b56fc74ed4d9318fd8a98b55c9f9214c9b0ffd
