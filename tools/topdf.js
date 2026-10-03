const { chromium } = require('playwright');
const path = require('path');

const SCRATCH = '/tmp/claude-0/-home-user-claude/7eca4544-36b5-5140-8141-260e6072dd2c/scratchpad';
const OUT = '/home/user/claude/docs';

const JOBS = [
  ['presence-kit', 'Presence-Kit.pdf', 'The Presence Kit'],
  ['launch-pack', 'LinkedIn-Launch-Pack.pdf', 'Your LinkedIn Launch Pack'],
  ['lamp', 'LAMP-Assistant.pdf', 'LAMP Assistant'],
];

(async () => {
  const browser = await chromium.launch();
  for (const [src, out, title] of JOBS) {
    const page = await browser.newPage();
    await page.goto('file://' + path.join(SCRATCH, src + '.html'), { waitUntil: 'networkidle' });
    await page.emulateMedia({ media: 'print' });
    await page.pdf({
      path: path.join(OUT, out),
      format: 'A4',
      printBackground: true,
      displayHeaderFooter: true,
      headerTemplate: '<div></div>',
      footerTemplate:
        '<div style="width:100%;font-family:Arial,sans-serif;font-size:8pt;color:#8a93a5;' +
        'padding:0 18mm;display:flex;justify-content:space-between;">' +
        '<span>' + title + '</span><span class="pageNumber"></span></div>',
      margin: { top: '20mm', bottom: '16mm', left: '18mm', right: '18mm' },
    });
    // Re-render page 1 with no footer, so the cover stays clean.
    await page.pdf({
      path: path.join(SCRATCH, src + '-cover.pdf'),
      format: 'A4', printBackground: true, pageRanges: '1',
      margin: { top: '20mm', bottom: '16mm', left: '18mm', right: '18mm' },
    });
    console.log('wrote', out);
    await page.close();
  }
  await browser.close();
})();
