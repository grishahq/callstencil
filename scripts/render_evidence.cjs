// Render the actual generated HTML report, without reconstructing its UI.
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('playwright');
(async () => {
 const root = path.resolve(__dirname, '..');
 const browser = await chromium.launch({headless:true});
 const page = await browser.newPage({viewport:{width:1280,height:1620},deviceScaleFactor:1});
 await page.goto(pathToFileURL(path.join(root,'evidence/demo/report.html')).href);
 await page.screenshot({path:path.join(root,'campaign/assets/demo-report.png'),fullPage:false});
 await page.setViewportSize({width:1280,height:1000});
 await page.goto(pathToFileURL(path.join(root,'evidence/quickstart.html')).href);
 await page.screenshot({path:path.join(root,'campaign/assets/release-quickstart.png'),fullPage:false});
 await browser.close();
})();
