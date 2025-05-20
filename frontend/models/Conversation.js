
import mongoose from 'mongoose';

const ChatMessageSchema = new mongoose.Schema({
  sender: { type: String, required: true },
  text: { type: String, required: true }
});

const ConversationSchema = new mongoose.Schema({
  session_id: { type: String, required: true, unique: true },
  user_id: { type: mongoose.Schema.Types.ObjectId, ref: 'User', required: true },
  job_role: { type: String, required: true },
  cv_text: { type: String, required: true },
  messages: { type: [ChatMessageSchema], default: [] },
  createdAt: { type: Date, default: Date.now },
  finished: { type: Boolean, default: false }
});

export default mongoose.models.Conversation || mongoose.model('Conversation', ConversationSchema);