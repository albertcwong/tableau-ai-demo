import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Multi-Agent Dashboard - Tableau AI Demo",
  description: "Interact with specialized AI agents for Tableau analysis",
};

export default function AgentsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
