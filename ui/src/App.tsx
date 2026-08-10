import { useState } from "react";
import { Tabs } from "./components/Tabs";
import { Dashboard } from "./components/Dashboard";
import { Library } from "./components/Library";
import { DSPEditor } from "./components/DSPEditor";
import { Settings } from "./components/Settings";
import { AICommandPalette } from "./components/AICommandPalette";
import { useSettings } from "./hooks/useSettings";

function App() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const { isLoaded } = useSettings(); // Initializes global root attributes

  if (!isLoaded) return <div className="min-h-screen bg-background" />;

  const TABS = [
    { id: "dashboard", label: "Dashboard" },
    { id: "library", label: "Library" },
    { id: "editor", label: "DSP Editor" },
    { id: "settings", label: "Settings" },
  ];

  return (
    <div className="min-h-screen bg-background text-foreground p-8 pb-24 overflow-y-auto">
      {/* Header */}
      <header className="mb-8 flex flex-col md:flex-row justify-between items-start md:items-center gap-6 max-w-6xl mx-auto w-full">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">DA4Linux</h1>
          <p className="text-muted-foreground mt-1">Dolby Atmos DSP Engine for Linux</p>
        </div>
        
        <div className="flex items-center gap-4">
          <Tabs tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />
          <button
            onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }))}
            className="flex items-center gap-2 bg-surface hover:bg-surface-hover border border-border px-4 py-2 rounded-xl transition-colors text-sm font-medium shadow-[var(--shadow-neumorphic-raised)]"
          >
            <span>Command Palette</span>
            <kbd className="font-mono text-[10px] bg-muted px-1.5 py-0.5 rounded text-muted-foreground border border-border">
              Ctrl+K
            </kbd>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-6xl mx-auto w-full">
        {activeTab === "dashboard" && <Dashboard />}
        {activeTab === "library" && <Library />}
        {activeTab === "editor" && <DSPEditor />}
        {activeTab === "settings" && <Settings />}
      </main>

      <AICommandPalette items={[]} />
    </div>
  );
}

export default App;

