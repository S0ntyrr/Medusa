import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ritmo Frost | Música en tu mesa",
  description: "Elige la próxima canción de tu visita.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return <html lang="es"><body className="min-h-full">{children}</body></html>;
}
