// ReviewService - in-memory review management
// Uses CommonJS module exports

let reviews = [];
let nextId = 1;

/**
 * Add a new review
 * @param {Object} reviewData - { userId, productId, rating, comment }
 * @returns {Object} created review with id and timestamp
 */
function addReview(reviewData) {
  const review = {
    id: nextId++,
    userId: reviewData.userId,
    productId: reviewData.productId,
    rating: reviewData.rating,
    comment: reviewData.comment || '',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  };
  reviews.push(review);
  return review;
}

/**
 * Get all reviews, optionally filtered by productId or userId
 * @param {Object} filter - { productId, userId }
 * @returns {Array} array of reviews
 */
function getReviews(filter = {}) {
  let result = [...reviews];
  if (filter.productId) {
    result = result.filter(r => r.productId === filter.productId);
  }
  if (filter.userId) {
    result = result.filter(r => r.userId === filter.userId);
  }
  return result;
}

/**
 * Get a single review by id
 * @param {number} id
 * @returns {Object|null}
 */
function getReviewById(id) {
  return reviews.find(r => r.id === id) || null;
}

/**
 * Update an existing review
 * @param {number} id
 * @param {Object} updates - { rating, comment }
 * @returns {Object|null} updated review or null if not found
 */
function updateReview(id, updates) {
  const review = reviews.find(r => r.id === id);
  if (!review) return null;
  if (updates.rating !== undefined) review.rating = updates.rating;
  if (updates.comment !== undefined) review.comment = updates.comment;
  review.updatedAt = new Date().toISOString();
  return review;
}

/**
 * Delete a review
 * @param {number} id
 * @returns {boolean} true if deleted, false if not found
 */
function deleteReview(id) {
  const index = reviews.findIndex(r => r.id === id);
  if (index === -1) return false;
  reviews.splice(index, 1);
  return true;
}

module.exports = {
  addReview,
  getReviews,
  getReviewById,
  updateReview,
  deleteReview
};
