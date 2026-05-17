// ProductService: Product catalog with categories and variants
// In-memory store, CommonJS module

const generateId = (() => {
  let id = 0;
  return () => ++id;
})();

class ProductService {
  constructor() {
    this.categories = [];
    this.products = [];
  }

  // Category methods
  addCategory(name, parentId = null) {
    const id = generateId();
    const category = { id, name, parentId };
    this.categories.push(category);
    return category;
  }

  getCategory(id) {
    return this.categories.find(cat => cat.id === id) || null;
  }

  listCategories() {
    return this.categories;
  }

  // Product methods
  addProduct({ name, description, price, categoryId, variants = [] }) {
    if (!name || price == null) {
      throw new Error('Product must have a name and price');
    }
    const id = generateId();
    const normalizedVariants = variants.map(v => ({
      id: generateId(),
      name: v.name || 'Default',
      priceAdjustment: v.priceAdjustment || 0,
      stock: v.stock || 0,
      attributes: v.attributes || {}
    }));
    const product = {
      id,
      name,
      description: description || '',
      price,
      categoryId: categoryId || null,
      variants: normalizedVariants
    };
    this.products.push(product);
    return product;
  }

  getProduct(id) {
    return this.products.find(prod => prod.id === id) || null;
  }

  updateProduct(id, updates) {
    const product = this.getProduct(id);
    if (!product) return null;
    Object.assign(product, updates);
    return product;
  }

  deleteProduct(id) {
    const index = this.products.findIndex(prod => prod.id === id);
    if (index === -1) return false;
    this.products.splice(index, 1);
    return true;
  }

  listProducts(categoryId = null) {
    if (categoryId) {
      return this.products.filter(p => p.categoryId === categoryId);
    }
    return this.products;
  }

  // Variant methods on a product
  addVariant(productId, variant) {
    const product = this.getProduct(productId);
    if (!product) return null;
    const newVariant = {
      id: generateId(),
      name: variant.name || 'New Variant',
      priceAdjustment: variant.priceAdjustment || 0,
      stock: variant.stock || 0,
      attributes: variant.attributes || {}
    };
    product.variants.push(newVariant);
    return newVariant;
  }

  updateVariant(productId, variantId, updates) {
    const product = this.getProduct(productId);
    if (!product) return null;
    const variant = product.variants.find(v => v.id === variantId);
    if (!variant) return null;
    Object.assign(variant, updates);
    return variant;
  }

  deleteVariant(productId, variantId) {
    const product = this.getProduct(productId);
    if (!product) return false;
    const index = product.variants.findIndex(v => v.id === variantId);
    if (index === -1) return false;
    product.variants.splice(index, 1);
    return true;
  }

  getVariant(productId, variantId) {
    const product = this.getProduct(productId);
    if (!product) return null;
    return product.variants.find(v => v.id === variantId) || null;
  }
}

module.exports = ProductService;
