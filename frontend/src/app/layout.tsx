import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { PrototypeBanner } from "@/components/PrototypeBanner";
import { AppFooter } from "@/components/ui/AppFooter";
import { AppHeader } from "@/components/ui/AppHeader";
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
    "A patient-facing clinical assistant that is allowed to refuse. Every answer is checked against the record before you see it.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      {/* Browser extensions (password managers, translators…) add attributes to <body> before
            React hydrates, which would log a spurious mismatch warning in development. */}
      <body suppressHydrationWarning className="flex min-h-full flex-col font-sans">
        <PrototypeBanner />
        <AppHeader />
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6 sm:py-10">{children}</main>
        <AppFooter />
      </body>
    </html>
  );
}
