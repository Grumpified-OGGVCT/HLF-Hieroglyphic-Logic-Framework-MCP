// In-memory store for reviews
let reviews = [];
let nextId = 1;

class Review {
  constructor({ userId, productId, rating, text }) {
    this.id = nextId++;
    this.userId = userId;
    this.productId = productId;
    this.rating = rating;
    this.text = text || '';
    this.status = 'pending'; // pending, approved, rejected
    this.createdAt = new Date().toISOString();
    this.updatedAt = this.createdAt;
  }
}

function createReview(data) {
  const review = new Review(data);
  reviews.push(review);
  return review;
}

function getAllReviews(filters = {}) {
  return reviews.filter(r => {
    if (filters.productId && r.productId !== filters.productId) return false;
    if (filters.userId && r.userId !== filters.userId) return false;
    if (filters.status && r.status !== filters.status) return false;
    return true;
  });
}

function getReviewById(id) {
  return reviews.find(r => r.id === id) || null;
}

function updateReview(id, updates) {
  const review = reviews.find(r => r.id === id);
  if (!review) return null;
  if (updates.rating !== undefined) review.rating = updates.rating;
  if (updates.text !== undefined) review.text = updates.text;
  review.updatedAt = new Date().toISOString();
  return review;
}

function deleteReview(id) {
  const index = reviews.findIndex(r => r.id === id);
  if (index === -1) return false;
  reviews.splice(index, 1);
  return true;
}

function moderateReview(id, status) {
  const review = reviews.find(r => r.id === id);
  if (!review) return null;
  if (!['approved', 'rejected'].includes(status)) {
    throw new Error('Invalid status. Use "approved" or "rejected".');
  }
  review.status = status;
  review.updatedAt = new Date().toISOString();
  return review;
}

module.exports = {
  createReview,
  getAllReviews,
  getReviewById,
  updateReview,
  deleteReview,
  moderateReview,
};