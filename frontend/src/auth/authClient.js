// One auth surface for the app, backed by Supabase or Firebase.
//
// VITE_AUTH_PROVIDER=supabase uses the shared SageRock Supabase project so a
// school administrator has the same login in RomaLume, the email tool, and
// Ask. Anything else keeps Firebase. The exported functions keep Firebase's
// call shapes (auth.currentUser.getIdToken(), onAuthStateChanged(auth, cb),
// signOut(auth), ...) so the sixty-odd callers do not change.
//
// See docs/supabase-platform.md.

import { createClient } from '@supabase/supabase-js';
import { initializeApp } from 'firebase/app';
import * as fb from 'firebase/auth';

export const AUTH_PROVIDER = (import.meta.env.VITE_AUTH_PROVIDER || 'firebase').toLowerCase();
export const isSupabase = AUTH_PROVIDER === 'supabase';

// ---------------------------------------------------------------- Supabase

function wrapSupabaseUser(session) {
  if (!session?.user) return null;
  const u = session.user;
  return {
    uid: u.id,
    email: u.email,
    emailVerified: Boolean(u.email_confirmed_at),
    displayName: u.user_metadata?.full_name || u.user_metadata?.name || null,
    isAdmin: false,
    provider: 'supabase',
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

let supabase = null;
let supabaseAuth = null;

if (isSupabase) {
  supabase = createClient(
    import.meta.env.VITE_SUPABASE_URL,
    import.meta.env.VITE_SUPABASE_ANON_KEY,
    { auth: { flowType: 'pkce', persistSession: true, autoRefreshToken: true } },
  );

  supabaseAuth = {
    provider: 'supabase',
    currentUser: null,
    client: supabase,
  };

  supabase.auth.onAuthStateChange((_event, session) => {
    supabaseAuth.currentUser = wrapSupabaseUser(session);
  });
}

// ---------------------------------------------------------------- Firebase

let firebaseAuth = null;

if (!isSupabase) {
  const app = initializeApp({
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
    authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
    storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
    messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
    appId: import.meta.env.VITE_FIREBASE_APP_ID,
    measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID,
  });
  firebaseAuth = fb.getAuth(app);
  firebaseAuth.provider = 'firebase';
}

// ---------------------------------------------------------------- Exports

export const auth = isSupabase ? supabaseAuth : firebaseAuth;

/** Firebase-style getAuth() for components that call it directly. */
export function getAuth() {
  return auth;
}

function unwrapSupabase({ data, error }) {
  if (error) throw new Error(error.message);
  return data;
}

export function onAuthStateChanged(_auth, callback) {
  if (!isSupabase) return fb.onAuthStateChanged(_auth, callback);

  // Deliver the persisted session first, then live changes.
  let fired = false;
  supabase.auth.getSession().then(({ data }) => {
    if (fired) return;
    fired = true;
    supabaseAuth.currentUser = wrapSupabaseUser(data.session);
    callback(supabaseAuth.currentUser);
  });
  const { data } = supabase.auth.onAuthStateChange((event, session) => {
    if (event === 'INITIAL_SESSION') return;
    fired = true;
    supabaseAuth.currentUser = wrapSupabaseUser(session);
    callback(supabaseAuth.currentUser);
  });
  return () => data.subscription.unsubscribe();
}

export async function signOut(_auth) {
  if (!isSupabase) return fb.signOut(_auth);
  unwrapSupabase(await supabase.auth.signOut());
  supabaseAuth.currentUser = null;
}

export async function signInWithEmailAndPassword(_auth, email, password) {
  if (!isSupabase) return fb.signInWithEmailAndPassword(_auth, email, password);
  const data = unwrapSupabase(await supabase.auth.signInWithPassword({ email, password }));
  supabaseAuth.currentUser = wrapSupabaseUser(data.session);
  return { user: supabaseAuth.currentUser };
}

export async function createUserWithEmailAndPassword(_auth, email, password) {
  if (!isSupabase) return fb.createUserWithEmailAndPassword(_auth, email, password);
  const data = unwrapSupabase(await supabase.auth.signUp({ email, password }));
  if (!data.session) {
    // Email confirmation is on for this project: the user must confirm before
    // a session exists. Surface that as a friendly message.
    const err = new Error('confirm-email');
    err.code = 'auth/confirm-email';
    throw err;
  }
  supabaseAuth.currentUser = wrapSupabaseUser(data.session);
  return { user: supabaseAuth.currentUser };
}

export async function sendPasswordResetEmail(_auth, email) {
  if (!isSupabase) return fb.sendPasswordResetEmail(_auth, email);
  unwrapSupabase(await supabase.auth.resetPasswordForEmail(email, {
    redirectTo: `${window.location.origin}/auth/action?mode=resetPassword`,
  }));
}

export async function updatePassword(user, newPassword) {
  if (!isSupabase) return fb.updatePassword(user, newPassword);
  unwrapSupabase(await supabase.auth.updateUser({ password: newPassword }));
}

export async function updateEmail(user, newEmail) {
  if (!isSupabase) return fb.updateEmail(user, newEmail);
  unwrapSupabase(await supabase.auth.updateUser({ email: newEmail }));
}

export async function updateProfile(user, { displayName }) {
  if (!isSupabase) return fb.updateProfile(user, { displayName });
  unwrapSupabase(await supabase.auth.updateUser({ data: { full_name: displayName } }));
  if (supabaseAuth.currentUser) supabaseAuth.currentUser.displayName = displayName;
}

/** Firebase reauth shape. On Supabase, re-sign-in with the current password. */
export const EmailAuthProvider = {
  credential(email, password) {
    return isSupabase ? { email, password } : fb.EmailAuthProvider.credential(email, password);
  },
};

export async function reauthenticateWithCredential(user, credential) {
  if (!isSupabase) return fb.reauthenticateWithCredential(user, credential);
  unwrapSupabase(await supabase.auth.signInWithPassword(credential));
}

// Password-reset / email-action page (Firebase action codes vs Supabase links).
export async function verifyPasswordResetCode(_auth, code) {
  if (!isSupabase) return fb.verifyPasswordResetCode(_auth, code);
  const { data } = await supabase.auth.getSession();
  if (!data.session) throw new Error('Reset link is invalid or has expired.');
  return data.session.user.email;
}

export async function confirmPasswordReset(_auth, _code, newPassword) {
  if (!isSupabase) return fb.confirmPasswordReset(_auth, _code, newPassword);
  unwrapSupabase(await supabase.auth.updateUser({ password: newPassword }));
}

export async function applyActionCode(_auth, code) {
  if (!isSupabase) return fb.applyActionCode(_auth, code);
  // Supabase confirms email through its own redirect; nothing to apply here.
}
