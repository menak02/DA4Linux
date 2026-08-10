import React, { useEffect, useState } from "react";
import { BentoTile } from "./BentoTile";
import { useProfile, PEQBand } from "../hooks/useProfile";
import * as Switch from "@radix-ui/react-switch";
import { invoke } from "@tauri-apps/api/core";

export const DSPEditor: React.FC = () => {
  const { profile, updateProfile, isLoaded } = useProfile();
  const [plugins, setPlugins] = useState<string[]>([]);

  useEffect(() => {
    invoke<string[]>("detect_plugins").then(setPlugins).catch(console.error);
  }, []);

  if (!isLoaded) return null;

  const updatePEQBand = (index: number, field: keyof PEQBand, value: number | string | boolean) => {
    const newBands = [...profile.peq_bands];
    newBands[index] = { ...newBands[index], [field]: value };
    updateProfile({ peq_bands: newBands });
  };

  const updateCompressor = (index: number, field: string, value: number) => {
    const newComp = [...profile.mb_compressor];
    newComp[index] = { ...newComp[index], [field]: value };
    updateProfile({ mb_compressor: newComp });
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 max-w-6xl mx-auto w-full view-reveal-card">
      
      {/* Parametric EQ */}
      <BentoTile title="Parametric EQ" description="Speaker correction filters" className="lg:col-span-2">
        <div className="mt-4 overflow-x-auto pb-2">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-muted-foreground uppercase bg-muted/50">
              <tr>
                <th className="px-4 py-3 rounded-l-lg">Type</th>
                <th className="px-4 py-3">Freq (Hz)</th>
                <th className="px-4 py-3">Gain (dB)</th>
                <th className="px-4 py-3">Q-Factor</th>
                <th className="px-4 py-3 rounded-r-lg text-right">Enabled</th>
              </tr>
            </thead>
            <tbody>
              {profile.peq_bands.map((band, idx) => (
                <tr key={idx} className="border-b border-border/50 last:border-0">
                  <td className="px-4 py-3">
                    <select 
                      value={band.filter_type} 
                      onChange={(e) => updatePEQBand(idx, "filter_type", e.target.value)}
                      className="bg-surface text-foreground border border-border rounded px-2 py-1 outline-none focus:border-primary text-xs"
                    >
                      <option className="bg-surface text-foreground" value="peaking">Peaking (Bell)</option>
                      <option className="bg-surface text-foreground" value="highpass">High-Pass</option>
                      <option className="bg-surface text-foreground" value="lowpass">Low-Pass</option>
                      <option className="bg-surface text-foreground" value="highshelf">High-Shelf</option>
                      <option className="bg-surface text-foreground" value="lowshelf">Low-Shelf</option>
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <input type="number" value={band.freq} onChange={(e) => updatePEQBand(idx, "freq", parseFloat(e.target.value))} className="w-20 bg-surface border border-border rounded px-2 py-1 outline-none focus:border-primary text-xs" />
                  </td>
                  <td className="px-4 py-3">
                    <input type="number" step="0.5" value={band.gain} onChange={(e) => updatePEQBand(idx, "gain", parseFloat(e.target.value))} className="w-16 bg-surface border border-border rounded px-2 py-1 outline-none focus:border-primary text-xs" />
                  </td>
                  <td className="px-4 py-3">
                    <input type="number" step="0.1" value={band.q} onChange={(e) => updatePEQBand(idx, "q", parseFloat(e.target.value))} className="w-16 bg-surface border border-border rounded px-2 py-1 outline-none focus:border-primary text-xs" />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Switch.Root
                      checked={band.enabled}
                      onCheckedChange={(checked) => updatePEQBand(idx, "enabled", checked)}
                      className="w-9 h-5 bg-muted rounded-full relative shadow-sm data-[state=checked]:bg-primary outline-none cursor-pointer"
                    >
                      <Switch.Thumb className="block w-4 h-4 bg-white rounded-full transition-transform translate-x-0.5 data-[state=checked]:translate-x-[18px]" />
                    </Switch.Root>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </BentoTile>

      {/* Multiband Compressor */}
      <BentoTile title="Multiband Compressor" description="4-Band dynamic range control">
        {!plugins.includes("lsp-plugins-lv2") && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/50 rounded-lg text-xs text-red-400">
            <strong>LSP Plugins Missing:</strong> Please install <code>lsp-plugins-lv2</code> to use this feature.
          </div>
        )}
        <div className={`mt-4 space-y-4 ${!plugins.includes("lsp-plugins-lv2") ? "opacity-50 pointer-events-none grayscale" : ""}`}>
          {profile.mb_compressor.map((band, idx) => (
            <div key={idx} className="p-3 bg-surface border border-border rounded-xl">
              <div className="text-xs font-semibold mb-3">Band {idx + 1}</div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-muted-foreground">Threshold</span>
                    <span className="font-mono">{band.threshold} dB</span>
                  </div>
                  <input type="range" min="-60" max="0" step="0.5" value={band.threshold} onChange={(e) => updateCompressor(idx, "threshold", parseFloat(e.target.value))} className="w-full accent-primary" />
                </div>
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-muted-foreground">Ratio</span>
                    <span className="font-mono">{band.ratio}:1</span>
                  </div>
                  <input type="range" min="1" max="10" step="0.1" value={band.ratio} onChange={(e) => updateCompressor(idx, "ratio", parseFloat(e.target.value))} className="w-full accent-primary" />
                </div>
              </div>
            </div>
          ))}
          {profile.mb_compressor.length === 0 && (
            <div className="text-sm text-muted-foreground italic">No multiband compressor data in this profile.</div>
          )}
        </div>
      </BentoTile>

      {/* Global Macros */}
      <BentoTile title="Macro Tuning" description="Global DSP macro parameters">
        <div className="mt-4 space-y-6">
          
          <div>
            <div className="flex justify-between text-sm mb-2">
              <span className="font-medium">Intelligent EQ (IEQ)</span>
              <span className="font-mono text-primary">{profile.ieq_amount}</span>
            </div>
            <input type="range" min="0" max="10" step="0.1" value={profile.ieq_amount} onChange={(e) => updateProfile({ ieq_amount: parseFloat(e.target.value) })} className="w-full accent-primary" />
            <div className="flex items-center justify-between mt-2">
              <span className="text-xs text-muted-foreground">Enable IEQ Processing</span>
              <Switch.Root
                checked={profile.ieq_enabled}
                onCheckedChange={(checked) => updateProfile({ ieq_enabled: checked })}
                className="w-9 h-5 bg-muted rounded-full relative shadow-sm data-[state=checked]:bg-primary outline-none cursor-pointer"
              >
                <Switch.Thumb className="block w-4 h-4 bg-white rounded-full transition-transform translate-x-0.5 data-[state=checked]:translate-x-[18px]" />
              </Switch.Root>
            </div>
          </div>

          <div>
            <div className="flex justify-between text-sm mb-2">
              <span className="font-medium">Dialogue Enhancer</span>
              <span className="font-mono text-primary">{profile.dialog_enhancer} dB</span>
            </div>
            <input type="range" min="0" max="12" step="0.5" value={profile.dialog_enhancer} onChange={(e) => updateProfile({ dialog_enhancer: parseFloat(e.target.value) })} className="w-full accent-primary" />
          </div>

          <div>
            <div className="flex justify-between text-sm mb-2">
              <span className="font-medium">Surround Virtualizer Boost</span>
              <span className="font-mono text-primary">{profile.surround_boost}</span>
            </div>
            <input type="range" min="0" max="10" step="0.5" value={profile.surround_boost} onChange={(e) => updateProfile({ surround_boost: parseFloat(e.target.value) })} className="w-full accent-primary" />
          </div>

          <div>
            <div className="flex justify-between text-sm mb-2">
              <span className="font-medium">Loudness Volmax Boost</span>
              <span className="font-mono text-primary">{(profile.volmax_boost / 16.0).toFixed(1)} dB</span>
            </div>
            <input type="range" min="0" max="400" step="16" value={profile.volmax_boost} onChange={(e) => updateProfile({ volmax_boost: parseFloat(e.target.value) })} className="w-full accent-primary" />
          </div>

        </div>
      </BentoTile>

    </div>
  );
};
