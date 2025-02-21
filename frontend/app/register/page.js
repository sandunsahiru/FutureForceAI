// app/register/page.js
"use client";
import { useState } from "react";

export default function RegisterPage() {
  const [formData, setFormData] = useState({
    fullName: "",
    email: "",
    password: "",
    careerInterest: "",
    experience: "",
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    // Send formData to the API route
    try {
      const res = await fetch('/api/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData),
      });

      const data = await res.json();
      if (!res.ok) {
        console.error("Registration error:", data.error);
        // You can also display an error message to the user here.
      } else {
        console.log("Registration successful:", data.message);
        // Redirect to login or home page, for example:
        window.location.href = "/login";
      }
    } catch (error) {
      console.error("Error submitting form:", error);
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
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Full Name */}
          <div>
            <label
              htmlFor="fullName"
              className="block text-gray-700 font-medium mb-2"
            >
              Full Name
            </label>
            <input
              id="fullName"
              name="fullName"
              type="text"
              value={formData.fullName}
              onChange={handleChange}
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
              placeholder="e.g. John Doe"
            />
          </div>

          {/* Email */}
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
              value={formData.email}
              onChange={handleChange}
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
              placeholder="e.g. john@example.com"
            />
          </div>

          {/* Password */}
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
              value={formData.password}
              onChange={handleChange}
              required
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
              placeholder="********"
            />
          </div>

          {/* Career Interest */}
          <div>
            <label
              htmlFor="careerInterest"
              className="block text-gray-700 font-medium mb-2"
            >
              Primary Career Interest
            </label>
            <input
              id="careerInterest"
              name="careerInterest"
              type="text"
              value={formData.careerInterest}
              onChange={handleChange}
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
              placeholder="e.g. Software Engineering"
            />
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
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
              placeholder="e.g. 3"
            />
          </div>

          <button
            type="submit"
            className="w-full py-3 bg-gradient-to-r from-purple-600 to-blue-500 text-white font-semibold rounded-full hover:shadow-lg transition-all"
          >
            Sign Up
          </button>
        </form>
      </div>
    </div>
    <Footer />
        </>
  );
}