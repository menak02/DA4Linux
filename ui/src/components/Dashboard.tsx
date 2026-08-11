import React from "react";
import { BentoTile } from "./BentoTile";
import { Volume2, HardDrive, RefreshCw, PowerOff } from "lucide-react";
import { invoke } from "@tauri-apps/api/core";
import { useProfile } from "../hooks/useProfile";

export const Dashboard: React.FC = () => {
  const { regenerateDsp } = useProfile();
  const [isBypassed, setIsBypassed] = React.useState(false);

  React.useEffect(() => {
    async function checkDspStatus() {
      try {
        const active = await invoke<boolean>("is_dsp_active");
        setIsBypassed(!active);
      } catch (e) {
        console.error("Failed to check active DSP state:", e);
      }
    }
    checkDspStatus();
  }, []);

  const handleRegenerate = async () => {
    try {
      const stdout = await regenerateDsp();
      setIsBypassed(false);
      alert(stdout || "DSP Profile applied successfully.");
    } catch (e) {
      alert("Error: " + e);
    }
  };

  const toggleBypass = async () => {
    try {
      if (isBypassed) {
        // Restore DSP
        const stdout = await regenerateDsp();
        setIsBypassed(false);
        alert(stdout || "DSP Profile restored successfully.");
      } else {
        // Bypass DSP
        await invoke("bypass_dsp_profile");
        setIsBypassed(true);
        alert("DSP Profile bypassed successfully.");
      }
    } catch (e) {
      alert("Error: " + e);
    }
  };

  const handleRestartServer = async () => {
    try {
      await invoke("restart_pipewire");
      // Check status again after restart
      setTimeout(async () => {
        try {
          const active = await invoke<boolean>("is_dsp_active");
          setIsBypassed(!active);
        } catch (e) {
          console.error("Failed to re-check DSP state after restart:", e);
        }
      }, 1000);
      alert("PipeWire server restarted successfully.");
    } catch (e) {
      alert("Error: " + e);
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto w-full view-reveal-card">
      <BentoTile
        title="Master Control"
        description="Global volume limiter and loudness maximization settings."
        badge="Active"
        className="md:col-span-2 row-span-2 flex flex-col justify-between shadow-[var(--shadow-neumorphic-raised)]"
      >
        <div className="flex-1 flex flex-col items-center justify-center py-8">
          <Volume2 className="w-16 h-16 text-primary mb-6 opacity-80" />
          <div className="text-5xl font-black tracking-tighter">+13.0<span className="text-2xl text-muted-foreground">dB</span></div>
          <div className="text-sm font-medium text-primary mt-2">Loudness Maximizer Running</div>
        </div>
        
        <div className="flex gap-4 mt-auto">
          <button onClick={handleRegenerate} className="flex-1 bg-primary text-primary-foreground font-semibold py-3 rounded-xl shadow-lg hover:bg-primary-hover transition-colors cursor-pointer">
            Regenerate DSP
          </button>
          <button 
            onClick={toggleBypass} 
            className={`px-6 font-medium py-3 rounded-xl transition-colors flex items-center justify-center gap-2 cursor-pointer ${
              isBypassed 
                ? "bg-destructive text-destructive-foreground hover:bg-destructive-hover" 
                : "bg-destructive/10 text-destructive hover:bg-destructive/20"
            }`}
            title={isBypassed ? "Restore DSP" : "Global Bypass"}
          >
            <PowerOff className="w-4 h-4" /> {isBypassed ? "Bypassed" : "Bypass"}
          </button>
          <button onClick={handleRestartServer} className="flex-1 bg-surface border border-border font-medium py-3 rounded-xl hover:bg-surface-hover transition-colors flex items-center justify-center gap-2 cursor-pointer">
            <RefreshCw className="w-4 h-4" /> Restart Server
          </button>
        </div>
      </BentoTile>

      <BentoTile
        title="Profile"
        description="Current hardware profile in use."
      >
        <div className="mt-4 p-4 bg-muted/50 rounded-xl border border-border">
          <div className="text-sm font-mono text-foreground font-semibold">Custom UI Profile</div>
          <div className="text-xs text-muted-foreground mt-1">Edited locally</div>
        </div>
      </BentoTile>

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
    </div>
  );
};

