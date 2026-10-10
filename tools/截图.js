// 无头浏览器截取监控面板全页截图
// 用法: node 截图.js [输出文件名] [等待毫秒]
const path = require("path");
const { chromium } = require("playwright");

(async () => {
  const out = process.argv[2] || "preview.png";
  const wait = parseInt(process.argv[3] || "6000", 10);
  const browser = await chromium.launch({ args: ["--no-sandbox"] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  await page.goto("http://127.0.0.1:8688/", { waitUntil: "networkidle" });
  await page.waitForTimeout(wait); // 等几次 2 秒轮询,让曲线和卡片有数据
  await page.screenshot({ path: path.resolve(out), fullPage: true });
  console.log("截图完成:", path.resolve(out));
  await browser.close();
})().catch(e => { console.error("截图失败:", e.message); process.exit(1); });
