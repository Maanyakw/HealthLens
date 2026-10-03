import type { Metadata } from "next";
import { Bricolage_Grotesque, Figtree } from "next/font/google";
import "./globals.css";

const display = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-bricolage",
  display: "swap",
});

const body = Figtree({
  subsets: ["latin"],
  variable: "--font-figtree",
  display: "swap",
});

export const metadata: Metadata = {
  title: "HealthLens | AI Health Companion",
  description:
    "Understand your health data, see chronic disease risk, learn why the AI predicted it, and track trends over time.",
};

// Runs before first paint so the saved theme never flashes.
const themeScript = `
(function(){
  try {
    var saved = localStorage.getItem('healthlens-theme');
    var ok = ['clinic','midnight','sunrise','meadow','dusk'];
    var t = ok.indexOf(saved) > -1 ? saved :
      (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'midnight' : 'clinic');
    document.documentElement.dataset.theme = t;
  } catch (e) { document.documentElement.dataset.theme = 'clinic'; }
})();
`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      data-theme="clinic"
      suppressHydrationWarning
      className={`${display.variable} ${body.variable}`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
