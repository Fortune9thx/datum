import { AppNav, HealthFooter } from "@/src/components/chrome";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <AppNav />
      <div style={{ flex: 1, padding: "36px 0 72px" }}>
        <div className="container">{children}</div>
      </div>
      <HealthFooter />
    </div>
  );
}
