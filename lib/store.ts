// lib/store.ts
import { create } from "zustand";
import { compute140Parameters } from "./compute140Parameters";
import { NODES } from "./graph";

// ================================================================
// TYPES
// ================================================================
export interface Station {
  name: string;
  lat: number;
  lon: number;
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