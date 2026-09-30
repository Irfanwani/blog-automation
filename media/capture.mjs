// Capture screenshots + a short demo video of a running web app.
// Usage: node capture.mjs <url> <outdir> <slug>
// Output: JSON manifest on stdout.
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const [url, outdir, slug] = process.argv.slice(2);
const shots = [];
const shot = async (page, name) => {
  const p = path.join(outdir, `${slug}-${name}.png`);
  await page.screenshot({ path: p });
  shots.push(p);
};

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 1280, height: 800 },
  recordVideo: { dir: outdir, size: { width: 1280, height: 720 } },
});
const page = await ctx.newPage();
await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 });
await page.waitForTimeout(3000);
await shot(page, 'shot-1-hero');

// gentle demo sweep: mouse path + one center click, ~15s of life
for (let i = 0; i <= 10; i++) {
  await page.mouse.move(200 + i * 90, 300 + (i % 2) * 150, { steps: 8 });
  await page.waitForTimeout(900);
}
await shot(page, 'shot-2-mid');
await page.mouse.click(640, 400);
await page.waitForTimeout(4000);
await shot(page, 'shot-3-end');
await page.waitForTimeout(2000);

const videoPath = await page.video().path();
await ctx.close();
await browser.close();

// convert to compact mp4 (LinkedIn/X friendly), keep under ~30s
const mp4 = path.join(outdir, `${slug}-demo.mp4`);
const { execFileSync } = await import('node:child_process');
try {
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', videoPath,
    '-t', '30', '-vf', 'scale=1280:720', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
    '-movflags', '+faststart', mp4], { timeout: 120000 });
  fs.unlinkSync(videoPath);
} catch {
  console.error(JSON.stringify({ warning: 'ffmpeg convert failed, keeping webm', video: videoPath }));
  console.log(JSON.stringify({ shots, video: videoPath }));
  process.exit(0);
}
console.log(JSON.stringify({ shots, video: mp4 }));
