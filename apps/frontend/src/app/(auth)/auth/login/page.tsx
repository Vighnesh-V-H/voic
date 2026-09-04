import { AuthForm } from "@/components/auth-form";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/**
 * Login page for existing merchant accounts.
 *
 * @returns A page with login form and welcome messaging.
 */
export default function LoginPage() {
  return (
    <section className="grid flex-1 items-center gap-11 py-16 lg:grid-cols-2 lg:gap-20">
      <div>
        <p className="mb-5 text-xs font-semibold tracking-[0.14em] text-muted-foreground uppercase">
          Welcome back
        </p>
        <h1 className="font-editorial mb-6 max-w-xl text-5xl text-balance sm:text-6xl">
          Your payment signal, in one place.
        </h1>
        <p className="max-w-xl text-lg leading-relaxed text-muted-foreground">
          Log in to see the merchant account that powers your Voic provider
          connection.
        </p>
      </div>
      <Card className="card-hover">
        <CardHeader>
          <CardTitle className="text-2xl">Log in</CardTitle>
          <CardDescription>
            Use the credentials for your merchant account.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AuthForm mode="login" />
        </CardContent>
      </Card>
    </section>
  );
}
