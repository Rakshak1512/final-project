import { createContext, useContext, useEffect, useState } from "react";
import api from "../api/axios.js";
import {
  firebaseConfigured,
  firebaseAuth,
  registerFirebaseUser,
  signInFirebaseUser,
  getFirebaseIdToken,
  signOutFirebase,
} from "../lib/firebase.js";

const AuthContext = createContext(null);

function persistSession(data) {
  localStorage.setItem("sems-access-token", data.access_token);
  localStorage.setItem("sems-refresh-token", data.refresh_token);
  localStorage.setItem("sems-user", JSON.stringify(data.user));
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem("sems-user");
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });

  // If both token and user profile are already cached in localStorage, start with loading=false
  // so protected routes render instantly (0ms) without waiting for network roundtrips.
  const [loading, setLoading] = useState(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("sems-access-token") : null;
    const stored = typeof window !== "undefined" ? localStorage.getItem("sems-user") : null;
    return Boolean(token && !stored);
  });

  useEffect(() => {
    let isMounted = true;
    const bootstrap = async () => {
      const token = localStorage.getItem("sems-access-token");
      if (!token) {
        if (isMounted) setLoading(false);
        return;
      }
      try {
        const { data } = await api.get("/auth/me");
        if (isMounted) {
          setUser(data);
          localStorage.setItem("sems-user", JSON.stringify(data));
        }
      } catch (err) {
        // If 401 Unauthorized, token is expired/invalid
        if (err.response?.status === 401 && isMounted) {
          localStorage.removeItem("sems-access-token");
          localStorage.removeItem("sems-refresh-token");
          localStorage.removeItem("sems-user");
          setUser(null);
        }
      } finally {
        if (isMounted) setLoading(false);
      }
      setLoading(false);
    };
    bootstrap();
    return () => {
      isMounted = false;
    };
  }, []);

  const login = async ({ email, password, role, remember_me }) => {
    // 1. Authoritative EventSphere backend authentication (enforces email verification, roles, approvals)
    const { data } = await api.post("/auth/login", {
      email: email.trim().toLowerCase(),
      password,
      role,
      remember_me,
    });

    persistSession(data);
    setUser(data.user);

    // 2. Synchronize Firebase Authentication client session if configured
    if (firebaseConfigured) {
      try {
        await signInFirebaseUser(email, password);
      } catch {
        // Firebase client state sync is non-blocking for authorized JWT session
      }
    }

    return data.user;
  };

  const register = async (payload) => {
    // Direct backend registration sending Gmail SMTP OTP
    const { data } = await api.post("/auth/register", {
      name: payload.name,
      email: payload.email,
      password: payload.password,
      confirm_password: payload.confirm_password || payload.password,
      role: payload.role,
      registration_number: payload.registration_number,
      admin_id: payload.admin_id,
      department: payload.department,
      semester: payload.semester,
    });
    return {
      ...data,
      emailVerificationRequired: true,
    };
  };

  const verifyEmailOtp = async ({ email, otp_code }) => {
    const { data } = await api.post("/auth/verify-email", {
      email,
      otp_code,
    });
    return data;
  };

  const resendVerificationOtp = async ({ email }) => {
    const { data } = await api.post("/auth/resend-verification-otp", {
      email,
    });
    return data;
  };

  const refreshFirebaseSession = async (role, remember_me = false) => {
    if (!firebaseAuth?.currentUser) throw new Error("No Firebase account is currently signed in.");
    await firebaseAuth.currentUser.reload();
    if (!firebaseAuth.currentUser.emailVerified) {
      throw new Error("Your email is not verified yet. Open the verification email and click the link, then return here.");
    }

    const idToken = await getFirebaseIdToken(true);
    const { data } = await api.post("/auth/firebase/session", {
      id_token: idToken,
      role,
      remember_me,
    });
    persistSession(data);
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    try {
      await signOutFirebase();
    } catch {
      // Continue clearing the EventSphere session even if Firebase sign-out fails.
    }
    localStorage.removeItem("sems-access-token");
    localStorage.removeItem("sems-refresh-token");
    localStorage.removeItem("sems-user");
    setUser(null);
  };

  const deleteAccount = async () => {
    await api.delete("/users/me");
    await logout();
  };

  const updateUser = (updated) => {
    setUser(updated);
    localStorage.setItem("sems-user", JSON.stringify(updated));
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        setUser: updateUser,
        loading,
        firebaseConfigured,
        firebaseAuth,
        login,
        register,
        verifyEmailOtp,
        resendVerificationOtp,
        refreshFirebaseSession,
        logout,
        deleteAccount,
        updateUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
