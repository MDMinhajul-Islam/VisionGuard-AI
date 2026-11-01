import {expect, test} from "@playwright/test";

test.beforeEach(async ({page}) => {
  const email=process.env.VISIONGUARD_E2E_EMAIL;
  const password=process.env.VISIONGUARD_E2E_PASSWORD;
  test.skip(!email||!password,"Set VISIONGUARD_E2E_EMAIL and VISIONGUARD_E2E_PASSWORD for authenticated browser tests.");
  await page.goto("/login");
  await page.getByLabel("Email").fill(email!);
  await page.getByLabel("Password").fill(password!);
  await page.getByRole("button",{name:"Sign in"}).click();
  await expect(page).toHaveURL(/\/$/);
});

test("real dashboard routes render and backend data is visible", async ({page}) => {
  await page.goto("/");
  await expect(page.getByRole("heading", {name: "Operations overview"})).toBeVisible();
  await expect(page.getByLabel("Current organization")).toHaveValue(/.+/);
  await expect(page.getByLabel("Current site")).toHaveValue(/.+/);
  await expect(page.getByText("Controlled research mode.")).toBeVisible();
  await page.getByRole("link", {name: /Video Workspace/}).click();
  await expect(page.getByRole("heading", {name: "Upload. Analyze. Review."})).toBeVisible();
  await expect(page.getByRole("heading", {name:"Video library"})).toBeVisible();
  await page.getByRole("link", {name: /Semantic Search/}).click();
  await expect(page.getByRole("heading", {name: "Search visual moments"})).toBeVisible();
  await page.getByRole("link", {name: /Models & System/}).click();
  await expect(page.getByRole("heading", {name: "Models & system"})).toBeVisible();
  await expect(page.getByText(/NVIDIA GeForce|CPU fallback/)).toBeVisible();
});

test("genuine video samples render in the synchronized analysis player", async ({page}) => {
  test.setTimeout(60_000);
  await page.goto("/videos");
  await expect(page.getByRole("heading",{name:"Video library"})).toBeVisible();
  const firstAnalysis=page.getByRole("link",{name:"Open Analysis"}).first();
  await expect(firstAnalysis).toBeVisible();
  await firstAnalysis.click();
  await expect(page.getByText("SSDLite320 MobileNetV3 Large").first()).toBeVisible();
  await expect(page.getByText("No interpolation",{exact:true})).toBeVisible();
  const video=page.locator(".analysis-stage video");
  await expect.poll(()=>video.evaluate(element=>(element as HTMLVideoElement).readyState)).toBeGreaterThan(0);
  const overlay=page.getByLabel("Synchronized computer vision overlay");
  await expect(overlay).toBeVisible();
  await expect.poll(()=>overlay.evaluate(canvas=>{
    const context=(canvas as HTMLCanvasElement).getContext("2d");
    if(!context)return 0;
    const pixels=context.getImageData(0,0,(canvas as HTMLCanvasElement).width,(canvas as HTMLCanvasElement).height).data;
    let visible=0;for(let index=3;index<pixels.length;index+=4)if(pixels[index])visible++;
    return visible;
  })).toBeGreaterThan(100);
  await page.getByRole("button",{name:"Pose"}).click();
  await page.getByRole("button",{name:"Next analyzed sample"}).click();
  await page.getByLabel("Speed").selectOption("1.5");
  await expect(page.getByRole("button",{name:"Enter fullscreen analysis"})).toBeVisible();
  await page.screenshot({path:"../data/external/validation/reports/sprint5b-video-analysis-player.png",fullPage:true});
});

test("analysis workspace has no compact-viewport horizontal overflow", async ({page}) => {
  await page.setViewportSize({width:390,height:844});
  await page.goto("/videos");
  await expect(page.getByRole("heading",{name:"Video library"})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});

test("revoked browser session returns to sign in", async ({page}) => {
  const response=await page.request.post("http://127.0.0.1:8000/api/auth/logout",{headers:{Origin:"http://127.0.0.1:3000"}});
  expect(response.status()).toBe(204);
  await page.goto("/");
  await expect(page).toHaveURL(/\/login\?reason=session_expired/);
  await expect(page.getByRole("heading",{name:"Sign in"})).toBeVisible();
});

test("real imported video playback and model-result inspection", async ({page}) => {
  test.setTimeout(60_000);
  const assetsResponse=page.waitForResponse(response=>response.url().endsWith("/api/datasets/assets"));
  await page.goto("/datasets");
  expect((await assetsResponse).ok()).toBeTruthy();
  await expect(page.getByRole("heading", {name:"Dataset evaluation"})).toBeVisible();
  await page.getByRole("button", {name:"fall-02"}).click();
  await expect(page.getByRole("heading", {name:"fall-02"})).toBeVisible();
  const video = page.locator("video");
  await expect(video).toBeVisible();
  await expect.poll(()=>video.evaluate(element=>(element as HTMLVideoElement).readyState)).toBeGreaterThan(0);
  await expect(page.getByText("Candidate", {exact:true}).first()).toBeVisible();
  await expect(page.getByText("source frame labels", {exact:true}).last()).toBeVisible();
  await page.getByRole("button", {name:"fall-18"}).click();
  await expect(page.getByRole("heading", {name:"Fall diagnostic evidence"})).toBeVisible();
  await expect(page.getByRole("button", {name:/Torso orientation/})).toBeVisible();
  await expect(page.getByText(/Improved replay/).first()).toBeVisible();
  await expect(page.getByText(/Motion fusion/).first()).toBeVisible();
  await expect(page.getByRole("button", {name:/Landmark bounding-box center Y/})).toBeVisible();
  await page.screenshot({path:"../data/external/validation/reports/fall18-diagnostics-dashboard.png",fullPage:true});
});

test("dataset evaluation workspace separates provenance and predictions", async ({page}) => {
  const evaluationResponse=page.waitForResponse(response=>response.url().includes("/api/datasets/evaluation"));
  await page.goto("/datasets");
  expect((await evaluationResponse).ok()).toBeTruthy();
  await expect(page.getByRole("heading", {name:"Dataset evaluation"})).toBeVisible();
  await expect(page.getByRole("heading", {name:"Preserved baseline"})).toBeVisible();
  await expect(page.getByText(/Event-level metrics require verified temporal annotations/)).toBeVisible();
  await expect(page.getByText("80.0%", {exact:true})).toBeVisible();
  await expect(page.getByText("40.0%", {exact:true})).toBeVisible();
  await expect(page.getByText("53.3%", {exact:true})).toBeVisible();
  await page.screenshot({path:"../data/external/validation/reports/dataset-evaluation-dashboard.png"});
});

