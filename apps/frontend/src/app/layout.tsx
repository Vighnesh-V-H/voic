import type { Metadata } from "next";
import "./globals.css";

import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import { Newsreader } from "next/font/google";

import { ThemeProvider } from "@/components/theme-provider";

const newsreader = Newsreader({
  subsets: ["latin"],
  variable: "--font-newsreader",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Voic | Payment recovery infrastructure",
  description: "Connect your payment provider and build a clearer recovery workflow.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${GeistSans.variable} ${GeistMono.variable} ${newsreader.variable}`}
    >
      <body>
        <div aria-hidden="true" className="ambient-blob" />
        <noscript>
          <style>{".reveal{opacity:1 !important;transform:none !important;}"}</style>
        </noscript>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
