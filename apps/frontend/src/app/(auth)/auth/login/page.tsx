import { AuthForm } from "@/components/auth-form";

export default function LoginPage() {
  return (
    <section className="auth-layout">
      <div className="auth-intro">
        <p className="eyebrow">Welcome back</p>
        <h1>Your payment signal, in one place.</h1>
        <p className="hero-copy">Log in to see the merchant account that powers your Voic provider connection.</p>
      </div>
      <div className="auth-card">
        <h2>Log in</h2>
        <p>Use the credentials for your merchant account.</p>
        <AuthForm mode="login" />
      </div>
    </section>
  );
}
