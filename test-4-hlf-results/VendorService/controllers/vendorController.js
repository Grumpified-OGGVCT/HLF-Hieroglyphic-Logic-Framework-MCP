const Vendor = require('../models/Vendor');
const vendorService = require('../services/vendorService');

// Create vendor
exports.createVendor = async (req, res) => {
  try {
    const vendor = await vendorService.createVendor(req.body, req.user);
    res.status(201).json(vendor);
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
};

// Get all vendors
exports.getVendors = async (req, res) => {
  try {
    const vendors = await vendorService.getVendors(req.query);
    res.json(vendors);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

// Get single vendor
exports.getVendorById = async (req, res) => {
  try {
    const vendor = await vendorService.getVendorById(req.params.id);
    if (!vendor) return res.status(404).json({ error: 'Vendor not found' });
    res.json(vendor);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

// Update vendor
exports.updateVendor = async (req, res) => {
  try {
    const vendor = await vendorService.updateVendor(req.params.id, req.body, req.user);
    if (!vendor) return res.status(404).json({ error: 'Vendor not found' });
    res.json(vendor);
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
};

// Delete vendor
exports.deleteVendor = async (req, res) => {
  try {
    await vendorService.deleteVendor(req.params.id, req.user);
    res.json({ message: 'Vendor deleted' });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
};

// Approve vendor
exports.approveVendor = async (req, res) => {
  try {
    const vendor = await vendorService.approveVendor(req.params.id, req.body.comment, req.user);
    res.json(vendor);
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
};

// Reject vendor
exports.rejectVendor = async (req, res) => {
  try {
    const vendor = await vendorService.rejectVendor(req.params.id, req.body.comment, req.user);
    res.json(vendor);
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
};
