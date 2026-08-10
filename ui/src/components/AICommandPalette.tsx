import React, { useState, useEffect } from "react";

export interface CommandItem {
  id: string;
  label: string;
  shortcut?: string;
  onSelect: () => void;
}

export const AICommandPalette: React.FC<{ items: CommandItem[] }> = ({
  items,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      } else if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  const filteredItems = items.filter((item) =>
    item.label.toLowerCase().includes(query.toLowerCase())
  );

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="AI Command Palette"
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 p-4 bg-black/40 backdrop-blur-sm"
    >
      <div className="w-full max-w-xl overflow-hidden rounded-2xl border border-border bg-surface shadow-2xl transition-all">
        <div className="flex items-center px-4 border-b border-border">
          <input
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder="Type a command or ask AI..."
            aria-autocomplete="list"
            aria-controls="command-list"
            className="w-full bg-transparent py-4 text-sm text-foreground outline-none placeholder:text-muted-foreground"
            autoFocus
          />
          <kbd className="hidden sm:inline-block px-2 py-1 text-xs font-mono text-muted-foreground bg-muted rounded border border-border">
            ESC
          </kbd>
        </div>
        <ul
          id="command-list"
          role="listbox"
          aria-label="Commands"
          className="max-h-72 overflow-y-auto p-2"
        >
          {filteredItems.map((item, idx) => (
            <li
              key={item.id}
              role="option"
              aria-selected={idx === selectedIndex}
              onClick={() => {
                item.onSelect();
                setIsOpen(false);
              }}
              onMouseEnter={() => setSelectedIndex(idx)}
              className={`flex items-center justify-between px-3 py-2.5 rounded-xl text-sm cursor-pointer transition-colors ${
                idx === selectedIndex
                  ? "bg-primary/10 text-primary font-medium"
                  : "text-foreground hover:bg-muted"
              }`}
            >
              <span>{item.label}</span>
              {item.shortcut && (
                <kbd className="px-1.5 py-0.5 text-[10px] font-mono bg-muted text-muted-foreground rounded border border-border">
                  {item.shortcut}
                </kbd>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
