"use client";

import React, { useEffect, useState } from "react";

interface ParameterData {
  [key: string]: number;
}

interface RiskBreakdown {
  collision: number;
  overcrowding: number;
  speed: number;
  health: number;
  other: number;
}

export default function AIDebugDashboard() {
  const [parameters, setParameters] = useState<ParameterData | null>(null);
  const [riskBreakdown, setRiskBreakdown] = useState<RiskBreakdown | null>(null);
  const [isVisible, setIsVisible] = useState(false);

  // Fetch parameters periodically
  useEffect(() => {
    if (!isVisible) return;

    const fetchParameters = async () => {
      try {
        const response = await fetch('http://localhost:8001/parameters_full');
        const data = await response.json();
        setParameters(data);

        // Calculate risk breakdown
        const risk = {
          collision: (data.P61 || 0) + (data.P62 || 0) + (data.P63 || 0),
          overcrowding: (data.P11 || 0) + (data.P12 || 0) + (data.P13 || 0),
          speed: (data.P31 || 0) + (data.P32 || 0) + (data.P33 || 0),
          health: (data.P1 || 0) + (data.P2 || 0) + (data.P3 || 0),
          other: (data.P91 || 0) + (data.P92 || 0) + (data.P93 || 0)
        };
        setRiskBreakdown(risk);
      } catch (error) {
        console.error('Failed to fetch parameters:', error);
      }
    };

    fetchParameters();
    const interval = setInterval(fetchParameters, 2000); // Update every 2 seconds
    return () => clearInterval(interval);
  }, [isVisible]);

  const getParameterGroup = (start: number, end: number) => {
    const params: { [key: string]: number } = {};
    for (let i = start; i <= end; i++) {
      const key = `P${i}`;
      params[key] = parameters?.[key] || 0;
    }
    return params;
  };

  const renderParameterGroup = (title: string, params: { [key: string]: number }, color: string) => (
    <div className="bg-gray-800 rounded-lg p-4">
      <h3 className={`text-lg font-bold mb-3 text-${color}-400`}>{title}</h3>
      <div className="grid grid-cols-5 gap-2 text-xs">
        {Object.entries(params).map(([key, value]) => (
          <div key={key} className="bg-gray-700 rounded p-2 text-center">
            <div className="text-gray-400">{key}</div>
            <div className={`text-${color}-400 font-bold`}>{value.toFixed(3)}</div>
          </div>
        ))}
      </div>
    </div>
  );

  const renderRiskChart = () => {
    if (!riskBreakdown) return null;

    const total = Object.values(riskBreakdown).reduce((a, b) => a + b, 0);
    const percentages = Object.entries(riskBreakdown).map(([key, value]) => ({
      category: key,
      percentage: total > 0 ? (value / total) * 100 : 0
    }));

    return (
      <div className="bg-gray-800 rounded-lg p-4">
        <h3 className="text-lg font-bold mb-3 text-red-400">Risk Breakdown</h3>
        <div className="space-y-2">
          {percentages.map(({ category, percentage }) => (
            <div key={category} className="flex items-center">
              <div className="w-20 text-sm capitalize">{category}</div>
              <div className="flex-1 bg-gray-700 rounded-full h-4 mx-2">
                <div
                  className="bg-red-500 h-4 rounded-full transition-all duration-300"
                  style={{ width: `${percentage}%` }}
                />
              </div>
              <div className="w-12 text-sm text-right">{percentage.toFixed(1)}%</div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  if (!isVisible) {
    return (
      <button
        onClick={() => setIsVisible(true)}
        className="fixed bottom-4 right-4 bg-cyan-600 hover:bg-cyan-500 text-white px-4 py-2 rounded-lg font-bold z-50"
      >
        AI DEBUG
      </button>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/90 backdrop-blur-lg z-50 overflow-auto">
      <div className="min-h-screen p-6">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="flex justify-between items-center mb-6">
            <h1 className="text-3xl font-bold text-cyan-400">AI Debug Dashboard</h1>
            <button
              onClick={() => setIsVisible(false)}
              className="bg-red-600 hover:bg-red-500 text-white px-4 py-2 rounded-lg font-bold"
            >
              CLOSE
            </button>
          </div>

          {/* Parameter Groups */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {renderParameterGroup("Network Health (P1-P10)", getParameterGroup(1, 10), "green")}
            {renderParameterGroup("Crowding (P11-P20)", getParameterGroup(11, 20), "yellow")}
            {renderParameterGroup("Speed Anomalies (P31-P40)", getParameterGroup(31, 40), "blue")}
            {renderParameterGroup("Collision Risks (P61-P70)", getParameterGroup(61, 70), "red")}
            {renderParameterGroup("Segment Risks (P91-P100)", getParameterGroup(91, 100), "purple")}
          </div>

          {/* Risk Breakdown Chart */}
          <div className="mb-6">
            {renderRiskChart()}
          </div>

          {/* Live Parameters Grid */}
          <div className="bg-gray-800 rounded-lg p-4">
            <h3 className="text-lg font-bold mb-3 text-cyan-400">All Parameters (Live)</h3>
            <div className="grid grid-cols-7 gap-1 text-xs max-h-96 overflow-auto">
              {parameters && Object.entries(parameters).map(([key, value]) => (
                <div key={key} className="bg-gray-700 rounded p-2 text-center">
                  <div className="text-gray-400">{key}</div>
                  <div className="text-cyan-400 font-bold">{value.toFixed(4)}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
