const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

async function takeScreenshot(htmlFile, outputBase, sizes) {
    const browser = await puppeteer.launch({
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const page = await browser.newPage();

    for (const size of sizes) {
        console.log(`Generating ${size.name} version: ${size.width}x${size.height}`);

        await page.setViewport({
            width: size.width,
            height: size.height
        });

        await page.goto(`file://${htmlFile}`, {
            waitUntil: 'networkidle0',
            timeout: 30000
        });

        // 等待字体和样式加载
        await page.waitForTimeout(1000);

        const outputPath = `${outputBase}-${size.name}.png`;
        await page.screenshot({
            path: outputPath,
            fullPage: false
        });

        console.log(`Saved: ${outputPath}`);
    }

    await browser.close();
}

async function main() {
    const docsPath = __dirname;
    const sizes = [
        { name: 'ppt', width: 1920, height: 1080 },     // PPT 16:9
        { name: 'ppt-hd', width: 2560, height: 1440 },  // PPT 高清 16:9
        { name: 'phone', width: 1080, height: 1920 },   // 手机竖屏 9:16
        { name: 'phone-wide', width: 1170, height: 2532 } // iPhone 尺寸
    ];

    const htmlFiles = [
        { input: 'backend-arch-dark.html', output: 'backend-arch' },
        { input: 'frontend-arch-dark.html', output: 'frontend-arch' }
    ];

    for (const file of htmlFiles) {
        const htmlPath = path.join(docsPath, file.input);
        console.log(`\nProcessing: ${file.input}`);
        await takeScreenshot(htmlPath, path.join(docsPath, file.output), sizes);
    }

    console.log('\nAll done!');
}

main().catch(console.error);
