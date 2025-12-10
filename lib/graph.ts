// app/lib/graph.ts
export type Node = {
  id: string;
  lat: number;
  lon: number;
  name?: string;
  isSwitch?: boolean; // optionally mark a node as a switch
};

export type Edge = {
  id: string;           // unique id for edge (useful for switches)
  from: string;         // node id
  to: string;           // node id
  directed?: boolean;   // if true: only from -> to allowed; otherwise undirected
  length?: number;      // meters (computed later)
  meta?: Record<string, any>;
};

// Example network containing branching/switches
export const NODES: Node[] = [
  { id: "A", lat: 28.7041, lon: 77.1025, name: "Delhi" },
  { id: "B", lat: 27.1767, lon: 78.0081, name: "Agra" },
  { id: "C", lat: 26.9124, lon: 75.7873, name: "Jaipur", isSwitch: true }, // switch node
  { id: "D", lat: 25.3176, lon: 82.9739, name: "Varanasi" },
  { id: "E", lat: 23.0225, lon: 72.5714, name: "Ahmedabad" },
  { id: "F", lat: 24.0, lon: 76.0, name: "Branch1" },
  { id: "G", lat: 25.0, lon: 77.0, name: "Branch2" }
];

export const EDGES: Edge[] = [
  { id: "A-B", from: "A", to: "B" },
  { id: "B-C", from: "B", to: "C" },
  // from C there is a branching: C->D and C->E (switch)
  { id: "C-D", from: "C", to: "D" },
  { id: "C-E", from: "C", to: "E" },
  // extra branches
  { id: "B-F", from: "B", to: "F" },
  { id: "B-G", from: "B", to: "G" }
];

// small helper to compute haversine & set length
export function computeEdgeLengths(nodes: Node[], edges: Edge[]) {
  const nodeMap: Record<string, Node> = {};
  nodes.forEach((n) => (nodeMap[n.id] = n));

  const R = 6371000;
  function hav(n1: Node, n2: Node) {
    const dLat = ((n2.lat - n1.lat) * Math.PI) / 180;
    const dLon = ((n2.lon - n1.lon) * Math.PI) / 180;
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos(n1.lat * Math.PI / 180) *
        Math.cos(n2.lat * Math.PI / 180) *
        Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }

  edges.forEach((e) => {
    const A = nodeMap[e.from];
    const B = nodeMap[e.to];
    e.length = A && B ? hav(A, B) : 0;
  });
}

computeEdgeLengths(NODES, EDGES);
