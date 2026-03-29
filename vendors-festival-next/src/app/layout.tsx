import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VENDORS - Digital Festival Marketplace",
  description: "Step into a live shopping festival with vibrant tent shops and interactive vendor chats."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
