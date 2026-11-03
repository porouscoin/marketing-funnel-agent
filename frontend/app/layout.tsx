import type { Metadata, Viewport } from "next";
import { Geist_Mono, Inter } from "next/font/google";
import "./globals.css";

const sans = Inter({ subsets: ["latin"], variable: "--font-sans" });
const mono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono" });

const description =
  "Paste a product page. An AI agent maps the competitors, writes ads, a landing hero and emails, and tests them on a panel of synthetic buyers.";

export const metadata: Metadata = {
  title: "Marketing funnel agent",
  description,
  openGraph: { title: "Marketing funnel agent", description, type: "website" },
  twitter: {
    card: "summary_large_image",
    title: "Marketing funnel agent",
    description,
  },
};

export const viewport: Viewport = {
  themeColor: "#0e0e0d",
  colorScheme: "dark",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
