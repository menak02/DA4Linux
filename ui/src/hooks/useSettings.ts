import { useState, useEffect } from "react";
import { load } from "@tauri-apps/plugin-store";

export type Theme = "light" | "dark" | "oled" | "system";

export interface Settings {
  theme: Theme;
  accentColor: string;
  reduceMotion: boolean;
  globalBypass: boolean;
}

const defaultSettings: Settings = {
  theme: "system",
  accentColor: "oklch(0.62 0.22 255)", // Default Violet
  reduceMotion: false,
  globalBypass: false,
};

let storeInstance: any = null;

async function getStore() {
  if (!storeInstance) {
    storeInstance = await load("settings.json", { autoSave: true });
  }
  return storeInstance;
}

export function useSettings() {
  const [settings, setSettingsState] = useState<Settings>(defaultSettings);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    async function loadSettings() {
      try {
        const store = await getStore();
        const saved = await store.get("settings");
        if (saved) {
          setSettingsState({ ...defaultSettings, ...(saved as any) });
        } else {
          await store.set("settings", defaultSettings);
        }
      } catch (e) {
        console.error("Failed to load settings:", e);
      } finally {
        setIsLoaded(true);
      }
    }
    loadSettings();
  }, []);

  const updateSettings = async (updates: Partial<Settings>) => {
    const newSettings = { ...settings, ...updates };
    setSettingsState(newSettings);
    try {
      const store = await getStore();
      await store.set("settings", newSettings);
      await store.save(); // explicitly save just in case
    } catch (e) {
      console.error("Failed to save settings:", e);
    }
  };

  // Apply settings to document root
  useEffect(() => {
    if (!isLoaded) return;
    const root = document.documentElement;

    // Apply theme
    if (settings.theme === "system") {
      const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      root.setAttribute("data-theme", isDark ? "dark" : "light");
    } else {
      root.setAttribute("data-theme", settings.theme);
    }

    // Apply accent color
    if (settings.accentColor) {
      root.style.setProperty("--accent", settings.accentColor);
      // Generate a slightly darker hover state automatically by dropping lightness
      const hoverMatch = settings.accentColor.match(/oklch\(([\d.]+)\s+([\d.]+)\s+([\d.]+)\)/);
      if (hoverMatch) {
        const l = Math.max(0, parseFloat(hoverMatch[1]) - 0.05);
        root.style.setProperty("--accent-hover", `oklch(${l} ${hoverMatch[2]} ${hoverMatch[3]})`);
      }
    }

    // Apply motion settings
    if (settings.reduceMotion) {
      root.setAttribute("data-motion", "reduced");
    } else {
      root.removeAttribute("data-motion");
    }
  }, [settings, isLoaded]);

  return { settings, updateSettings, isLoaded };
}
