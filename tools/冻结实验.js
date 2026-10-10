const fs = require("fs");
const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch({ args: ["--no-sandbox"] });
  const page = await browser.newPage({ viewport: { width: 900, height: 400 } });
  await page.goto("http://127.0.0.1:8688/", { waitUntil: "networkidle" });
  await page.waitForTimeout(3000);
  const a = await page.evaluate(() => document.getElementById("statusText").textContent);
  await page.screenshot({ path: "p1.png" });
  await page.waitForTimeout(4000);
  const b = await page.evaluate(() => document.getElementById("statusText").textContent);
  await page.screenshot({ path: "p2.png" });
  const s1 = fs.statSync("p1.png").size, s2 = fs.statSync("p2.png").size;
  const b1 = fs.readFileSync("p1.png"), b2 = fs.readFileSync("p2.png");
  console.log("DOM时刻1:", a);
  console.log("DOM时刻2:", b);
  console.log("p1字节:", s1, " p2字节:", s2, " 内容相同:", b1.equals(b2));
  // 用浏览器把 PNG 显示出来,读取画面上的标题栏文本区域的平均亮度做粗校验
  await browser.close();
})().catch(e => { console.error("失败:", e.message); process.exit(1); });
