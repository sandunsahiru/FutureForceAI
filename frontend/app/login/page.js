// app/login/page.js
"use client";
import { useState } from "react";
import Header from "../Header";
import Footer from "../Footer";
import Link from "next/link";

export default function LoginPage() {
  const [credentials, setCredentials] = useState({ email: "", password: "" });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validateForm = () => {
    const newErrors = {};
    
    // Validate email
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!credentials.email.trim()) {
      newErrors.email = "Email is required";
    } else if (!emailRegex.test(credentials.email)) {
      newErrors.email = "Please enter a valid email address";
    }
    
    // Validate password
    if (!credentials.password) {
      newErrors.password = "Password is required";
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setCredentials((prev) => ({ ...prev, [name]: value }));
    
    // Clear error for this field when user types
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: null }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Validate form
    if (!validateForm()) {
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(credentials),
      });

      const data = await res.json();
      if (!res.ok) {
        setErrors((prev) => ({ 
          ...prev, 
          form: data.error || "Invalid email or password" 
        }));
      } else {
        console.log("Login successful:", data.message);
        // The cookie is automatically set by Next.js
        window.location.href = "/dashboard";
      }
    } catch (error) {
      console.error("Error logging in:", error);
      setErrors((prev) => ({ 
        ...prev, 
        form: "An unexpected error occurred. Please try again." 
      }));
    } finally {
      setIsSubmitting(false);
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
          
          {errors.form && (
            <div className="mb-4 p-3 bg-red-50 border border-red-300 text-red-700 rounded-md">
              {errors.form}
            </div>
          )}
          
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Email Field */}
            <div>
              <label
                htmlFor="email"
                className="block text-gray-700 font-medium mb-2"
              >
                Email <span className="text-red-500">*</span>
              </label>
              <input
                id="email"
                name="email"
                type="email"
                value={credentials.email}
                onChange={handleChange}
                required
                className={`w-full px-4 py-2 border ${
                  errors.email ? 'border-red-500' : 'border-gray-300'
                } rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500`}
                placeholder="e.g. john@example.com"
              />
              {errors.email && (
                <p className="text-red-500 text-sm mt-1">{errors.email}</p>
              )}
            </div>

            {/* Password Field */}
            <div>
              <label
                htmlFor="password"
                className="block text-gray-700 font-medium mb-2"
              >
                Password <span className="text-red-500">*</span>
              </label>
              <input
                id="password"
                name="password"
                type="password"
                value={credentials.password}
                onChange={handleChange}
                required
                className={`w-full px-4 py-2 border ${
                  errors.password ? 'border-red-500' : 'border-gray-300'
                } rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500`}
                placeholder="********"
              />
              {errors.password && (
                <p className="text-red-500 text-sm mt-1">{errors.password}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-3 bg-gradient-to-r from-purple-600 to-blue-500 text-white font-semibold rounded-full hover:shadow-lg transition-all disabled:opacity-70 disabled:cursor-not-allowed"
            >
              {isSubmitting ? "Logging In..." : "Log In"}
            </button>
            
            <div className="text-center mt-4">
              <p className="text-gray-600">
                Don't have an account?{" "}
                <Link href="/register" className="text-purple-600 hover:text-purple-800 font-medium">
                  Sign Up
                </Link>
              </p>
            </div>
          </form>
        </div>
      </div>
      <Footer />
    </>
  );
}