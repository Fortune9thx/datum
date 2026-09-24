"use client";

import { useState } from "react";
import { FAQ } from "@/src/lib/datum/registry";

export function Faq() {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <div>
      {FAQ.map((item, i) => {
        const isOpen = open === i;
        return (
          <div key={item.q}>
            <button
              className="faq-q"
              aria-expanded={isOpen}
              onClick={() => setOpen(isOpen ? null : i)}
            >
              <span>{item.q}</span>
              <span className="mono muted" aria-hidden="true">
                {isOpen ? "[ − ]" : "[ + ]"}
              </span>
            </button>
            {isOpen ? <div className="faq-a">{item.a}</div> : null}
          </div>
        );
      })}
    </div>
  );
}
