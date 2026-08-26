import type { Metadata } from "next";
import { Figtree, Mulish } from "next/font/google";
import "./globals.css";

/**
 * Senus uses Figtree for headings and Mulish for body copy on senus.com.
 * Matching them is most of what makes this read as the company's own product
 * rather than a generic dashboard.
 */
const figtree = Figtree({
  variable: "--font-figtree",
  subsets: ["latin"],
  display: "swap",
});

const mulish = Mulish({
  variable: "--font-mulish",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Senus PLC — Board Report",
  description:
    "AI-native board report for Senus PLC, built from published financial statements.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // Pinned to light. A board pack is a printed-document idiom - white paper,
    // ink, one strong brand colour - and following the reader's OS theme would
    // hand half of them a dark report they did not ask for.
    <html
      lang="en"
      data-theme="light"
      className={`${figtree.variable} ${mulish.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
