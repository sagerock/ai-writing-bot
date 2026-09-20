// One auth surface for the app, backed by Supabase.
//
// RomaLume uses the shared SageRock Supabase project so a school administrator
// has the same login in RomaLume, the email tool, and Ask. The exported
// functions keep the call shapes the app grew up with
// (auth.currentUser.getIdToken(), onAuthStateChanged(auth, cb), signOut(auth))
// so the sixty-odd callers did not change when Firebase was retired
// (2026-09-20). See docs/supabase-platform.md.

import { createClient } from '@supabase/supabase-js';

export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY,
  { auth: { flowType: 'pkce', persistSession: true, autoRefreshToken: true } },
);

function wrapUser(session) {
  if (!session?.user) return null;
  const u = session.user;
  return {
    uid: u.id,
    email: u.email,
    emailVerified: Boolean(u.email_confirmed_at),
    displayName: u.user_metadata?.full_name || u.user_metadata?.name || null,
    isAdmin: false,
    school: null,
    async getIdToken() {
      const { data } = await supabase.auth.getSession();
      return data.session?.access_token || session.access_token;
    },
    async getIdTokenResult() {
      const token = await this.getIdToken();
      return { token, claims: {} };
    },
  };
}

export const auth = { currentUser: null, client: supabase };

supabase.auth.onAuthStateChange((_event, session) => {
  auth.currentUser = wrapUser(session);
});

/** Firebase-style getAuth() for components that call it directly. */
export function getAuth() {
  return auth;
}

function unwrap({ data, error }) {
  if (error) throw new Error(error.message);
  return data;
}

export function onAuthStateChanged(_auth, callback) {
  // Deliver the persisted session first, then live changes.
  let fired = false;
  supabase.auth.getSession().then(({ data }) => {
    if (fired) return;
    fired = true;
    auth.currentUser = wrapUser(data.session);
    callback(auth.currentUser);
  });
  const { data } = supabase.auth.onAuthStateChange((event, session) => {
    if (event === 'INITIAL_SESSION') return;
    fired = true;
    auth.currentUser = wrapUser(session);
    callback(auth.currentUser);
  });
  return () => data.subscription.unsubscribe();
}

export async function signOut() {
  unwrap(await supabase.auth.signOut());
  auth.currentUser = null;
}

export async function signInWithEmailAndPassword(_auth, email, password) {
  const data = unwrap(await supabase.auth.signInWithPassword({ email, password }));
  auth.currentUser = wrapUser(data.session);
  return { user: auth.currentUser };
}

export async function createUserWithEmailAndPassword(_auth, email, password) {
  const data = unwrap(await supabase.auth.signUp({ email, password }));
  if (!data.session) {
    // Email confirmation is on for this project: no session until confirmed.
    const err = new Error('confirm-email');
    err.code = 'auth/confirm-email';
    throw err;
  }
  auth.currentUser = wrapUser(data.session);
  return { user: auth.currentUser };
}

export async function sendPasswordResetEmail(_auth, email) {
  unwrap(await supabase.auth.resetPasswordForEmail(email, {
    redirectTo: `${window.location.origin}/auth/action?mode=resetPassword`,
  }));
}

export async function updatePassword(_user, newPassword) {
  unwrap(await supabase.auth.updateUser({ password: newPassword }));
}

export async function updateEmail(_user, newEmail) {
  unwrap(await supabase.auth.updateUser({ email: newEmail }));
}

export async function updateProfile(_user, { displayName }) {
  unwrap(await supabase.auth.updateUser({ data: { full_name: displayName } }));
  if (auth.currentUser) auth.currentUser.displayName = displayName;
}

/** Firebase reauth shape: re-sign-in with the current password. */
export const EmailAuthProvider = {
  credential(email, password) {
    return { email, password };
  },
};

export async function reauthenticateWithCredential(_user, credential) {
  unwrap(await supabase.auth.signInWithPassword(credential));
}

// Password-reset / email-action page. Supabase delivers the user here with a
// recovery session already established from the link.
export async function verifyPasswordResetCode() {
  const { data } = await supabase.auth.getSession();
  if (!data.session) throw new Error('Reset link is invalid or has expired.');
  return data.session.user.email;
}

export async function confirmPasswordReset(_auth, _code, newPassword) {
  unwrap(await supabase.auth.updateUser({ password: newPassword }));
}

export async function applyActionCode() {
  // Supabase confirms email through its own redirect; nothing to apply here.
}
