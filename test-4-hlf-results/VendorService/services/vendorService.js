const Vendor = require('../models/Vendor');

const createVendor = async (vendorData, user) => {
  const { name, email, phone, address, taxId } = vendorData;
  if (!name || !email) {
    throw new Error('Name and email are required');
  }
  const vendor = new Vendor({
    name,
    email,
    phone,
    address,
    taxId,
    status: 'pending',
    createdBy: user.id,
  });
  await vendor.save();
  return vendor;
};

const getVendors = async (filters) => {
  const query = {};
  if (filters.status) {
    query.status = filters.status;
  }
  if (filters.createdBy) {
    query.createdBy = filters.createdBy;
  }
  return Vendor.find(query).sort({ createdAt: -1 });
};

const getVendorById = async (id) => {
  return Vendor.findById(id);
};

const updateVendor = async (id, updateData, user) => {
  const vendor = await Vendor.findById(id);
  if (!vendor) throw new Error('Vendor not found');
  const allowedUpdates = ['name', 'email', 'phone', 'address', 'taxId'];
  const updates = {};
  for (const key of Object.keys(updateData)) {
    if (allowedUpdates.includes(key)) {
      updates[key] = updateData[key];
    }
  }
  Object.assign(vendor, updates);
  await vendor.save();
  return vendor;
};

const deleteVendor = async (id, user) => {
  const vendor = await Vendor.findById(id);
  if (!vendor) throw new Error('Vendor not found');
  if (user.role !== 'admin') throw new Error('Unauthorized: admin only');
  await vendor.deleteOne();
};

const approveVendor = async (id, comment, user) => {
  if (user.role !== 'admin') throw new Error('Unauthorized: admin only');
  const vendor = await Vendor.findById(id);
  if (!vendor) throw new Error('Vendor not found');
  if (vendor.status === 'approved') throw new Error('Vendor already approved');
  vendor.status = 'approved';
  vendor.approvalHistory.push({
    status: 'approved',
    changedBy: user.id,
    comment: comment || '',
    timestamp: new Date()
  });
  await vendor.save();
  return vendor;
};

const rejectVendor = async (id, comment, user) => {
  if (user.role !== 'admin') throw new Error('Unauthorized: admin only');
  const vendor = await Vendor.findById(id);
  if (!vendor) throw new Error('Vendor not found');
  if (vendor.status === 'rejected') throw new Error('Vendor already rejected');
  vendor.status = 'rejected';
  vendor.approvalHistory.push({
    status: 'rejected',
    changedBy: user.id,
    comment: comment || '',
    timestamp: new Date()
  });
  await vendor.save();
  return vendor;
};

module.exports = {
  createVendor,
  getVendors,
  getVendorById,
  updateVendor,
  deleteVendor,
  approveVendor,
  rejectVendor,
};
