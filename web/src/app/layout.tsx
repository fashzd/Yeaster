import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Yeaster · Autonomous Trading",
  description: "An autonomous BNB momentum trading agent — one mind, orchestrated stages.",
};

export const viewport: Viewport = {
  themeColor: "#070b1a",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {/* Living tinted-acrylic background */}
        <div className="acrylic-field" aria-hidden />

        {/* Global SVG goo filter: makes sibling blobs merge & separate. */}
        <svg width="0" height="0" aria-hidden style={{ position: "absolute" }}>
          <defs>
            <filter id="yeaster-goo">
              <feGaussianBlur in="SourceGraphic" stdDeviation="11" result="blur" />
              <feColorMatrix
                in="blur"
                mode="matrix"
                values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 22 -10"
                result="goo"
              />
              <feBlend in="SourceGraphic" in2="goo" />
            </filter>
          </defs>
        </svg>

        {children}
      </body>
    </html>
  );
}
