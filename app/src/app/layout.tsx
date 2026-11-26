import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import { Nav } from "@/components/Nav";
import "./globals.css";

const inter = Inter({ subsets: ["latin", "latin-ext"], variable: "--font-inter" });
const mono = JetBrains_Mono({ subsets: ["latin", "latin-ext"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "bistlab",
  description: "BIST analiz ve risk platformu — eğitim amaçlıdır, yatırım tavsiyesi değildir.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr" className={`${inter.variable} ${mono.variable}`}>
      <body>
        <Nav />
        <main className="container" style={{ padding: "24px 32px 48px", display: "grid", gap: 20 }}>
          {children}
        </main>
        <footer className="container" style={{ paddingBottom: 32 }}>
          <p className="note">
            Veriler Yahoo Finance, TCMB EVDS ve KAP kaynaklıdır; hatalı ya da gecikmeli olabilir. Eğitim
            amaçlıdır; yatırım tavsiyesi değildir.
          </p>
        </footer>
      </body>
    </html>
  );
}
