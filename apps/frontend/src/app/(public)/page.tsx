import Link from "next/link";

export default function Home() {
  return (
    <main className="shell">
      <header className="site-header">
        <Link className="wordmark" href="/">
          voic<span>.</span>
        </Link>
        <nav className="nav" aria-label="Main navigation">
          <Link href="/auth/login">Log in</Link>
          <Link className="button button-primary" href="/auth/signup">Get started</Link>
        </nav>
      </header>
      <section className="hero">
        <div>
          <p className="eyebrow">Payment recovery infrastructure</p>
          <h1>Turn failed payments into a second chance.</h1>
          <p className="hero-copy">
            Voic gives merchants a reliable foundation for connecting payment data,
            understanding what failed, and building a more thoughtful recovery flow.
          </p>
          <div className="hero-actions">
            <Link className="button button-primary" href="/auth/signup">Create your workspace</Link>
            <Link className="button button-secondary" href="/auth/login">I already have an account</Link>
          </div>
        </div>
        <div className="signal-card" aria-label="Voic integration status preview">
          <div className="signal-card-header"><span>Workspace signal</span><span>Phase 01</span></div>
          <div className="signal-line"><span className="signal-dot" /><div><strong>Identity verified</strong><small>Merchant boundary established</small></div></div>
          <div className="signal-line"><span className="signal-dot" /><div><strong>Provider-ready</strong><small>Provider connection comes next</small></div></div>
          <div className="signal-line"><span className="signal-dot" /><div><strong>Events have a home</strong><small>Every payment event belongs somewhere</small></div></div>
        </div>
      </section>
    </main>
  );
}
