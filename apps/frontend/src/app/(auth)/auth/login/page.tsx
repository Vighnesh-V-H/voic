import { AuthForm } from "@/components/auth-form";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function LoginPage() {
  return (
    <section className="grid flex-1 items-center gap-11 py-12 lg:grid-cols-2 lg:gap-20">
      <div>
        <p className="mb-5 text-xs font-extrabold tracking-[0.14em] text-primary uppercase">
          Welcome back
        </p>
        <h1 className="mb-6 max-w-xl text-5xl leading-[0.95] font-extrabold tracking-tighter text-balance sm:text-6xl">
          Your payment signal, in one place.
        </h1>
        <p className="max-w-xl text-lg leading-relaxed text-muted-foreground">
          Log in to see the merchant account that powers your Voic provider
          connection.
        </p>
      </div>
      <Card className="shadow-[12px_12px_0_0_var(--secondary)]">
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
