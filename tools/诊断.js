const { chromium } = require("playwright");
(async () => {
  console.log("node时间:", new Date().toISOString());
  const browser = await chromium.launch({ args: ["--no-sandbox"] });
  const page = await browser.newPage({ viewport: { width: 900, height: 700 } });
  const t0 = Date.now();
  await page.goto("http://127.0.0.1:8688/", { waitUntil: "domcontentloaded" });
  console.log("goto耗时:", Date.now() - t0, "ms");
  await page.waitForTimeout(3000);
  const info = await page.evaluate(async () => {
    const r = await fetch("/api/stats", { cache: "no-store" });
    const d = await r.json();
    return {
      页面时钟: new Date().toISOString(),
      页面fetch到的time: d.time,
      页面fetch到的proc_time: d.process.time,
      页面标题栏: document.getElementById("statusText").textContent,
      进程表首行: (document.querySelector("#procTable tbody tr") || {}).innerText,
    };
  });
  console.log(JSON.stringify(info, null, 2));
  // 拦截下一次请求看真实响应头
  page.on("response", async (resp) => {
    if (resp.url().includes("/api/stats")) {
      console.log("响应头: age=", resp.headers()["age"], " date=", resp.headers()["date"], " from=", resp.headers()["from"], " x-cache=", resp.headers()["x-cache"]);
    }
  });
  await page.waitForTimeout(2500);
  await browser.close();
})().catch(e => { console.error("失败:", e.message); process.exit(1); });
