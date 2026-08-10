import React, { useOptimistic, startTransition } from "react";
import { BentoTile } from "./BentoTile";
import * as Switch from "@radix-ui/react-switch";

const STAGES = [
  { id: "ieq", label: "Intelligent EQ", desc: "Dynamic frequency response balancing" },
  { id: "peq", label: "Parametric EQ", desc: "Static headphone/speaker corrections" },
  { id: "mb_compressor", label: "Multiband Compressor", desc: "Advanced dynamic range control" },
  { id: "dialog_enhancer", label: "Dialog Enhancer", desc: "Boosts speech frequencies" },
  { id: "volmax", label: "Volume Maximizer", desc: "Prevents clipping while maximizing loudness" },
  { id: "surround", label: "Surround Virtualizer", desc: "Spatial audio rendering" },
];

export const Stages: React.FC = () => {
  // Mock state for now
  const [activeStages, setActiveStages] = React.useState<string[]>(["ieq", "peq", "volmax"]);
  
  // React 19 useOptimistic for instant UI feedback
  const [optimisticStages, setOptimisticStages] = useOptimistic<string[], string>(
    activeStages,
    (state, toggledId) => 
      state.includes(toggledId) 
        ? state.filter(id => id !== toggledId) 
        : [...state, toggledId]
  );

  const handleToggle = (id: string) => {
    startTransition(async () => {
      setOptimisticStages(id);
      // In a real app, this would trigger the Rust backend
      // await updateBackendStages(newStages);
      setActiveStages(prev => prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]);
    });
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl mx-auto w-full view-reveal-card">
      {STAGES.map((stage) => {
        const isActive = optimisticStages.includes(stage.id);
        return (
          <BentoTile
            key={stage.id}
            title={stage.label}
            description={stage.desc}
            className={`transition-colors ${isActive ? "border-primary/50 bg-primary/5" : ""}`}
          >
            <div className="mt-6 flex justify-between items-center">
              <span className="text-sm font-medium text-muted-foreground">
                {isActive ? "Enabled" : "Disabled"}
              </span>
              <Switch.Root
                checked={isActive}
                onCheckedChange={() => handleToggle(stage.id)}
                className="w-11 h-6 bg-muted rounded-full relative shadow-[var(--shadow-neumorphic-pressed)] data-[state=checked]:bg-primary outline-none cursor-pointer"
              >
                <Switch.Thumb className="block w-5 h-5 bg-white rounded-full transition-transform duration-100 translate-x-0.5 will-change-transform data-[state=checked]:translate-x-[22px]" />
              </Switch.Root>
            </div>
          </BentoTile>
        );
      })}
    </div>
  );
};
