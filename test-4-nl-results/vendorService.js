const vendors = [];

class VendorService {
  async getVendor(id) {
    return vendors.find(v => v.id === id) || null;
  }

  async createVendor(data) {
    const id = Date.now().toString();
    const vendor = { id, ...data };
    vendors.push(vendor);
    return vendor;
  }

  async updateVendor(id, updates) {
    const index = vendors.findIndex(v => v.id === id);
    if (index === -1) return null;
    vendors[index] = { ...vendors[index], ...updates };
    return vendors[index];
  }

  async deleteVendor(id) {
    const index = vendors.findIndex(v => v.id === id);
    if (index === -1) return false;
    vendors.splice(index, 1);
    return true;
  }

  async listVendors() {
    return [...vendors];
  }
}

module.exports = VendorService;
