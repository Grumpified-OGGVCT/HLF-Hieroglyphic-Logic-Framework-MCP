const express = require('express');
const router = express.Router();
const vendorController = require('../controllers/vendorController');
const auth = require('../middleware/auth');
const { requireAdmin } = require('../middleware/auth');

router.use(auth);

router.post('/', vendorController.createVendor);
router.get('/', vendorController.getVendors);
router.get('/:id', vendorController.getVendorById);
router.put('/:id', vendorController.updateVendor);
router.delete('/:id', requireAdmin, vendorController.deleteVendor);
router.patch('/:id/approve', requireAdmin, vendorController.approveVendor);
router.patch('/:id/reject', requireAdmin, vendorController.rejectVendor);

module.exports = router;
