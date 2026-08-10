import { BentoTile } from "./components/BentoTile";
import { AICommandPalette } from "./components/AICommandPalette";
import { Volume2, HardDrive, RefreshCw } from "lucide-react";
import { Command } from "@tauri-apps/plugin-shell";

function App() {
  const runCommand = async (args: string[]) => {
    try {
      const command = Command.sidecar("bin/da4linux-cli", args);
      const output = await command.execute();
      console.log(output.stdout);
      alert(output.stdout || output.stderr || "Command executed successfully.");
    } catch (e) {
      console.error(e);
      alert("Error: " + e);
    }
  };

  const commands = [
    { id: "1", label: "Regenerate Config", onSelect: () => runCommand(["generate"]) },
    { id: "2", label: "Restart PipeWire", onSelect: () => runCommand(["restart-pipewire"]) },
    { id: "3", label: "Check Status", onSelect: () => runCommand(["status"]) },
  ];

  return (
    <div className="min-h-screen bg-background text-foreground p-8">
      {/* Header */}
      <header className="mb-12 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">DA4Linux</h1>
          <p className="text-muted-foreground mt-1">Dolby Atmos DSP Engine for Linux</p>
        </div>
        <button
          onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }))}
          className="flex items-center gap-2 bg-surface hover:bg-surface-hover border border-border px-4 py-2 rounded-xl transition-colors text-sm font-medium shadow-sm"
        >
          <span>Command Palette</span>
          <kbd className="font-mono text-[10px] bg-muted px-1.5 py-0.5 rounded text-muted-foreground border border-border">
            Ctrl+K
          </kbd>
        </button>
      </header>

      {/* Main Grid */}
      <main className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto">
        {/* Large Main Control Tile */}
        <BentoTile
          title="Master Control"
          description="Global volume limiter and loudness maximization settings."
          badge="Active"
          className="md:col-span-2 row-span-2 flex flex-col justify-between"
        >
          <div className="flex-1 flex flex-col items-center justify-center py-8">
            <Volume2 className="w-16 h-16 text-primary mb-6 opacity-80" />
            <div className="text-5xl font-black tracking-tighter">+13.0<span className="text-2xl text-muted-foreground">dB</span></div>
            <div className="text-sm font-medium text-primary mt-2">Loudness Maximizer Running</div>
          </div>
          
          <div className="flex gap-4 mt-auto">
            <button onClick={() => runCommand(["generate"])} className="flex-1 bg-primary text-primary-foreground font-semibold py-3 rounded-xl shadow-lg hover:opacity-90 transition-opacity cursor-pointer">
              Regenerate DSP
            </button>
            <button onClick={() => runCommand(["restart-pipewire"])} className="flex-1 bg-surface border border-border font-medium py-3 rounded-xl hover:bg-surface-hover transition-colors flex items-center justify-center gap-2 cursor-pointer">
              <RefreshCw className="w-4 h-4" /> Restart Server
            </button>
          </div>
        </BentoTile>

        {/* Small Settings Tile */}
        <BentoTile
          title="Profile"
          description="Current hardware profile in use."
        >
          <div className="mt-4 p-4 bg-muted/50 rounded-xl border border-border">
            <div className="text-sm font-mono text-foreground font-semibold">LENOVO_20WNS73J00</div>
            <div className="text-xs text-muted-foreground mt-1">Realtek ALC257</div>
          </div>
        </BentoTile>

        {/* Small Hardware Tile */}
        <BentoTile
          title="Output Target"
          description="PipeWire audio sink destination."
        >
          <div className="flex items-center gap-3 mt-4">
            <div className="p-3 bg-primary/10 rounded-full text-primary">
              <HardDrive className="w-5 h-5" />
            </div>
            <div className="truncate text-sm font-medium">alsa_output.pci-0000_00_1f.3...</div>
          </div>
        </BentoTile>

        {/* Stages Tile */}
        <BentoTile
          title="DSP Stages"
          description="Toggle individual processing blocks."
          className="md:col-span-1"
        >
          <div className="space-y-3 mt-4">
            {["Parametric EQ", "Loudness", "Multiband Compressor", "Surround Virtualizer"].map(stage => (
              <label key={stage} className="flex items-center justify-between p-3 rounded-xl border border-border bg-surface hover:border-primary/30 transition-colors cursor-pointer">
                <span className="text-sm font-medium">{stage}</span>
                <input type="checkbox" defaultChecked className="accent-primary w-4 h-4 rounded" />
              </label>
            ))}
          </div>
        </BentoTile>
      </main>

      <AICommandPalette items={commands} />
    </div>
  );
}

export default App;
