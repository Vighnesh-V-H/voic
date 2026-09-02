import Link from "next/link";

export default function AuthLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <main className="auth-page shell">
      <header className="site-header">
        <Link className="wordmark" href="/">voic<span>.</span></Link>
        <Link className="text-link" href="/">Back to home</Link>
      </header>
      {children}
    </main>
  );
}
