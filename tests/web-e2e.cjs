/* Browser-level smoke test, runs against a REAL local FastAPI+FFmpeg backend. */
const {chromium} = require("playwright");
const fs = require("node:fs");
const assert = require("node:assert/strict");
(async()=>{
  const browser=await chromium.launch({headless:true,args:["--no-sandbox"]});
  const page=await browser.newPage({viewport:{width:1440,height:980},acceptDownloads:true});
  const errors=[];
  page.on("pageerror",error=>errors.push(error.message));
  page.on("response",async response=>{
    if(response.url().includes("/api/v1/incidents") && response.request().method()==="POST"){
      console.log("UPLOAD HTTP",response.status(),(await response.text()).slice(0,600));
    }
  });
  try{
    await page.goto("http://127.0.0.1:8000",{waitUntil:"domcontentloaded"});
    await page.locator("#key").fill("ci-private-operator-key");
    await page.locator('#loginForm button[type="submit"]').click();
    await page.locator("#authScreen").waitFor({state:"hidden",timeout:15000});
    await page.locator("#nCases").waitFor();
    assert.equal(await page.locator("#nCases").textContent(),"0");
    await page.locator("#file").setInputFiles("tests/e2e-demo.mp4");
    await page.waitForFunction(()=>!document.querySelector("#upload").disabled,null,{timeout:12000});
    await page.locator("#uploadClaim").fill("Take photo, blue Kia on the left shoulder");
    await page.locator("#upload").click();
    await page.waitForFunction(()=>document.querySelector("#nCases").textContent==="1",
      null,{timeout:20000});
    await page.waitForFunction(()=>document.querySelector("#caseState").textContent.includes("REVIEW AVAILABLE"),
      null,{timeout:70000});
    await page.waitForFunction(()=>document.querySelector("#caseVideo").readyState>=1,
      null,{timeout:30000});
    assert.equal(await page.locator("#caseVideo").isVisible(),true);
    assert.equal(await page.locator("#reviewClaim").inputValue(),
      "Take photo, blue Kia on the left shoulder");
    await page.locator("#reviewEventSecond").fill("1.0");
    await page.locator("#reviewNote").fill("Fixture is an empty generated road-colored frame; no real incident.");
    await page.locator("#reviewStatus").selectOption("reviewed_no_conclusion");
    await page.locator("#saveReview").click();
    await page.waitForFunction(()=>document.querySelector("#toast").textContent.includes("saved"),null,{timeout:12000});
    fs.mkdirSync("artifacts/ui",{recursive:true});
    await page.locator("#studio").scrollIntoViewIfNeeded();
    await page.screenshot({path:"artifacts/ui/evidence-studio-desktop.png",fullPage:true});
    const downloadPromise=page.waitForEvent("download");
    await page.locator("#report").click();
    const download=await downloadPromise;
    assert.ok(download.suggestedFilename().endsWith(".pdf"));
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:"artifacts/ui/evidence-studio-mobile.png",fullPage:true});
    assert.deepEqual(errors,[],"Browser runtime exceptions");
    console.log("PASS: authenticated import, real FFmpeg processing, review save, PDF download, desktop/mobile screenshots");
  }catch(error){
    console.error("E2E state:",{
      uploadStatus:await page.locator("#uploadStatus").textContent().catch(()=>null),
      toast:await page.locator("#toast").textContent().catch(()=>null),
      caseCount:await page.locator("#nCases").textContent().catch(()=>null),
      authVisible:await page.locator("#authScreen").isVisible().catch(()=>null),
      runtimeErrors:errors
    });
    fs.mkdirSync("artifacts/ui",{recursive:true});
    await page.screenshot({path:"artifacts/ui/diagnostic-failure.png",fullPage:true}).catch(()=>{});
    throw error;
  }finally{
    await browser.close();
  }
})().catch(error=>{console.error(error);process.exit(1)});
