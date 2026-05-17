let products = [];
let nextId = 1;

const getAll = () => {
  return Promise.resolve(products);
};

const getById = (id) => {
  const product = products.find(p => p.id === id);
  return Promise.resolve(product || null);
};

const create = (data) => {
  if (!data || !data.name || !data.price) {
    return Promise.reject(new Error('Product name and price are required'));
  }
  const newProduct = {
    id: nextId++,
    name: data.name,
    price: data.price,
    description: data.description || ''
  };
  products.push(newProduct);
  return Promise.resolve(newProduct);
};

const update = (id, data) => {
  const index = products.findIndex(p => p.id === id);
  if (index === -1) {
    return Promise.resolve(null);
  }
  if (data.name !== undefined) products[index].name = data.name;
  if (data.price !== undefined) products[index].price = data.price;
  if (data.description !== undefined) products[index].description = data.description;
  return Promise.resolve(products[index]);
};

const deleteProduct = (id) => {
  const index = products.findIndex(p => p.id === id);
  if (index === -1) {
    return Promise.resolve(false);
  }
  products.splice(index, 1);
  return Promise.resolve(true);
};

module.exports = {
  getAll,
  getById,
  create,
  update,
  delete: deleteProduct
};
