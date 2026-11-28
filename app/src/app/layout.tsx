import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import { Nav } from "@/components/Nav";
import "./globals.css";

const inter = Inter({ subsets: ["latin", "latin-ext"], variable: "--font-inter" });
const mono = JetBrains_Mono({ subsets: ["latin", "latin-ext"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "bistlab",
  description:
    "Equity analytics and risk lab built on Borsa Istanbul — for education, not investment advice.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body>
        <Nav />
        <main className="container" style={{ padding: "24px 32px 48px", display: "grid", gap: 20 }}>
          {children}
        </main>
        <footer className="container" style={{ paddingBottom: 32 }}>
          <p className="note">
            Data from Yahoo Finance, the central bank&apos;s EVDS service and KAP; it may be inaccurate
            or delayed. For education only; not investment advice.
          </p>
        </footer>
      </body>
    </html>
  );
}
