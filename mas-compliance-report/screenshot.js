const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1400, height: 900 });
  await page.goto('file://' + process.cwd() + '/index.html');
  await page.waitForTimeout(2000); // Wait for charts to render
  await page.screenshot({ path: 'report-screenshot.png', fullPage: true });
  console.log('Screenshot saved to report-screenshot.png');
  await browser.close();
})();
