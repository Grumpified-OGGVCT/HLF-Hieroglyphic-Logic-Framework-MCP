// CustomerService Agent - Customer profiles and address book

const customers = [];
const addresses = [];
let nextCustomerId = 1;
let nextAddressId = 1;

function registerCustomer(name, email, phone) {
    const customer = {
        id: nextCustomerId++,
        name,
        email,
        phone,
        createdAt: new Date()
    };
    customers.push(customer);
    return customer;
}

function getCustomerById(id) {
    return customers.find(c => c.id === id) || null;
}

function updateCustomer(id, updates) {
    const customer = getCustomerById(id);
    if (!customer) return null;
    Object.assign(customer, updates);
    return customer;
}

function deleteCustomer(id) {
    const index = customers.findIndex(c => c.id === id);
    if (index === -1) return false;
    customers.splice(index, 1);
    // remove associated addresses
    for (let i = addresses.length - 1; i >= 0; i--) {
        if (addresses[i].customerId === id) {
            addresses.splice(i, 1);
        }
    }
    return true;
}

function addAddressToCustomer(customerId, type, street, city, state, zip, country) {
    // ensure customer exists
    if (!getCustomerById(customerId)) return null;
    const address = {
        id: nextAddressId++,
        customerId,
        type, // 'billing' or 'shipping'
        street,
        city,
        state,
        zip,
        country
    };
    addresses.push(address);
    return address;
}

function updateAddress(addressId, updates) {
    const address = addresses.find(a => a.id === addressId);
    if (!address) return null;
    Object.assign(address, updates);
    return address;
}

function deleteAddress(addressId) {
    const index = addresses.findIndex(a => a.id === addressId);
    if (index === -1) return false;
    addresses.splice(index, 1);
    return true;
}

function getAddressesForCustomer(customerId) {
    return addresses.filter(a => a.customerId === customerId);
}

module.exports = {
    registerCustomer,
    getCustomerById,
    updateCustomer,
    deleteCustomer,
    addAddressToCustomer,
    updateAddress,
    deleteAddress,
    getAddressesForCustomer
};
