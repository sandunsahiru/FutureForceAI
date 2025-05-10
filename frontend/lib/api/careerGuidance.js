/**
 * Career Guidance API utility functions
 */

/**
 * Upload a CV file for career analysis
 * @param {File} cvFile - The CV file to upload
 * @returns {Promise<Object>} - Response with CV ID
 */
export async function uploadCV(cvFile) {
    const formData = new FormData();
    formData.append('cv_file', cvFile);
  
    const response = await fetch('/api/career-guidance/upload-cv', {
      method: 'POST',
      body: formData,
      credentials: 'include',
    });
  
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to upload CV');
    }
  
    return response.json();
  }
  
  /**
   * Analyze career path based on CV and preferences
   * @param {string} cvId - The ID of the uploaded CV
   * @param {Array<string>} careerInterests - List of career interests
   * @param {Object} careerGoals - Career goals object
   * @returns {Promise<Object>} - Career analysis results
   */
  export async function analyzeCareerPath(cvId, careerInterests, careerGoals = {}) {
    const response = await fetch('/api/career-guidance/analyze', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        cv_id: cvId,
        career_interests: careerInterests,
        career_goals: careerGoals
      }),
      credentials: 'include',
    });
  
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to analyze career path');
    }
  
    return response.json();
  }
  
  /**
   * Get career guidance history
   * @returns {Promise<Object>} - Career guidance history
   */
  export async function getCareerGuidanceHistory() {
    const response = await fetch('/api/career-guidance/history', {
      method: 'GET',
      credentials: 'include',
    });
  
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to fetch career guidance history');
    }
  
    return response.json();
  }
  
  /**
   * Get market data for a job role
   * @param {string} jobRole - The job role to get market data for
   * @param {string} location - Optional location filter
   * @returns {Promise<Object>} - Market data for the job role
   */
  export async function getMarketData(jobRole, location = null) {
    const response = await fetch('/api/career-guidance/market-data', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        job_role: jobRole,
        location: location
      }),
      credentials: 'include',
    });
  
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to fetch market data');
    }
  
    return response.json();
  }