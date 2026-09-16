const fs=require('fs');
const assert=require('assert');

const app=fs.readFileSync('src/memetrader/chain_web_static/app.js','utf8');

assert.match(
  app,
  /<td>\$\{time\(live\.updatedAt,true\)\}<\/td><\/tr>/,
  'strategy account update column must include the full date and time',
);
