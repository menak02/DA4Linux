import React from "react";
import { useSettings, Theme } from "../hooks/useSettings";
import { cn } from "../lib/utils";
import { Moon, Sun, Monitor, Check } from "lucide-react";

const ACCENT_COLORS = [
  { name: "Violet", value: "oklch(0.62 0.22 255)" },
  { name: "Emerald", value: "oklch(0.65 0.16 150)" },
  { name: "Rose", value: "oklch(0.60 0.20 15)" },
  { name: "Amber", value: "oklch(0.70 0.18 60)" },
  { name: "Sky", value: "oklch(0.65 0.15 220)" },
];

export const ThemeSelector: React.FC = () => {
  const { settings, updateSettings, isLoaded } = useSettings();

  if (!isLoaded) return null;

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <label className="text-sm font-semibold text-foreground">Color Scheme</label>
        <div className="grid grid-cols-4 gap-2">
          {(["light", "dark", "oled", "system"] as Theme[]).map((theme) => {
            const isActive = settings.theme === theme;
            return (
              <button
                key={theme}
                onClick={() => updateSettings({ theme })}
                className={cn(
                  "flex flex-col items-center justify-center gap-2 py-3 rounded-xl border border-border transition-all",
                  isActive
                    ? "bg-primary/10 border-primary text-primary shadow-sm"
                    : "bg-surface text-muted-foreground hover:bg-surface-hover hover:text-foreground"
                )}
              >
                {theme === "light" && <Sun className="w-5 h-5" />}
                {theme === "dark" && <Moon className="w-5 h-5" />}
                {theme === "oled" && <Moon className="w-5 h-5 fill-current" />}
                {theme === "system" && <Monitor className="w-5 h-5" />}
                <span className="text-xs font-medium capitalize">{theme}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="space-y-3">
        <label className="text-sm font-semibold text-foreground">Accent Color</label>
        <div className="flex flex-wrap gap-3">
          {ACCENT_COLORS.map((color) => {
            const isActive = settings.accentColor === color.value;
            return (
              <button
                key={color.name}
                onClick={() => updateSettings({ accentColor: color.value })}
                className={cn(
                  "w-10 h-10 rounded-full flex items-center justify-center transition-transform hover:scale-110",
                  isActive && "ring-2 ring-offset-2 ring-offset-background ring-primary shadow-lg"
                )}
                style={{ backgroundColor: color.value }}
                title={color.name}
                aria-label={`Select ${color.name} accent color`}
              >
                {isActive && <Check className="w-5 h-5 text-white mix-blend-difference" />}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
