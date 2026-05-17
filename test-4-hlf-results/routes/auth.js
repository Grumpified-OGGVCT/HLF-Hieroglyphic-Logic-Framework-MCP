const express = require('express');
const router = express.Router();
const authController = require('../controllers/authController');
const auth = require('../middleware/auth');

router.post('/register', authController.register);
router.post('/login', authController.login);
router.get('/protected', auth(), authController.protected);
router.get('/admin', auth(['admin']), authController.adminOnly);

module.exports = router;