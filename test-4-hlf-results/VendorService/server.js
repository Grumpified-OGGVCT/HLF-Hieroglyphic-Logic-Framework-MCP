const express = require('express');
const bodyParser = require('body-parser');
const connectDB = require('./config/db');
const vendorRoutes = require('./routes/vendors');

const app = express();
app.use(bodyParser.json());

connectDB();

app.use('/api/vendors', vendorRoutes);

const PORT = process.env.PORT || 3003;
app.listen(PORT, () => console.log(`VendorService running on port ${PORT}`));

module.exports = app;
