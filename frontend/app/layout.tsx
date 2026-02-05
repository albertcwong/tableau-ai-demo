import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ValidationLoader } from "@/components/ValidationLoader";
import { TableauScriptLoader } from "@/components/TableauScriptLoader";
import { ThemeInitializer } from "@/components/ThemeInitializer";
import { AuthProvider } from "@/components/auth/AuthContext";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Tableau AI Demo",
  description: "AI-powered Tableau analytics and visualization assistant",
  icons: {
    icon: '/icon.png',
    apple: '/icon.png',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <AuthProvider>
          <ThemeInitializer />
          {/* Load Tableau Embedding API v3 script */}
          <TableauScriptLoader />
          {process.env.NODE_ENV === 'development' && <ValidationLoader />}
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
