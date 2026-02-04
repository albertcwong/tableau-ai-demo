"use client";

import { useState, useEffect } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function MCPTestPage() {
  const [status, setStatus] = useState<string>("Disconnected");
  const [events, setEvents] = useState<Array<{ time: string; event: string; data: any }>>([]);
  const [eventSource, setEventSource] = useState<EventSource | null>(null);
  const [error, setError] = useState<string | null>(null);

  const connect = () => {
    try {
      setError(null);
      setStatus("Connecting...");
      
      const es = new EventSource(`${API_URL}/mcp/sse`);
      
      es.onopen = () => {
        setStatus("Connected");
        addEvent("Connection opened", {});
      };

      es.addEventListener("connected", (e) => {
        try {
          const data = e.data ? JSON.parse(e.data) : {};
          addEvent("Connected event", data);
        } catch (err) {
          addEvent("Connected event (raw)", e.data || "No data");
        }
      });

      es.addEventListener("heartbeat", (e) => {
        try {
          const data = e.data ? JSON.parse(e.data) : {};
          addEvent("Heartbeat", data);
        } catch (err) {
          addEvent("Heartbeat (raw)", e.data || "No data");
        }
      });

      es.addEventListener("error", (e) => {
        try {
          const data = e.data ? JSON.parse(e.data) : {};
          addEvent("Error event", data);
          setError(data.error || "Unknown error");
        } catch (err) {
          addEvent("Error event (raw)", e.data || "No data");
          setError("Error parsing error event");
        }
      });

      es.onerror = (e) => {
        console.error("EventSource error:", e);
        setStatus("Error");
        setError("Connection error. Check console for details.");
        es.close();
      };

      es.onmessage = (e) => {
        try {
          if (e.data) {
            const data = JSON.parse(e.data);
            addEvent("Message", data);
          } else {
            addEvent("Message (empty)", {});
          }
        } catch (err) {
          addEvent("Message (raw)", e.data || "No data");
        }
      };

      setEventSource(es);
    } catch (err) {
      setError(`Failed to connect: ${err}`);
      setStatus("Error");
    }
  };

  const disconnect = () => {
    if (eventSource) {
      eventSource.close();
      setEventSource(null);
      setStatus("Disconnected");
      addEvent("Disconnected", {});
    }
  };

  const addEvent = (eventType: string, data: any) => {
    setEvents((prev) => [
      {
        time: new Date().toLocaleTimeString(),
        event: eventType,
        data,
      },
      ...prev,
    ]);
  };

  const clearEvents = () => {
    setEvents([]);
  };

  useEffect(() => {
    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [eventSource]);

  return (
    <div className="container mx-auto p-6 max-w-4xl">
      <h1 className="text-3xl font-bold mb-6">MCP Server SSE Test Page</h1>

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-semibold">Connection Status</h2>
            <p className="text-sm text-gray-600">
              Status: <span className={`font-bold ${status === "Connected" ? "text-green-600" : status === "Error" ? "text-red-600" : "text-gray-600"}`}>{status}</span>
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={connect}
              disabled={status === "Connected" || status === "Connecting..."}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              Connect
            </button>
            <button
              onClick={disconnect}
              disabled={status !== "Connected"}
              className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              Disconnect
            </button>
            <button
              onClick={clearEvents}
              className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
            >
              Clear Events
            </button>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded p-3 mb-4">
            <p className="text-red-800 text-sm">{error}</p>
          </div>
        )}

        <div className="bg-gray-50 rounded p-4">
          <h3 className="font-semibold mb-2">Endpoint:</h3>
          <code className="text-sm bg-white p-2 rounded block break-all">{API_URL}/mcp/sse</code>
          <p className="text-xs text-gray-600 mt-2">
            Using API_URL: {API_URL}
          </p>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Events ({events.length})</h2>
          {events.length > 0 && (
            <span className="text-sm text-gray-600">
              Latest: {events[0]?.time}
            </span>
          )}
        </div>

        {events.length === 0 ? (
          <p className="text-gray-500 text-center py-8">No events yet. Click Connect to start receiving SSE events.</p>
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {events.map((event, index) => (
              <div
                key={index}
                className="border rounded p-3 bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <div className="flex justify-between items-start mb-2">
                  <span className="font-semibold text-sm">{event.event}</span>
                  <span className="text-xs text-gray-500">{event.time}</span>
                </div>
                <pre className="text-xs bg-white p-2 rounded overflow-x-auto">
                  {JSON.stringify(event.data, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="mt-6 bg-blue-50 border border-blue-200 rounded p-4">
        <h3 className="font-semibold mb-2">Expected Behavior:</h3>
        <ul className="list-disc list-inside text-sm space-y-1">
          <li>On connect, you should see a "Connected event" with server info</li>
          <li>Every 30 seconds, you should see a "Heartbeat" event</li>
          <li>Events should appear in real-time as they arrive</li>
        </ul>
      </div>
    </div>
  );
}
