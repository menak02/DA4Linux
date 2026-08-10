import React from "react";

export interface BentoTileProps {
  title: string;
  description: string;
  badge?: string;
  className?: string;
  children?: React.ReactNode;
}

export const BentoTile: React.FC<BentoTileProps> = ({
  title,
  description,
  badge,
  className = "",
  children,
}) => (
  <article
    tabIndex={0}
    aria-label={`${title} card`}
    className={`group relative overflow-hidden rounded-3xl border border-border bg-surface p-6 sm:p-8 transition-all duration-300 hover:border-primary/50 hover:shadow-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${className}`}
  >
    {badge && (
      <span className="inline-block rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary mb-4">
        {badge}
      </span>
    )}
    <h3 className="text-xl font-bold tracking-tight text-foreground">
      {title}
    </h3>
    <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
      {description}
    </p>
    {children && <div className="mt-6">{children}</div>}
  </article>
);
