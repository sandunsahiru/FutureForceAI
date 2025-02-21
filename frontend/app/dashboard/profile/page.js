// frontend/app/dashboard/profile/page.js
"use client";
import { useState, useEffect } from "react";
import Header from "../../Header";
import Footer from "../../Footer";

export default function ProfilePage() {
  const [profile, setProfile] = useState({
    fullName: "",
    email: "",
    careerInterest: "",
    experience: "",
  });

  // Simulate fetching profile data from an API
  useEffect(() => {
    const fetchProfile = async () => {
      // Replace with an actual API call when available.
      const data = {
        fullName: "John Doe",
        email: "john@example.com",
        careerInterest: "Software Engineering",
        experience: 3,
      };
      setProfile(data);
    };
    fetchProfile();
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setProfile((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    // TODO: Implement profile update API call here
    console.log("Profile Updated:", profile);
  };

  return (
    <>
      <Header />
      <div className="min-h-screen bg-slate-50 flex flex-col items-center pt-24 pb-10 px-4">
        <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl p-8">
          <h2 className="text-3xl font-bold text-center text-purple-700 mb-6">
            Your Profile
          </h2>
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Full Name */}
            <div>
              <label htmlFor="fullName" className="block text-gray-700 font-medium mb-2">
                Full Name
              </label>
              <input
                id="fullName"
                name="fullName"
                type="text"
                value={profile.fullName}
                onChange={handleChange}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                placeholder="e.g. John Doe"
              />
            </div>

            {/* Email */}
            <div>
              <label htmlFor="email" className="block text-gray-700 font-medium mb-2">
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                value={profile.email}
                onChange={handleChange}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                placeholder="e.g. john@example.com"
              />
            </div>

            {/* Career Interest */}
            <div>
              <label htmlFor="careerInterest" className="block text-gray-700 font-medium mb-2">
                Primary Career Interest
              </label>
              <input
                id="careerInterest"
                name="careerInterest"
                type="text"
                value={profile.careerInterest}
                onChange={handleChange}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                placeholder="e.g. Software Engineering"
              />
            </div>

            {/* Experience */}
            <div>
              <label htmlFor="experience" className="block text-gray-700 font-medium mb-2">
                Years of Experience
              </label>
              <input
                id="experience"
                name="experience"
                type="number"
                min="0"
                value={profile.experience}
                onChange={handleChange}
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                placeholder="e.g. 3"
              />
            </div>

            <button
              type="submit"
              className="w-full py-3 bg-gradient-to-r from-purple-600 to-blue-500 text-white font-semibold rounded-full hover:shadow-lg transition-all"
            >
              Update Profile
            </button>
          </form>
        </div>
      </div>
      <Footer />
    </>
  );
}