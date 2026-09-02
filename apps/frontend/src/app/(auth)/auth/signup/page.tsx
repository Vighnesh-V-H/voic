import { AuthForm } from "@/components/auth-form";

export default function SignupPage() {
  return (
    <section className="auth-layout">
      <div className="auth-intro">
        <p className="eyebrow">Start with the boundary</p>
        <h1>Build your recovery foundation with confidence.</h1>
        <p className="hero-copy">Create a merchant workspace first. Provider connections and payment events will belong to it.</p>
      </div>
      <div className="auth-card">
        <h2>Create your account</h2>
        <p>Your merchant account starts with one secure identity.</p>
        <AuthForm mode="signup" />
      </div>
    </section>
  );
}
