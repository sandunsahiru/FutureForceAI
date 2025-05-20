
import mongoose from 'mongoose';

const UserSchema = new mongoose.Schema({
  fullName: { type: String, required: true },
  email: { type: String, required: true, unique: true },
  passwordHash: { type: String, required: true },
  careerInterest: { type: String, required: true },
  experience: { type: Number, default: 0 },
  createdAt: { type: Date, default: Date.now },
});


export default mongoose.models.User || mongoose.model('User', UserSchema);