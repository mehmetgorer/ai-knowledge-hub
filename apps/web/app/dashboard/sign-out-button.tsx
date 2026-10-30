import { authButtonClassName } from "@/components/auth-shell";
import { dashboardGhostButtonClassName } from "@/components/dashboard/ui";

import { signOut } from "../auth/sign-out/actions";

type SignOutButtonProps = {
  variant?: "default" | "ghost";
};

export function SignOutButton({ variant = "default" }: SignOutButtonProps) {
  const className =
    variant === "ghost" ? dashboardGhostButtonClassName : authButtonClassName;
  return (
    <form action={signOut}>
      <button type="submit" className={className}>
        Sign out
      </button>
    </form>
  );
}
