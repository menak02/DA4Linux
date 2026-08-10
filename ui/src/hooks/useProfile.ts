import { useState, useEffect } from "react";
import { load } from "@tauri-apps/plugin-store";
import { invoke } from "@tauri-apps/api/core";

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

export interface AudioOptimizerBand {
  gains: number[];
}

export interface DAX3Profile {
  name: string;
  endpoint_type: string;
  peq_bands: PEQBand[];
  ao_bands: AudioOptimizerBand[];
  mb_compressor: MBCompressorBand[];
  volmax_boost: number;
  ieq_enabled: boolean;
  ieq_amount: number;
  ieq_curve: number[];
  dialog_enhancer: number;
  volume_leveler: number;
  surround_boost: number;
  crossover_freqs: number[];
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
  ao_bands: [],
  mb_compressor: [
    { threshold: -20, ratio: 2.0, attack: 5.0, release: 50.0, knee: 2.0, makeup_gain: 0 },
    { threshold: -24, ratio: 2.5, attack: 5.0, release: 50.0, knee: 2.0, makeup_gain: 0 },
    { threshold: -18, ratio: 1.5, attack: 5.0, release: 50.0, knee: 2.0, makeup_gain: 0 },
    { threshold: -20, ratio: 2.0, attack: 5.0, release: 50.0, knee: 2.0, makeup_gain: 0 },
  ],
  volmax_boost: 200.0,
  ieq_enabled: true,
  ieq_amount: 5.0,
  ieq_curve: [],
  dialog_enhancer: 0.0,
  volume_leveler: 0.0,
  surround_boost: 0.0,
  crossover_freqs: [],
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
      // Apply immediately in real-time
      await invoke("apply_dsp_profile", { profile: newProfile });
    } catch (e) {
      console.error("Failed to save or apply profile:", e);
    }
  };

  const importFromXml = async (xmlPath: string) => {
    try {
      // NOTE: We will port parse_dax3_xml to Rust soon.
      // For now, this is a placeholder.
      alert(`XML Parsing is being ported to Rust! Check back soon.`);
    } catch (e) {
      console.error(e);
      alert("Failed to parse XML: " + e);
    }
  };

  const regenerateDsp = async () => {
    try {
      // Direct IPC call to Rust to load the PipeWire module in real-time!
      await invoke("apply_dsp_profile", { profile });
      return "Successfully loaded into PipeWire";
    } catch (e) {
      console.error("Failed to apply DSP:", e);
      throw e;
    }
  };

  return { profile, updateProfile, isLoaded, importFromXml, regenerateDsp };
}
