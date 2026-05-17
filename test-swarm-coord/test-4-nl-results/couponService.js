const coupons = {};

function createCoupon(code, discount, expiryDate) {
  if (coupons[code]) throw new Error('Coupon already exists');
  coupons[code] = { code, discount, expiryDate, used: false };
  return coupons[code];
}

function validateCoupon(code) {
  const coupon = coupons[code];
  if (!coupon) return false;
  if (coupon.used) return false;
  if (coupon.expiryDate && new Date(coupon.expiryDate) < new Date()) return false;
  return true;
}

function applyCoupon(code, total) {
  if (!validateCoupon(code)) throw new Error('Invalid or expired coupon');
  const coupon = coupons[code];
  const discounted = total * (1 - coupon.discount / 100);
  coupon.used = true;
  return discounted;
}

function resetCoupon(code) {
  if (coupons[code]) coupons[code].used = false;
}

module.exports = { createCoupon, validateCoupon, applyCoupon, resetCoupon };
