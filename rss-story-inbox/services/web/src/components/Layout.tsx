import Link from "next/link";

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ maxWidth: 980, margin: "0 auto", padding: 16, fontFamily: "system-ui" }}>
      <header style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>RSS Story Inbox</h2>
        <nav style={{ display: "flex", gap: 10 }}>
          <Link href="/">Queue</Link>
          <Link href="/kept">Kept</Link>
          <Link href="/shortlist">Shortlist</Link>
          <Link href="/published">Published</Link>
          <Link href="/profile">Profile</Link>
        </nav>
      </header>
      {children}
    </div>
  );
}
