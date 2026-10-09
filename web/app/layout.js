import "./globals.css";

export const metadata = {
  title: "MetricMind",
  description: "Agentic Semantic BI — the LLM never writes SQL",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
