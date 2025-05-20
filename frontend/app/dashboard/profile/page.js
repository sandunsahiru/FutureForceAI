// frontend/app/dashboard/profile/page.js
"use client";
import { useState, useEffect } from "react";
import Header from "../../Header";
import Footer from "../../Footer";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function ProfilePage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);
  const [profile, setProfile] = useState({
    fullName: "",
    email: "",
    careerInterest: "",
    experience: 0,
  });

  // Fetch authenticated user's profile data
  useEffect(() => {
    const fetchUserProfile = async () => {
      try {
        // Check if user is authenticated
        const authResponse = await fetch("/api/auth/check", {
          method: "GET",
          credentials: "include",
        });
        
        if (!authResponse.ok) {
          router.push("/login");
          return;
        }
        
        const authData = await authResponse.json();
        if (!authData.authenticated || !authData.userId) {
          router.push("/login");
          return;
        }
        
        // Fetch user profile
        const profileResponse = await fetch(`/api/users/profile`, {
          method: "GET",
          credentials: "include",
        });
        
        if (!profileResponse.ok) {
          throw new Error("Failed to fetch profile data");
        }
        
        const profileData = await profileResponse.json();
        setProfile({
          fullName: profileData.fullName || "",
          email: profileData.email || "",
          careerInterest: profileData.careerInterest || "",
          experience: profileData.experience || 0,
        });
      } catch (err) {
        console.error("Error fetching profile:", err);
        setError("Failed to load your profile. Please try again.");
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchUserProfile();
  }, [router]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    
    // Convert experience to number when it's the experience field
    if (name === "experience") {
      setProfile((prev) => ({ ...prev, [name]: parseInt(value) || 0 }));
    } else {
      setProfile((prev) => ({ ...prev, [name]: value }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    
    try {
      const response = await fetch("/api/users/profile", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(profile),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to update profile");
      }
      
      // Show success message
      alert("Profile updated successfully!");
    } catch (err) {
      console.error("Error updating profile:", err);
      setError(err.message || "Failed to update profile");
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <>
        <Header />
        <div className="min-h-screen bg-slate-50 flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500 mx-auto"></div>
            <p className="mt-3 text-gray-600">Loading your profile...</p>
          </div>
        </div>
        <Footer />
      </>
    );
  }

  return (
    <>
      <Header />
      <div className="min-h-screen bg-slate-50 flex flex-col items-center pt-24 pb-10 px-4">
        <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl p-8">
          <h2 className="text-3xl font-bold text-center text-purple-700 mb-6">
            Your Profile
          </h2>
          
          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
              <p>{error}</p>
            </div>
          )}
          
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
                className="w-full px-4 py-2 border border-gray-300 bg-gray-50 rounded-md focus:outline-none"
                placeholder="e.g. john@example.com"
                readOnly
              />
              <p className="text-xs text-gray-500 mt-1">Email cannot be changed</p>
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
              disabled={isSaving}
              className="w-full py-3 bg-gradient-to-r from-purple-600 to-blue-500 text-white font-semibold rounded-full hover:shadow-lg transition-all disabled:opacity-70 disabled:cursor-not-allowed"
            >
              {isSaving ? "Updating..." : "Update Profile"}
            </button>
            
            {/* Back to Dashboard Button */}
            <Link 
              href="/dashboard" 
              className="block w-full py-3 bg-gray-100 text-gray-700 font-semibold rounded-full text-center hover:bg-gray-200 transition-all"
            >
              Back to Dashboard
            </Link>
          </form>
        </div>
      </div>
      <Footer />
    </>
  );
}