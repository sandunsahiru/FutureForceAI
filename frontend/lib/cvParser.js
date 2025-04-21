// frontend/lib/cvParser.js
import { readFile } from 'fs/promises';
import path from 'path';

/**
 * Extract text from a CV file
 * This is a frontend wrapper that calls the appropriate backend API
 * @param {File} file - The CV file object
 * @returns {Promise<string>} - The extracted text
 */
export async function extractTextFromFile(file) {
  try {
    // Create form data to send to API
    const formData = new FormData();
    formData.append('cv_file', file);
    
    // Send to backend API
    const response = await fetch('/api/interview/process-cv', {
      method: 'POST',
      body: formData,
      credentials: 'include'
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const data = await response.json();
    return data.extractedText || '';
  } catch (error) {
    console.error('Error extracting text from file:', error);
    return '';
  }
}

/**
 * Format and clean extracted CV text
 * @param {string} text - The extracted text
 * @returns {string} - The formatted text
 */
export function formatCVText(text) {
  if (!text) return '';
  
  // Replace multiple newlines with a single one
  let formatted = text.replace(/\n{3,}/g, '\n\n');
  
  // Remove excessive spaces
  formatted = formatted.replace(/[ \t]+/g, ' ');
  
  // Trim whitespace
  formatted = formatted.trim();
  
  return formatted;
}

/**
 * Extract key information from CV text
 * @param {string} text - The CV text
 * @returns {Object} - Extracted information (name, email, skills, etc.)
 */
export function extractCVInfo(text) {
  if (!text) return {};
  
  // Basic extraction - in production you'd want more sophisticated parsing
  const info = {
    name: '',
    email: '',
    phone: '',
    skills: [],
    education: [],
    experience: []
  };
  
  // Try to find email
  const emailMatch = text.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
  if (emailMatch) {
    info.email = emailMatch[0];
  }
  
  // Try to find phone number (basic pattern)
  const phoneMatch = text.match(/(\+\d{1,3}[-\s]?)?\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}/);
  if (phoneMatch) {
    info.phone = phoneMatch[0];
  }
  
  // This is simplified - a real implementation would be more sophisticated
  
  return info;
}