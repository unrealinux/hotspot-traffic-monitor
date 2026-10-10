const path = require("path");
const { chromium } = require("playwright");
(async () => {
  const out = process.argv[2] || "preview-proc.png";
  const wait = parseInt(process.argv[3] || "6000", 10);
  const browser = await chromium.launch({ args: ["--no-sandbox"] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1380 } });
  await page.goto("http://127.0.0.1:8688/", { waitUntil: "networkidle" });
  await page.waitForTimeout(wait);
  const info = await page.evaluate(() => ({
    标题栏: document.getElementById("statusText").textContent,
    进程表: Array.from(document.querySelectorAll("#procTable tbody tr"))
              .map(tr => Array.from(tr.children).map(td => td.textContent.trim()).join(" | ")),
  }));
  console.log("脚本自校验 —— 页面标题栏:", info.标题栏);
  info.进程表.forEach(r => console.log("  表行:", r));
  await page.screenshot({ path: path.resolve(out), fullPage: true });
  console.log("已保存:", path.resolve(out));
  await browser.close();
})().catch(e => { console.error("失败:", e.message); process.exit(1); });
