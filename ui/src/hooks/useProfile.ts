import { useState, useEffect } from "react";
import { load } from "@tauri-apps/plugin-store";
import { Command } from "@tauri-apps/plugin-shell";

export interface PEQBand {
  filter_type: string;
  freq: number;
  gain: number;
  q: number;
  enabled: boolean;
}

export interface MBCompressorBand {
  threshold: number;
  ratio: number;
  attack: number;
  release: number;
  knee: number;
  makeup_gain: number;
}

export interface DAX3Profile {
  name: string;
  endpoint_type: string;
  peq_bands: PEQBand[];
  mb_compressor: MBCompressorBand[];
  volmax_boost: number;
  ieq_enabled: boolean;
  ieq_amount: number;
  dialog_enhancer: number;
  surround_boost: number;
}

const defaultProfile: DAX3Profile = {
  name: "Default UI Profile",
  endpoint_type: "internal_speaker",
  peq_bands: [
    { filter_type: "highpass", freq: 90, gain: 0.0, q: 0.7, enabled: true },
    { filter_type: "peaking", freq: 150, gain: 3.5, q: 1.2, enabled: true },
    { filter_type: "peaking", freq: 500, gain: -1.5, q: 1.0, enabled: true },
    { filter_type: "peaking", freq: 3500, gain: -2.0, q: 1.5, enabled: true },
    { filter_type: "highshelf", freq: 8000, gain: 2.5, q: 0.7, enabled: true },
  ],
  mb_compressor: [
    { threshold: -20, ratio: 2.0, attack: 5.0, release: 50.0, knee: 2.0, makeup_gain: 0 },
    { threshold: -24, ratio: 2.5, attack: 5.0, release: 50.0, knee: 2.0, makeup_gain: 0 },
    { threshold: -18, ratio: 1.5, attack: 5.0, release: 50.0, knee: 2.0, makeup_gain: 0 },
    { threshold: -20, ratio: 2.0, attack: 5.0, release: 50.0, knee: 2.0, makeup_gain: 0 },
  ],
  volmax_boost: 200.0,
  ieq_enabled: true,
  ieq_amount: 5.0,
  dialog_enhancer: 0.0,
  surround_boost: 0.0,
};

let storeInstance: any = null;

async function getStore() {
  if (!storeInstance) {
    storeInstance = await load("profile.json", { autoSave: true });
  }
  return storeInstance;
}

export function useProfile() {
  const [profile, setProfileState] = useState<DAX3Profile>(defaultProfile);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    async function loadProfile() {
      try {
        const store = await getStore();
        const saved = await store.get("profile");
        if (saved) {
          setProfileState({ ...defaultProfile, ...(saved as any) });
        } else {
          await store.set("profile", defaultProfile);
        }
      } catch (e) {
        console.error("Failed to load profile:", e);
      } finally {
        setIsLoaded(true);
      }
    }
    loadProfile();
  }, []);

  const updateProfile = async (updates: Partial<DAX3Profile>) => {
    const newProfile = { ...profile, ...updates };
    setProfileState(newProfile);
    try {
      const store = await getStore();
      await store.set("profile", newProfile);
      await store.save();
    } catch (e) {
      console.error("Failed to save profile:", e);
    }
  };

  const importFromXml = async (xmlPath: string) => {
    try {
      const command = Command.sidecar("bin/da4linux-cli", ["parse", "--json", xmlPath]);
      const output = await command.execute();
      if (output.code !== 0) throw new Error(output.stderr);
      
      const parsed = JSON.parse(output.stdout);
      const endpointKey = Object.keys(parsed.endpoints)[0];
      if (endpointKey) {
        const p = parsed.endpoints[endpointKey];
        await updateProfile({
          name: p.name || endpointKey,
          peq_bands: p.peq_bands || [],
          mb_compressor: p.mb_compressor || [],
          volmax_boost: p.volmax_boost || 0,
          ieq_enabled: p.ieq_enabled || false,
          ieq_amount: p.ieq_amount || 0,
          dialog_enhancer: p.dialog_enhancer || 0,
          surround_boost: p.surround_boost || 0,
        });
        alert(`Successfully imported DAX3 Profile: ${p.name || endpointKey}`);
      }
    } catch (e) {
      console.error(e);
      alert("Failed to parse XML: " + e);
    }
  };

  const regenerateDsp = async (activeStages: string[] = []) => {
    try {
      const profileJson = JSON.stringify(profile);
      const args = ["generate", "--json-profile", profileJson];
      if (activeStages.length > 0) {
        args.push("--stages", activeStages.join(","));
      }
      
      const command = Command.sidecar("bin/da4linux-cli", args);
      const output = await command.execute();
      
      if (output.code !== 0) {
        throw new Error(output.stderr);
      }
      
      // Auto-restart pipewire
      await Command.sidecar("bin/da4linux-cli", ["restart-pipewire"]).execute();
      
      return output.stdout;
    } catch (e) {
      console.error(e);
      throw e;
    }
  };

  return { profile, updateProfile, isLoaded, importFromXml, regenerateDsp };
}
