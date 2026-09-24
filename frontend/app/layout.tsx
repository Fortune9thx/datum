import type { Metadata } from "next";
import { CONTRACT_ADDRESS } from "@/src/lib/datum/network";
import "./globals.css";

export const metadata: Metadata = {
  title: "DATUM",
  description: "Official station observation at locked publishers for this window.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const addr = CONTRACT_ADDRESS || "0x(not deployed)";
  return (
    <html lang="en">
      <body>
        <main>{children}</main>
        <footer>
          DATUM &middot; Studio Next &middot; 61997 &middot; state may reset &middot; {addr}
        </footer>
      </body>
    </html>
  );
}
