const mongoose = require('mongoose');

const approvalHistorySchema = new mongoose.Schema({
  status: { type: String, enum: ['approved', 'rejected'], required: true },
  changedBy: { type: String, required: true },
  comment: { type: String, default: '' },
  timestamp: { type: Date, default: Date.now }
}, { _id: false });

const vendorSchema = new mongoose.Schema({
  name: { type: String, required: true },
  email: { type: String, required: true, unique: true },
  phone: { type: String },
  address: { type: String },
  taxId: { type: String },
  status: { type: String, enum: ['pending', 'approved', 'rejected'], default: 'pending' },
  createdBy: { type: String, required: true },
  approvalHistory: [approvalHistorySchema],
}, { timestamps: true });

module.exports = mongoose.model('Vendor', vendorSchema);
