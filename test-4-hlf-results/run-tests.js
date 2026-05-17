const { runTests } = require('./integration.test');
runTests().catch(err => {
  console.error(err);
  process.exit(1);
});
