const puppeteer = require('puppeteer');
const path = require('path');

async function takeScreenshot(browser, htmlFile, outputPath, width, height) {
    const page = await browser.newPage();
    await page.setViewport({ width, height });

    await page.goto(`file://${htmlFile}`, {
        waitUntil: 'networkidle0',
        timeout: 30000
    });

    await new Promise(r => setTimeout(r, 500));

    await page.screenshot({
        path: outputPath,
        fullPage: false
    });

    await page.close();
    console.log(`Generated: ${path.basename(outputPath)}`);
}

async function main() {
    const docsPath = __dirname;
    const browser = await puppeteer.launch({
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    try {
        // PPT版本 (1920x1080 16:9)
        await takeScreenshot(
            browser,
            path.join(docsPath, 'backend-arch-ppt.html'),
            path.join(docsPath, 'backend-arch-ppt.png'),
            1920, 1080
        );
        await takeScreenshot(
            browser,
            path.join(docsPath, 'frontend-arch-ppt.html'),
            path.join(docsPath, 'frontend-arch-ppt.png'),
            1920, 1080
        );

        // 手机版本 (1080x1920 9:16)
        await takeScreenshot(
            browser,
            path.join(docsPath, 'backend-arch-phone.html'),
            path.join(docsPath, 'backend-arch-phone.png'),
            1080, 1920
        );
        await takeScreenshot(
            browser,
            path.join(docsPath, 'frontend-arch-phone.html'),
            path.join(docsPath, 'frontend-arch-phone.png'),
            1080, 1920
        );

        console.log('\nAll images generated successfully!');
    } finally {
        await browser.close();
    }
}

main().catch(console.error);
