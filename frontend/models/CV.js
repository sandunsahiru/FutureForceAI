// frontend/models/CV.js
import mongoose from 'mongoose';

const CVSchema = new mongoose.Schema({
    userId: { 
        type: mongoose.Schema.Types.Mixed, // Accepts both string and ObjectId
        ref: 'User', 
        required: true 
      },
  filename: { 
    type: String, 
    required: true 
  },
  originalName: { 
    type: String, 
    required: true 
  },
  fileSize: { 
    type: Number, 
    required: true 
  },
  filePath: { 
    type: String 
  },
  contentType: { 
    type: String, 
    required: true 
  },
  extractedText: { 
    type: String, 
    default: '' 
  },
  uploadedAt: { 
    type: Date, 
    default: Date.now 
  },
  lastUsed: { 
    type: Date, 
    default: Date.now 
  },
  // New field for timestamp-based ID for consistent file naming
  fileId: {
    type: String,
    index: true  // Add index for faster lookups by fileId
  }
});

// Create indexes for faster lookups
CVSchema.index({ userId: 1 });
CVSchema.index({ uploadedAt: -1 });

export default mongoose.models.CV || mongoose.model('CV', CVSchema);