// app/register/page.js
"use client";
import { useState } from "react";
import Header from "../Header";
import Footer from "../Footer";
import Link from "next/link";

export default function RegisterPage() {
    const [formData, setFormData] = useState({
        fullName: "",
        email: "",
        password: "",
        careerInterest: "",
        experience: "",
    });
    const [errors, setErrors] = useState({});
    const [isSubmitting, setIsSubmitting] = useState(false);

    const validateForm = () => {
        const newErrors = {};
        
        // Validate full name
        if (!formData.fullName.trim()) {
            newErrors.fullName = "Full name is required";
        }
        
        // Validate email
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!formData.email.trim()) {
            newErrors.email = "Email is required";
        } else if (!emailRegex.test(formData.email)) {
            newErrors.email = "Please enter a valid email address";
        }
        
        // Validate password
        if (!formData.password) {
            newErrors.password = "Password is required";
        } else if (formData.password.length < 6) {
            newErrors.password = "Password must be at least 6 characters";
        }
        
        // Validate career interest
        if (!formData.careerInterest.trim()) {
            newErrors.careerInterest = "Career interest is required";
        }
        
        // Experience is optional, but if provided, must be a number
        if (formData.experience && isNaN(Number(formData.experience))) {
            newErrors.experience = "Experience must be a number";
        }
        
        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData((prev) => ({ ...prev, [name]: value }));
        
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
        
        // Send formData to the API route
        try {
            const res = await fetch('/api/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    ...formData,
                    experience: formData.experience ? Number(formData.experience) : 0
                }),
            });

            const data = await res.json();
            if (!res.ok) {
                if (data.error === "Email already in use") {
                    setErrors((prev) => ({ ...prev, email: "This email is already registered" }));
                } else {
                    setErrors((prev) => ({ ...prev, form: data.error || "Registration failed" }));
                }
            } else {
                console.log("Registration successful:", data.message);
                // Redirect to login page
                window.location.href = "/login";
            }
        } catch (error) {
            console.error("Error submitting form:", error);
            setErrors((prev) => ({ ...prev, form: "An unexpected error occurred. Please try again." }));
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
                        Create Your Account
                    </h2>
                    
                    {errors.form && (
                        <div className="mb-4 p-3 bg-red-50 border border-red-300 text-red-700 rounded-md">
                            {errors.form}
                        </div>
                    )}
                    
                    <form onSubmit={handleSubmit} className="space-y-5">
                        {/* Full Name */}
                        <div>
                            <label
                                htmlFor="fullName"
                                className="block text-gray-700 font-medium mb-2"
                            >
                                Full Name <span className="text-red-500">*</span>
                            </label>
                            <input
                                id="fullName"
                                name="fullName"
                                type="text"
                                value={formData.fullName}
                                onChange={handleChange}
                                required
                                className={`w-full px-4 py-2 border ${
                                    errors.fullName ? 'border-red-500' : 'border-gray-300'
                                } rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500`}
                                placeholder="e.g. John Doe"
                            />
                            {errors.fullName && (
                                <p className="text-red-500 text-sm mt-1">{errors.fullName}</p>
                            )}
                        </div>

                        {/* Email */}
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
                                value={formData.email}
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

                        {/* Password */}
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
                                value={formData.password}
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
                            <p className="text-xs text-gray-500 mt-1">
                                Must be at least 6 characters
                            </p>
                        </div>

                        {/* Career Interest */}
                        <div>
                            <label
                                htmlFor="careerInterest"
                                className="block text-gray-700 font-medium mb-2"
                            >
                                Primary Career Interest <span className="text-red-500">*</span>
                            </label>
                            <input
                                id="careerInterest"
                                name="careerInterest"
                                type="text"
                                value={formData.careerInterest}
                                onChange={handleChange}
                                required
                                className={`w-full px-4 py-2 border ${
                                    errors.careerInterest ? 'border-red-500' : 'border-gray-300'
                                } rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500`}
                                placeholder="e.g. Software Engineering"
                            />
                            {errors.careerInterest && (
                                <p className="text-red-500 text-sm mt-1">{errors.careerInterest}</p>
                            )}
                        </div>

                        {/* Experience (Optional) */}
                        <div>
                            <label
                                htmlFor="experience"
                                className="block text-gray-700 font-medium mb-2"
                            >
                                Years of Experience
                            </label>
                            <input
                                id="experience"
                                name="experience"
                                type="number"
                                min="0"
                                value={formData.experience}
                                onChange={handleChange}
                                className={`w-full px-4 py-2 border ${
                                    errors.experience ? 'border-red-500' : 'border-gray-300'
                                } rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500`}
                                placeholder="e.g. 3"
                            />
                            {errors.experience && (
                                <p className="text-red-500 text-sm mt-1">{errors.experience}</p>
                            )}
                        </div>

                        <button
                            type="submit"
                            disabled={isSubmitting}
                            className="w-full py-3 bg-gradient-to-r from-purple-600 to-blue-500 text-white font-semibold rounded-full hover:shadow-lg transition-all disabled:opacity-70 disabled:cursor-not-allowed"
                        >
                            {isSubmitting ? "Creating Account..." : "Sign Up"}
                        </button>
                        
                        <div className="text-center mt-4">
                            <p className="text-gray-600">
                                Already have an account?{" "}
                                <Link href="/login" className="text-purple-600 hover:text-purple-800 font-medium">
                                    Log In
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