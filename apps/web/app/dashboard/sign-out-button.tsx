import { authButtonClassName } from "@/components/auth-shell";

import { signOut } from "../auth/sign-out/actions";

export function SignOutButton() {
  return (
    <form action={signOut}>
      <button type="submit" className={authButtonClassName}>
        Sign out
      </button>
    </form>
  );
}
