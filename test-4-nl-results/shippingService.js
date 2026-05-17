class ShippingService {
  calculateShippingCost(weight, distance, method = 'standard') {
    const baseRate = 5.0;
    const weightRate = 0.5 * weight;
    const distanceRate = 0.01 * distance;
    let multiplier = 1;
    if (method === 'express') multiplier = 1.5;
    else if (method === 'overnight') multiplier = 2.0;
    return (baseRate + weightRate + distanceRate) * multiplier;
  }

  generateTrackingNumber() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let tracking = '';
    for (let i = 0; i < 10; i++) {
      tracking += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return `SHIP${tracking}`;
  }

  shipOrder(orderId, address, shippingMethod = 'standard') {
    const trackingNumber = this.generateTrackingNumber();
    const cost = this.calculateShippingCost(1, 100, shippingMethod); // dummy weight/distance
    console.log(`Shipping order ${orderId} to ${address} with tracking ${trackingNumber}`);
    return {
      orderId,
      trackingNumber,
      cost,
      status: 'shipped',
      estimatedDelivery: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString()
    };
  }
}

module.exports = ShippingService;
