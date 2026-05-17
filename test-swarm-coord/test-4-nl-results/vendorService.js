const { EventEmitter } = require('events');

/**
 * In-memory vendor store and business logic.
 */
class VendorService extends EventEmitter {
  constructor() {
    super();
    this.vendors = new Map();
    this.counter = 0;
  }

  /**
   * Add a new vendor.
   * @param {Object} vendorData - must have name, optional description, contact
   * @returns {Object} created vendor with id
   */
  addVendor(vendorData) {
    if (!vendorData || !vendorData.name) {
      throw new Error('Vendor name is required');
    }
    const id = ++this.counter;
    const vendor = {
      id,
      name: vendorData.name,
      description: vendorData.description || '',
      contact: vendorData.contact || '',
      createdAt: new Date().toISOString()
    };
    this.vendors.set(id, vendor);
    this.emit('vendorAdded', vendor);
    return { ...vendor };
  }

  /**
   * Get a single vendor by id.
   * @param {number} id
   * @returns {Object|null}
   */
  getVendor(id) {
    const vendor = this.vendors.get(id);
    return vendor ? { ...vendor } : null;
  }

  /**
   * Update an existing vendor.
   * @param {number} id
   * @param {Object} updates - fields to update (name, description, contact)
   * @returns {Object} updated vendor
   */
  updateVendor(id, updates) {
    const vendor = this.vendors.get(id);
    if (!vendor) {
      throw new Error(`Vendor with id ${id} not found`);
    }
    const allowed = ['name', 'description', 'contact'];
    for (const key of allowed) {
      if (updates.hasOwnProperty(key)) {
        vendor[key] = updates[key];
      }
    }
    this.emit('vendorUpdated', vendor);
    return { ...vendor };
  }

  /**
   * Delete a vendor by id.
   * @param {number} id
   * @returns {boolean} true if deleted
   */
  deleteVendor(id) {
    const existed = this.vendors.has(id);
    if (existed) {
      const vendor = this.vendors.get(id);
      this.vendors.delete(id);
      this.emit('vendorDeleted', vendor);
    }
    return existed;
  }

  /**
   * List all vendors.
   * @returns {Array} array of vendor objects
   */
  listVendors() {
    return Array.from(this.vendors.values()).map(v => ({ ...v }));
  }
}

module.exports = VendorService;
