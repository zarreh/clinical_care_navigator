import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { PrototypeBanner } from "@/components/PrototypeBanner";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Clinical Care Navigator",
  description:
    "A patient-facing clinical assistant that is allowed to refuse — every answer is checked against the record before you see it, and streamed node-by-node.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <PrototypeBanner />
        <nav className="border-b border-neutral-200 px-4 py-2 text-sm dark:border-neutral-800">
          <div className="mx-auto flex max-w-3xl gap-4">
            <Link className="font-semibold hover:underline" href="/">
              Ask a question
            </Link>
            <Link className="text-neutral-500 hover:underline" href="/reviews">
              Clinician review queue
            </Link>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
