import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Voic | Payment recovery infrastructure",
  description: "Connect your payment provider and build a clearer recovery workflow.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
