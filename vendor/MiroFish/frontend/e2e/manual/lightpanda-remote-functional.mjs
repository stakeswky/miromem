import { readFileSync } from 'node:fs';

import { chromium } from '@playwright/test';

const cdpEndpoint = process.env.LIGHTPANDA_CDP ?? 'http://127.0.0.1:9334';
const appUrl = process.env.LIGHTPANDA_APP_URL ?? 'http://127.0.0.1:5173/';
const apiRewriteBase = process.env.LIGHTPANDA_API_BASE ?? 'http://127.0.0.1:5002';
const pdfPath = process.env.TEST_PDF_PATH ?? '/Users/jimmy/Downloads/skills/miromem/美联储加息契机深度分析.pdf';
const prompt =
  process.env.TEST_PROMPT ??
  '请基于这份报告，推演美联储加息契机对金融市场、美元走势、风险资产和舆论预期的影响。';

const browser = await chromium.connectOverCDP(cdpEndpoint);
const page = await browser.newPage();
await page.bringToFront();
page.setDefaultTimeout(120000);

page.on('console', (msg) => {
  console.log('CONSOLE', msg.type(), msg.text());
});
page.on('pageerror', (err) => {
  console.log('PAGEERROR', err.message);
});
page.on('requestfailed', (req) => {
  console.log('REQUESTFAILED', req.method(), req.url(), req.failure()?.errorText || '');
});
page.on('response', (res) => {
  if (res.url().includes('/api/')) {
    console.log('RESPONSE', res.status(), res.request().method(), res.url());
  }
});

await page.route('http://localhost:5001/api/**', async (route) => {
  const originalUrl = route.request().url();
  const rewrittenUrl = originalUrl.replace('http://localhost:5001', apiRewriteBase);
  console.log('ROUTE_REWRITE', originalUrl, '=>', rewrittenUrl);
  await route.continue({ url: rewrittenUrl });
});

console.log('STEP', 'goto', appUrl);
let gotoTimedOut = false;
try {
  await page.goto(appUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
} catch (error) {
  gotoTimedOut = true;
  console.log('GOTO_TIMEOUT', error.message);
}
await page.waitForTimeout(3000);
let uiReady = false;
try {
  await page.waitForFunction(() => document.body.innerText.includes('上传文档'), {
    timeout: 120000,
  });
  uiReady = true;
} catch (error) {
  uiReady = false;
  console.log('UI_READY_TIMEOUT', error.message);
}
console.log('GOTO_TIMED_OUT', gotoTimedOut);
console.log('UI_READY', uiReady);
console.log('TITLE', await page.title());
console.log('URL', page.url());
console.log('READY_STATE', await page.evaluate(() => document.readyState));
console.log(
  'BODY_PREVIEW',
  await page.evaluate(() => document.body.innerText.slice(0, 1500)),
);

const pdfBytes = Array.from(readFileSync(pdfPath));
console.log('STEP', 'inject-pdf', pdfPath, 'bytes', pdfBytes.length);

const injection = await page.evaluate(
  ({ bytes, promptText }) => {
    const input = document.querySelector('input[type="file"]');
    const textarea = document.querySelector('textarea');
    if (!input || !textarea) {
      return { ok: false, reason: 'missing input or textarea' };
    }

    const file = new File([Uint8Array.from(bytes)], '美联储加息契机深度分析.pdf', {
      type: 'application/pdf',
    });
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));

    textarea.value = promptText;
    textarea.dispatchEvent(new Event('input', { bubbles: true }));

    const button = Array.from(document.querySelectorAll('button')).find((btn) =>
      btn.textContent?.includes('启动引擎'),
    );

    return {
      ok: true,
      fileCount: input.files?.length ?? 0,
      fileName: input.files?.[0]?.name ?? null,
      buttonDisabled: button ? button.disabled : null,
      textareaLength: textarea.value.length,
    };
  },
  { bytes: pdfBytes, promptText: prompt },
);

console.log('INJECTION', JSON.stringify(injection));

const startButton = page.getByRole('button', { name: /启动引擎/ });
try {
  console.log('BUTTON_ENABLED', await startButton.isEnabled());
} catch (error) {
  console.log('BUTTON_LOOKUP_FAILED', error.message);
  console.log(
    'DOM_DIAG',
    await page.evaluate(() => ({
      readyState: document.readyState,
      bodyText: document.body.innerText.slice(0, 2000),
      buttonTexts: Array.from(document.querySelectorAll('button'))
        .slice(0, 20)
        .map((button) => button.textContent?.trim()),
      textareaCount: document.querySelectorAll('textarea').length,
      fileInputCount: document.querySelectorAll('input[type="file"]').length,
    })),
  );
  throw error;
}

console.log('STEP', 'click-start');
await startButton.click();
await page.waitForURL(/\/process\/.+/, { timeout: 15000 });
console.log('URL_AFTER_CLICK', page.url());

let projectRouteReached = false;
try {
  await page.waitForURL(
    (url) => /\/process\/.+/.test(url.toString()) && !url.toString().endsWith('/process/new'),
    { timeout: 240000 },
  );
  projectRouteReached = true;
} catch {
  projectRouteReached = false;
}

console.log('PROJECT_ROUTE_REACHED', projectRouteReached, page.url());

let envSetupVisible = false;
try {
  await page.waitForFunction(() => document.body.innerText.includes('进入环境搭建'), {
    timeout: 120000,
  });
  envSetupVisible = true;
} catch {
  envSetupVisible = false;
}
console.log('ENV_SETUP_VISIBLE', envSetupVisible);

const bodyText = await page.locator('body').innerText();
console.log('BODY_TEXT_START');
console.log(bodyText.slice(0, 5000));
console.log('BODY_TEXT_END');

const screenshotPath = '/tmp/lightpanda-remote-functional.png';
await page.screenshot({ path: screenshotPath, fullPage: true });
console.log('SCREENSHOT', screenshotPath);

await browser.close();
