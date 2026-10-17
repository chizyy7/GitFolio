import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import { AuthProvider } from "@/context/AuthContext";
import { Navbar } from "@/components/Navbar";
import { SiteFooter } from "@/components/SiteFooter";

import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

const siteName = process.env.NEXT_PUBLIC_SITE_NAME ?? "GitFolio";

export const metadata: Metadata = {
  title: {
    default: `${siteName} — AI-powered version control & portfolio`,
    template: `%s · ${siteName}`,
  },
  description:
    "GitFolio is a self-hosted version control and developer portfolio platform with a local " +
    "AI (Llama 3.2) that explains, reviews and searches your code.",
  applicationName: siteName,
  keywords: [
    "git",
    "portfolio",
    "ai code review",
    "rag",
    "llama 3.2",
    "ollama",
    "developer portfolio",
  ],
  authors: [{ name: siteName }],
  openGraph: {
    title: `${siteName} — AI-powered version control`,
    description: "Push code, get AI reviews, ask questions about your own repository.",
    type: "website",
  },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: "#0d1117",
  colorScheme: "dark light",
};

/**
 * Theme bootstrapping.
 *
 * Applied before paint so the first frame already has the right palette
 * (avoids a flash of the wrong theme).
 */
const themeScript = `
(function () {
  try {
    var stored = localStorage.getItem('gitfolio.theme');
    var theme = stored || 'dark';
    document.documentElement.classList.toggle('light', theme === 'light');
  } catch (e) {
    /* localStorage unavailable — stay on the default dark theme */
  }
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${jetbrains.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-screen bg-canvas font-sans text-fg">
        <AuthProvider>
          <div className="flex min-h-screen flex-col">
            <Navbar />
            <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
              {children}
            </main>
            <SiteFooter />
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
