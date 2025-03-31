"use client";
import { useState } from "react";
import Header from "../Header";
import Footer from "../Footer";

export default function LoginPage() {
  const [credentials, setCredentials] = useState({ email: "", password: "" });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setCredentials((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        // body is the JSON with email/password
        body: JSON.stringify(credentials),
      });

      const data = await res.json();
      if (!res.ok) {
        console.error("Login error:", data.error);
        return;
      }

      console.log("Login successful:", data.message);
      // Optionally check or store user info from data
      // The cookie is automatically set by Next.js
      window.location.href = "/dashboard";
    } catch (error) {
      console.error("Error logging in:", error);
    }
  };

  return (
    <>
      <Header />
      <div className="min-h-screen bg-slate-50 flex flex-col items-center pt-24 pb-10 px-4">
        <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-8">
          <h2 className="text-3xl font-bold text-center text-purple-700 mb-6">
            Log In to Your Account
          </h2>
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Email Field */}
            <div>
              <label
                htmlFor="email"
                className="block text-gray-700 font-medium mb-2"
              >
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                value={credentials.email}
                onChange={handleChange}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                placeholder="e.g. john@example.com"
              />
            </div>

            {/* Password Field */}
            <div>
              <label
                htmlFor="password"
                className="block text-gray-700 font-medium mb-2"
              >
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                value={credentials.password}
                onChange={handleChange}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                placeholder="********"
              />
            </div>

            <button
              type="submit"
              className="w-full py-3 bg-gradient-to-r from-purple-600 to-blue-500 text-white font-semibold rounded-full hover:shadow-lg transition-all"
            >
              Log In
            </button>
          </form>
        </div>
      </div>
      <Footer />
    </>
  );
}