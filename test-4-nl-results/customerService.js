const customers = new Map();
let nextId = 1;

class CustomerService {
  getCustomer(id) {
    const customer = customers.get(id);
    if (!customer) {
      throw new Error(`Customer with id ${id} not found`);
    }
    return { ...customer };
  }

  createCustomer(data) {
    if (!data || !data.name) {
      throw new Error('Customer name is required');
    }
    const id = nextId++;
    const customer = { id, name: data.name, email: data.email || '', ...data };
    customers.set(id, customer);
    return { ...customer };
  }

  updateCustomer(id, data) {
    const existing = customers.get(id);
    if (!existing) {
      throw new Error(`Customer with id ${id} not found`);
    }
    const updated = { ...existing, ...data, id };
    customers.set(id, updated);
    return { ...updated };
  }

  deleteCustomer(id) {
    if (!customers.has(id)) {
      throw new Error(`Customer with id ${id} not found`);
    }
    customers.delete(id);
    return true;
  }

  listCustomers() {
    return Array.from(customers.values()).map(c => ({ ...c }));
  }
}

module.exports = CustomerService;