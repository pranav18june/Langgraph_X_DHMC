const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: "new" });
  const page = await browser.newPage();
  
  // Wait for dev server
  await new Promise(r => setTimeout(r, 2000));
  
  page.on('console', msg => console.log('BROWSER CONSOLE:', msg.text()));
  page.on('pageerror', err => console.log('BROWSER ERROR:', err.toString()));
  
  console.log("Navigating to Simulator...");
  await page.goto('http://localhost:5173/simulator');
  
  console.log("Waiting for Run Simulation button...");
  await page.waitForSelector('.btn--primary');
  
  console.log("Clicking Run Simulation...");
  await page.evaluate(() => {
    document.querySelector('.btn--primary').click();
  });
  
  console.log("Waiting for simulation to complete...");
  // Wait for the View Full Audit button to appear
  await page.waitForFunction(() => {
    const btns = Array.from(document.querySelectorAll('.btn--primary'));
    return btns.some(b => b.textContent.includes('View Full Audit'));
  }, { timeout: 30000 });
  
  console.log("Simulation complete! Navigating to Explorer...");
  await page.goto('http://localhost:5173/explorer');
  await page.waitForSelector('.explorer__header', { timeout: 5000 });
  
  const explorerContent = await page.evaluate(() => document.body.innerHTML);
  if (explorerContent.includes('No Chain Data Available')) {
    console.log("EXPLORER IS EMPTY! It shows 'No Chain Data Available'");
  } else {
    console.log("EXPLORER HAS DATA.");
    const treeHTML = await page.evaluate(() => {
      const tree = document.querySelector('.merkle-tree');
      return tree ? tree.innerHTML.substring(0, 200) : 'NO TREE';
    });
    console.log("TREE:", treeHTML);
  }
  
  console.log("Navigating to Glossary...");
  await page.goto('http://localhost:5173/glossary');
  await page.waitForSelector('.glossary__header', { timeout: 5000 });
  
  const glossaryContent = await page.evaluate(() => document.body.innerHTML);
  if (glossaryContent.includes('No terms found')) {
    console.log("GLOSSARY IS EMPTY! It shows 'No terms found'");
  } else {
    console.log("GLOSSARY HAS DATA.");
    const cards = await page.evaluate(() => document.querySelectorAll('.glossary__card').length);
    console.log(`Found ${cards} glossary cards.`);
  }
  
  await browser.close();
})();
