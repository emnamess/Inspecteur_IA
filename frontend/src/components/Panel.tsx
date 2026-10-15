import type { ReactNode } from "react";

export function Panel({ title, children, className = "" }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={`flex flex-col rounded-xl border border-stone-800 bg-stone-900/60 ${className}`}>
      <h2 className="border-b border-stone-800 px-4 py-3 font-serif text-lg text-amber-200">{title}</h2>
      <div className="flex min-h-0 flex-1 flex-col p-4">{children}</div>
    </section>
  );
}
