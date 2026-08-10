import React from "react";
import { BentoTile } from "./BentoTile";
import { ThemeSelector } from "./ThemeSelector";
import { useSettings } from "../hooks/useSettings";
import * as Switch from "@radix-ui/react-switch";

export const Settings: React.FC = () => {
  const { settings, updateSettings, isLoaded } = useSettings();

  if (!isLoaded) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-6xl mx-auto w-full view-reveal-card">
      <BentoTile title="Appearance" description="Customize the application theme and colors.">
        <div className="mt-6">
          <ThemeSelector />
        </div>
      </BentoTile>

      <BentoTile title="Accessibility" description="Configure motion and contrast preferences.">
        <div className="mt-6 space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-foreground">Reduce Motion</div>
              <div className="text-xs text-muted-foreground mt-1">Disables CSS animations and spring transitions.</div>
            </div>
            <Switch.Root
              checked={settings.reduceMotion}
              onCheckedChange={(checked) => updateSettings({ reduceMotion: checked })}
              className="w-11 h-6 bg-muted rounded-full relative shadow-[var(--shadow-neumorphic-pressed)] data-[state=checked]:bg-primary outline-none cursor-pointer"
            >
              <Switch.Thumb className="block w-5 h-5 bg-white rounded-full transition-transform duration-100 translate-x-0.5 will-change-transform data-[state=checked]:translate-x-[22px]" />
            </Switch.Root>
          </div>
          
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-foreground">High Contrast</div>
              <div className="text-xs text-muted-foreground mt-1">Increases border opacities and foreground contrast.</div>
            </div>
            <Switch.Root
              checked={false} // Placeholder for future implementation
              className="w-11 h-6 bg-muted rounded-full relative shadow-[var(--shadow-neumorphic-pressed)] data-[state=checked]:bg-primary outline-none cursor-pointer"
            >
              <Switch.Thumb className="block w-5 h-5 bg-white rounded-full transition-transform duration-100 translate-x-0.5 will-change-transform data-[state=checked]:translate-x-[22px]" />
            </Switch.Root>
          </div>
        </div>
      </BentoTile>
    </div>
  );
};
