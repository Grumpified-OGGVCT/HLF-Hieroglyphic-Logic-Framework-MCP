const shippingData = {
  rates: [
    { carrier: 'Standard', price: 5.99, days: 5 },
    { carrier: 'Express', price: 12.99, days: 2 },
    { carrier: 'Overnight', price: 24.99, days: 1 }
  ],
  tracking: {
    'TRACK123': { status: 'In Transit', location: 'Memphis, TN', eta: '2025-04-10' },
    'TRACK456': { status: 'Delivered', location: 'Denver, CO', delivered: '2025-04-08' },
    'TRACK789': { status: 'Processing', location: 'Los Angeles, CA', eta: null }
  }
};

/**
 * Get shipping rates for a given package details.
 * @param {Object} packageDetails - { weight, dimensions, origin, destination }
 * @returns {Array} Array of rate objects
 */
function getShippingRates(packageDetails) {
  // Simulate rate calculation based on weight (simplified)
  const weight = packageDetails && packageDetails.weight ? packageDetails.weight : 1;
  return shippingData.rates.map(rate => ({
    ...rate,
    price: +(rate.price * weight).toFixed(2)
  }));
}

/**
 * Track a shipment by tracking number.
 * @param {string} trackingNumber
 * @returns {Object|null} Tracking info or null if not found
 */
function trackShipment(trackingNumber) {
  return shippingData.tracking[trackingNumber] || null;
}

module.exports = {
  getShippingRates,
  trackShipment
};