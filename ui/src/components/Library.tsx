import React from "react";
import { BentoTile } from "./BentoTile";
import { useProfile } from "../hooks/useProfile";
import { open } from "@tauri-apps/plugin-dialog";
import { UploadCloud, DownloadCloud, FileText } from "lucide-react";
import PRESETS from "../presets.json";

export const Library: React.FC = () => {
  const { profile, importFromXml, isLoaded, updateProfile } = useProfile();

  if (!isLoaded) return null;

  const handleImport = async () => {
    const file = await open({
      multiple: false,
      filters: [{ name: "DAX3 XML", extensions: ["xml"] }],
    });
    if (file && typeof file === "string") {
      await importFromXml(file);
    }
  };

  const handleLoadPreset = async (presetProfile: any) => {
    await updateProfile(presetProfile);
    alert(`Successfully applied profile: ${presetProfile.name}`);
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-6xl mx-auto w-full view-reveal-card">
      <BentoTile title="Import DAX3 Tuning" description="Extract Dolby Atmos profiles directly from Windows DriverStore XML files.">
        <div 
          onClick={handleImport}
          className="mt-6 border-2 border-dashed border-border rounded-xl p-8 flex flex-col items-center justify-center cursor-pointer hover:border-primary hover:bg-primary/5 transition-colors"
        >
          <UploadCloud className="w-12 h-12 text-muted-foreground mb-4" />
          <div className="text-sm font-semibold">Click to browse for XML</div>
          <div className="text-xs text-muted-foreground mt-1">dax3_ext_*.xml</div>
        </div>

        <div className="mt-6 p-4 bg-muted/50 rounded-xl border border-border">
          <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Current Loaded Profile</div>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/20 rounded-lg text-primary">
              <FileText className="w-4 h-4" />
            </div>
            <div className="font-medium text-sm">{profile.name}</div>
          </div>
        </div>
      </BentoTile>

      <BentoTile title="Community Hub" description="Browse and download reverse-engineered profiles for your laptop." badge="Coming Soon">
        <div className="mt-6 space-y-3">
          {PRESETS.map((preset) => (
            <div key={preset.id} className="p-4 rounded-xl bg-surface border border-border flex items-center justify-between hover:border-primary/50 transition-colors cursor-pointer" onClick={() => handleLoadPreset(preset.profile)}>
              <div>
                <div className="text-sm font-semibold">{preset.name}</div>
                <div className="text-xs text-muted-foreground mt-1">by {preset.author}</div>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs font-medium text-muted-foreground">{preset.downloads} <DownloadCloud className="w-3 h-3 inline ml-1"/></span>
                <button className="px-3 py-1.5 bg-primary/10 text-primary rounded-lg text-xs font-semibold hover:bg-primary hover:text-white transition-colors">
                  Get
                </button>
              </div>
            </div>
          ))}
        </div>
      </BentoTile>
    </div>
  );
};
