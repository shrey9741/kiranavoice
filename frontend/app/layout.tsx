import type { Metadata, Viewport } from "next";
import { Hind_Siliguri, Tiro_Bangla } from "next/font/google";
import "./globals.css";

const ui = Hind_Siliguri({
  subsets: ["bengali", "latin"],
  weight: ["400", "500", "600"],
  variable: "--font-ui",
  display: "swap",
});

const hand = Tiro_Bangla({
  subsets: ["bengali", "latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-hand",
  display: "swap",
});

export const metadata: Metadata = {
  title: "KiranaVoice",
  description: "Voice-first order assistant for neighbourhood kirana stores",
  // Stops Chrome's automatic translation, which breaks live updates in this app
  other: { google: "notranslate" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#EEF2EE",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="bn" translate="no" className={`${ui.variable} ${hand.variable}`}>
      <body>{children}</body>
    </html>
  );
}
