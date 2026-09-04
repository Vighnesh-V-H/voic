import { AuthForm } from "@/components/auth-form";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/**
 * Signup page for creating new merchant accounts.
 *
 * @returns A page with signup form and onboarding messaging.
 */
export default function SignupPage() {
  return (
    <section className="grid flex-1 items-center gap-11 py-16 lg:grid-cols-2 lg:gap-20">
      <div>
        <p className="mb-5 text-xs font-semibold tracking-[0.14em] text-muted-foreground uppercase">
          Start with the boundary
        </p>
        <h1 className="font-editorial mb-6 max-w-xl text-5xl text-balance sm:text-6xl">
          Build your recovery foundation with confidence.
        </h1>
        <p className="max-w-xl text-lg leading-relaxed text-muted-foreground">
          Create a merchant workspace first. Provider connections and payment
          events will belong to it.
        </p>
      </div>
      <Card className="card-hover">
        <CardHeader>
          <CardTitle className="text-2xl">Create your account</CardTitle>
          <CardDescription>
            Your merchant account starts with one secure identity.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AuthForm mode="signup" />
        </CardContent>
      </Card>
    </section>
  );
}
